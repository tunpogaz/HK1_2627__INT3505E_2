import pytest
from src.config import TestConfig
from src.extensions import db
from src.factory import create_app

@pytest.fixture
def app():
    """Fixture cung cấp Flask app cấu hình in-memory cho testing."""
    app = create_app(TestConfig)
    with app.app_context():
        db.create_all()
        yield app
        db.session.remove()
        db.drop_all()

@pytest.fixture
def client(app):
    """Fixture cung cấp TestClient của Flask."""
    return app.test_client()
