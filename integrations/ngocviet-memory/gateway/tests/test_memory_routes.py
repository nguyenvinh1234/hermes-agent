from .conftest import HERMES_HEADERS, OPENCLAW_HEADERS


def test_add_search_get_update_delete_roundtrip(client):
    add_resp = client.post(
        "/v1/memory/add",
        json={
            "user_id": "ngocviet-owner",
            "content": "Hermes is the orchestration hub.",
            "memory_class": "shared",
            "project_id": "global",
            "domain": "architecture",
        },
        headers=HERMES_HEADERS,
    )
    assert add_resp.status_code == 201
    memory_id = add_resp.json()["id"]
    assert memory_id

    search_resp = client.post(
        "/v1/memory/search",
        json={"user_id": "ngocviet-owner", "query": "orchestration hub", "memory_class": ["shared"]},
        headers=HERMES_HEADERS,
    )
    assert search_resp.status_code == 200
    assert any(r["id"] == memory_id for r in search_resp.json()["results"])

    get_resp = client.get(f"/v1/memory/{memory_id}", headers=HERMES_HEADERS)
    assert get_resp.status_code == 200

    patch_resp = client.patch(
        f"/v1/memory/{memory_id}", json={"status": "superseded"}, headers=HERMES_HEADERS
    )
    assert patch_resp.status_code == 200

    delete_resp = client.delete(f"/v1/memory/{memory_id}", headers=HERMES_HEADERS)
    assert delete_resp.status_code == 200

    confirm_resp = client.get(f"/v1/memory/{memory_id}", headers=HERMES_HEADERS)
    assert confirm_resp.status_code == 404


def test_agent_private_isolated_between_hermes_and_openclaw(client):
    add_resp = client.post(
        "/v1/memory/add",
        json={
            "user_id": "ngocviet-owner",
            "content": "Hermes internal scratch note.",
            "memory_class": "agent_private",
        },
        headers=HERMES_HEADERS,
    )
    assert add_resp.status_code == 201

    search_as_hermes = client.post(
        "/v1/memory/search",
        json={"user_id": "ngocviet-owner", "query": "scratch note", "memory_class": ["agent_private"]},
        headers=HERMES_HEADERS,
    )
    assert len(search_as_hermes.json()["results"]) == 1

    search_as_openclaw = client.post(
        "/v1/memory/search",
        json={"user_id": "ngocviet-owner", "query": "scratch note", "memory_class": ["agent_private"]},
        headers=OPENCLAW_HEADERS,
    )
    assert len(search_as_openclaw.json()["results"]) == 0


def test_shared_readable_by_both_clients(client):
    client.post(
        "/v1/memory/add",
        json={
            "user_id": "ngocviet-owner",
            "content": "Company-wide SOP: always confirm before deploy.",
            "memory_class": "shared",
        },
        headers=HERMES_HEADERS,
    )
    search_as_openclaw = client.post(
        "/v1/memory/search",
        json={"user_id": "ngocviet-owner", "query": "SOP always confirm", "memory_class": ["shared"]},
        headers=OPENCLAW_HEADERS,
    )
    assert len(search_as_openclaw.json()["results"]) == 1


def test_project_isolation_between_projects(client):
    client.post(
        "/v1/memory/add",
        json={
            "user_id": "ngocviet-owner",
            "content": "Obsidian vault structure decision.",
            "memory_class": "project",
            "project_id": "obsidian",
        },
        headers=HERMES_HEADERS,
    )
    same_project = client.post(
        "/v1/memory/search",
        json={
            "user_id": "ngocviet-owner",
            "query": "vault structure",
            "memory_class": ["project"],
            "project_id": "obsidian",
        },
        headers=HERMES_HEADERS,
    )
    assert len(same_project.json()["results"]) == 1

    other_project = client.post(
        "/v1/memory/search",
        json={
            "user_id": "ngocviet-owner",
            "query": "vault structure",
            "memory_class": ["project"],
            "project_id": "mach3-turret",
        },
        headers=HERMES_HEADERS,
    )
    assert len(other_project.json()["results"]) == 0


def test_secret_content_rejected_on_add(client):
    resp = client.post(
        "/v1/memory/add",
        json={
            "user_id": "ngocviet-owner",
            "content": "Our deploy key is sk-abcdefghijklmnopqrstuvwx, keep it safe.",
            "memory_class": "shared",
        },
        headers=HERMES_HEADERS,
    )
    assert resp.status_code == 400


def test_cannot_delete_memory_owned_by_other_agent(client):
    add_resp = client.post(
        "/v1/memory/add",
        json={"user_id": "ngocviet-owner", "content": "OpenClaw private note.", "memory_class": "agent_private"},
        headers=OPENCLAW_HEADERS,
    )
    memory_id = add_resp.json()["id"]

    delete_as_hermes = client.delete(f"/v1/memory/{memory_id}", headers=HERMES_HEADERS)
    assert delete_as_hermes.status_code == 403


def test_ready_endpoint_reports_components(client):
    resp = client.get("/ready")
    assert resp.status_code == 200
    body = resp.json()
    assert body["ready"] is True
    assert body["components"] == {"gateway": True, "mem0": True, "postgres": True}
