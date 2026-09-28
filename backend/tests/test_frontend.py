from fastapi.testclient import TestClient

from backend.app.main import app


def test_required_frontend_pages_and_shared_assets_are_served():
    pages = [
        "/",
        "/login.html",
        "/register.html",
        "/dashboard.html",
        "/resume.html",
        "/jobs.html",
        "/job-details.html",
        "/advisor.html",
    ]
    with TestClient(app) as client:
        for path in pages:
            response = client.get(path)
            assert response.status_code == 200, path
            assert "text/html" in response.headers["content-type"]
        script = client.get("/assets/js/app.js")
        style = client.get("/assets/css/styles.css")

    assert script.status_code == 200
    assert "apiRequest" in script.text
    assert style.status_code == 200
    assert "--ink" in style.text