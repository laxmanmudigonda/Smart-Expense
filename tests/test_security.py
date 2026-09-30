import pytest

from app import create_app


@pytest.mark.parametrize(
    "path",
    (
        "/dashboard",
        "/transactions",
        "/transactions/add",
        "/transactions/export",
        "/categories",
        "/budgets",
        "/analytics",
        "/api/analytics",
    ),
)
def test_private_get_routes_require_login(client, path):
    response = client.get(path)
    assert response.status_code == 302
    assert response.headers["Location"].endswith("/login")


def test_security_headers_are_present(client):
    response = client.get("/")

    assert response.headers["X-Content-Type-Options"] == "nosniff"
    assert response.headers["X-Frame-Options"] == "DENY"
    assert response.headers["Referrer-Policy"] == "same-origin"
    assert "frame-ancestors 'none'" in response.headers["Content-Security-Policy"]


def test_authenticated_pages_disable_browser_caching(client, register):
    register()

    response = client.get("/dashboard")

    assert response.headers["Cache-Control"] == "no-store"


def test_search_text_is_treated_as_data(client, register):
    register()

    response = client.get("/transactions?search=%25%27+OR+1%3D1+--")

    assert response.status_code == 200
    assert b"No transactions found" in response.data


def test_production_requires_explicit_secret(monkeypatch):
    monkeypatch.setenv("APP_ENV", "production")
    monkeypatch.delenv("SECRET_KEY", raising=False)

    with pytest.raises(RuntimeError, match="SECRET_KEY"):
        create_app()
