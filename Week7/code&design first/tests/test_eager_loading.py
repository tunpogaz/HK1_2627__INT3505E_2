import pytest
from sqlalchemy import event
from shared.extensions import db
from shared.models import Product, Order, OrderItem
from sqlalchemy.orm import selectinload

def test_post_order_with_multiple_items(code_first_client):
    """Test POST /api/v1/orders creating an Order with multiple OrderItems (Slide 42)."""
    # Create 2 products
    p1 = code_first_client.post("/api/v1/products", json={
        "sku": "SKU-MONITOR-01",
        "name": "Dell 27 Inch 4K Monitor",
        "price_cents": 45000,
        "qty_in_stock": 20
    }).json
    p2 = code_first_client.post("/api/v1/products", json={
        "sku": "SKU-MOUSE-01",
        "name": "Logitech MX Master 3S",
        "price_cents": 9900,
        "qty_in_stock": 50
    }).json

    # POST new Order linking both products via OrderItems
    order_payload = {
        "order_number": "ORD-2024-ALPHA",
        "customer_email": "john.doe@example.com",
        "items": [
            {"product_id": p1["id"], "quantity": 1},
            {"product_id": p2["id"], "quantity": 2}
        ]
    }
    res_order = code_first_client.post("/api/v1/orders", json=order_payload)
    assert res_order.status_code == 201
    order_data = res_order.json
    assert order_data["order_number"] == "ORD-2024-ALPHA"
    assert len(order_data["items"]) == 2
    assert order_data["items"][0]["product_id"] == p1["id"]
    assert order_data["items"][1]["product_id"] == p2["id"]

def test_eager_loading_prevents_n_plus_one_queries(code_first_app, code_first_client):
    """
    Test GET with eager loading (selectinload) vs N+1 queries (Slide 20, 21, 42).
    Verifies that querying N orders with their items emits a constant number of queries (2),
    instead of 1 + N queries.
    """
    with code_first_app.app_context():
        # Setup: Create 1 product and 5 orders with items
        prod = Product(
            sku="SKU-PHONE-99",
            name="Pixel 9 Pro",
            price_cents=99900,
            qty_in_stock=100
        )
        db.session.add(prod)
        db.session.commit()

        # Seed 5 orders, each having an OrderItem
        for i in range(1, 6):
            order = Order(
                order_number=f"ORD-EAGER-{i:03d}",
                customer_email=f"user{i}@example.com",
                status="completed"
            )
            item = OrderItem(
                order=order,
                product=prod,
                quantity=1,
                unit_price_cents=prod.price_cents
            )
            db.session.add_all([order, item])
        db.session.commit()

    # Query counter list
    executed_queries = []

    def before_cursor_execute(conn, cursor, statement, parameters, context, executemany):
        clean_stmt = statement.strip().upper()
        # Count SELECT queries touching orders or order_items
        if clean_stmt.startswith("SELECT") and ("ORDERS" in clean_stmt or "ORDER_ITEMS" in clean_stmt):
            executed_queries.append(statement)

    engine = db.engine
    event.listen(engine, "before_cursor_execute", before_cursor_execute)

    try:
        # Call GET /api/v1/orders which uses selectinload(Order.items).selectinload(OrderItem.product)
        res = code_first_client.get("/api/v1/orders")
        assert res.status_code == 200
        orders = res.json
        assert len(orders) == 5

        # Inspect number of queries emitted:
        # With lazy loading (Slide 20), this would emit 1 + 5 = 6 queries (or 1 + 5 + 5 = 11 queries with product).
        # With selectinload, this emits exactly 1 query for orders + 1 query for order_items (using WHERE order_id IN (...)) + 1 query for products.
        # Total queries must be <= 3, proving N+1 is completely eliminated.
        select_queries_count = len(executed_queries)
        assert select_queries_count <= 3, (
            f"Expected <= 3 queries due to selectinload eager loading, but got {select_queries_count} queries!\n"
            f"Queries executed:\n" + "\n".join(executed_queries)
        )
    finally:
        event.remove(engine, "before_cursor_execute", before_cursor_execute)

