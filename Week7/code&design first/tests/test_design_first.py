import pytest

def test_design_first_crud_lifecycle(design_first_client):
    """Verify endpoints in the Design-First API routed via Connexion (Slide 7-9)."""
    # 1. POST create product
    payload = {
        "sku": "SKU-DES-001",
        "name": "Design-First ThinkPad",
        "price_cents": 180000,
        "qty_in_stock": 5
    }
    res_create = design_first_client.post("/products", json=payload)
    assert res_create.status_code == 201
    prod = res_create.json()
    prod_id = prod["id"]
    assert prod["sku"] == "SKU-DES-001"
    assert prod["qty_in_stock"] == 5

    # 2. Duplicate SKU returns 409 Conflict
    res_dup = design_first_client.post("/products", json=payload)
    assert res_dup.status_code == 409
    assert res_dup.json()["code"] == "conflict"

    # 3. GET product by ID
    res_get = design_first_client.get(f"/products/{prod_id}")
    assert res_get.status_code == 200
    assert res_get.json()["name"] == "Design-First ThinkPad"

    # 4. POST reserve stock
    res_res = design_first_client.post(f"/products/{prod_id}/reserve", json={"qty": 2})
    assert res_res.status_code == 200
    assert res_res.json()["qty_in_stock"] == 3

    # Reserve exceeding stock returns 409 OutOfStock
    res_res_fail = design_first_client.post(f"/products/{prod_id}/reserve", json={"qty": 10})
    assert res_res_fail.status_code == 409
    assert res_res_fail.json()["code"] == "out_of_stock"

    # 5. GET list
    res_list = design_first_client.get("/products")
    assert res_list.status_code == 200
    data = res_list.json()
    assert len(data) >= 1

    # 6. DELETE soft-delete
    res_del = design_first_client.delete(f"/products/{prod_id}")
    assert res_del.status_code == 204

    # 7. Verification: Deleted product returns 404
    res_get_deleted = design_first_client.get(f"/products/{prod_id}")
    assert res_get_deleted.status_code == 404

def test_design_first_schema_validation(design_first_client):
    """Verify that Connexion automatically enforces OpenAPI schema rules (Slide 7, 9)."""
    # Negative price rejected by OpenAPI schema without manual Python code
    res_bad_price = design_first_client.post("/products", json={
        "sku": "SKU-INVALID",
        "name": "Invalid Price Item",
        "price_cents": -50
    })
    assert res_bad_price.status_code == 400
