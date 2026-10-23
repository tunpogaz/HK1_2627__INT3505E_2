"""
Week 6: Authentication & Authorization
1. POST /api/v1/auth/login: Xác thực mật khẩu với bcrypt, cấp access & refresh token
2. POST /api/v1/auth/refresh: Cấp mới access token và xoay vòng refresh token
3. GET /api/v1/posts/<id>: Phân quyền 3 lớp (AuthN -> Scope 'posts:read' -> Object-Level Auth chống BOLA)
4. Tích hợp Swagger UI tương tác trực tiếp tại /docs
5. Chuẩn hóa lỗi RFC 7807
"""

import os
import time
from datetime import datetime, timezone, timedelta
from flask import Flask, jsonify, request, redirect, Response
from flask_jwt_extended import (
    JWTManager, create_access_token, create_refresh_token,
    jwt_required, get_jwt_identity, get_jwt
)
from sqlalchemy import select

from models import db, User, Post, Friendship
from auth import (
    configure_jwt_callbacks, problem_details, require_roles,
    require_scopes, check_post_access_policy, REVOKED_TOKEN_JTIS
)

app = Flask(__name__)

app.config.update(
    SECRET_KEY=os.environ.get("FLASK_SECRET_KEY", "super-secret-key-social-net-2026-min-256-bits-random"),
    JWT_SECRET_KEY=os.environ.get("JWT_SECRET_KEY", "jwt-signing-secret-key-long-entropy-256-bits-must-be-kept-secret"),
    JWT_ACCESS_TOKEN_EXPIRES=timedelta(minutes=15),
    JWT_REFRESH_TOKEN_EXPIRES=timedelta(days=30),
    JWT_ALGORITHM="HS256",
    JWT_DECODE_ALGORITHMS=["HS256"],
    SQLALCHEMY_DATABASE_URI="sqlite:///social_network.db",
    SQLALCHEMY_TRACK_MODIFICATIONS=False
)

db.init_app(app)
jwt = JWTManager(app)
configure_jwt_callbacks(jwt)

LOGIN_FAILURES = {}
RATE_LIMIT_WINDOW = 60
MAX_FAILED_ATTEMPTS = 5


def check_rate_limit(identifier: str) -> bool:
    """Kiểm tra giới hạn tần suất đăng nhập sai trong 60 giây."""
    now = time.time()
    failures = LOGIN_FAILURES.get(identifier, [])
    failures = [t for t in failures if now - t < RATE_LIMIT_WINDOW]
    LOGIN_FAILURES[identifier] = failures
    return len(failures) < MAX_FAILED_ATTEMPTS


def record_failed_attempt(identifier: str):
    LOGIN_FAILURES.setdefault(identifier, []).append(time.time())

# API ROUTES: AUTHENTICATION

@app.post("/api/v1/auth/login")
def login():
    """
    POST /auth/login (Slide 16, 29, 30)
    Xác thực người dùng bằng email và mật khẩu. Cấp phát cặp Access & Refresh tokens.
    """
    # 1. Kiểm tra payload
    payload = request.get_json(silent=True)
    if not payload or not isinstance(payload, dict):
        return problem_details(
            status=400,
            title="Invalid JSON Payload",
            detail="Request body phải là đối tượng JSON hợp lệ.",
            code="INVALID_PAYLOAD"
        )

    email = payload.get("email", "").strip().lower()
    password = payload.get("password", "")

    if not email or not password:
        return problem_details(
            status=400,
            title="Missing Credentials",
            detail="Yêu cầu cung cấp đầy đủ cả hai trường 'email' và 'password'.",
            code="VALIDATION_ERROR"
        )

    # 2. Kiểm tra Rate Limiting chống Brute-force
    client_ip = request.remote_addr or "127.0.0.1"
    rate_key = f"{client_ip}:{email}"
    if not check_rate_limit(rate_key):
        return problem_details(
            status=429,
            title="Too Many Requests",
            detail="Tài khoản này đã đăng nhập sai quá 5 lần. Vui lòng thử lại sau 60 giây.",
            code="RATE_LIMIT_EXCEEDED"
        )

    # 3. Tìm user trong DB và xác minh mật khẩu bằng bcrypt
    user = db.session.scalar(select(User).filter_by(email=email))
    if not user or not user.check_password(password):
        record_failed_attempt(rate_key)
        # Thông báo lỗi chung, chống User Enumeration (Slide 29)
        return problem_details(
            status=401,
            title="Authentication Failed",
            detail="Email hoặc mật khẩu không chính xác.",
            code="INVALID_CREDENTIALS"
        )

    if not user.is_active:
        return problem_details(
            status=403,
            title="Account Disabled",
            detail="Tài khoản của bạn đã bị vô hiệu hóa.",
            code="ACCOUNT_DISABLED"
        )

    # Xóa lịch sử đăng nhập sai khi thành công
    LOGIN_FAILURES.pop(rate_key, None)

    # 4. Tạo Claims tối thiểu cho JWT
    user_claims = {
        "roles": user.get_roles_list(),
        "scopes": user.get_scopes_list(),
        "email": user.email
    }

    # 5. Cấp phát Access Token và Refresh Token
    uid_str = str(user.id)
    access_token = create_access_token(
        identity=uid_str,
        additional_claims=user_claims
    )
    refresh_token = create_refresh_token(
        identity=uid_str,
        additional_claims={"scopes": ["offline_access"]}
    )

    return jsonify({
        "accessToken": access_token,
        "refreshToken": refresh_token,
        "tokenType": "Bearer",
        "expiresIn": 900,
        "user": user.to_public_dto()
    }), 200, {"Cache-Control": "no-store"}


@app.post("/api/v1/auth/refresh")
@jwt_required(refresh=True)
def refresh_token():
    """
    POST /auth/refresh (Slide 15, 17, 20, 30)
    Làm mới phiên làm việc bằng Refresh Token.
    Áp dụng kỹ thuật Refresh Token Rotation (RTR): Thu hồi token cũ và cấp mới cả hai token.
    """
    jwt_data = get_jwt()
    old_jti = jwt_data.get("jti")
    user_id = get_jwt_identity()

    # Kiểm tra loại token phải là refresh
    if jwt_data.get("type") != "refresh":
        return problem_details(
            status=403,
            title="Invalid Token Type",
            detail="Endpoint này chỉ chấp nhận token loại 'refresh'.",
            code="INVALID_TOKEN_TYPE"
        )

    # 1. Thu hồi Refresh Token cũ
    REVOKED_TOKEN_JTIS.add(old_jti)

    # 2. Truy xuất quyền mới nhất của User từ DB
    user = db.session.get(User, int(user_id))
    if not user or not user.is_active:
        return problem_details(
            status=401,
            title="User Unavailable",
            detail="Người dùng không tồn tại hoặc đã bị khóa tài khoản.",
            code="USER_INACTIVE"
        )

    user_claims = {
        "roles": user.get_roles_list(),
        "scopes": user.get_scopes_list(),
        "email": user.email
    }

    # 3. Sinh cặp token mới
    new_access_token = create_access_token(
        identity=str(user.id),
        additional_claims=user_claims
    )
    new_refresh_token = create_refresh_token(
        identity=str(user.id),
        additional_claims={"scopes": ["offline_access"]}
    )

    return jsonify({
        "accessToken": new_access_token,
        "refreshToken": new_refresh_token,
        "tokenType": "Bearer",
        "expiresIn": 900
    }), 200, {"Cache-Control": "no-store"}


@app.post("/api/v1/auth/logout")
@jwt_required()
def logout():
    """
    POST /auth/logout (Slide 15, 16)
    Đăng xuất và đưa jti của token hiện tại vào Blocklist thu hồi.
    """
    jti = get_jwt().get("jti")
    REVOKED_TOKEN_JTIS.add(jti)
    return jsonify({
        "message": "Đăng xuất thành công. Token đã được thu hồi vào blocklist."
    }), 200


# API ROUTES: POSTS

@app.get("/api/v1/posts/<int:post_id>")
@jwt_required()
@require_scopes("posts:read")
def get_post(post_id: int):
    """
    GET /posts/{id} (Slide 24, 25, 26, 30)
    Áp dụng mô hình phân quyền chặt chẽ 3 lớp:
    1. AuthN: Token hợp lệ
    2. Scope: Có scope 'posts:read'
    3. Object-Level Auth: Kiểm tra quyền sở hữu và chế độ hiển thị bài viết, chống BOLA (OWASP API1:2023)
    """
    current_user_id = int(get_jwt_identity())
    claims = get_jwt()
    user_roles = claims.get("roles", [])

    post = db.session.get(Post, post_id)
    if not post:
        return problem_details(
            status=404,
            title="Post Not Found",
            detail=f"Không tìm thấy bài viết với mã ID={post_id}.",
            code="POST_NOT_FOUND"
        )

    is_friend = False
    if post.visibility == "friends_only":
        friendship = db.session.scalar(
            select(Friendship).filter(
                ((Friendship.user_id == current_user_id) & (Friendship.friend_id == post.author_id)) |
                ((Friendship.user_id == post.author_id) & (Friendship.friend_id == current_user_id))
            )
        )
        is_friend = (friendship is not None)

    allowed, reason = check_post_access_policy(post, current_user_id, user_roles, is_friend)
    if not allowed:
        return problem_details(
            status=403,
            title="Forbidden Resource",
            detail=reason,
            code="BOLA_ACCESS_DENIED"
        )

    return jsonify(post.to_dto()), 200


@app.post("/api/v1/posts")
@jwt_required()
@require_scopes("posts:write")
def create_post():
    """Tạo bài viết mới (hỗ trợ kiểm thử)."""
    current_user_id = int(get_jwt_identity())
    data = request.get_json(silent=True) or {}

    title = data.get("title", "").strip()
    content = data.get("content", "").strip()
    visibility = data.get("visibility", "public").strip().lower()

    if not title or not content:
        return problem_details(
            status=400,
            title="Validation Error",
            detail="Trường 'title' và 'content' là bắt buộc.",
            code="VALIDATION_ERROR"
        )

    if visibility not in ("public", "private", "friends_only"):
        visibility = "public"

    new_post = Post(
        title=title,
        content=content,
        visibility=visibility,
        tags=data.get("tags", "general"),
        author_id=current_user_id
    )
    db.session.add(new_post)
    db.session.commit()

    return jsonify(new_post.to_dto()), 201

# SWAGGER UI & OPENAPI SPECIFICATION ROUTES

@app.get("/openapi.json")
def get_openapi_json():
    """Phục vụ file đặc tả OpenAPI JSON."""
    file_path = os.path.join(os.path.dirname(__file__), "openapi.json")
    if os.path.exists(file_path):
        with open(file_path, "r", encoding="utf-8") as f:
            return Response(f.read(), mimetype="application/json")
    return jsonify({"error": "openapi.json not found"}), 404


@app.get("/openapi.yaml")
def get_openapi_yaml():
    """Phục vụ file đặc tả OpenAPI YAML."""
    file_path = os.path.join(os.path.dirname(__file__), "openapi.yaml")
    if os.path.exists(file_path):
        with open(file_path, "r", encoding="utf-8") as f:
            return Response(f.read(), mimetype="text/yaml")
    return jsonify({"error": "openapi.yaml not found"}), 404


SWAGGER_UI_HTML = """
<!DOCTYPE html>
<html lang="vi">
<head>
    <meta charset="UTF-8">
    <title>Social Network API - Swagger UI (Week 6)</title>
    <link rel="stylesheet" href="https://unpkg.com/swagger-ui-dist@5.18.2/swagger-ui.css" />
    <style>
        body { margin: 0; background: #fafafa; }
        .top-banner { background: #1e3a8a; color: white; padding: 12px 24px; font-family: sans-serif; display: flex; justify-content: space-between; align-items: center; }
        .top-banner a { color: #38bdf8; text-decoration: none; font-weight: bold; }
    </style>
</head>
<body>
    <div class="top-banner">
        <div><strong>UET INT3505E · Buổi 06: Authentication & Authorization API</strong> (Vũ Tuấn Phong - 22028258)</div>
        <div><a href="/openapi.json" target="_blank">View OpenAPI JSON</a> | <a href="/openapi.yaml" target="_blank">View OpenAPI YAML</a></div>
    </div>
    <div id="swagger-ui"></div>
    <script src="https://unpkg.com/swagger-ui-dist@5.18.2/swagger-ui-bundle.js"></script>
    <script>
        window.onload = () => {
            window.ui = SwaggerUIBundle({
                url: '/openapi.json',
                dom_id: '#swagger-ui',
                deepLinking: true,
                presets: [
                    SwaggerUIBundle.presets.apis,
                    SwaggerUIBundle.SwaggerUIStandalonePreset
                ],
                layout: "BaseLayout"
            });
        };
    </script>
</body>
</html>
"""

@app.get("/docs")
def swagger_docs():
    """Giao diện Swagger UI tương tác với tính năng 'Try it out'."""
    return Response(SWAGGER_UI_HTML, mimetype="text/html")


@app.get("/")
def home_redirect():
    """Chuyển hướng trang chủ sang /docs."""
    return redirect("/docs")

# DATABASE SEED DATA

def seed_database():
    """Khởi tạo database và dữ liệu mẫu với mật khẩu được hash bằng bcrypt."""
    db.create_all()

    if db.session.scalar(select(User).limit(1)):
        return

    # 1. Tạo Users mẫu
    alice = User(
        username="alice_dev",
        email="alice@vnu.edu.vn",
        roles="user",
        scopes="posts:read,posts:write,profile"
    )
    alice.set_password("AlicePass123!")

    bob = User(
        username="bob_security",
        email="bob@vnu.edu.vn",
        roles="user",
        scopes="posts:read,posts:write,profile"
    )
    bob.set_password("BobPass123!")

    admin = User(
        username="admin_root",
        email="admin@vnu.edu.vn",
        roles="admin,user",
        scopes="posts:read,posts:write,admin:all,profile"
    )
    admin.set_password("AdminMaster2026!")

    guest = User(
        username="guest_user",
        email="guest@vnu.edu.vn",
        roles="guest",
        scopes="profile"
    )
    guest.set_password("GuestPass123!")

    db.session.add_all([alice, bob, admin, guest])
    db.session.commit()

    # 2. Tạo Posts mẫu để kiểm thử BOLA
    p1 = Post(
        title="[Public] Chào mừng đến với Mạng xã hội UET",
        content="Bài viết công khai của Alice, mọi người dùng có quyền đọc đều xem được.",
        visibility="public",
        tags="welcome,social",
        author_id=alice.id
    )
    p2 = Post(
        title="[Private] Nhật ký bí mật cá nhân của Alice",
        content="Nội dung riêng tư của Alice: Dữ liệu này chỉ Alice hoặc Admin mới có quyền truy cập. Nếu Bob đọc được là bị lỗi BOLA (OWASP API1:2023)!",
        visibility="private",
        tags="secret,private",
        author_id=alice.id
    )
    p3 = Post(
        title="[Public] Nghiên cứu về chuẩn bảo mật OAuth 2.0 & JWT",
        content="Bài viết phân tích của Bob về các kỹ thuật phòng vệ API...",
        visibility="public",
        tags="oauth,jwt,security",
        author_id=bob.id
    )
    p4 = Post(
        title="[Private] Ghi chú riêng tư của Bob",
        content="Ghi chú tài khoản ngân hàng và mã PIN của Bob.",
        visibility="private",
        tags="private,finance",
        author_id=bob.id
    )

    db.session.add_all([p1, p2, p3, p4])
    db.session.commit()
    print("Database seeded with sample users (Alice, Bob, Admin, Guest) and posts!")


with app.app_context():
    seed_database()

if __name__ == "__main__":
    app.run(host="127.0.0.1", port=5000, debug=True)

