"""Blueprint v1: full_name.

Kèm mở rộng: Gắn Sunset response header khi v1 sắp tắt.
"""
from flask import Blueprint, jsonify
from .users_data import get_user

bp = Blueprint("v1", __name__, url_prefix="/users")

@bp.after_request
def add_deprecation_headers(response):
    """Mở rộng 3: Gắn Sunset và Deprecation header thông báo v1 sắp bị gỡ bỏ."""
    response.headers["Sunset"] = "Thu, 31 Dec 2026 23:59:59 GMT"
    response.headers["Deprecation"] = "true"
    response.headers["Link"] = '</api/v2/users>; rel="successor-version"'
    return response

@bp.route("/<int:uid>", methods=["GET"])
def get(uid):
    u = get_user(uid)
    if not u:
        return jsonify({"error": "nf"}), 404
    return jsonify({
        "id": uid,
        "full_name": f"{u['first_name']} {u['last_name']}",
        "email": u["email"]
    })
