# Báo cáo Thực hành Tuần 6: Authentication và Authorization trong REST API

---

## 1. Giải đáp chi tiết 3 câu hỏi của đề bài cho từng Endpoint

| Endpoint | Yêu cầu Xác thực & Scope | Các lỗi có thể xảy ra | HTTP Status Codes |
| :--- | :--- | :--- | :---: |
| `POST /auth/login` | - AuthN: Không yêu cầu (Public).<br>- Scope: Không yêu cầu. | - Thiếu email hoặc password trong body.<br>- Sai định dạng JSON.<br>- Sai email hoặc sai mật khẩu.<br>- Vượt quá giới hạn tần suất thử mật khẩu (Brute-force).<br>- Tài khoản bị vô hiệu hóa. | `200 OK`<br>`400 Bad Request`<br>`401 Unauthorized`<br>`403 Forbidden`<br>`422 Unprocessable`<br>`429 Too Many Requests` |
| `POST /auth/refresh` | - AuthN: Bắt buộc Refresh Token (`Bearer <refreshToken>`).<br>- Scope: Cần scope `offline_access` và token type là `refresh`. | - Thiếu Refresh Token.<br>- Refresh Token đã hết hạn.<br>- Refresh Token nằm trong Blocklist thu hồi (Replay attack).<br>- Gửi nhầm Access Token vào endpoint refresh.<br>- Tài khoản người dùng bị khóa. | `200 OK`<br>`400 Bad Request`<br>`401 Unauthorized`<br>`403 Forbidden`<br>`429 Too Many Requests` |
| `GET /posts/{id}` | - AuthN: Bắt buộc Access Token (`Bearer <accessToken>`).<br>- Scope: Bắt buộc scope `posts:read`.<br>- Ownership: Quyền đối tượng (BOLA check). | - Không truyền token hoặc token hết hạn/bị revoke.<br>- Token thiếu scope `posts:read`.<br>- Lỗi BOLA: Cố tình đọc bài viết `private` của người khác khi không phải chủ sở hữu.<br>- Bài viết không tồn tại.<br>- Lỗi chữ ký token (Algorithm confusion). | `200 OK`<br>`401 Unauthorized`<br>`403 Forbidden`<br>`404 Not Found`<br>`429 Too Many Requests` |

---

## 2. Tóm tắt Báo cáo Kiểm toán An toàn Bảo mật ([`SecurityAudit.md`](./SecurityAudit.md))

Tài liệu đã phân tích chuyên sâu 7 điểm lộ lọt thông tin & lỗ hổng dựa trên OWASP API Security Top 10: 2023 và bài giảng Buổi 6:

1. Lỗ hổng BOLA (OWASP API1:2023) tại `GET /posts/{id}`: Kẻ tấn công thay đổi `{id}` trên URL để đọc trộm bài viết riêng tư (`private`) của người khác. $\rightarrow$ *Khắc phục: Áp dụng Lớp 3 kiểm tra quyền tác giả trước khi trả dữ liệu.*
2. Rò rỉ PII và Secret trong JWT Payload (Slide 18): Nhầm lẫn JWT có tính bí mật nên đưa `password_hash` vào claims. $\rightarrow$ *Khắc phục: Coi Payload là plaintext công khai, chỉ lưu `sub`, `roles`, `scopes`, `exp`.*
3. Tấn công Token Replay & Thiếu Revocation Blocklist: Refresh Token bị đánh cắp có thể tái sử dụng vô hạn. $\rightarrow$ *Khắc phục: Xoay vòng Refresh Token (RTR) và lưu `jti` bị thu hồi vào Blocklist.*
4. Lỗ hổng Algorithm Confusion & Bỏ qua xác minh `alg=none` (Slide 18): Attacker sửa header thành `alg=none` hoặc dùng Public Key RSA để ký HS256 giả mạo Admin. $\rightarrow$ *Khắc phục: Cấu hình cứng danh sách trắng thuật toán `JWT_DECODE_ALGORITHMS=["HS256"]`.*
5. User Enumeration & Brute-force tại `POST /auth/login`: Phản hồi "Sai email" vs "Sai mật khẩu" giúp hacker dò quét tài khoản. $\rightarrow$ *Khắc phục: Trả thông báo lỗi chung kèm Rate Limiting (HTTP 429).*
6. Thời hạn sống của Token quá dài (Unbounded Expiration): Access token sống 30 ngày không thu hồi được khi bị rò rỉ. $\rightarrow$ *Khắc phục: Access Token sống 15 phút, Refresh Token sống 30 ngày có cơ chế thu hồi.*
7. Lưu trữ Token tại `localStorage` (XSS Risk): JavaScript độc hại có thể đánh cắp token dễ dàng. $\rightarrow$ *Khắc phục: Khuyến nghị lưu Refresh Token trong Cookie `HttpOnly`, `Secure`, `SameSite=Strict`.*

---