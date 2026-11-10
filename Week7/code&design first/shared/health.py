from flask import Blueprint, jsonify
from sqlalchemy import text
from .extensions import db

health_bp = Blueprint("health", __name__, url_prefix="")

@health_bp.get("/healthz")
def liveness():
    """Liveness probe: returns 200 if the web process is alive (Slide 36-37)."""
    return jsonify({"status": "ok"}), 200

@health_bp.get("/ready")
def readiness():
    """Readiness probe: validates dependencies like database connectivity (Slide 36-37)."""
    checks = {}
    try:
        db.session.execute(text("SELECT 1"))
        checks["db"] = "ok"
    except Exception as e:
        checks["db"] = f"err: {str(e)}"

    ok = all(v == "ok" for v in checks.values())
    status_code = 200 if ok else 503
    return jsonify({
        "status": "ok" if ok else "degraded",
        "checks": checks
    }), status_code

