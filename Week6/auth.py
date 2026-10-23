from functools import wraps
from flask import jsonify, request, g
from flask_jwt_extended import get_jwt, get_jwt_identity, verify_jwt_in_request

REVOKED_TOKEN_JTIS = set()


def problem_details(status: int, title: str, detail: str, code: str = None, instance: str = None):
    """Tạo phản hồi lỗi chuẩn hóa theo tiêu chuẩn RFC 7807 (application/problem+json)."""
    payload = {
        "type": f"https://api.social.net/errors/{code.lower().replace('_', '-') if code else 'error'}",
        "title": title,
        "status": status,
        "detail": detail,
        "instance": instance or request.path
    }
    if code:
        payload["code"] = code
    return jsonify(payload), status, {"Content-Type": "application/problem+json"}


def configure_jwt_callbacks(jwt):
    """Đăng ký các hàm bắt lỗi của Flask-JWT-Extended theo chuẩn RFC 7807 (Slide 15)."""

    @jwt.token_in_blocklist_loader
    def check_if_token_revoked(_jwt_header, jwt_payload: dict) -> bool:
        jti = jwt_payload.get("jti")
        return jti in REVOKED_TOKEN_JTIS

    @jwt.expired_token_loader
    def expired_token_callback(_jwt_header, jwt_payload: dict):
        return problem_details(
            status=401,
            title="Token Expired",
            detail=f"Token loại '{jwt_payload.get('type', 'token')}' đã hết hạn. Vui lòng refresh hoặc đăng nhập lại.",
            code="TOKEN_EXPIRED"
        )

    @jwt.invalid_token_loader
    def invalid_token_callback(reason: str):
        return problem_details(
            status=401,
            title="Invalid Token",
            detail=f"Token không hợp lệ hoặc chữ ký số bị sai: {reason}",
            code="TOKEN_INVALID"
        )

    @jwt.unauthorized_loader
    def unauthorized_callback(reason: str):
        return problem_details(
            status=401,
            title="Unauthorized",
            detail=f"Thiếu thông tin chứng thực trong header Authorization: {reason}",
            code="TOKEN_MISSING"
        )

    @jwt.revoked_token_loader
    def revoked_token_callback(_jwt_header, _jwt_payload: dict):
        return problem_details(
            status=401,
            title="Token Revoked",
            detail="Token này đã bị thu hồi (đăng xuất hoặc token replay). Vui lòng đăng nhập lại.",
            code="TOKEN_REVOKED"
        )


def require_roles(*allowed_roles):
    """
    Decorator kiểm tra vai trò (RBAC - Coarse-grained, Slide 24).
    Chấp nhận nếu người dùng có ít nhất một trong các vai trò được phép (OR logic).
    """
    def decorator(fn):
        @wraps(fn)
        def wrapper(*args, **kwargs):
            verify_jwt_in_request()
            claims = get_jwt()
            user_roles = set(claims.get("roles", []))
            
            if not user_roles.intersection(set(allowed_roles)):
                return problem_details(
                    status=403,
                    title="Forbidden Role",
                    detail=f"Tài khoản cần có một trong các vai trò: {list(allowed_roles)}.",
                    code="INSUFFICIENT_ROLE"
                )
            return fn(*args, **kwargs)
        return wrapper
    return decorator


def require_scopes(*needed_scopes):
    """
    Decorator kiểm tra phạm vi quyền (OAuth2 Scope - Fine-grained, Slide 25).
    Chấp nhận khi token chứa đầy đủ tất cả các scopes được yêu cầu (AND logic).
    """
    def decorator(fn):
        @wraps(fn)
        def wrapper(*args, **kwargs):
            verify_jwt_in_request()
            claims = get_jwt()
            granted_scopes = set(claims.get("scopes", []))
            needed = set(needed_scopes)
            
            if not needed.issubset(granted_scopes):
                missing = list(needed.difference(granted_scopes))
                return problem_details(
                    status=403,
                    title="Insufficient Scope",
                    detail=f"Token thiếu các scope bắt buộc: {missing}. Cần có đủ: {list(needed_scopes)}.",
                    code="INSUFFICIENT_SCOPE"
                )
            return fn(*args, **kwargs)
        return wrapper
    return decorator


def check_post_access_policy(post, current_user_id: int, user_roles: list, is_friend: bool = False) -> tuple[bool, str]:
    """
    Kiểm tra chính sách phân quyền theo đối tượng (Object-Level Authorization - Slide 24, 26).
    Ngăn chặn triệt để lỗ hổng OWASP API1:2023 - BOLA (Broken Object Level Authorization).
    """
    # 1. Bài viết công khai: Bất kỳ user nào có scope posts:read đều được đọc
    if post.visibility == "public":
        return True, "OK"

    # 2. Quản trị viên có quyền xem kiểm duyệt mọi bài viết
    if "admin" in user_roles:
        return True, "OK (Admin override)"

    # 3. Tác giả sở hữu bài viết
    if post.author_id == current_user_id:
        return True, "OK (Owner)"

    # 4. Bài viết chỉ dành cho bạn bè
    if post.visibility == "friends_only":
        if is_friend:
            return True, "OK (Friend)"
        return False, "Bài viết này chỉ hiển thị cho bạn bè của tác giả."

    # 5. Bài viết riêng tư
    if post.visibility == "private":
        return False, "Bài viết này ở chế độ riêng tư, chỉ tác giả mới có quyền xem."

    return False, "Không có quyền truy cập bài viết này."

