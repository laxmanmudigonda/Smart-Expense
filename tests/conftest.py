import pytest

from app import create_app, init_db


@pytest.fixture()
def app(tmp_path):
    application = create_app(
        {
            "TESTING": True,
            "DATABASE": str(tmp_path / "test.db"),
            "SECRET_KEY": "test-only-secret",
        }
    )
    with application.app_context():
        init_db()
    return application


@pytest.fixture()
def client(app):
    return app.test_client()


def get_csrf_token(client, path):
    client.get(path)
    with client.session_transaction() as session:
        return session["csrf_token"]


@pytest.fixture()
def csrf_token():
    return get_csrf_token


@pytest.fixture()
def register(client, csrf_token):
    def register_user(
        username="alice",
        password="Secure123",
        confirmation="Secure123",
    ):
        return client.post(
            "/register",
            data={
                "username": username,
                "password": password,
                "confirmation": confirmation,
                "csrf_token": csrf_token(client, "/register"),
            },
            follow_redirects=True,
        )

    return register_user
