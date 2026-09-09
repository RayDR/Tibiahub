from app.core.security import create_access_token


def auth(user):
    return {"Authorization": f"Bearer {create_access_token(user.username)}"}


def test_site_presentation_defaults_are_public(client):
    response = client.get("/api/v1/site-presentation")
    assert response.status_code == 200
    assert response.json() == {
        "navbar_show_icons": True,
        "navbar_alignment": "center",
        "navbar_show_global_search": True,
    }


def test_admin_can_update_public_site_presentation(client, db):
    from tests.conftest import make_user

    admin = make_user(db, username="presentation-admin", is_superuser=True)
    response = client.put(
        "/api/v1/admin/site-presentation",
        headers=auth(admin),
        json={
            "navbar_show_icons": False,
            "navbar_alignment": "right",
            "navbar_show_global_search": False,
        },
    )
    assert response.status_code == 200
    assert response.json()["navbar_alignment"] == "right"

    public = client.get("/api/v1/site-presentation")
    assert public.status_code == 200
    assert public.json() == response.json()


def test_non_admin_cannot_update_site_presentation(client, db):
    from tests.conftest import make_user

    user = make_user(db, username="presentation-user", is_superuser=False)
    response = client.put(
        "/api/v1/admin/site-presentation",
        headers=auth(user),
        json={"navbar_alignment": "left"},
    )
    assert response.status_code in {401, 403}
