import sys
from pathlib import Path

# Đảm bảo đường dẫn import blueprints hoạt động ở mọi working directory
BASE_DIR = Path(__file__).resolve().parent
if str(BASE_DIR) not in sys.path:
    sys.path.insert(0, str(BASE_DIR))

from flask import Flask
from blueprints.v1 import bp as v1_bp
from blueprints.v2 import bp as v2_bp


def create_app():
    """Application Factory mount cả hai Blueprint theo URI Path."""
    application = Flask(__name__)
    # Ghép url_prefix của blueprint để đảm bảo route là /api/v1/users/<id>
    application.register_blueprint(v1_bp, url_prefix=f"/api/v1{v1_bp.url_prefix or ''}")
    application.register_blueprint(v2_bp, url_prefix=f"/api/v2{v2_bp.url_prefix or ''}")
    return application


app = create_app()

if __name__ == "__main__":
    print("🚀 API Versioning Service (URI Path Versioning - Lab 1) đang chạy tại: http://127.0.0.1:5000")
    print("👉 v1: http://127.0.0.1:5000/api/v1/users/1  (full_name, kèm Sunset & Deprecation header)")
    print("👉 v2: http://127.0.0.1:5000/api/v2/users/1  (first_name + last_name - breaking change)")
    print("👉 v2: POST http://127.0.0.1:5000/api/v2/users (Thêm user mới)")
    app.run(port=5000, debug=True)
