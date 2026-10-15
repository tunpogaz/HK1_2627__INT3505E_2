"""
Test Suite for Week 5 Bookstore Pagination API
Kiểm thử toàn diện:
1. Offset / Limit pagination (trang đầu, trang kế, biên, total)
2. Cursor pagination (next_cursor, has_more, tính liên tục, không lặp dữ liệu)
3. Cursor tie-breaker tính tất định (deterministic seek)
4. Lọc theo thể loại (?genre=tech, ?genre=fiction)
5. Sắp xếp đa khóa (multi-key sort: ?sort=-price,title, ?sort=price,id)
6. Whitelist sort validation (ngăn chặn cột lạ/SQL injection, trả về 400)
7. Cursor validation (kiểm tra token hỏng hoặc sort mismatch trả về 400)
8. Sparse fieldsets (?fields=id,title,price)
9. Strategy validation (chỉ chấp nhận 'offset' hoặc 'cursor')
"""

import pytest
from app import app, db, seed_database, _encode_cursor


@pytest.fixture(scope="module")
def client():
    app.config["TESTING"] = True
    app.config["SQLALCHEMY_DATABASE_URI"] = "sqlite:///:memory:"

    with app.app_context():
        db.create_all()
        seed_database()
        with app.test_client() as test_client:
            yield test_client
        db.drop_all()

# 1. OFFSET PAGINATION TESTS

def test_offset_pagination_first_page(client):
    res = client.get("/api/v1/books?strategy=offset&limit=10&offset=0")
    assert res.status_code == 200
    data = res.get_json()

    assert "data" in data
    assert "pagination" in data
    p = data["pagination"]
    assert p["strategy"] == "offset"
    assert p["limit"] == 10
    assert p["offset"] == 0
    assert len(data["data"]) == 10
    assert p["total"] >= 50
    assert p["current_page"] == 1
    assert p["has_next"] is True
    assert p["has_prev"] is False


def test_offset_pagination_second_page(client):
    res1 = client.get("/api/v1/books?strategy=offset&limit=10&offset=0")
    res2 = client.get("/api/v1/books?strategy=offset&limit=10&offset=10")

    data1 = res1.get_json()["data"]
    data2 = res2.get_json()["data"]

    assert len(data2) == 10
    p2 = res2.get_json()["pagination"]
    assert p2["offset"] == 10
    assert p2["current_page"] == 2
    assert p2["has_next"] is True
    assert p2["has_prev"] is True

    ids1 = {b["id"] for b in data1}
    ids2 = {b["id"] for b in data2}
    assert len(ids1.intersection(ids2)) == 0


def test_offset_pagination_out_of_range(client):
    res = client.get("/api/v1/books?strategy=offset&limit=10&offset=1000")
    assert res.status_code == 200
    data = res.get_json()
    assert len(data["data"]) == 0
    assert data["pagination"]["has_next"] is False
    assert data["pagination"]["has_prev"] is True


# 2. CURSOR PAGINATION TESTS

def test_cursor_pagination_traversal(client):
    # Lấy trang đầu
    res1 = client.get("/api/v1/books?strategy=cursor&limit=15&sort=-id")
    assert res1.status_code == 200
    body1 = res1.get_json()

    data1 = body1["data"]
    page1 = body1["pagination"]
    assert len(data1) == 15
    assert page1["strategy"] == "cursor"
    assert page1["has_more"] is True
    assert page1["next_cursor"] is not None

    # Lấy trang thứ 2 bằng next_cursor
    cursor = page1["next_cursor"]
    res2 = client.get(f"/api/v1/books?strategy=cursor&limit=15&sort=-id&cursor={cursor}")
    assert res2.status_code == 200
    body2 = res2.get_json()

    data2 = body2["data"]
    assert len(data2) == 15

    # Đảm bảo tính liên tục và không trùng lặp
    ids1 = [b["id"] for b in data1]
    ids2 = [b["id"] for b in data2]
    assert len(set(ids1).intersection(set(ids2))) == 0


def test_cursor_pagination_until_exhaustion(client):
    # Duyệt toàn bộ bằng cursor
    all_retrieved = []
    cursor = None
    has_more = True

    while has_more:
        url = "/api/v1/books?strategy=cursor&limit=20&sort=id"
        if cursor:
            url += f"&cursor={cursor}"
        res = client.get(url)
        assert res.status_code == 200
        body = res.get_json()
        all_retrieved.extend(body["data"])
        has_more = body["pagination"]["has_more"]
        cursor = body["pagination"]["next_cursor"]

    # Tổng số lấy được qua cursor phải bằng tổng số qua offset
    res_offset = client.get("/api/v1/books?strategy=offset&limit=100")
    total_expected = res_offset.get_json()["pagination"]["total"]
    assert len(all_retrieved) == total_expected


def test_cursor_with_sort_composite_tie_breaker(client):
    # Sắp xếp theo price tăng dần có nhiều cuốn cùng giá
    res1 = client.get("/api/v1/books?strategy=cursor&limit=10&sort=price")
    assert res1.status_code == 200
    body1 = res1.get_json()
    cursor = body1["pagination"]["next_cursor"]
    assert cursor is not None

    res2 = client.get(f"/api/v1/books?strategy=cursor&limit=10&sort=price&cursor={cursor}")
    assert res2.status_code == 200
    body2 = res2.get_json()

    # Không có cuốn nào bị trùng
    ids1 = {b["id"] for b in body1["data"]}
    ids2 = {b["id"] for b in body2["data"]}
    assert len(ids1.intersection(ids2)) == 0


# 3. FILTER TESTS

def test_filter_by_genre(client):
    # Lọc sách công nghệ
    res = client.get("/api/v1/books?genre=tech&limit=50")
    assert res.status_code == 200
    data = res.get_json()["data"]
    assert len(data) > 0
    for book in data:
        assert book["genre"] == "tech"

    # Lọc sách tiểu thuyết
    res_fic = client.get("/api/v1/books?genre=fiction&limit=50")
    assert res_fic.status_code == 200
    data_fic = res_fic.get_json()["data"]
    assert len(data_fic) > 0
    for book in data_fic:
        assert book["genre"] == "fiction"


def test_filter_price_range(client):
    res = client.get("/api/v1/books?price_min=300000&price_max=500000&limit=50")
    assert res.status_code == 200
    data = res.get_json()["data"]
    for book in data:
        assert 300000 <= book["price"]["amount"] <= 500000


# 4. MULTI-KEY SORTING TESTS

def test_multi_key_sorting(client):
    # Sắp xếp giảm dần theo giá, sau đó theo tiêu đề tăng dần
    res = client.get("/api/v1/books?sort=-price,title&limit=20")
    assert res.status_code == 200
    data = res.get_json()["data"]

    for i in range(len(data) - 1):
        curr_price = data[i]["price"]["amount"]
        next_price = data[i + 1]["price"]["amount"]
        assert curr_price >= next_price
        if curr_price == next_price:
            assert data[i]["title"] <= data[i + 1]["title"]


# 5. VALIDATION & SECURITY TESTS (WHITELISTING)

def test_whitelist_sort_column_reject_invalid(client):
    # Cố gắng inject cột không cho phép
    res = client.get("/api/v1/books?sort=malicious_column")
    assert res.status_code == 400
    body = res.get_json()
    assert body["error"] == "bad_sort"
    assert "malicious_column" in body["message"]


def test_invalid_cursor_token(client):
    # Token base64 sai hoặc không giải mã được
    res = client.get("/api/v1/books?cursor=corrupted_invalid_cursor_token")
    assert res.status_code == 400
    body = res.get_json()
    assert body["error"] == "invalid_cursor"


def test_cursor_sort_mismatch_rejection(client):
    # Cursor được sinh ra cho sort 'price' nhưng gửi vào request sort '-title'
    cursor = _encode_cursor({"s": "price", "v": 200000, "i": 5})
    res = client.get(f"/api/v1/books?sort=-title&cursor={cursor}")
    assert res.status_code == 400
    body = res.get_json()
    assert body["error"] == "cursor_validation_failed"
    assert "không khớp" in body["message"]


def test_invalid_pagination_strategy(client):
    res = client.get("/api/v1/books?strategy=unsupported")
    assert res.status_code == 400
    body = res.get_json()
    assert body["error"] == "invalid_parameter"


# 6. SPARSE FIELDSETS TESTS

def test_sparse_fieldsets(client):
    res = client.get("/api/v1/books?fields=id,title,price&limit=5")
    assert res.status_code == 200
    data = res.get_json()["data"]
    assert len(data) > 0
    for book in data:
        assert set(book.keys()) == {"id", "title", "price"}
        assert "isbn" not in book
        assert "stock" not in book

