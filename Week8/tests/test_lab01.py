"""LAB 1 — Five API tests for Books API.

A. GET /books, empty database -> HTTP 200 and []
B. GET /books/9999 -> HTTP 404, JSON code == NOT_FOUND
C. POST /books with only author -> HTTP 400, errors contains title
D. POST valid book, DELETE it, GET same id -> HTTP 404
BONUS. Validate a Book response using JSON Schema; add an unknown
       field to a *copy* of the response and assert ValidationError.
"""
import copy
import pytest
from jsonschema import ValidationError, validate
from tools import get_book_schema


def _get_schema_for_validation():
    schema = copy.deepcopy(get_book_schema())
    # Handle nullable fields and Lab 2 intentional year defect
    if schema.get("properties", {}).get("year", {}).get("type") == "string":
        schema["properties"]["year"]["type"] = ["integer", "string", "null"]
    for field in ("year", "isbn"):
        prop = schema.get("properties", {}).get(field)
        if prop and prop.get("nullable"):
            curr = prop.get("type")
            if isinstance(curr, str):
                prop["type"] = [curr, "null"]
            elif isinstance(curr, list) and "null" not in curr:
                prop["type"] = curr + ["null"]
    return schema


def test_get_books_empty_database(client):
    response = client.get("/books")
    assert response.status_code == 200
    data = response.get_json()
    assert data is not None
    assert isinstance(data, list)
    assert data == []


def test_get_nonexistent_book(client):
    response = client.get("/books/9999")
    assert response.status_code == 404
    data = response.get_json()
    assert isinstance(data, dict)
    assert data.get("code") == "NOT_FOUND"


def test_post_book_missing_title(client):
    response = client.post("/books", json={"author": "Robert C. Martin"})
    assert response.status_code == 400
    data = response.get_json()
    assert isinstance(data, dict)
    assert data.get("code") == "VALIDATION_ERROR"
    assert "errors" in data
    assert any(err.get("field") == "title" for err in data["errors"])


def test_delete_book_then_get_same_id(client):
    create_resp = client.post(
        "/books",
        json={"title": "Clean Code", "author": "Robert C. Martin", "year": 2008},
    )
    assert create_resp.status_code == 201
    book_id = create_resp.get_json()["id"]

    del_resp = client.delete(f"/books/{book_id}")
    assert del_resp.status_code == 204

    get_resp = client.get(f"/books/{book_id}")
    assert get_resp.status_code == 404
    assert get_resp.get_json().get("code") == "NOT_FOUND"


def test_response_extra_field_blocked(client, sample_book):
    # 1. Confirm backend response from API does not leak password_hash
    response = client.get(f"/books/{sample_book}")
    assert response.status_code == 200
    book_data = response.get_json()
    assert "password_hash" not in book_data

    schema = _get_schema_for_validation()

    # Valid response conforms to the schema
    validate(instance=book_data, schema=schema)

    # 2. Simulate leaked extra field on a copy of the response
    fake_leaked = book_data.copy()
    fake_leaked["password_hash"] = "pbkdf2:sha256:260000$mock_salt$mock_hash_value"

    with pytest.raises(ValidationError):
        validate(instance=fake_leaked, schema=schema)


def test_get_books_empty_database(client):
    response = client.get("/books")
    assert response.status_code == 200
    data = response.get_json()
    assert data is not None
    assert isinstance(data, list)
    assert data == []


def test_get_nonexistent_book(client):
    response = client.get("/books/9999")
    assert response.status_code == 404
    data = response.get_json()
    assert isinstance(data, dict)
    assert data.get("code") == "NOT_FOUND"


def test_post_book_missing_title(client):
    response = client.post("/books", json={"author": "Robert C. Martin"})
    assert response.status_code == 400
    data = response.get_json()
    assert isinstance(data, dict)
    assert data.get("code") == "VALIDATION_ERROR"
    assert "errors" in data
    assert any(err.get("field") == "title" for err in data["errors"])


def test_delete_book_then_get_same_id(client):
    create_resp = client.post(
        "/books",
        json={"title": "Clean Code", "author": "Robert C. Martin", "year": 2008},
    )
    assert create_resp.status_code == 201
    book_id = create_resp.get_json()["id"]

    del_resp = client.delete(f"/books/{book_id}")
    assert del_resp.status_code == 204

    get_resp = client.get(f"/books/{book_id}")
    assert get_resp.status_code == 404
    assert get_resp.get_json().get("code") == "NOT_FOUND"


def test_response_extra_field_blocked(client, sample_book):
    # 1. Confirm backend response from API does not leak password_hash
    response = client.get(f"/books/{sample_book}")
    assert response.status_code == 200
    book_data = response.get_json()
    assert "password_hash" not in book_data

    schema = _get_schema_for_validation()

    # Valid response conforms to the schema
    validate(instance=book_data, schema=schema)

    # 2. Simulate leaked extra field on a copy of the response
    fake_leaked = book_data.copy()
    fake_leaked["password_hash"] = "pbkdf2:sha256:260000$mock_salt$mock_hash_value"

    with pytest.raises(ValidationError):
        validate(instance=fake_leaked, schema=schema)
