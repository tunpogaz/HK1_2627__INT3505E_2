from flask import Flask

from .config import DefaultConfig
from .extensions import db, migrate
from .errors import register_error_handlers
from .logging_config import configure_logging
from .api import products_bp, orders_bp, health_bp

def create_app(config=None):
    """Application Factory tạo Flask App hoàn chỉnh (Slide 13, 16)."""
    app = Flask(__name__)
    cfg = config or DefaultConfig
    app.config.from_object(cfg)

    # Khởi tạo extensions
    db.init_app(app)
    migrate.init_app(app, db)
    configure_logging(app)
    register_error_handlers(app)

    # Đăng ký Blueprints
    app.register_blueprint(health_bp)
    app.register_blueprint(products_bp)
    app.register_blueprint(orders_bp)

    # Khởi tạo bảng cơ sở dữ liệu nếu chưa tồn tại
    with app.app_context():
        db.create_all()

    return app
