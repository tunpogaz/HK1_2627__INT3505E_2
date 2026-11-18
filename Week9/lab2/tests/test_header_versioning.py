import pytest
from app import app


@pytest.fixture
def client():
    app.config["TESTING"] = True
    with app.test_client() as client:
        yield client


def test_default_version(client):
    """Mặc định khi không gửi header X-API-Version -> phục vụ version mới nhất (v2)."""
    response = client.get("/users/1")
    assert response.status_code == 200
    assert response.headers.get("X-API-Version-Served") == "2"

    data = response.get_json()
    assert data["id"] == 1
    assert data["first_name"] == "Văn"
    assert data["last_name"] == "Nguyễn"
    assert data["email"] == "a@vnu.vn"
    assert "full_name" not in data


def test_explicit_version_1(client):
    """Gửi header X-API-Version: 1 -> phục vụ schema v1 (full_name)."""
    response = client.get("/users/1", headers={"X-API-Version": "1"})
    assert response.status_code == 200
    assert response.headers.get("X-API-Version-Served") == "1"

    data = response.get_json()
    assert data["id"] == 1
    assert data["full_name"] == "Văn Nguyễn"
    assert "first_name" not in data
    assert "last_name" not in data


def test_dated_version(client):
    """Gửi header X-API-Version theo ngày (2024-06-20) -> phục vụ phiên bản chỉ định."""
    response = client.get("/users/1", headers={"X-API-Version": "2024-06-20"})
    assert response.status_code == 200
    assert response.headers.get("X-API-Version-Served") == "2024-06-20"

    data = response.get_json()
    assert data["id"] == 1
    assert data["first_name"] == "Văn"
    assert data["last_name"] == "Nguyễn"
    assert data["email"] == "a@vnu.vn"


def test_unsupported_version_returns_400(client):
    """Gửi version không hỗ trợ (ví dụ 99) -> trả về HTTP 400, không fallback ngầm định."""
    response = client.get("/users/1", headers={"X-API-Version": "99"})
    assert response.status_code == 400

    data = response.get_json()
    assert data == {"error": "unsupported version"}


def test_unsupported_version_string_returns_400(client):
    """Gửi version định dạng lạ (ví dụ v3-beta) -> HTTP 400."""
    response = client.get("/users/1", headers={"X-API-Version": "v3-beta"})
    assert response.status_code == 400
    assert response.get_json() == {"error": "unsupported version"}


def test_user_not_found(client):
    """Truy vấn người dùng không tồn tại -> HTTP 404."""
    response = client.get("/users/999")
    assert response.status_code == 404
    assert response.get_json() == {"error": "not found"}
    assert response.headers.get("X-API-Version-Served") == "2"
