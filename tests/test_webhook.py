import pytest
from fastapi.testclient import TestClient
from app.main import app
from app.database import init_db
from app.config import settings

# Initialize test database tables
init_db()

# Disable webhook secret check during unit tests
settings.github_webhook_secret = None

client = TestClient(app)

def test_health_endpoint():
    response = client.get("/health")
    assert response.status_code == 200
    assert response.json()["status"] == "healthy"

def test_simulate_pr_review_endpoint():
    payload = {
        "repo_full_name": "owner/testrepo",
        "pr_number": 42,
        "pr_title": "Test PR",
        "author": "dev",
        "filename": "auth.py",
        "diff_content": 'API_KEY = "sk_live_1234567890123456"\ndef login(user):\n    eval(user)'
    }
    response = client.post("/api/simulate", json=payload)
    assert response.status_code == 200
    data = response.json()
    assert data["severity_score"] > 0
    assert data["total_findings"] >= 2

def test_webhook_ignores_non_pr_event():
    response = client.post(
        "/webhook",
        headers={"X-GitHub-Event": "push"},
        json={"ref": "refs/heads/main"}
    )
    assert response.status_code == 200
    assert response.json()["status"] == "ignored"

def test_stats_endpoint():
    response = client.get("/api/stats")
    assert response.status_code == 200
    assert "total_prs_reviewed" in response.json()
