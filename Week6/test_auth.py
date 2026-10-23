"""
Test Suite for Week 6: Authentication & Authorization API
Kiểm thử toàn diện:
1. Đăng nhập thành công, cấp cặp Access Token & Refresh Token (200)
2. Đăng nhập sai mật khẩu (401 - Lỗi chung chống user enumeration)
3. Đăng nhập thiếu trường bắt buộc (400 - Validation error)
4. Giới hạn tần suất đăng nhập (429 - Rate limit chống brute-force)
5. Làm mới token thành công (200 - Token rotation)
6. Chống tấn công lặp lại (401 - Replay attack detection với refresh token cũ)
7. Đọc bài viết công khai thành công (200)
8. Đọc bài viết riêng tư của chính mình thành công (200)
9. CHỐNG BOLA: Đọc trộm bài viết riêng tư của người khác bị chặn đứng (403 BOLA_ACCESS_DENIED)
10. Quản trị viên (admin) có quyền kiểm duyệt bài viết riêng tư (200)
11. Kiểm tra Scope: Tài khoản thiếu scope 'posts:read' bị từ chối (403 INSUFFICIENT_SCOPE)
12. Gọi API thiếu header Authorization bị từ chối (401)
13. Truy vấn bài viết không tồn tại (404)
14. Đăng xuất và thu hồi token (401 khi dùng lại token đã revoke)
"""

import pytest
from app import app, db, seed_database, REVOKED_TOKEN_JTIS, LOGIN_FAILURES


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


@pytest.fixture(autouse=True)
def clean_state():
    """Làm sạch blocklist và login failures trước mỗi bài test."""
    REVOKED_TOKEN_JTIS.clear()
    LOGIN_FAILURES.clear()


# ============================================================================
# 1. AUTHENTICATION TESTS (LOGIN)
# ============================================================================

def test_login_success(client):
    res = client.post("/api/v1/auth/login", json={
        "email": "alice@vnu.edu.vn",
        "password": "AlicePass123!"
    })
    assert res.status_code == 200
    data = res.get_json()

    assert "accessToken" in data
    assert "refreshToken" in data
    assert data["tokenType"] == "Bearer"
    assert data["expiresIn"] == 900
    assert "user" in data
    user = data["user"]
    assert user["email"] == "alice@vnu.edu.vn"
    assert user["username"] == "alice_dev"
    assert "user" in user["roles"]
    assert "posts:read" in user["scopes"]
    # TUYỆT ĐỐI không để lộ hash mật khẩu (Slide 29)
    assert "password_hash" not in user
    assert "pwd_hash" not in user


def test_login_invalid_password(client):
    res = client.post("/api/v1/auth/login", json={
        "email": "alice@vnu.edu.vn",
        "password": "WrongPassword999!"
    })
    assert res.status_code == 401
    body = res.get_json()
    assert body["status"] == 401
    assert body["title"] == "Authentication Failed"
    assert "không chính xác" in body["detail"]


def test_login_missing_fields(client):
    res = client.post("/api/v1/auth/login", json={
        "email": "alice@vnu.edu.vn"
    })
    assert res.status_code == 400
    body = res.get_json()
    assert body["status"] == 400
    assert "VALIDATION_ERROR" in body.get("code", "")


def test_login_rate_limiting(client):
    # Thử đăng nhập sai liên tục 5 lần
    for _ in range(5):
        res = client.post("/api/v1/auth/login", json={
            "email": "bob@vnu.edu.vn",
            "password": "badpassword"
        })
        assert res.status_code == 401

    # Lần thứ 6 phải bị chặn bởi mã 429 Too Many Requests
    res_rate_limited = client.post("/api/v1/auth/login", json={
        "email": "bob@vnu.edu.vn",
        "password": "badpassword"
    })
    assert res_rate_limited.status_code == 429
    body = res_rate_limited.get_json()
    assert body["status"] == 429
    assert body["code"] == "RATE_LIMIT_EXCEEDED"


# ============================================================================
# 2. TOKEN REFRESH & ROTATION TESTS
# ============================================================================

def test_refresh_token_success_and_rotation(client):
    # Bước 1: Login lấy refresh token
    login_res = client.post("/api/v1/auth/login", json={
        "email": "alice@vnu.edu.vn",
        "password": "AlicePass123!"
    })
    refresh_token_1 = login_res.get_json()["refreshToken"]

    # Bước 2: Gọi refresh token
    refresh_res = client.post("/api/v1/auth/refresh", headers={
        "Authorization": f"Bearer {refresh_token_1}"
    })
    assert refresh_res.status_code == 200
    body = refresh_res.get_json()

    assert "accessToken" in body
    assert "refreshToken" in body
    refresh_token_2 = body["refreshToken"]
    assert refresh_token_2 != refresh_token_1  # Đã xoay vòng token mới (RTR)

    # Bước 3: THỬ NGHIỆM CHỐNG REPLAY ATTACK (Slide 20)
    # Cố tình dùng lại refresh_token_1 cũ đã bị thu hồi -> Bị từ chối mã 401!
    replay_res = client.post("/api/v1/auth/refresh", headers={
        "Authorization": f"Bearer {refresh_token_1}"
    })
    assert replay_res.status_code == 401
    assert replay_res.get_json()["code"] == "TOKEN_REVOKED"


def test_refresh_using_access_token_rejected(client):
    login_res = client.post("/api/v1/auth/login", json={
        "email": "alice@vnu.edu.vn",
        "password": "AlicePass123!"
    })
    access_token = login_res.get_json()["accessToken"]

    # Dùng nhầm Access Token vào endpoint refresh -> Phải bị từ chối
    res = client.post("/api/v1/auth/refresh", headers={
        "Authorization": f"Bearer {access_token}"
    })
    assert res.status_code in (401, 403, 422)


# ============================================================================
# 3. POSTS ACCESS & BOLA PREVENTION (OBJECT-LEVEL AUTHORIZATION)
# ============================================================================

def test_get_public_post_success(client):
    # Bob xem bài viết public của Alice (Post ID 1)
    login_bob = client.post("/api/v1/auth/login", json={
        "email": "bob@vnu.edu.vn",
        "password": "BobPass123!"
    })
    bob_token = login_bob.get_json()["accessToken"]

    res = client.get("/api/v1/posts/1", headers={
        "Authorization": f"Bearer {bob_token}"
    })
    assert res.status_code == 200
    post = res.get_json()
    assert post["id"] == 1
    assert post["visibility"] == "public"
    assert "Chào mừng" in post["title"]


def test_get_own_private_post_success(client):
    # Alice xem bài viết private của CHÍNH MÌNH (Post ID 2)
    login_alice = client.post("/api/v1/auth/login", json={
        "email": "alice@vnu.edu.vn",
        "password": "AlicePass123!"
    })
    alice_token = login_alice.get_json()["accessToken"]

    res = client.get("/api/v1/posts/2", headers={
        "Authorization": f"Bearer {alice_token}"
    })
    assert res.status_code == 200
    post = res.get_json()
    assert post["id"] == 2
    assert post["visibility"] == "private"
    assert "Alice" in post["title"]


def test_bola_prevention_reject_unauthorized_user(client):
    """
    KIỂM THỬ CHỐNG LỖ HỔNG OWASP API1:2023 - BOLA
    Bob có token hợp lệ, có scope 'posts:read', nhưng cố đọc trộm bài viết 'private' của Alice (Post ID 2)
    Hệ thống PHẢI CHẶN ĐỨNG với mã HTTP 403 Forbidden!
    """
    login_bob = client.post("/api/v1/auth/login", json={
        "email": "bob@vnu.edu.vn",
        "password": "BobPass123!"
    })
    bob_token = login_bob.get_json()["accessToken"]

    res = client.get("/api/v1/posts/2", headers={
        "Authorization": f"Bearer {bob_token}"
    })
    assert res.status_code == 403
    body = res.get_json()
    assert body["status"] == 403
    assert body["title"] == "Forbidden Resource"
    assert body["code"] == "BOLA_ACCESS_DENIED"


def test_admin_override_private_post(client):
    # Quản trị viên (admin) có quyền xem kiểm duyệt mọi bài viết
    login_admin = client.post("/api/v1/auth/login", json={
        "email": "admin@vnu.edu.vn",
        "password": "AdminMaster2026!"
    })
    admin_token = login_admin.get_json()["accessToken"]

    res = client.get("/api/v1/posts/2", headers={
        "Authorization": f"Bearer {admin_token}"
    })
    assert res.status_code == 200
    assert res.get_json()["id"] == 2


def test_insufficient_scope_rejected(client):
    # Tài khoản Guest chỉ có scope 'profile', thiếu scope 'posts:read' (Slide 25)
    login_guest = client.post("/api/v1/auth/login", json={
        "email": "guest@vnu.edu.vn",
        "password": "GuestPass123!"
    })
    guest_token = login_guest.get_json()["accessToken"]

    res = client.get("/api/v1/posts/1", headers={
        "Authorization": f"Bearer {guest_token}"
    })
    assert res.status_code == 403
    body = res.get_json()
    assert body["status"] == 403
    assert body["code"] == "INSUFFICIENT_SCOPE"


def test_missing_token_rejected(client):
    # Không truyền header Authorization
    res = client.get("/api/v1/posts/1")
    assert res.status_code == 401
    body = res.get_json()
    assert body["status"] == 401
    assert body["code"] == "TOKEN_MISSING"


def test_post_not_found(client):
    login_alice = client.post("/api/v1/auth/login", json={
        "email": "alice@vnu.edu.vn",
        "password": "AlicePass123!"
    })
    alice_token = login_alice.get_json()["accessToken"]

    res = client.get("/api/v1/posts/99999", headers={
        "Authorization": f"Bearer {alice_token}"
    })
    assert res.status_code == 404
    body = res.get_json()
    assert body["status"] == 404
    assert body["code"] == "POST_NOT_FOUND"


# ============================================================================
# 4. LOGOUT & REVOCATION TEST
# ============================================================================

def test_logout_revokes_token(client):
    login_alice = client.post("/api/v1/auth/login", json={
        "email": "alice@vnu.edu.vn",
        "password": "AlicePass123!"
    })
    alice_token = login_alice.get_json()["accessToken"]

    # Đăng xuất
    logout_res = client.post("/api/v1/auth/logout", headers={
        "Authorization": f"Bearer {alice_token}"
    })
    assert logout_res.status_code == 200

    # Dùng lại token vừa đăng xuất -> Bị chặn mã 401 Token Revoked!
    res_after_logout = client.get("/api/v1/posts/1", headers={
        "Authorization": f"Bearer {alice_token}"
    })
    assert res_after_logout.status_code == 401
    assert res_after_logout.get_json()["code"] == "TOKEN_REVOKED"

