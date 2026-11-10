import sys
from pathlib import Path
import connexion
from connexion.resolver import RelativeResolver

current_dir = Path(__file__).resolve().parent
if str(current_dir) not in sys.path:
    sys.path.insert(0, str(current_dir))

from models import db, Product

def create_app(config=None):
    """Application Factory cho Design-First (Slide 9 & 13)."""
    # 1. Khởi tạo Connexion App với thư mục chứa spec openapi/ (Slide 9)
    connexion_app = connexion.FlaskApp(__name__, specification_dir=str(current_dir / "openapi"))

    # 2. Cấu hình Database
    db_uri = "sqlite:///design_first.db"
    if config and hasattr(config, "SQLALCHEMY_DATABASE_URI"):
        db_uri = config.SQLALCHEMY_DATABASE_URI

    connexion_app.app.config["SQLALCHEMY_DATABASE_URI"] = db_uri
    connexion_app.app.config["SQLALCHEMY_TRACK_MODIFICATIONS"] = False
    db.init_app(connexion_app.app)

    with connexion_app.app.app_context():
        db.create_all()

    # 3. Đăng ký file hợp đồng products.yaml (Slide 9)
    connexion_app.add_api(
        "products.yaml",
        resolver=RelativeResolver("api"),
        validate_responses=True
    )
    return connexion_app

app = create_app()

if __name__ == "__main__":
    print("🚀 Design-First API đang chạy tại: http://localhost:5001")
    print("👉 Swagger UI (Tự sinh): http://localhost:5001/ui")
    print("👉 Endpoint danh sách: http://localhost:5001/products")
    app.run(port=5001)
