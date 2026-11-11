"""Shared fixtures for all exercises; each test receives a fresh SQLite database."""
import pytest
from app import create_app
from models import Book, db


@pytest.fixture()
def app(tmp_path):
    application = create_app({
        "TESTING": True,
        "SQLALCHEMY_DATABASE_URI": f"sqlite:///{tmp_path / 'test.db'}",
    })
    yield application
    with application.app_context():
        db.session.remove()
        db.drop_all()


@pytest.fixture()
def client(app):
    return app.test_client()


@pytest.fixture()
def sample_book(app):
    with app.app_context():
        book = Book(title="API Design Patterns", author="J.J. Geewax", year=2021)
        db.session.add(book)
        db.session.commit()
        return book.id


@pytest.fixture()
def book_with_extra_field(client, sample_book):
    """Simulate a backend response containing an unexpected/leaked field (password_hash)."""
    response = client.get(f"/books/{sample_book}")
    payload = response.get_json().copy()
    payload["password_hash"] = "pbkdf2:sha256:260000$mock_salt$mock_hash_value"
    return payload

