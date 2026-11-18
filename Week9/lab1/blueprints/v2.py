"""Blueprint v2: first_name + last_name.

Kèm mở rộng: Thêm endpoint POST /users cho v2.
"""
from flask import Blueprint, jsonify, request
from .users_data import get_user, add_user

bp = Blueprint("v2", __name__, url_prefix="/users")

@bp.route("/<int:uid>", methods=["GET"])
def get(uid):
    u = get_user(uid)
    if not u:
        return jsonify({"error": "nf"}), 404
    return jsonify({
        "id": uid,
        "first_name": u["first_name"],
        "last_name": u["last_name"],
        "email": u["email"]
    })

@bp.route("", methods=["POST"])
def create_user():
    """Mở rộng 1: Thêm POST /users cho v2."""
    if not request.is_json:
        return jsonify({"error": "bad_request", "message": "Expected application/json"}), 400

    data = request.get_json(silent=True) or {}
    first_name = data.get("first_name", "").strip()
    last_name = data.get("last_name", "").strip()
    email = data.get("email", "").strip()

    if not first_name or not last_name or not email:
        return jsonify({
            "error": "validation_error",
            "message": "Missing required fields: first_name, last_name, email"
        }), 400

    new_id, user = add_user(first_name, last_name, email)
    return jsonify({
        "id": new_id,
        "first_name": user["first_name"],
        "last_name": user["last_name"],
        "email": user["email"]
    }), 201
