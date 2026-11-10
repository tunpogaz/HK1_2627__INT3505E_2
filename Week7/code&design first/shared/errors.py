from flask import jsonify
from werkzeug.exceptions import HTTPException

class ApiError(Exception):
    """Base class for all business errors (Slide 30)."""
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
    """Global error handlers registration (Slide 31)."""
    @app.errorhandler(ApiError)
    def _on_api(err):
        return jsonify({
            "code": err.code,
            "message": err.message
        }), err.status_code

    @app.errorhandler(HTTPException)
    def _on_http(err):
        return jsonify({
            "code": err.name.lower().replace(" ", "_"),
            "message": err.description
        }), err.code

    @app.errorhandler(Exception)
    def _on_err(err):
        app.logger.exception("unhandled_exception")
        return jsonify({
            "code": "internal_error",
            "message": str(err) if app.config.get("DEBUG") else "An internal server error occurred"
        }), 500

