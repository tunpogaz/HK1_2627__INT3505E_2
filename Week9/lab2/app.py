from functools import wraps
from flask import Flask, jsonify, request

LATEST = "2"
SUPPORTED = {"1", "2", "2024-06-20"}
USERS = {
    1: {"f": "Văn", "l": "Nguyễn", "e": "a@vnu.vn"},
    2: {"f": "Trang", "l": "Trần", "e": "b@vnu.vn"},
}

app = Flask(__name__)


def api_version(supported=SUPPORTED, default=LATEST):
    """Decorator quản lý versioning qua HTTP Request Header 'X-API-Version'.

    - Nếu client không truyền header -> Sử dụng phiên bản mặc định (mới nhất).
    - Nếu phiên bản không hợp lệ -> Trả về HTTP 400 và không fallback.
    - Truyền tham số version vào hàm endpoint xử lý logic tương ứng.
    - Gắn header 'X-API-Version-Served' vào response để client / debug biết phiên bản đã phục vụ.
    """
    def decorate(fn):
        @wraps(fn)
        def wrapper(*args, **kwargs):
            v = request.headers.get("X-API-Version", default)
            if v not in supported:
                return jsonify(error="unsupported version"), 400
            result = fn(v, *args, **kwargs)
            if isinstance(result, tuple):
                response = jsonify(result[0])
                response.status_code = result[1]
            else:
                response = jsonify(result)
            response.headers["X-API-Version-Served"] = v
            return response
        return wrapper
    return decorate


@app.route("/users/<int:uid>")
@api_version()
def get_user(version, uid):
    u = USERS.get(uid)
    if not u:
        return {"error": "not found"}, 404
    if version == "1":
        return {"id": uid, "full_name": u["f"] + " " + u["l"]}
    return {"id": uid, "first_name": u["f"], "last_name": u["l"], "email": u["e"]}


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000, debug=True)
