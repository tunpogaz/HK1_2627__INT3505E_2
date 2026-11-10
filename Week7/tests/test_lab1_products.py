import pytest

def test_lab1_full_product_crud_lifecycle(client):
    """
    Kiểm thử toàn diện 6 endpoints của Lab 1 (Slide 24, 27, 28):
    1. POST /api/v1/products (Tạo sản phẩm)
    2. Conflict 409 khi trùng SKU
    3. GET /api/v1/products/<id> (Lấy chi tiết)
    4. POST /api/v1/products/<id>/reserve (Đặt trước tồn kho)
    5. Conflict 409 khi hết hàng tồn kho
    6. PATCH /api/v1/products/<id> (Cập nhật 1 phần)
    7. GET /api/v1/products (Phân trang ?page=1&size=20)
    8. DELETE /api/v1/products/<id> (Xóa mềm archived=True)
    9. GET sau khi xóa mềm trả về 404
    """
    # 1. POST tạo sản phẩm
    payload = {
        "sku": "SKU-IPHONE-15",
        "name": "Apple iPhone 15 Pro",
        "description": "Natural Titanium 256GB",
        "price_cents": 120000,
        "qty_in_stock": 10
    }
    res_create = client.post("/api/v1/products", json=payload)
    assert res_create.status_code == 201
    prod = res_create.json
    prod_id = prod["id"]
    assert prod["sku"] == "SKU-IPHONE-15"
    assert prod["qty_in_stock"] == 10
    assert prod["archived"] is False

    # 2. POST trùng SKU -> 409 Conflict
    res_dup = client.post("/api/v1/products", json=payload)
    assert res_dup.status_code == 409
    assert res_dup.json["code"] == "conflict"

    # 3. GET sản phẩm theo ID
    res_get = client.get(f"/api/v1/products/{prod_id}")
    assert res_get.status_code == 200
    assert res_get.json["name"] == "Apple iPhone 15 Pro"

    # 4. POST reserve đặt trước 3 sản phẩm
    res_res = client.post(f"/api/v1/products/{prod_id}/reserve", json={"qty": 3})
    assert res_res.status_code == 200
    assert res_res.json["qty_in_stock"] == 7

    # 5. POST reserve vượt quá tồn kho còn lại -> 409 OutOfStock
    res_res_fail = client.post(f"/api/v1/products/{prod_id}/reserve", json={"qty": 15})
    assert res_res_fail.status_code == 409
    assert res_res_fail.json["code"] == "out_of_stock"

    # 6. PATCH cập nhật một phần
    res_patch = client.patch(f"/api/v1/products/{prod_id}", json={
        "name": "Apple iPhone 15 Pro Max",
        "price_cents": 135000
    })
    assert res_patch.status_code == 200
    assert res_patch.json["name"] == "Apple iPhone 15 Pro Max"
    assert res_patch.json["price_cents"] == 135000

    # 7. GET danh sách phân trang (?page=1&size=20)
    res_list = client.get("/api/v1/products?page=1&size=10")
    assert res_list.status_code == 200
    data = res_list.json
    assert data["page"] == 1
    assert data["size"] == 10
    assert data["total"] == 1
    assert len(data["items"]) == 1

    # 8. DELETE xóa mềm
    res_del = client.delete(f"/api/v1/products/{prod_id}")
    assert res_del.status_code == 204

    # 9. Xác nhận: sau khi xóa mềm, GET chi tiết trả 404 và GET danh sách loại trừ
    res_get_archived = client.get(f"/api/v1/products/{prod_id}")
    assert res_get_archived.status_code == 404

    res_list_after = client.get("/api/v1/products")
    assert res_list_after.json["total"] == 0
    assert len(res_list_after.json["items"]) == 0

def test_lab1_validation_errors(client):
    """Kiểm thử validation dữ liệu ngõ vào (Slide 26, 32)."""
    # Giá âm
    res_bad_price = client.post("/api/v1/products", json={
        "sku": "SKU-BAD-1",
        "name": "Bad Price",
        "price_cents": -50
    })
    assert res_bad_price.status_code == 422
    assert res_bad_price.json["code"] == "validation_error"

    # Tên rỗng
    res_empty_name = client.post("/api/v1/products", json={
        "sku": "SKU-BAD-2",
        "name": "   ",
        "price_cents": 1000
    })
    assert res_empty_name.status_code == 422
    assert res_empty_name.json["code"] == "validation_error"

