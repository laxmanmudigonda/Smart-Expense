import sqlite3


def test_custom_category_can_be_created_renamed_and_deleted(
    app, client, register, csrf_token
):
    register()
    create_response = client.post(
        "/categories/add",
        data={
            "name": "Pet Care",
            "type": "expense",
            "csrf_token": csrf_token(client, "/categories"),
        },
        follow_redirects=True,
    )
    with sqlite3.connect(app.config["DATABASE"]) as database:
        category_id = database.execute(
            "SELECT id FROM categories WHERE name = 'Pet Care'"
        ).fetchone()[0]

    edit_response = client.post(
        f"/categories/{category_id}/edit",
        data={
            "name": "Pets",
            "csrf_token": csrf_token(client, "/categories"),
        },
        follow_redirects=True,
    )
    delete_response = client.post(
        f"/categories/{category_id}/delete",
        data={"csrf_token": csrf_token(client, "/categories")},
        follow_redirects=True,
    )

    assert b"Custom category created" in create_response.data
    assert b"Category updated" in edit_response.data
    assert b"Category deleted" in delete_response.data


def test_default_category_cannot_be_edited_or_deleted(
    app, client, register, csrf_token
):
    register()
    with sqlite3.connect(app.config["DATABASE"]) as database:
        category_id = database.execute(
            "SELECT id FROM categories WHERE name = 'Salary'"
        ).fetchone()[0]

    edit_response = client.post(
        f"/categories/{category_id}/edit",
        data={
            "name": "Changed",
            "csrf_token": csrf_token(client, "/categories"),
        },
        follow_redirects=True,
    )
    delete_response = client.post(
        f"/categories/{category_id}/delete",
        data={"csrf_token": csrf_token(client, "/categories")},
        follow_redirects=True,
    )

    assert b"Default categories cannot be edited" in edit_response.data
    assert b"Default categories cannot be deleted" in delete_response.data
