def test_invalid_navbar_alignment_is_rejected(client):
    response = client.put(
        "/api/v1/admin/site-presentation",
        json={"navbar_alignment": "diagonal"},
    )
    assert response.status_code in {401, 403, 422}
