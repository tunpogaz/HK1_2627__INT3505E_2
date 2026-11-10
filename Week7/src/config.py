import os

class DefaultConfig:
    """Cấu hình mặc định theo chuẩn 12-factor (Slide 33)."""
    SECRET_KEY = os.environ.get("SECRET_KEY", "dev-not-for-prod")
    JSON_SORT_KEYS = False
    SQLALCHEMY_DATABASE_URI = os.environ.get("DB_URL", "sqlite:///dev.db")
    SQLALCHEMY_TRACK_MODIFICATIONS = False
    SQLALCHEMY_ENGINE_OPTIONS = {
        "pool_pre_ping": True,
        "pool_recycle": 1800
    }
    LOG_LEVEL = os.environ.get("LOG_LEVEL", "INFO")

class TestConfig(DefaultConfig):
    """Cấu hình phục vụ kiểm thử in-memory (Slide 33)."""
    TESTING = True
    SQLALCHEMY_DATABASE_URI = "sqlite:///:memory:"
    LOG_LEVEL = "WARNING"

class ProductionConfig(DefaultConfig):
    """Cấu hình môi trường Production (Slide 33)."""
    LOG_LEVEL = "WARNING"
    SQLALCHEMY_ENGINE_OPTIONS = {
        "pool_size": 10,
        "max_overflow": 20,
        "pool_recycle": 1800,
        "pool_pre_ping": True
    }

