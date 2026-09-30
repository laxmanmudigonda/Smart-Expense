import sqlite3

from werkzeug.security import check_password_hash


def test_register_creates_hashed_account_and_logs_user_in(app, client, register):
    response = register()

    assert response.status_code == 200
    assert b"Hello, alice" in response.data
    with sqlite3.connect(app.config["DATABASE"]) as database:
        user = database.execute(
            "SELECT username, password_hash FROM users WHERE username = ?",
            ("alice",),
        ).fetchone()

    assert user[0] == "alice"
    assert user[1] != "Secure123"
    assert check_password_hash(user[1], "Secure123")


def test_duplicate_username_is_rejected_case_insensitively(client, register):
    register(username="Alice")
    client.post(
        "/logout",
        data={"csrf_token": _session_token(client)},
    )

    response = register(username="alice")

    assert b"already registered" in response.data


def test_registration_validates_password_and_confirmation(client, register):
    weak_response = register(password="short1", confirmation="short1")
    mismatch_response = register(password="Secure123", confirmation="Different123")

    assert b"at least 8 characters" in weak_response.data
    assert b"must match" in mismatch_response.data


def test_login_rejects_incorrect_password_and_accepts_correct_one(
    client, register, csrf_token
):
    register()
    client.post(
        "/logout",
        data={"csrf_token": _session_token(client)},
    )

    incorrect = client.post(
        "/login",
        data={
            "username": "alice",
            "password": "Wrong123",
            "csrf_token": csrf_token(client, "/login"),
        },
        follow_redirects=True,
    )
    correct = client.post(
        "/login",
        data={
            "username": "alice",
            "password": "Secure123",
            "csrf_token": csrf_token(client, "/login"),
        },
        follow_redirects=True,
    )

    assert b"Invalid username or password" in incorrect.data
    assert b"Hello, alice" in correct.data


def test_logout_clears_session(client, register):
    register()
    response = client.post(
        "/logout",
        data={"csrf_token": _session_token(client)},
        follow_redirects=True,
    )

    assert b"You have been logged out" in response.data
    assert client.get("/dashboard").status_code == 302


def test_dashboard_requires_login(client):
    response = client.get("/dashboard")

    assert response.status_code == 302
    assert response.headers["Location"].endswith("/login")


def test_post_without_csrf_token_is_rejected(client):
    response = client.post(
        "/register",
        data={
            "username": "alice",
            "password": "Secure123",
            "confirmation": "Secure123",
        },
    )

    assert response.status_code == 400
    assert b"could not be verified" in response.data


def _session_token(client):
    with client.session_transaction() as session:
        return session["csrf_token"]
