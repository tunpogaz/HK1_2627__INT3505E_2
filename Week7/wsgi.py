import sys
from pathlib import Path

# Đảm bảo đường dẫn import cho src
current_dir = Path(__file__).resolve().parent
if str(current_dir) not in sys.path:
    sys.path.insert(0, str(current_dir))

from src.factory import create_app
from src.extensions import db

app = create_app()

if __name__ == "__main__":
    with app.app_context():
        db.create_all()
    print("🚀 Backend Service (Lab 1 & Orders) đang chạy tại: http://localhost:5000")
    print("👉 Health Liveness: http://localhost:5000/healthz")
    print("👉 Health Readiness: http://localhost:5000/ready")
    print("👉 Products: http://localhost:5000/api/v1/products")
    print("👉 Orders: http://localhost:5000/api/v1/orders")
    app.run(port=5000, debug=True)

