import httpx


def test_seeds_ten_default_cases(client):
    response = client.get("/api/eval-cases")

    assert response.status_code == 200
    cases = response.json()
    assert len(cases) == 10
    assert cases[0]["name"] == "Customer renewal"


def test_case_crud(client):
    payload = {
        "name": "Test case",
        "description": "Editable",
        "prompt": "From Alex: can Dana meet for 30 minutes tomorrow?",
        "expected": {
            "title": "Test",
            "requester": "Alex",
            "duration_minutes": 30,
            "priority": "normal",
            "meeting_type": "internal",
            "attendees": ["Dana"],
            "preferred_windows": [],
            "constraints": [],
            "missing_fields": [],
            "sensitivity": "low",
            "async_candidate": False,
            "escalation_required": False,
        },
        "active": True,
    }

    created = client.post("/api/eval-cases", json=payload)
    assert created.status_code == 200
    case_id = created.json()["id"]

    payload["name"] = "Updated case"
    updated = client.put(f"/api/eval-cases/{case_id}", json=payload)
    assert updated.status_code == 200
    assert updated.json()["name"] == "Updated case"

    deleted = client.delete(f"/api/eval-cases/{case_id}")
    assert deleted.status_code == 200
    assert client.put(f"/api/eval-cases/{case_id}", json=payload).status_code == 404


def test_eval_runner_calls_ai_backend_and_scores_valid_output(client, monkeypatch):
    calls = []

    def fake_post(url, json, timeout):
        calls.append({"url": url, "json": json, "timeout": timeout})
        return httpx.Response(
            200,
            json={
                "id": "airesp_test",
                "provider": "ollama",
                "model": "gemma4:31b-cloud",
                "content": (
                    '{"title":"Renewal Risk Discussion","requester":"Jordan","duration_minutes":30,'
                    '"priority":"high","meeting_type":"customer","attendees":["Dana","Priya"],'
                    '"preferred_windows":[{"start":"2026-05-19T13:00:00","end":"2026-05-19T17:00:00"}],'
                    '"constraints":[],"missing_fields":[],"sensitivity":"medium",'
                    '"async_candidate":false,"escalation_required":false}'
                ),
                "latency_ms": 123,
            },
        )

    monkeypatch.setattr(httpx, "post", fake_post)

    response = client.post("/api/eval-runs")

    assert response.status_code == 200
    body = response.json()
    assert calls
    assert all(call["url"] == "http://ai-backend.test/v1/chat" for call in calls)
    assert body["total_cases"] == 10
    assert body["results"][0]["provider"] == "ollama"
    assert body["results"][0]["passed"] is True


def test_malformed_ai_json_is_invalid_output_not_crash(client, monkeypatch):
    def fake_post(url, json, timeout):
        return httpx.Response(200, json={"content": "not json", "provider": "ollama", "model": "gemma4:31b-cloud", "latency_ms": 50})

    monkeypatch.setattr(httpx, "post", fake_post)

    response = client.post("/api/eval-runs")

    assert response.status_code == 200
    result = response.json()["results"][0]
    assert result["status"] == "invalid_output"
    assert result["passed"] is False


def test_field_diff_identifies_mismatches(client, monkeypatch):
    def fake_post(url, json, timeout):
        return httpx.Response(
            200,
            json={
                "content": (
                    '{"title":"Wrong","requester":"Wrong","duration_minutes":60,'
                    '"priority":"low","meeting_type":"internal","attendees":["From Jordan"],'
                    '"preferred_windows":[],"constraints":[],"missing_fields":[],"sensitivity":"low",'
                    '"async_candidate":false,"escalation_required":false}'
                ),
                "provider": "ollama",
                "model": "gemma4:31b-cloud",
                "latency_ms": 50,
            },
        )

    monkeypatch.setattr(httpx, "post", fake_post)

    response = client.post("/api/eval-runs")

    assert response.status_code == 200
    result = response.json()["results"][0]
    failed_fields = {diff["field"] for diff in result["diffs"] if not diff["passed"]}
    assert {"requester", "duration_minutes", "priority", "attendees"}.issubset(failed_fields)


def test_health_does_not_require_provider_keys(client):
    response = client.get("/health")

    assert response.status_code == 200
    assert response.json()["service"] == "eval-backend"
