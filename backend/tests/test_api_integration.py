"""
End-to-end integration test through the real HTTP API, using the mock PSI +
mock LLM providers - this is effectively what `python -m app.seed_demo` does
for one URL, exercised through pytest so it's covered by the test suite
(product spec section 22: "demo data seeding").
"""


def test_full_pipeline_via_api(client):
    # 1. Create a site
    resp = client.post("/api/sites", json={"name": "Deccan Herald", "base_url": "https://www.deccanherald.com/"})
    assert resp.status_code == 201
    site_id = resp.json()["site_id"]

    # 2. Add a URL
    resp = client.post(f"/api/sites/{site_id}/urls", json={
        "url": "https://www.deccanherald.com/", "url_category": "homepage", "enabled": True,
    })
    assert resp.status_code == 201
    url_id = resp.json()["url_id"]

    # 3. Run PSI enough times to satisfy the stabilization minimum
    for _ in range(5):
        resp = client.post(f"/api/urls/{url_id}/run")
        assert resp.status_code == 200
        assert resp.json()["run_status"] == "success"

    resp = client.get(f"/api/urls/{url_id}/runs")
    assert resp.status_code == 200
    assert len(resp.json()) == 5

    # 4. Stabilize
    resp = client.post(f"/api/urls/{url_id}/stabilize", json={})
    assert resp.status_code == 200
    stabilized = resp.json()
    assert stabilized["run_count"] == 5
    assert "lcp_ms" in stabilized["median_metrics"]

    resp = client.get(f"/api/urls/{url_id}/stabilized")
    assert resp.status_code == 200

    # 5. Analyze -> recommendations
    resp = client.post(f"/api/urls/{url_id}/analyze")
    assert resp.status_code == 200
    rec = resp.json()
    assert rec["validation_status"] in ("valid", "needs_review", "invalid")
    assert rec["priority_rank"] in ("P0", "P1", "P2", "P3")
    assert isinstance(rec["source_run_ids"], list) and len(rec["source_run_ids"]) == 5

    resp = client.get(f"/api/urls/{url_id}/recommendations")
    assert resp.status_code == 200
    assert len(resp.json()) == 1

    # 6. Trends
    resp = client.get(f"/api/urls/{url_id}/trends")
    assert resp.status_code == 200
    trends = resp.json()
    assert trends["url_id"] == url_id
    assert any(m["metric"] == "lcp_ms" for m in trends["metrics"])


def test_stabilize_before_enough_runs_returns_422(client):
    resp = client.post("/api/sites", json={"name": "Prajavani", "base_url": "https://www.prajavani.net/"})
    site_id = resp.json()["site_id"]
    resp = client.post(f"/api/sites/{site_id}/urls", json={"url": "https://www.prajavani.net/", "url_category": "homepage"})
    url_id = resp.json()["url_id"]

    client.post(f"/api/urls/{url_id}/run")  # only 1 run
    resp = client.post(f"/api/urls/{url_id}/stabilize", json={})
    assert resp.status_code == 422


def test_analyze_before_stabilize_returns_422(client):
    resp = client.post("/api/sites", json={"name": "Prajavani", "base_url": "https://www.prajavani.net/"})
    site_id = resp.json()["site_id"]
    resp = client.post(f"/api/sites/{site_id}/urls", json={"url": "https://www.prajavani.net/", "url_category": "homepage"})
    url_id = resp.json()["url_id"]

    resp = client.post(f"/api/urls/{url_id}/analyze")
    assert resp.status_code == 422


def test_get_nonexistent_url_returns_404(client):
    resp = client.get("/api/urls/99999/runs")
    assert resp.status_code == 404


def test_duplicate_site_name_returns_409(client):
    client.post("/api/sites", json={"name": "Deccan Herald", "base_url": "https://www.deccanherald.com/"})
    resp = client.post("/api/sites", json={"name": "Deccan Herald", "base_url": "https://www.deccanherald.com/"})
    assert resp.status_code == 409


def test_invalid_url_scheme_rejected_by_schema(client):
    resp = client.post("/api/sites", json={"name": "X", "base_url": "https://x.com/"})
    site_id = resp.json()["site_id"]
    resp = client.post(f"/api/sites/{site_id}/urls", json={"url": "ftp://not-http.com", "url_category": "homepage"})
    assert resp.status_code == 422


def test_get_single_url_by_id(client):
    resp = client.post("/api/sites", json={"name": "Deccan Herald", "base_url": "https://www.deccanherald.com/"})
    site_id = resp.json()["site_id"]
    resp = client.post(f"/api/sites/{site_id}/urls", json={"url": "https://www.deccanherald.com/", "url_category": "homepage"})
    url_id = resp.json()["url_id"]

    resp = client.get(f"/api/urls/{url_id}")
    assert resp.status_code == 200
    body = resp.json()
    assert body["url_id"] == url_id
    assert body["site_id"] == site_id
