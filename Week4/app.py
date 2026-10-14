"""
Week 4: API Specification và OpenAPI với Flask + Swagger UI
Dựa theo nội dung slide Buổi 4 (UET - Kỹ thuật Hướng Dịch vụ)
- Cung cấp 5 endpoints chuẩn RESTful cho Tasks API (list, create, get, patch, delete)
- Endpoint /openapi.json trả về đặc tả OpenAPI 3.0.3 (đọc từ openapi.json / tasks-api.yaml / apispec)
- Endpoint /docs nhúng Swagger UI hiển thị docs và cho phép "Try it out" tương tác trực tiếp
- Chuẩn lỗi RFC 7807 (Problem Details) application/problem+json
"""

import os
import json
import uuid
from datetime import datetime, timezone
from flask import Flask, jsonify, request, redirect, Response

# Cố gắng import marshmallow, apispec, yaml nếu môi trường đã cài đặt
try:
    import yaml
    HAS_YAML = True
except ImportError:
    HAS_YAML = False

try:
    from marshmallow import Schema, fields, validate, ValidationError
    HAS_MARSHMALLOW = True
except ImportError:
    HAS_MARSHMALLOW = False

    # Fallback nhẹ nếu chưa cài marshmallow
    class ValidationError(Exception):
        def __init__(self, messages):
            self.messages = messages
            super().__init__(str(messages))

    class Schema:
        def load(self, data):
            if not isinstance(data, dict):
                raise ValidationError({"_schema": ["Dữ liệu phải là JSON object"]})
            return data

try:
    from apispec import APISpec
    from apispec.ext.marshmallow import MarshmallowPlugin
    from apispec_webframeworks.flask import FlaskPlugin
    HAS_APISPEC = True
except ImportError:
    HAS_APISPEC = False

# Khởi tạo ứng dụng Flask
app = Flask(__name__)

# ==============================================================================
# 1. ĐỊNH NGHĨA MARSHMALLOW SCHEMAS (Nếu có marshmallow)
# ==============================================================================
if HAS_MARSHMALLOW:
    class TaskSchema(Schema):
        """Schema mô tả một Task đầy đủ"""
        id = fields.UUID(dump_only=True)
        title = fields.Str(required=True, validate=validate.Length(min=1))
        status = fields.Str(load_default="open", validate=validate.OneOf(["open", "in_progress", "done"]))
        priority = fields.Str(load_default="normal", validate=validate.OneOf(["low", "normal", "high"]))
        dueDate = fields.Date()
        assigneeId = fields.Str()
        createdAt = fields.DateTime(dump_only=True)
        updatedAt = fields.DateTime(dump_only=True)

    class CreateTaskInputSchema(Schema):
        """Schema dữ liệu đầu vào khi tạo task (POST)"""
        title = fields.Str(required=True, validate=validate.Length(min=1))
        status = fields.Str(load_default="open", validate=validate.OneOf(["open", "in_progress", "done"]))
        priority = fields.Str(load_default="normal", validate=validate.OneOf(["low", "normal", "high"]))
        dueDate = fields.Date()
        assigneeId = fields.Str()

    class UpdateTaskInputSchema(Schema):
        """Schema dữ liệu đầu vào khi cập nhật một phần task (PATCH)"""
        title = fields.Str(validate=validate.Length(min=1))
        status = fields.Str(validate=validate.OneOf(["open", "in_progress", "done"]))
        priority = fields.Str(validate=validate.OneOf(["low", "normal", "high"]))
        dueDate = fields.Date()
        assigneeId = fields.Str()

    class ErrorSchema(Schema):
        """Schema phản hồi lỗi chuẩn RFC 7807 (Problem Details)"""
        type = fields.Str()
        title = fields.Str(required=True)
        status = fields.Int(required=True)
        detail = fields.Str()
        instance = fields.Str()
        traceId = fields.Str()

# ==============================================================================
# 2. KHỞI TẠO APISPEC (Slide 27 - 28)
# ==============================================================================
if HAS_APISPEC and HAS_MARSHMALLOW:
    spec = APISpec(
        title="Tasks API",
        version="1.0.0",
        openapi_version="3.0.3",
        plugins=[FlaskPlugin(), MarshmallowPlugin()],
    )
    spec.components.schema("Task", schema=TaskSchema)
    spec.components.schema("CreateTaskInput", schema=CreateTaskInputSchema)
    spec.components.schema("UpdateTaskInput", schema=UpdateTaskInputSchema)
    spec.components.schema("Error", schema=ErrorSchema)
else:
    spec = None

# ==============================================================================
# 3. CƠ SỞ DỮ LIỆU MẪU (In-Memory Database)
# ==============================================================================
TASKS_DB = [
    {
        "id": "9b1deb4d-3b7d-4bad-9bdd-2b0d7b3dcb6d",
        "title": "Thiết kế OpenAPI Specification cho Tasks API",
        "status": "done",
        "priority": "high",
        "dueDate": "2026-10-15",
        "assigneeId": "user-101",
        "createdAt": "2026-10-14T08:00:00Z",
        "updatedAt": "2026-10-14T08:30:00Z",
    },
    {
        "id": "c73a038b-118a-44d4-a146-5e5d16531102",
        "title": "Xây dựng Flask app tích hợp Swagger UI",
        "status": "open",
        "priority": "high",
        "dueDate": "2026-10-16",
        "assigneeId": "user-102",
        "createdAt": "2026-10-14T09:00:00Z",
        "updatedAt": "2026-10-14T09:00:00Z",
    },
    {
        "id": "e4587c6b-28a1-432d-89fa-118d53b26c04",
        "title": "Kiểm thử tự động các endpoint với Swagger UI Try it out",
        "status": "open",
        "priority": "normal",
        "dueDate": "2026-10-20",
        "assigneeId": "user-101",
        "createdAt": "2026-10-14T10:00:00Z",
        "updatedAt": "2026-10-14T10:00:00Z",
    },
    {
        "id": "f82b135a-90ce-4e12-b217-7e61a49dc975",
        "title": "Viết README mô tả 2 quyết định thiết kế khó nhất",
        "status": "open",
        "priority": "low",
        "dueDate": "2026-10-25",
        "assigneeId": "user-103",
        "createdAt": "2026-10-14T11:00:00Z",
        "updatedAt": "2026-10-14T11:00:00Z",
    },
]

# ==============================================================================
# 4. HELPER CHUẨN LỖI RFC 7807 (Problem Details)
# ==============================================================================
def problem_details(status: int, title: str, detail: str, instance: str, error_type: str = "about:blank", invalid_params=None):
    payload = {
        "type": error_type,
        "title": title,
        "status": status,
        "detail": detail,
        "instance": instance,
        "traceId": str(uuid.uuid4()),
    }
    if invalid_params:
        payload["invalidParams"] = invalid_params
    resp = jsonify(payload)
    resp.status_code = status
    resp.headers["Content-Type"] = "application/problem+json"
    return resp

# Giao diện Swagger UI nhúng
SWAGGER_HTML = """<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8">
  <title>Tasks API - Swagger UI</title>
  <link rel="stylesheet" href="https://cdn.jsdelivr.net/npm/swagger-ui-dist@5/swagger-ui.css">
  <link rel="icon" type="image/png" href="https://cdn.jsdelivr.net/npm/swagger-ui-dist@5/favicon-32x32.png" sizes="32x32" />
  <style>
    html { box-sizing: border-box; overflow-y: scroll; }
    *, *:before, *:after { box-sizing: inherit; }
    body { margin: 0; background: #fafafa; font-family: sans-serif; }
    .topbar { display: none; }
    .custom-header {
      background: #1e293b;
      color: #fff;
      padding: 12px 24px;
      display: flex;
      justify-content: space-between;
      align-items: center;
      box-shadow: 0 2px 4px rgba(0,0,0,0.1);
    }
    .custom-header h1 { margin: 0; font-size: 1.25rem; font-weight: 600; }
    .custom-header a {
      color: #38bdf8;
      text-decoration: none;
      font-size: 0.9rem;
      font-weight: 500;
    }
    .custom-header a:hover { text-decoration: underline; }
  </style>
</head>
<body>
  <div class="custom-header">
    <h1>Tasks API Documentation · OAS 3.0.3</h1>
    <div>
      <a href="/openapi.json" target="_blank">Raw openapi.json</a> &nbsp;|&nbsp;
      <a href="/openapi.yaml" target="_blank">Raw openapi.yaml</a>
    </div>
  </div>
  <div id="swagger-ui"></div>
  <script src="https://cdn.jsdelivr.net/npm/swagger-ui-dist@5/swagger-ui-bundle.js"></script>
  <script src="https://cdn.jsdelivr.net/npm/swagger-ui-dist@5/swagger-ui-standalone-preset.js"></script>
  <script>
    window.onload = function() {
      window.ui = SwaggerUIBundle({
        url: "/openapi.json",
        dom_id: '#swagger-ui',
        deepLinking: true,
        presets: [
          SwaggerUIBundle.presets.apis,
          SwaggerUIStandalonePreset
        ],
        plugins: [
          SwaggerUIBundle.plugins.DownloadUrl
        ],
        layout: "StandaloneLayout",
        defaultModelsExpandDepth: 2,
        defaultModelExpandDepth: 2,
        docExpansion: "list"
      });
    };
  </script>
</body>
</html>
"""

# ==============================================================================
# 5. CÁC ROUTES PHỤC VỤ TÀI LIỆU (SWAGGER UI & OPENAPI SPEC)
# ==============================================================================
@app.get("/")
def index():
    """Điều hướng trang chủ đến /docs"""
    return redirect("/docs")


@app.get("/docs")
def docs():
    """Render trang tài liệu tương tác Swagger UI (Slide 27, 28, 33)"""
    return Response(SWAGGER_HTML, mimetype="text/html; charset=utf-8")


@app.get("/openapi.json")
def spec_json():
    """Trả về đặc tả OpenAPI ở định dạng JSON (Slide 25, 28, 33)"""
    current_dir = os.path.dirname(os.path.abspath(__file__))
    
    # 1. Ưu tiên đọc từ openapi.json đã có sẵn
    json_path = os.path.join(current_dir, "openapi.json")
    if os.path.exists(json_path):
        with open(json_path, "r", encoding="utf-8") as f:
            return jsonify(json.load(f))

    # 2. Nếu có YAML và thư viện yaml
    if HAS_YAML:
        candidates = ["tasks-api.yaml", "openapi.yaml", "w4-1.yaml"]
        for filename in candidates:
            yaml_path = os.path.join(current_dir, filename)
            if os.path.exists(yaml_path):
                with open(yaml_path, "r", encoding="utf-8") as f:
                    return jsonify(yaml.safe_load(f))

    # 3. Fallback sang spec sinh bởi apispec (nếu có)
    if spec:
        return jsonify(spec.to_dict())

    return jsonify({"openapi": "3.0.3", "info": {"title": "Tasks API", "version": "1.0.0"}})


@app.get("/openapi.yaml")
def spec_yaml():
    """Trả về đặc tả OpenAPI ở định dạng YAML"""
    current_dir = os.path.dirname(os.path.abspath(__file__))
    candidates = ["tasks-api.yaml", "openapi.yaml", "w4-1.yaml"]
    for filename in candidates:
        yaml_path = os.path.join(current_dir, filename)
        if os.path.exists(yaml_path):
            with open(yaml_path, "r", encoding="utf-8") as f:
                content = f.read()
                return Response(content, mimetype="text/yaml; charset=utf-8")

    if spec and HAS_YAML:
        return Response(yaml.dump(spec.to_dict(), allow_unicode=True), mimetype="text/yaml; charset=utf-8")

    return Response("openapi: 3.0.3\ninfo:\n  title: Tasks API\n  version: 1.0.0\n", mimetype="text/yaml; charset=utf-8")


# ==============================================================================
# 6. NĂM ENDPOINTS TASKS API (Slide 22, 23, 27-30)
# Hỗ trợ cả prefix /v1/tasks và /tasks để đồng bộ hoàn toàn với Swagger UI và Slide
# ==============================================================================

# --- Endpoint 1: GET /tasks (List Tasks) ---
@app.get("/tasks")
@app.get("/v1/tasks")
def list_tasks():
    """get:
    tags: [tasks]
    summary: Lấy danh sách task (List tasks)
    description: Trả về danh sách task có phân trang và lọc theo trạng thái
    parameters:
      - name: limit
        in: query
        schema: {type: integer, minimum: 1, maximum: 100, default: 20}
      - name: status
        in: query
        schema: {type: string, enum: [open, in_progress, done]}
    responses:
      200:
        content:
          application/json:
            schema: TaskSchema
      400:
        content:
          application/problem+json:
            schema: ErrorSchema
      401:
        content:
          application/problem+json:
            schema: ErrorSchema
    """
    raw_limit = request.args.get("limit", default="20")
    try:
        limit = int(raw_limit)
        if limit < 1 or limit > 100:
            return problem_details(
                status=400,
                title="Bad Request",
                detail="Tham số 'limit' phải là số nguyên trong khoảng từ 1 đến 100.",
                instance=request.path,
            )
    except ValueError:
        return problem_details(
            status=400,
            title="Bad Request",
            detail=f"Tham số 'limit'='{raw_limit}' không phải là số nguyên hợp lệ.",
            instance=request.path,
        )

    # Lọc theo status
    status_filter = request.args.get("status")
    if status_filter:
        valid_statuses = ["open", "in_progress", "done"]
        if status_filter not in valid_statuses:
            return problem_details(
                status=400,
                title="Bad Request",
                detail=f"Trạng thái '{status_filter}' không hợp lệ. Chỉ chấp nhận: {valid_statuses}.",
                instance=request.path,
            )
        filtered = [t for t in TASKS_DB if t.get("status") == status_filter]
    else:
        filtered = TASKS_DB

    total = len(filtered)
    items = filtered[:limit]

    return jsonify({
        "items": items,
        "total": total,
        "limit": limit
    }), 200


# --- Endpoint 2: POST /tasks (Create Task) ---
@app.post("/tasks")
@app.post("/v1/tasks")
def create_task():
    """post:
    tags: [tasks]
    summary: Tạo task mới (Create task)
    requestBody:
      required: true
      content:
        application/json:
          schema: CreateTaskInputSchema
    responses:
      201:
        content:
          application/json:
            schema: TaskSchema
      400:
        content:
          application/problem+json:
            schema: ErrorSchema
      422:
        content:
          application/problem+json:
            schema: ErrorSchema
    """
    data = request.get_json(silent=True)
    if data is None or not isinstance(data, dict):
        return problem_details(
            status=400,
            title="Bad Request",
            detail="Request body phải ở định dạng JSON hợp lệ.",
            instance=request.path,
        )

    # Validate với marshmallow schema nếu có, ngược lại validate thủ công
    if HAS_MARSHMALLOW:
        schema = CreateTaskInputSchema()
        try:
            validated_data = schema.load(data)
        except ValidationError as err:
            return problem_details(
                status=422,
                title="Validation Error",
                detail=f"Dữ liệu payload không hợp lệ: {err.messages}",
                instance=request.path,
                invalid_params=[{"name": k, "reason": v} for k, v in err.messages.items()]
            )
    else:
        title = data.get("title", "").strip() if isinstance(data.get("title"), str) else ""
        if not title:
            return problem_details(
                status=422,
                title="Validation Error",
                detail="Trường 'title' là bắt buộc và không được để trống.",
                instance=request.path,
                invalid_params=[{"name": "title", "reason": "Trường 'title' không được để trống"}]
            )
        validated_data = data

    now_iso = datetime.now(timezone.utc).isoformat()
    new_id = str(uuid.uuid4())
    due_date_str = validated_data.get("dueDate")
    if hasattr(due_date_str, "isoformat"):
        due_date_str = due_date_str.isoformat()

    new_task = {
        "id": new_id,
        "title": validated_data["title"],
        "status": validated_data.get("status", "open"),
        "priority": validated_data.get("priority", "normal"),
        "dueDate": due_date_str,
        "assigneeId": validated_data.get("assigneeId"),
        "createdAt": now_iso,
        "updatedAt": now_iso,
    }

    TASKS_DB.append(new_task)

    location = f"/v1/tasks/{new_id}"
    resp = jsonify(new_task)
    resp.status_code = 201
    resp.headers["Location"] = location
    return resp


# --- Endpoint 3: GET /tasks/{taskId} (Get Task by ID) ---
@app.get("/tasks/<string:task_id>")
@app.get("/v1/tasks/<string:task_id>")
def get_task_by_id(task_id):
    """get:
    tags: [tasks]
    summary: Lấy chi tiết task theo ID
    parameters:
      - name: taskId
        in: path
        required: true
        schema: {type: string, format: uuid}
    responses:
      200:
        content:
          application/json:
            schema: TaskSchema
      404:
        content:
          application/problem+json:
            schema: ErrorSchema
    """
    task = next((t for t in TASKS_DB if t["id"] == task_id), None)
    if not task:
        return problem_details(
            status=404,
            title="Task Not Found",
            detail=f"Không tìm thấy task với ID '{task_id}'.",
            instance=request.path,
        )

    return jsonify(task), 200


# --- Endpoint 4: PATCH /tasks/{taskId} (Partially Update Task) ---
@app.patch("/tasks/<string:task_id>")
@app.patch("/v1/tasks/<string:task_id>")
def patch_task(task_id):
    """patch:
    tags: [tasks]
    summary: Cập nhật một phần task
    parameters:
      - name: taskId
        in: path
        required: true
        schema: {type: string, format: uuid}
    requestBody:
      required: true
      content:
        application/json:
          schema: UpdateTaskInputSchema
    responses:
      200:
        content:
          application/json:
            schema: TaskSchema
      404:
        content:
          application/problem+json:
            schema: ErrorSchema
      422:
        content:
          application/problem+json:
            schema: ErrorSchema
    """
    task = next((t for t in TASKS_DB if t["id"] == task_id), None)
    if not task:
        return problem_details(
            status=404,
            title="Task Not Found",
            detail=f"Không tìm thấy task với ID '{task_id}'.",
            instance=request.path,
        )

    data = request.get_json(silent=True)
    if data is None or not isinstance(data, dict):
        return problem_details(
            status=400,
            title="Bad Request",
            detail="Request body phải ở định dạng JSON hợp lệ.",
            instance=request.path,
        )

    if HAS_MARSHMALLOW:
        schema = UpdateTaskInputSchema()
        try:
            validated_data = schema.load(data)
        except ValidationError as err:
            return problem_details(
                status=422,
                title="Validation Error",
                detail=f"Dữ liệu cập nhật không hợp lệ: {err.messages}",
                instance=request.path,
            )
    else:
        validated_data = data

    for field, val in validated_data.items():
        if field == "dueDate" and hasattr(val, "isoformat"):
            task[field] = val.isoformat()
        else:
            task[field] = val

    task["updatedAt"] = datetime.now(timezone.utc).isoformat()

    return jsonify(task), 200


# --- Endpoint 5: DELETE /tasks/{taskId} (Delete Task) ---
@app.delete("/tasks/<string:task_id>")
@app.delete("/v1/tasks/<string:task_id>")
def delete_task(task_id):
    """delete:
    tags: [tasks]
    summary: Xoá task
    parameters:
      - name: taskId
        in: path
        required: true
        schema: {type: string, format: uuid}
    responses:
      204:
        description: Xoá thành công, no content
      404:
        content:
          application/problem+json:
            schema: ErrorSchema
    """
    global TASKS_DB
    task = next((t for t in TASKS_DB if t["id"] == task_id), None)
    if not task:
        return problem_details(
            status=404,
            title="Task Not Found",
            detail=f"Không tìm thấy task với ID '{task_id}'.",
            instance=request.path,
        )

    TASKS_DB = [t for t in TASKS_DB if t["id"] != task_id]
    return "", 204


# ==============================================================================
# 7. ĐĂNG KÝ VIEW VÀO APISPEC (Slide 28 - Demo 24)
# ==============================================================================
if spec:
    try:
        with app.test_request_context():
            spec.path(view=list_tasks)
            spec.path(view=create_task)
            spec.path(view=get_task_by_id)
            spec.path(view=patch_task)
            spec.path(view=delete_task)
    except Exception as e:
        print(f"Lưu ý: Không thể đăng ký apispec view docstrings: {e}")


# ==============================================================================
# 8. CHẠY SERVER FLASK
# ==============================================================================
if __name__ == "__main__":
    print("=" * 60)
    print("Tasks API Server đang chạy!")
    print("Swagger UI Documentation: http://localhost:5000/docs")
    print("OpenAPI Specification:   http://localhost:5000/openapi.json")
    print("=" * 60)
    app.run(host="0.0.0.0", port=5000, debug=True)

