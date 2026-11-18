# Week 9 - Lab 2: Header Versioning với Decorator `@api_version`

Thực hành theo **Slide 21 (Practice 2 / 5)** - Môn Kiến trúc hướng dịch vụ (SOA): *09 API Versioning & Lifecycle Management*.

---

## 1. Mục tiêu bài lab

- Cùng giữ nguyên một URL duy nhất: `GET /users/{id}` cho tất cả các phiên bản API.
- Client chủ động chọn phiên bản mong muốn thông qua HTTP Request Header: `X-API-Version`.
- Server tự động gắn HTTP Response Header: `X-API-Version-Served` để client và hệ thống giám sát (monitoring/debugging) nhận biết chính xác phiên bản được phục vụ.
- Sử dụng mô hình thiết kế **Decorator Pattern** trong Python (`@api_version`) để trừu tượng hóa và tái sử dụng logic phân giải versioning trên các endpoints.

---

## 2. Bốn điểm cần nhớ (Core Principles)

1. **Decorator parse `X-API-Version`**: Lấy header từ request; nếu client không gửi thì tự động fallback về phiên bản mặc định (`default=LATEST` là `"2"`).
2. **Trả `X-API-Version-Served` header**: Mọi response thành công đều phản hồi header chỉ rõ version đã xử lý.
3. **Endpoint xử lý logic đa schema**:
   - Version `"1"`: trả về `full_name` (`"Văn Nguyễn"`).
   - Version `"2"` & `"2024-06-20"`: trả về chi tiết `first_name`, `last_name`, `email`.
4. **Version lạ -> HTTP 400, không fallback**: Nếu client yêu cầu version không nằm trong `SUPPORTED` (ví dụ `X-API-Version: 99`), server trả về lỗi `400 Bad Request` với message `{"error": "unsupported version"}` mà không cố gắng fallback về default.

---

## 3. Cấu trúc thư mục

```text
Week9/lab2/
├── app.py                      # Flask app chứa decorator @api_version & route /users/<int:uid>
├── requirements.txt            # Danh sách dependencies
├── tests/
│   ├── __init__.py
│   └── test_header_versioning.py  # 6 bài test tự động bao phủ toàn bộ kịch bản
└── README.md                   # Hướng dẫn chi tiết
```

---

## 4. Cài đặt và Chạy Server

### Kích hoạt môi trường ảo:
```bash
source /Users/tuanphong/Downloads/KTHDV/HK1_2627__INT3505E_2/Week7/.venv/bin/activate
```

### Khởi chạy ứng dụng Flask:
```bash
cd /Users/tuanphong/Downloads/KTHDV/HK1_2627__INT3505E_2/Week9/lab2
python app.py
```
Server sẽ chạy mặc định tại: `http://127.0.0.1:5000`.

---

## 5. Hướng dẫn Test với cURL (Các kịch bản từ Slide)

Mở một terminal mới và chạy các lệnh sau:

### 1. Default (không truyền header -> dùng version mới nhất `v2`)
```bash
curl -i http://127.0.0.1:5000/users/1
```
*Kết quả mong đợi:*
- Status: `HTTP/1.1 200 OK`
- Header: `X-API-Version-Served: 2`
- Body:
```json
{
  "email": "a@vnu.vn",
  "first_name": "Văn",
  "id": 1,
  "last_name": "Nguyễn"
}
```

### 2. Chỉ định phiên bản `v1` rõ ràng
```bash
curl -i -H "X-API-Version: 1" http://127.0.0.1:5000/users/1
```
*Kết quả mong đợi:*
- Status: `HTTP/1.1 200 OK`
- Header: `X-API-Version-Served: 1`
- Body:
```json
{
  "full_name": "Văn Nguyễn",
  "id": 1
}
```

### 3. Chỉ định Dated Version (`2024-06-20`)
```bash
curl -i -H "X-API-Version: 2024-06-20" http://127.0.0.1:5000/users/1
```
*Kết quả mong đợi:*
- Status: `HTTP/1.1 200 OK`
- Header: `X-API-Version-Served: 2024-06-20`
- Body:
```json
{
  "email": "a@vnu.vn",
  "first_name": "Văn",
  "id": 1,
  "last_name": "Nguyễn"
}
```

### 4. Version không hợp lệ -> HTTP 400
```bash
curl -i -H "X-API-Version: 99" http://127.0.0.1:5000/users/1
```
*Kết quả mong đợi:*
- Status: `HTTP/1.1 400 BAD REQUEST`
- Body:
```json
{
  "error": "unsupported version"
}
```

---

## 6. Chạy Automated Tests (Pytest)

Chạy bộ unit test tự động để kiểm thử tất cả các trường hợp:
```bash
cd /Users/tuanphong/Downloads/KTHDV/HK1_2627__INT3505E_2/Week9/lab2
/Users/tuanphong/Downloads/KTHDV/HK1_2627__INT3505E_2/Week7/.venv/bin/pytest tests/ -v
```
Hoặc từ root dự án:
```bash
PYTHONPATH=Week9/lab2 /Users/tuanphong/Downloads/KTHDV/HK1_2627__INT3505E_2/Week7/.venv/bin/pytest Week9/lab2/tests/ -v
```

---

## 7. So sánh Header Versioning và URI Versioning

| Tiêu chí | URI Versioning (Lab 1) | Header Versioning (Lab 2) |
| :--- | :--- | :--- |
| **URL** | Đổi URL (`/api/v1/users`, `/api/v2/users`) | Giữ nguyên URL (`/users/{id}`) |
| **Tuân thủ chuẩn REST** | Vi phạm nguyên tắc resource identifier độc lập | Tuân thủ tốt vì URL định danh tài nguyên thuần túy |
| **Caching** | Rất dễ cache tại CDN/Proxy theo URL | Phức tạp hơn, cần cấu hình header `Vary: X-API-Version` |
| **Dated Versioning** | Khó đưa date vào URL (làm URL cồng kềnh) | Rất phù hợp với date-based (ví dụ Stripe: `2024-06-20`) |
| **Khả năng test qua trình duyệt** | Dễ dàng gõ URL trên browser | Cần client hỗ trợ tùy biến header (cURL, Postman) |
