import sqlite3


def ids(app):
    with sqlite3.connect(app.config["DATABASE"]) as database:
        user_id = database.execute("SELECT id FROM users").fetchone()[0]
        categories = dict(
            database.execute(
                "SELECT name, id FROM categories WHERE user_id = ?", (user_id,)
            ).fetchall()
        )
    return user_id, categories


def test_analytics_endpoint_returns_complete_empty_shape(client, register):
    register()

    page = client.get("/analytics?month=2026-09")
    response = client.get("/api/analytics?month=2026-09")
    data = response.get_json()

    assert page.status_code == 200
    assert b"Income versus expenses" in page.data
    assert response.status_code == 200
    assert len(data["monthly"]["labels"]) == 12
    assert data["monthly"]["income_cents"] == [0] * 12
    assert data["monthly"]["expense_cents"] == [0] * 12
    assert data["categories"]["labels"] == []
    assert data["budgets"]["labels"] == []


def test_analytics_uses_database_transactions_and_budgets(
    app, client, register
):
    register()
    user_id, categories = ids(app)
    with sqlite3.connect(app.config["DATABASE"]) as database:
        database.executemany(
            """
            INSERT INTO transactions
                (user_id, category_id, type, amount_cents, description, transaction_date)
            VALUES (?, ?, ?, ?, '', ?)
            """,
            (
                (user_id, categories["Salary"], "income", 200_000, "2026-09-01"),
                (user_id, categories["Food & Dining"], "expense", 25_000, "2026-09-02"),
                (user_id, categories["Travel"], "expense", 10_000, "2026-08-02"),
            ),
        )
        database.execute(
            """
            INSERT INTO budgets (user_id, category_id, month, limit_cents)
            VALUES (?, ?, '2026-09', 30000)
            """,
            (user_id, categories["Food & Dining"]),
        )

    data = client.get("/api/analytics?month=2026-09").get_json()

    assert data["monthly"]["income_cents"][-1] == 200_000
    assert data["monthly"]["expense_cents"][-1] == 25_000
    assert data["monthly"]["expense_cents"][-2] == 10_000
    assert data["categories"] == {
        "labels": ["Food & Dining"],
        "expense_cents": [25_000],
    }
    assert data["budgets"]["limit_cents"] == [30_000]
    assert data["budgets"]["spent_cents"] == [25_000]


def test_analytics_page_and_api_require_login(client):
    assert client.get("/analytics").status_code == 302
    assert client.get("/api/analytics").status_code == 302
