from flask import jsonify
from werkzeug.exceptions import HTTPException

class ApiError(Exception):
    """Lớp Exception cơ sở cho toàn bộ lỗi nghiệp vụ (Slide 30)."""
    status_code = 500
    code = "internal_error"

    def __init__(self, code=None, message="", status=None):
        super().__init__(message)
        if code:
            self.code = code
        if status:
            self.status_code = status
        self.message = message

class NotFound(ApiError):
    status_code = 404
    code = "not_found"

class Conflict(ApiError):
    status_code = 409
    code = "conflict"

class OutOfStock(ApiError):
    status_code = 409
    code = "out_of_stock"

class BadRequest(ApiError):
    status_code = 400
    code = "bad_request"

class ValidationError(ApiError):
    status_code = 422
    code = "validation_error"

def register_error_handlers(app):
    """Đăng ký global error handler định dạng JSON nhất quán (Slide 31)."""
    @app.errorhandler(ApiError)
    def _on_api(err):
        return jsonify({
            "code": err.code,
            "message": err.message,
            "error": err.code,
            "detail": err.message
        }), err.status_code

    @app.errorhandler(HTTPException)
    def _on_http(err):
        code_str = err.name.lower().replace(" ", "_")
        return jsonify({
            "code": code_str,
            "message": err.description,
            "error": code_str,
            "detail": err.description
        }), err.code

    @app.errorhandler(Exception)
    def _on_err(err):
        app.logger.exception("unhandled_exception")
        return jsonify({
            "code": "internal_error",
            "message": str(err) if app.config.get("DEBUG") else "An internal server error occurred",
            "error": "internal_error",
            "detail": "An internal server error occurred"
        }), 500

