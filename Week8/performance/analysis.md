# Lab 4 — Phân tích kết quả

| Kịch bản | Users | Spawn rate | Duration | p95 (ms) | Failure rate | RPS |
|---|---:|---:|---:|---:|---:|---:|
| A | 10 | 2 | 30s | 29 | 0.00% | 5.05 |
| B | 50 | 5 | 60s | 6 | 0.07% | 23.26 |
| C | 200 | 50 | 30s | 44 | 0.24% | 98.24 |

---

### 1. Kịch bản có p95 cao nhất là gì? Dùng số liệu quan sát để giải thích.
- **Kịch bản có p95 cao nhất:** **Kịch bản C** với $p95 = 44\text{ ms}$ (so với Kịch bản A là $29\text{ ms}$ và Kịch bản B là $6\text{ ms}$).
- **Giải thích bằng số liệu quan sát:**
  - Ở Kịch bản C, tải được đẩy lên rất cao với **200 users** đồng thời và tốc độ sinh (spawn rate) nhanh **50 users/giây**, đạt thông lượng xử lý lên tới **98.24 RPS** (tổng cộng 2,924 requests trong 30 giây).
  - Tải cao làm tăng áp lực đồng thời lên server Flask development server (chạy đơn tiến trình/đơn luồng Werkzeug) và SQLite (có cơ chế khóa file khi ghi). 
  - Mặc dù median (50%) vẫn rất nhanh ở mức 2 ms, nhưng độ lệch chuẩn và độ trễ đuôi (tail latency) ở các request cuối phân vị tăng vọt (thời gian phản hồi tối đa vọt lên 260 ms ở kịch bản C), kéo percentile 95% lên mức 44 ms.
  - *Ghi chú về Kịch bản A:* p95 của A (29 ms) cao hơn B (6 ms) chủ yếu do thời gian chạy ngắn (30s) với tổng số request ít (148 reqs), chịu ảnh hưởng bởi một số request khởi tạo/cold start ban đầu. Khi kịch bản B chạy dài 60s (1,390 reqs), hệ thống đã warm-up ổn định nên p95 giảm xuống 6 ms trước khi bị bão hòa tải ở kịch bản C.

---

### 2. Endpoint nào tăng failure rate? Phân biệt lỗi HTTP thực và lỗi đánh dấu trong Locust.
- **Endpoint tăng failure rate:** Duy nhất endpoint `GET /books?year=[year]` phát sinh failure (0.07% ở kịch bản B với 1 failure và 0.24% ở kịch bản C với 7 failures).
- **Phân biệt lỗi HTTP thực và lỗi đánh dấu trong Locust:**
  - **Lỗi HTTP thực (Real HTTP Errors):** Là khi backend server phát sinh sự cố hoặc quá tải thật sự và gửi về các mã trạng thái HTTP lỗi (ví dụ: `500 Internal Server Error`, `502 Bad Gateway`, `503 Service Unavailable`, `504 Gateway Timeout`). Trong toàn bộ 3 lần chạy đo đếm, **server Flask không phát sinh bất kỳ lỗi HTTP thực nào** (100% request từ server đều trả về HTTP 200, 201, 204 hoặc 404 hợp lệ).
  - **Lỗi đánh dấu trong Locust (Client-side / Synthetic Failures):** Là khi HTTP response từ server trả về vẫn là `200 OK`, nhưng mã kịch bản test Locust ở phía client chủ động gọi hàm `response.failure("Simulated 1% client-side SLA threshold breach")` để giả lập tỉ lệ lỗi vi phạm ngưỡng SLA nghiệp vụ (1%). Báo cáo Locust hiển thị chính xác lỗi này tại mục Error Report.

---

### 3. Với SLO giả định p95 < 300 ms, kịch bản nào đạt? Nêu giới hạn của phép đo.
- **Đánh giá SLO:** Cả 3 kịch bản **A (29 ms), B (6 ms), và C (44 ms)** đều **ĐẠT** yêu cầu SLO $p95 < 300\text{ ms}$ (tất cả đều thấp hơn rất nhiều so với ngưỡng 300 ms).
- **Giới hạn của phép đo:**
  1. **Môi trường mạng cục bộ (Loopback):** Cả client Locust và server API cùng chạy trên cùng một máy qua `127.0.0.1`, triệt tiêu hoàn toàn các yếu tố mạng thực tế: Network latency, packet loss, jitter, DNS resolution, băng thông và TLS termination.
  2. **Máy chủ phát triển (Development Server):** Server chạy bằng Flask development server (Werkzeug), không đại diện cho hạ tầng production chạy qua WSGI production (như Gunicorn/Uvicorn multi-worker) kết hợp Reverse Proxy (Nginx/Envoy).
  3. **Cơ sở dữ liệu SQLite:** SQLite lưu trữ file cục bộ và lock ở cấp database khi ghi, không phản ánh được cơ chế quản lý pool, locking phân tán và độ trễ mạng của các hệ quản trị CSDL Client-Server thực tế như PostgreSQL hay MySQL.
  4. **Kích thước dữ liệu nhỏ:** Số lượng bản ghi trong database chưa đủ lớn để tạo áp lực lên Disk I/O hay chỉ mục (indexes).
  5. *Kết luận:* Phép đo chỉ có ý nghĩa kiểm thử luồng tải và chức năng thực hành, **không thể dùng để khẳng định hay cam kết SLO cho hệ thống production thực tế**.

---

### 4. Nếu connection pool bị giới hạn ở 5, bạn sẽ kiểm chứng ảnh hưởng như thế nào?
Để kiểm chứng ảnh hưởng của giới hạn connection pool ở mức 5:
1. **Cấu hình Connection Pool trong ứng dụng:** Cấu hình SQLAlchemy với `pool_size = 5`, tắt overflow và đặt timeout ngắn:
   ```python
   app.config["SQLALCHEMY_ENGINE_OPTIONS"] = {
       "pool_size": 5,
       "max_overflow": 0,    # Không cho phép vượt quá 5 kết nối
       "pool_timeout": 3     # Chờ tối đa 3 giây trước khi báo lỗi Timeout
   }
   ```
2. **Tạo kịch bản giữ kết nối lâu (Simulated Latency):** Trong endpoint xử lý database (ví dụ POST create book hoặc GET books), chèn độ trễ giả lập giữ transaction (ví dụ `time.sleep(0.5)` hoặc query database có độ trễ) để kéo dài thời gian chiếm giữ kết nối của mỗi worker.
3. **Chạy kiểm thử tải đồng thời:** Dùng Locust sinh tải với số lượng người dùng đồng thời vượt quá 5 (ví dụ 20–50 users đồng thời) liên tục gửi request.
4. **Đo lường & Quan sát:**
   - **Tỉ lệ lỗi (Error Rate):** Khi cả 5 kết nối đều bận quá 3 giây, SQLAlchemy sẽ ném lỗi `TimeoutError: QueuePool limit of size 5 overflow 0 reached, connection timed out`, khiến server trả về HTTP 500. Ta sẽ quan sát thấy failure rate tăng vọt.
   - **Thời gian phản hồi (p95):** Các request phải xếp hàng chờ kết nối được giải phóng, dẫn đến thời gian chờ tăng vọt theo cấp số cộng (queueing delay).
   - **Đối chứng:** So sánh biểu đồ response time và failure rate giữa `pool_size = 5` và `pool_size = 20` để chứng minh hiện tượng cạn kiệt connection pool.
