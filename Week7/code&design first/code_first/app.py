import sys
from pathlib import Path
from flask import Flask
from flask_smorest import Api

parent_dir = Path(__file__).resolve().parent.parent
if str(parent_dir) not in sys.path:
    sys.path.insert(0, str(parent_dir))

from shared.config import DefaultConfig
from shared.extensions import db, migrate
from shared.errors import register_error_handlers
from shared.logging_config import configure_logging
from shared.health import health_bp
try:
    from code_first.api import products_blp, orders_blp
except ImportError:
    from api import products_blp, orders_blp

def create_app(config=None):
    """Application Factory for Code-First approach using flask-smorest (Slide 10-13)."""
    app = Flask(__name__)
    cfg = config or DefaultConfig
    app.config.from_object(cfg)

    # Initialize extensions
    db.init_app(app)
    migrate.init_app(app, db)
    configure_logging(app)
    register_error_handlers(app)

    # Register health checks (/healthz, /ready)
    app.register_blueprint(health_bp)

    # Initialize flask-smorest Api
    api = Api(app)
    api.register_blueprint(products_blp)
    api.register_blueprint(orders_blp)

    return app

if __name__ == "__main__":
    app = create_app()
    with app.app_context():
        db.create_all()
    print("🚀 Running Code-First API at http://localhost:5000")
    print("📖 Swagger UI Documentation: http://localhost:5000/swagger-ui")
    print("📄 OpenAPI JSON Specification: http://localhost:5000/openapi.json")
    app.run(port=5000, debug=True)

