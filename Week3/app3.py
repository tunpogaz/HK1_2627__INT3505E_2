import base64
import json
from flask import Flask, jsonify, request

app = Flask(__name__)

ORDERS_DATA = [
    {"id": 1, "customer_id": 101, "status": "paid", "total": 120000, "created_at": "2026-09-01T08:30:00Z"},
    {"id": 2, "customer_id": 102, "status": "pending", "total": 450000, "created_at": "2026-09-02T09:15:00Z"},
    {"id": 3, "customer_id": 101, "status": "paid", "total": 230000, "created_at": "2026-09-03T10:00:00Z"},
    {"id": 4, "customer_id": 103, "status": "cancelled", "total": 90000, "created_at": "2026-09-04T11:45:00Z"},
    {"id": 5, "customer_id": 104, "status": "shipped", "total": 510000, "created_at": "2026-09-05T13:20:00Z"},
    {"id": 6, "customer_id": 102, "status": "paid", "total": 180000, "created_at": "2026-09-06T14:10:00Z"},
    {"id": 7, "customer_id": 105, "status": "pending", "total": 320000, "created_at": "2026-09-07T15:00:00Z"},
    {"id": 8, "customer_id": 101, "status": "paid", "total": 750000, "created_at": "2026-09-08T16:30:00Z"},
    {"id": 9, "customer_id": 103, "status": "shipped", "total": 290000, "created_at": "2026-09-09T17:15:00Z"},
    {"id": 10, "customer_id": 104, "status": "paid", "total": 620000, "created_at": "2026-09-10T18:00:00Z"},
    {"id": 11, "customer_id": 105, "status": "cancelled", "total": 150000, "created_at": "2026-09-11T19:25:00Z"},
    {"id": 12, "customer_id": 102, "status": "paid", "total": 410000, "created_at": "2026-09-12T20:10:00Z"},
]

ALLOWED_SORT_FIELDS = {"id", "total", "created_at"}
AVAILABLE_FIELDS = set(ORDERS_DATA[0].keys())

def build_error_response(detail, status_code=400):
    """Định dạng phản hồi lỗi theo chuẩn RFC 7807 problem+json"""
    payload = {
        "type": "about:blank",
        "title": "Bad Request",
        "status": status_code,
        "detail": detail,
        "instance": request.path,
    }
    response = jsonify(payload)
    response.status_code = status_code
    response.headers["Content-Type"] = "application/problem+json"
    return response

def serialize_cursor(payload_dict):
    """Mã hoá dictionary thành chuỗi Base64 an toàn cho URL"""
    raw_bytes = json.dumps(payload_dict).encode("utf-8")
    return base64.urlsafe_b64encode(raw_bytes).decode("utf-8")

def parse_cursor(cursor_str):
    """Giải mã cursor từ Base64"""
    raw_bytes = base64.urlsafe_b64decode(cursor_str.encode("utf-8"))
    return json.loads(raw_bytes.decode("utf-8"))

@app.get("/orders")
def get_orders():
    sort_query = request.args.get("sort", "id")
    is_descending = sort_query.startswith("-")
    field_to_sort = sort_query.lstrip("-")

    if field_to_sort not in ALLOWED_SORT_FIELDS:
        return build_error_response(
            f"Invalid sort field '{field_to_sort}'. Supported fields: {sorted(list(ALLOWED_SORT_FIELDS))}"
        )

    try:
        raw_limit = int(request.args.get("limit", 10))
        limit = max(1, min(raw_limit, 100))
    except ValueError:
        return build_error_response("The 'limit' parameter must be an integer.")

    filtered_orders = ORDERS_DATA

    target_status = request.args.get("status")
    if target_status:
        filtered_orders = [item for item in filtered_orders if item["status"].lower() == target_status.lower()]

    raw_customer_id = request.args.get("customer_id")
    if raw_customer_id:
        try:
            target_cid = int(raw_customer_id)
            filtered_orders = [item for item in filtered_orders if item["customer_id"] == target_cid]
        except ValueError:
            return build_error_response("The 'customer_id' parameter must be an integer.")

    sorted_orders = sorted(
        filtered_orders,
        key=lambda item: (item[field_to_sort], item["id"]),
        reverse=is_descending
    )

    cursor_token = request.args.get("cursor")
    if cursor_token:
        try:
            cursor_info = parse_cursor(cursor_token)
            if cursor_info.get("sort") != sort_query:
                raise ValueError("Cursor does not match the requested sort order.")

            pivot = (cursor_info["val"], cursor_info["id"])
            if is_descending:
                sorted_orders = [item for item in sorted_orders if (item[field_to_sort], item["id"]) < pivot]
            else:
                sorted_orders = [item for item in sorted_orders if (item[field_to_sort], item["id"]) > pivot]
        except Exception:
            return build_error_response("Invalid or malformed cursor.")

    records = sorted_orders[:limit]

    next_cursor = None
    if len(sorted_orders) > limit:
        last_record = records[-1]
        next_cursor = serialize_cursor({
            "sort": sort_query,
            "val": last_record[field_to_sort],
            "id": last_record["id"],
        })

    fields_query = request.args.get("fields")
    if fields_query:
        selected_fields = [f.strip() for f in fields_query.split(",") if f.strip()]
        unrecognized_fields = set(selected_fields) - AVAILABLE_FIELDS
        if unrecognized_fields:
            return build_error_response(f"Unrecognized fields: {sorted(list(unrecognized_fields))}")

        records = [{k: item[k] for k in selected_fields} for item in records]

    return jsonify({
        "data": records,
        "next_cursor": next_cursor
    }), 200

if __name__ == "__main__":
    app.run(host="127.0.0.1", port=5000, debug=True)