from flask import Flask, jsonify, request, make_response

app = Flask(__name__)
posts = []
_next_id = 1

@app.get("/api/v1/posts")
def list_posts():
    return jsonify({
        "data": posts,
        "total": len(posts)
    }), 200

@app.post("/api/v1/posts")
def create_post():
    global _next_id
    if not request.is_json:
        return jsonify(error="expected JSON"), 415
    data = request.get_json(silent=True) or {}
    title = (data.get("title") or "").strip()
    content = (data.get("content") or "").strip()
    if not title or not content:
        return jsonify(error="title and content are required"), 422

    post = {
        "id": _next_id,
        "title": title,
        "content": content
    }
    posts.append(post)
    _next_id += 1
    resp = make_response(jsonify(post), 201)
    resp.headers["Location"] = f"/api/v1/posts/{post['id']}"
    return resp

if __name__ == "__main__":
    app.run(host="127.0.0.1", port=5000, debug=True)