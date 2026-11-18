"""Automated tests for URI Path Versioning."""
import pytest
import sys
from pathlib import Path

# Đảm bảo đường dẫn import app
LAB1_DIR = Path(__file__).resolve().parent.parent
if str(LAB1_DIR) not in sys.path:
    sys.path.insert(0, str(LAB1_DIR))

from app import create_app
from blueprints.users_data import reset_users


@pytest.fixture
def client():
    reset_users()
    application = create_app()
    application.config["TESTING"] = True
    with application.test_client() as test_client:
        yield test_client
    reset_users()


def test_get_user_v1_schema_and_headers(client):
    """v1: Trả về full_name kết hợp và gắn Sunset + Deprecation header."""
    response = client.get("/api/v1/users/1")
    assert response.status_code == 200

    data = response.get_json()
    assert data["id"] == 1
    assert data["full_name"] == "Văn Nguyễn"
    assert data["email"] == "a@vnu.vn"
    assert "first_name" not in data
    assert "last_name" not in data

    # Kiểm tra Mở rộng 3: Sunset & Deprecation headers
    assert "Sunset" in response.headers
    assert response.headers["Sunset"] == "Thu, 31 Dec 2026 23:59:59 GMT"
    assert response.headers.get("Deprecation") == "true"
    assert 'rel="successor-version"' in response.headers.get("Link", "")


def test_get_user_v2_breaking_change_schema(client):
    """v2: Trả về first_name và last_name riêng biệt."""
    response = client.get("/api/v2/users/1")
    assert response.status_code == 200

    data = response.get_json()
    assert data["id"] == 1
    assert data["first_name"] == "Văn"
    assert data["last_name"] == "Nguyễn"
    assert data["email"] == "a@vnu.vn"
    assert "full_name" not in data

    # v2 là phiên bản hiện tại, không có header Sunset
    assert "Sunset" not in response.headers


def test_get_user_not_found(client):
    """Cả v1 và v2 đều trả 404 cho user không tồn tại."""
    res_v1 = client.get("/api/v1/users/999")
    assert res_v1.status_code == 404
    assert res_v1.get_json() == {"error": "nf"}

    res_v2 = client.get("/api/v2/users/999")
    assert res_v2.status_code == 404
    assert res_v2.get_json() == {"error": "nf"}


def test_post_user_v2_success(client):
    """Mở rộng 1: Tạo user mới qua POST /api/v2/users."""
    new_user_payload = {
        "first_name": "Hoàng",
        "last_name": "Lê",
        "email": "hoang@vnu.vn"
    }
    response = client.post("/api/v2/users", json=new_user_payload)
    assert response.status_code == 201

    data = response.get_json()
    assert data["id"] == 3
    assert data["first_name"] == "Hoàng"
    assert data["last_name"] == "Lê"
    assert data["email"] == "hoang@vnu.vn"

    # Kiểm tra lại qua v2 GET
    get_v2 = client.get("/api/v2/users/3")
    assert get_v2.status_code == 200
    assert get_v2.get_json()["first_name"] == "Hoàng"

    # Single source dữ liệu: v1 GET cũng đọc được nhưng theo schema full_name
    get_v1 = client.get("/api/v1/users/3")
    assert get_v1.status_code == 200
    assert get_v1.get_json()["full_name"] == "Hoàng Lê"


def test_post_user_v2_validation_error(client):
    """Mở rộng 1: POST /api/v2/users thiếu trường bắt buộc báo lỗi 400."""
    response = client.post("/api/v2/users", json={"first_name": "Hoàng"})
    assert response.status_code == 400
    data = response.get_json()
    assert data["error"] == "validation_error"
