# LAB 1 — URI Path Versioning: User API v1 → v2 với Flask Blueprint

---

## 1. Mục tiêu và Kiến trúc

Triển khai chiến lược **URI Path Versioning** phân tách không gian URL thành 2 phiên bản độc lập thông qua **Flask Blueprint**:

- **v1 (`/api/v1/users/{id}`)**: Schema ban đầu trả về `full_name` gộp. Đang trong giai đoạn chuẩn bị ngừng hỗ trợ (Deprecation).
- **v2 (`/api/v2/users/{id}`)**: Schema mới (Breaking change) tách thành `first_name` và `last_name`.
- **Dữ liệu nguồn duy nhất (`users_data.py`)**: Đảm bảo cả hai phiên bản cùng đọc/ghi chung một nguồn dữ liệu (Single Source of Truth).

---

## 2. Hoàn thành đầy đủ 3 yêu cầu 

1. **Mở rộng 1 — Thêm `POST /users` cho v2**:
   - Cho phép tạo user mới với schema tách rời `first_name`, `last_name`, `email`.
   - Trả về mã `201 Created` và tự động cập nhật vào nguồn dữ liệu `USERS`.
2. **Mở rộng 2 — Tài liệu OpenAPI Spec (`openapi.yaml`)**:
   - Thiết kế đặc tả OpenAPI 3.0.3 chuẩn hóa cho cả 2 phiên bản v1 và v2.
   - Đạt chuẩn lint của Spectral với **0 problem**.
3. **Mở rộng 3 — Gắn Sunset Response Headers cho v1 (RFC 8594 & RFC 9745)**:
   - Khi client gọi v1, response tự động gắn các header:
     - `Sunset: Thu, 31 Dec 2026 23:59:59 GMT` (Thời điểm chính thức tắt endpoint).
     - `Deprecation: true` (Báo hiệu cho SDK / Observability tooling).
     - `Link: </api/v2/users>; rel="successor-version"` (Điều hướng client sang phiên bản kế nhiệm).

---

## 3. Cấu trúc thư mục

```text
Week9/lab1/
├── app.py                      # Application Factory mount cả 2 Blueprint v1 và v2
├── blueprints/
│   ├── __init__.py
│   ├── users_data.py           # Nguồn dữ liệu chung (Single source of truth)
│   ├── v1.py                   # Blueprint v1 (full_name + Sunset header)
│   └── v2.py                   # Blueprint v2 (first_name, last_name + POST user)
├── openapi.yaml                # OpenAPI Spec chuẩn hóa v1 & v2 (Mở rộng 2)
├── tests/
│   ├── __init__.py
│   └── test_users_versioning.py# Bộ test tự động Pytest (5/5 passed)
├── requirements.txt            # Thư viện phụ thuộc
└── README.md                   # Tài liệu hướng dẫn
```

---

## 4. Hướng dẫn chạy thử nghiệm & cURL

### Bước 1: Khởi động server

```bash
cd Week9/lab1
source ../../Week7/.venv/bin/activate
python app.py
```

> Server sẽ lắng nghe tại `http://127.0.0.1:5000`.

### Bước 2: Test các endpoint qua cURL

**1. Gọi v1 (Schema cũ: `full_name`, kèm Sunset headers):**

```bash
curl -i http://127.0.0.1:5000/api/v1/users/1
```

*Kết quả:*

```http
HTTP/1.1 200 OK
Sunset: Thu, 31 Dec 2026 23:59:59 GMT
Deprecation: true
Link: </api/v2/users>; rel="successor-version"
Content-Type: application/json

{
  "email": "a@vnu.vn",
  "full_name": "Văn Nguyễn",
  "id": 1
}
```

**2. Gọi v2 (Schema mới: `first_name` + `last_name`):**

```bash
curl -i http://127.0.0.1:5000/api/v2/users/1
```

*Kết quả:*

```http
HTTP/1.1 200 OK
Content-Type: application/json

{
  "email": "a@vnu.vn",
  "first_name": "Văn",
  "id": 1,
  "last_name": "Nguyễn"
}
```

**3. Tạo user mới qua `POST /api/v2/users` (Mở rộng 1):**

```bash
curl -i -X POST http://127.0.0.1:5000/api/v2/users \
  -H "Content-Type: application/json" \
  -d '{"first_name": "Hoàng", "last_name": "Lê", "email": "hoang@vnu.vn"}'
```

*Kết quả:* HTTP `201 Created`

```json
{
  "email": "hoang@vnu.vn",
  "first_name": "Hoàng",
  "id": 3,
  "last_name": "Lê"
}
```

---

## 5. Chạy kiểm thử tự động (Pytest)

Chạy bộ kiểm thử tự động:

```bash
pytest tests/ -v
```

Kết quả:

```text
tests/test_users_versioning.py::test_get_user_v1_schema_and_headers PASSED      [ 20%]
tests/test_users_versioning.py::test_get_user_v2_breaking_change_schema PASSED  [ 40%]
tests/test_users_versioning.py::test_get_user_not_found PASSED                [ 60%]
tests/test_users_versioning.py::test_post_user_v2_success PASSED              [ 80%]
tests/test_users_versioning.py::test_post_user_v2_validation_error PASSED      [100%]

============================== 5 passed in 0.08s ===============================
```
