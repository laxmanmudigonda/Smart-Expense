import sqlite3


def category_id(app, category_name):
    with sqlite3.connect(app.config["DATABASE"]) as database:
        return database.execute(
            "SELECT id FROM categories WHERE name = ?",
            (category_name,),
        ).fetchone()[0]


def add_transaction(
    client,
    csrf_token,
    category,
    transaction_type="expense",
    amount="12.34",
    description="Lunch",
    transaction_date="2026-09-29",
):
    return client.post(
        "/transactions/add",
        data={
            "type": transaction_type,
            "category_id": category,
            "amount": amount,
            "description": description,
            "transaction_date": transaction_date,
            "csrf_token": csrf_token(client, "/transactions/add"),
        },
        follow_redirects=True,
    )


def test_registration_creates_default_categories(app, register):
    register()

    with sqlite3.connect(app.config["DATABASE"]) as database:
        count = database.execute(
            "SELECT COUNT(*) FROM categories WHERE is_default = 1"
        ).fetchone()[0]

    assert count == 17


def test_add_transaction_stores_integer_cents(app, client, register, csrf_token):
    register()
    food_id = category_id(app, "Food & Dining")

    response = add_transaction(client, csrf_token, food_id)

    assert b"Transaction added" in response.data
    with sqlite3.connect(app.config["DATABASE"]) as database:
        transaction = database.execute(
            "SELECT type, amount_cents, description FROM transactions"
        ).fetchone()
    assert transaction == ("expense", 1234, "Lunch")


def test_invalid_amount_and_category_type_are_rejected(
    app, client, register, csrf_token
):
    register()
    salary_id = category_id(app, "Salary")

    amount_response = add_transaction(
        client, csrf_token, salary_id, transaction_type="income", amount="1.999"
    )
    mismatch_response = add_transaction(
        client, csrf_token, salary_id, transaction_type="expense"
    )

    assert b"up to two decimals" in amount_response.data
    assert b"matches the transaction type" in mismatch_response.data


def test_edit_and_delete_transaction(app, client, register, csrf_token):
    register()
    food_id = category_id(app, "Food & Dining")
    groceries_id = category_id(app, "Groceries")
    add_transaction(client, csrf_token, food_id)
    with sqlite3.connect(app.config["DATABASE"]) as database:
        transaction_id = database.execute("SELECT id FROM transactions").fetchone()[0]

    edit_response = client.post(
        f"/transactions/{transaction_id}/edit",
        data={
            "type": "expense",
            "category_id": groceries_id,
            "amount": "25.50",
            "description": "Weekly groceries",
            "transaction_date": "2026-09-28",
            "csrf_token": csrf_token(client, f"/transactions/{transaction_id}/edit"),
        },
        follow_redirects=True,
    )
    delete_response = client.post(
        f"/transactions/{transaction_id}/delete",
        data={"csrf_token": csrf_token(client, "/transactions")},
        follow_redirects=True,
    )

    assert b"Transaction updated" in edit_response.data
    assert b"25.50" in edit_response.data
    assert b"Transaction deleted" in delete_response.data
    with sqlite3.connect(app.config["DATABASE"]) as database:
        assert database.execute("SELECT COUNT(*) FROM transactions").fetchone()[0] == 0


def test_search_and_type_filter(app, client, register, csrf_token):
    register()
    food_id = category_id(app, "Food & Dining")
    salary_id = category_id(app, "Salary")
    add_transaction(client, csrf_token, food_id, description="Cafe lunch")
    add_transaction(
        client,
        csrf_token,
        salary_id,
        transaction_type="income",
        amount="1000.00",
        description="September salary",
    )

    response = client.get("/transactions?search=salary&type=income")

    assert b"September salary" in response.data
    assert b"Cafe lunch" not in response.data


def test_user_cannot_access_another_users_transaction(
    app, client, register, csrf_token
):
    register(username="alice")
    food_id = category_id(app, "Food & Dining")
    add_transaction(client, csrf_token, food_id)
    with sqlite3.connect(app.config["DATABASE"]) as database:
        transaction_id = database.execute("SELECT id FROM transactions").fetchone()[0]

    client.post(
        "/logout",
        data={"csrf_token": csrf_token(client, "/dashboard")},
    )
    register(username="bob")

    assert client.get(f"/transactions/{transaction_id}/edit").status_code == 404
    response = client.post(
        f"/transactions/{transaction_id}/delete",
        data={"csrf_token": csrf_token(client, "/transactions")},
    )
    assert response.status_code == 404
