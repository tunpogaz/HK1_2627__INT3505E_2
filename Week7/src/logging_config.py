import json
import logging
import sys
import time
from flask import has_request_context, request

class JsonFormatter(logging.Formatter):
    """Structured JSON formatter ghi log 1 dòng theo dõi request_id và latency (Slide 35)."""
    def format(self, rec):
        p = {
            "ts": self.formatTime(rec, "%Y-%m-%dT%H:%M:%SZ"),
            "level": rec.levelname,
            "msg": rec.getMessage(),
        }
        if has_request_context():
            p["rid"] = request.headers.get("X-Request-Id", "-")
            p["method"] = request.method
            p["path"] = request.path
        return json.dumps(p, ensure_ascii=False)

def configure_logging(app):
    """Cấu hình log dạng JSON và đo đạc latency request (Slide 35)."""
    h = logging.StreamHandler(sys.stdout)
    h.setFormatter(JsonFormatter())
    app.logger.handlers = [h]
    app.logger.setLevel(app.config.get("LOG_LEVEL", "INFO"))

    @app.before_request
    def _record_start():
        request._t0 = time.perf_counter()

    @app.after_request
    def _record_done(resp):
        if hasattr(request, "_t0"):
            ms = round((time.perf_counter() - request._t0) * 1000, 2)
            app.logger.info(f"{request.method} {request.path} {resp.status_code} in {ms}ms")
        return resp

