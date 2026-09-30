import sqlite3


def user_and_category_ids(app):
    with sqlite3.connect(app.config["DATABASE"]) as database:
        user_id = database.execute("SELECT id FROM users").fetchone()[0]
        categories = dict(
            database.execute(
                "SELECT name, id FROM categories WHERE user_id = ?",
                (user_id,),
            ).fetchall()
        )
    return user_id, categories


def insert_transaction(
    app,
    user_id,
    category_id,
    transaction_type,
    amount_cents,
    transaction_date,
    description,
):
    with sqlite3.connect(app.config["DATABASE"]) as database:
        database.execute(
            """
            INSERT INTO transactions
                (user_id, category_id, type, amount_cents, description, transaction_date)
            VALUES (?, ?, ?, ?, ?, ?)
            """,
            (
                user_id,
                category_id,
                transaction_type,
                amount_cents,
                description,
                transaction_date,
            ),
        )


def test_empty_dashboard_displays_zero_values(client, register):
    register()

    response = client.get("/dashboard?month=2026-09")

    assert response.status_code == 200
    assert response.data.count("₹0.00".encode()) == 4
    assert b"No transactions yet" in response.data


def test_dashboard_calculates_balance_monthly_totals_and_savings(
    app, client, register
):
    register()
    user_id, categories = user_and_category_ids(app)
    insert_transaction(
        app, user_id, categories["Salary"], "income", 3_000_000, "2026-09-01", "Salary"
    )
    insert_transaction(
        app, user_id, categories["Food & Dining"], "expense", 100_000, "2026-09-29", "Cafe"
    )
    insert_transaction(
        app, user_id, categories["Travel"], "expense", 50_000, "2026-08-31", "Trip"
    )

    response = client.get("/dashboard?month=2026-09")

    assert "₹28,500.00".encode() in response.data
    assert "₹30,000.00".encode() in response.data
    assert "₹1,000.00".encode() in response.data
    assert "₹29,000.00".encode() in response.data
    assert b"September 2026" in response.data


def test_dashboard_category_distribution_uses_selected_month(
    app, client, register
):
    register()
    user_id, categories = user_and_category_ids(app)
    insert_transaction(
        app, user_id, categories["Food & Dining"], "expense", 1_000, "2026-09-10", "Lunch"
    )
    insert_transaction(
        app, user_id, categories["Travel"], "expense", 3_000, "2026-09-11", "Bus"
    )

    response = client.get("/dashboard?month=2026-09")

    assert b"25.0% of monthly expenses" in response.data
    assert b"75.0% of monthly expenses" in response.data


def test_invalid_month_falls_back_without_error(client, register):
    register()

    response = client.get("/dashboard?month=not-a-month")

    assert response.status_code == 200
    assert b"Your financial overview" in response.data


def test_dashboard_refreshes_after_add_edit_and_delete(
    app, client, register, csrf_token
):
    register()
    _, categories = user_and_category_ids(app)
    add_response = client.post(
        "/transactions/add",
        data={
            "type": "expense",
            "category_id": categories["Food & Dining"],
            "amount": "10.00",
            "description": "Lunch",
            "transaction_date": "2026-09-15",
            "csrf_token": csrf_token(client, "/transactions/add"),
        },
    )
    assert add_response.status_code == 302
    with sqlite3.connect(app.config["DATABASE"]) as database:
        transaction_id = database.execute("SELECT id FROM transactions").fetchone()[0]
    assert "₹10.00".encode() in client.get("/dashboard?month=2026-09").data

    client.post(
        f"/transactions/{transaction_id}/edit",
        data={
            "type": "expense",
            "category_id": categories["Food & Dining"],
            "amount": "20.00",
            "description": "Lunch",
            "transaction_date": "2026-09-15",
            "csrf_token": csrf_token(
                client, f"/transactions/{transaction_id}/edit"
            ),
        },
    )
    assert "₹20.00".encode() in client.get("/dashboard?month=2026-09").data

    client.post(
        f"/transactions/{transaction_id}/delete",
        data={"csrf_token": csrf_token(client, "/transactions")},
    )
    dashboard = client.get("/dashboard?month=2026-09")
    assert dashboard.data.count("₹0.00".encode()) == 4
