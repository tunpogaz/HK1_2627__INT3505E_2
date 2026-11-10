import pytest
from sqlalchemy import event
from src.extensions import db
from src.models import Product, Order, OrderItem

def test_post_order_with_multiple_items(client):
    """Kiểm thử POST /api/v1/orders tạo Order liên kết nhiều sản phẩm qua OrderItem (Bài tập 2, Slide 42)."""
    # 1. Tạo 2 sản phẩm
    p1 = client.post("/api/v1/products", json={
        "sku": "SKU-MONITOR-01",
        "name": "Dell UltraSharp 27",
        "price_cents": 50000,
        "qty_in_stock": 20
    }).json

    p2 = client.post("/api/v1/products", json={
        "sku": "SKU-MOUSE-01",
        "name": "Logitech MX Master 3S",
        "price_cents": 10000,
        "qty_in_stock": 50
    }).json

    # 2. Tạo đơn hàng chứa 2 OrderItems liên kết 2 sản phẩm trên
    order_payload = {
        "order_number": "ORD-2024-ALPHA",
        "customer_email": "student@example.com",
        "items": [
            {"product_id": p1["id"], "quantity": 1},
            {"product_id": p2["id"], "quantity": 2}
        ]
    }
    res = client.post("/api/v1/orders", json=order_payload)
    assert res.status_code == 201
    order_data = res.json
    assert order_data["order_number"] == "ORD-2024-ALPHA"
    assert len(order_data["items"]) == 2
    assert order_data["items"][0]["product_id"] == p1["id"]
    assert order_data["items"][1]["product_id"] == p2["id"]

    # 3. Tạo đơn hàng với order_number tự sinh và unit_price_cents chỉ định
    res2 = client.post("/api/v1/orders", json={
        "customer_email": "student2@example.com",
        "items": [
            {"product_id": p1["id"], "quantity": 1, "unit_price_cents": 45000}
        ]
    })
    assert res2.status_code == 201
    assert res2.json["order_number"].startswith("ORD-")
    assert res2.json["items"][0]["unit_price_cents"] == 45000

def test_eager_loading_prevents_n_plus_one_queries(app, client):
    """
    Kiểm thử GET với Eager Loading (selectinload) và đo đếm số câu truy vấn DB (Bài tập 5, Slide 20, 21, 42).
    Xác minh rằng khi truy vấn N đơn hàng, số câu SQL SELECT chỉ là hằng số (<= 3 queries)
    thay vì bị bẫy N+1 query (1 + N + N queries).
    """
    with app.app_context():
        # Setup: Tạo 1 sản phẩm và 5 đơn hàng, mỗi đơn hàng có 1 OrderItem
        prod = Product(
            sku="SKU-PHONE-99",
            name="Google Pixel 9",
            price_cents=80000,
            qty_in_stock=100
        )
        db.session.add(prod)
        db.session.commit()

        for i in range(1, 6):
            order = Order(
                order_number=f"ORD-TEST-{i:03d}",
                customer_email=f"customer{i}@example.com",
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

    # Đo đếm câu lệnh SQL SELECT phát ra
    executed_select_queries = []

    def before_cursor_execute(conn, cursor, statement, parameters, context, executemany):
        clean = statement.strip().upper()
        if clean.startswith("SELECT") and ("ORDERS" in clean or "ORDER_ITEMS" in clean):
            executed_select_queries.append(statement)

    engine = db.engine
    event.listen(engine, "before_cursor_execute", before_cursor_execute)

    try:
        # Gọi GET /api/v1/orders có dùng selectinload(Order.items).selectinload(OrderItem.product)
        res = client.get("/api/v1/orders")
        assert res.status_code == 200
        orders = res.json
        assert len(orders) == 5

        # Đánh giá số query:
        # Nếu Lazy Loading (Slide 20 CÁCH SAI): sẽ phát 1 query lấy Orders + 5 query lấy OrderItems = 6 queries
        # Với selectinload (Slide 20 HƯỚNG SỬA): phát 1 query orders + 1 query order_items WHERE order_id IN (...)
        total_queries = len(executed_select_queries)
        assert total_queries <= 3, (
            f"Eager loading thất bại! Dự kiến <= 3 queries, nhưng đã phát {total_queries} queries:\n"
            + "\n".join(executed_select_queries)
        )
    finally:
        event.remove(engine, "before_cursor_execute", before_cursor_execute)

