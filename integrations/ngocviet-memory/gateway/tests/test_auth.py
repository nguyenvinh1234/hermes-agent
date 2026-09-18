from .conftest import HERMES_HEADERS


def test_missing_api_key_rejected(client):
    resp = client.post("/v1/memory/search", json={"user_id": "u", "query": "hi"})
    assert resp.status_code == 401


def test_invalid_api_key_rejected(client):
    resp = client.post(
        "/v1/memory/search",
        json={"user_id": "u", "query": "hi"},
        headers={"X-NgocViet-API-Key": "not-a-real-key"},
    )
    assert resp.status_code == 401


def test_valid_key_accepted(client):
    resp = client.post(
        "/v1/memory/search", json={"user_id": "u", "query": "hi"}, headers=HERMES_HEADERS
    )
    assert resp.status_code == 200


def test_health_does_not_require_auth(client):
    assert client.get("/health").status_code == 200


def test_client_cannot_spoof_agent_id(client):
    resp = client.post(
        "/v1/memory/add",
        json={"user_id": "u", "content": "fact", "agent_id": "openclaw"},
        headers=HERMES_HEADERS,
    )
    assert resp.status_code == 422
