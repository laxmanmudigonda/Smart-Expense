import sqlite3

def test_landing_page_loads(app):
    response = app.test_client().get("/")

    assert response.status_code == 200
    assert b"Know where your money goes" in response.data
    assert b"/static/logo.svg" in response.data


def test_unknown_page_uses_custom_error_page(app):
    response = app.test_client().get("/does-not-exist")

    assert response.status_code == 404
    assert b"Page not found" in response.data


def test_schema_creates_core_tables(app):
    with sqlite3.connect(app.config["DATABASE"]) as database:
        table_names = {
            row[0]
            for row in database.execute(
                "SELECT name FROM sqlite_master WHERE type = 'table'"
            )
        }

    assert {"users", "categories", "transactions", "budgets"} <= table_names


def test_foreign_keys_are_enabled_by_application_connection(app):
    with app.app_context():
        from app import get_db

        enabled = get_db().execute("PRAGMA foreign_keys").fetchone()[0]

    assert enabled == 1
