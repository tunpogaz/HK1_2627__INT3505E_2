import pytest
from shared.config import TestConfig
from shared.extensions import db
from code_first.app import create_app as create_code_first_app
from design_first.app import create_app as create_design_first_app

@pytest.fixture
def code_first_app():
    app = create_code_first_app(TestConfig)
    with app.app_context():
        db.create_all()
        yield app
        db.session.remove()
        db.drop_all()

@pytest.fixture
def code_first_client(code_first_app):
    return code_first_app.test_client()

@pytest.fixture
def design_first_app():
    connexion_app = create_design_first_app(TestConfig)
    flask_app = connexion_app.app
    with flask_app.app_context():
        db.create_all()
        yield connexion_app
        db.session.remove()
        db.drop_all()

@pytest.fixture
def design_first_client(design_first_app):
    return design_first_app.test_client()

