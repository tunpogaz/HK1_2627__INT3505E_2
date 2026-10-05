import uuid
import logging
from flask import Flask, jsonify, request
from werkzeug.exceptions import HTTPException

app = Flask(__name__)
ERROR_BASE = "https://api.example.com/probs"

logging.basicConfig(level=logging.ERROR)

class ApiProblem(Exception):
    def __init__(self, status, title, detail=None, type_path=None, **extra):
        self.status = status
        self.title = title
        self.detail = detail
        self.type_path = type_path
        self.extra = extra

def _problem(status, title, detail=None, type_path=None, **extra):
    body = {
        "type": f"{ERROR_BASE}/{type_path}" if type_path else "about:blank",
        "title": title,
        "status": status,
        "instance": request.path,
        "trace_id": str(uuid.uuid4()),
    }
    if detail:
        body["detail"] = detail
    body.update(extra)

    resp = jsonify(body)
    resp.status_code = status
    resp.headers["Content-Type"] = "application/problem+json"
    return resp

@app.errorhandler(ApiProblem)
def handle_api_problem(e):
    return _problem(
        status=e.status,
        title=e.title,
        detail=e.detail,
        type_path=e.type_path,
        **e.extra
    )

@app.errorhandler(HTTPException)
def handle_http_exception(e):
    return _problem(
        status=e.code,
        title=e.name,
        detail=e.description,
        type_path=f"http-{e.code}"
    )

@app.errorhandler(Exception)
def handle_unexpected_exception(e):
    app.logger.error("Unhandled Exception: %s", str(e), exc_info=True)
    return _problem(
        status=500,
        title="Internal Server Error",
        detail="An unexpected error occurred. Please contact support with the trace_id.",
        type_path="internal-server-error"
    )

USERS = {
    42: {"id": 42, "name": "Alice"}
}

@app.get("/users/<int:id>")
def get_user(id):
    user = USERS.get(id)
    if not user:
        raise ApiProblem(
            status=404,
            title="User not found",
            detail=f"User with ID {id} does not exist in the database.",
            type_path="user-not-found",
            resource_id=id
        )
    return jsonify(user), 200

@app.get("/crash")
def simulate_crash():
    return 1 / 0

if __name__ == "__main__":
    app.run(host="127.0.0.1", port=5000, debug=False)