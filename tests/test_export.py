import csv
import io
import sqlite3


def test_csv_export_applies_filters_and_blocks_formula_injection(
    app, client, register
):
    register()
    with sqlite3.connect(app.config["DATABASE"]) as database:
        user_id = database.execute("SELECT id FROM users").fetchone()[0]
        database.execute(
            "INSERT INTO categories (user_id, name, type) VALUES (?, ?, 'expense')",
            (user_id, "+Injected Category"),
        )
        category_id = database.execute(
            "SELECT id FROM categories WHERE name = '+Injected Category'"
        ).fetchone()[0]
        database.execute(
            """
            INSERT INTO transactions
                (user_id, category_id, type, amount_cents, description, transaction_date)
            VALUES (?, ?, 'expense', 1234, '=HYPERLINK(""bad"")', '2026-09-12')
            """,
            (user_id, category_id),
        )
        salary_id = database.execute(
            "SELECT id FROM categories WHERE user_id = ? AND name = 'Salary'",
            (user_id,),
        ).fetchone()[0]
        database.execute(
            """
            INSERT INTO transactions
                (user_id, category_id, type, amount_cents, description, transaction_date)
            VALUES (?, ?, 'income', 50000, 'Salary', '2026-09-01')
            """,
            (user_id, salary_id),
        )

    response = client.get("/transactions/export?type=expense")
    rows = list(csv.reader(io.StringIO(response.get_data(as_text=True))))

    assert response.status_code == 200
    assert response.mimetype == "text/csv"
    assert "attachment" in response.headers["Content-Disposition"]
    assert rows[0] == ["Date", "Type", "Category", "Description", "Amount"]
    assert rows[1][2] == "'+Injected Category"
    assert rows[1][3].startswith("'=")
    assert rows[1][4] == "12.34"
    assert len(rows) == 2


def test_csv_export_requires_login(client):
    assert client.get("/transactions/export").status_code == 302
