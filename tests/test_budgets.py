import sqlite3


def owned_category_id(app, username, category_name):
    with sqlite3.connect(app.config["DATABASE"]) as database:
        return database.execute(
            """
            SELECT c.id FROM categories c
            JOIN users u ON u.id = c.user_id
            WHERE u.username = ? AND c.name = ?
            """,
            (username, category_name),
        ).fetchone()[0]


def create_budget(client, csrf_token, category_id, month="2026-09", limit="100.00"):
    return client.post(
        "/budgets/add",
        data={
            "category_id": category_id,
            "month": month,
            "limit": limit,
            "csrf_token": csrf_token(client, f"/budgets?month={month}"),
        },
        follow_redirects=True,
    )


def test_create_budget_stores_integer_cents(app, client, register, csrf_token):
    register()
    category_id = owned_category_id(app, "alice", "Food & Dining")

    response = create_budget(client, csrf_token, category_id, limit="250.50")

    assert b"Budget created" in response.data
    with sqlite3.connect(app.config["DATABASE"]) as database:
        budget = database.execute(
            "SELECT month, limit_cents FROM budgets"
        ).fetchone()
    assert budget == ("2026-09", 25_050)


def test_duplicate_monthly_category_budget_is_rejected(
    app, client, register, csrf_token
):
    register()
    category_id = owned_category_id(app, "alice", "Food & Dining")
    create_budget(client, csrf_token, category_id)

    response = create_budget(client, csrf_token, category_id)

    assert b"already exists" in response.data
    with sqlite3.connect(app.config["DATABASE"]) as database:
        assert database.execute("SELECT COUNT(*) FROM budgets").fetchone()[0] == 1


def test_budget_requires_owned_expense_category(
    app, client, register, csrf_token
):
    register()
    income_category_id = owned_category_id(app, "alice", "Salary")

    response = create_budget(client, csrf_token, income_category_id)

    assert b"expense categories" in response.data


def test_budget_calculates_spending_remaining_and_overage(
    app, client, register, csrf_token
):
    register()
    category_id = owned_category_id(app, "alice", "Food & Dining")
    create_budget(client, csrf_token, category_id, limit="100.00")
    with sqlite3.connect(app.config["DATABASE"]) as database:
        user_id = database.execute("SELECT id FROM users WHERE username = 'alice'").fetchone()[0]
        database.executemany(
            """
            INSERT INTO transactions
                (user_id, category_id, type, amount_cents, description, transaction_date)
            VALUES (?, ?, 'expense', ?, '', ?)
            """,
            (
                (user_id, category_id, 12_500, "2026-09-20"),
                (user_id, category_id, 9_999, "2026-08-31"),
            ),
        )

    response = client.get("/budgets?month=2026-09")
    dashboard = client.get("/dashboard?month=2026-09")

    assert "₹125.00 of ₹100.00".encode() in response.data
    assert "Over by ₹25.00".encode() in response.data
    assert b"125.0% utilized" in response.data
    assert b"125.0% used" in dashboard.data


def test_edit_and_delete_budget(app, client, register, csrf_token):
    register()
    category_id = owned_category_id(app, "alice", "Travel")
    create_budget(client, csrf_token, category_id)
    with sqlite3.connect(app.config["DATABASE"]) as database:
        budget_id = database.execute("SELECT id FROM budgets").fetchone()[0]

    edit_response = client.post(
        f"/budgets/{budget_id}/edit",
        data={
            "limit": "175.25",
            "csrf_token": csrf_token(client, "/budgets?month=2026-09"),
        },
        follow_redirects=True,
    )
    delete_response = client.post(
        f"/budgets/{budget_id}/delete",
        data={
            "csrf_token": csrf_token(client, "/budgets?month=2026-09")
        },
        follow_redirects=True,
    )

    assert b"Budget updated" in edit_response.data
    assert "₹175.25".encode() in edit_response.data
    assert b"Budget deleted" in delete_response.data


def test_user_cannot_modify_another_users_budget(
    app, client, register, csrf_token
):
    register(username="alice")
    category_id = owned_category_id(app, "alice", "Food & Dining")
    create_budget(client, csrf_token, category_id)
    with sqlite3.connect(app.config["DATABASE"]) as database:
        budget_id = database.execute("SELECT id FROM budgets").fetchone()[0]
    client.post(
        "/logout",
        data={"csrf_token": csrf_token(client, "/dashboard")},
    )
    register(username="bob")

    edit_response = client.post(
        f"/budgets/{budget_id}/edit",
        data={
            "limit": "1.00",
            "csrf_token": csrf_token(client, "/budgets"),
        },
    )
    delete_response = client.post(
        f"/budgets/{budget_id}/delete",
        data={"csrf_token": csrf_token(client, "/budgets")},
    )

    assert edit_response.status_code == 404
    assert delete_response.status_code == 404
