from fastapi.testclient import TestClient


def test_cors_preflight_allows_vite_dev_origin_and_options_method() -> None:
    from app.main import app

    client = TestClient(app)
    response = client.options(
        "/admin/stats",
        headers={
            "Origin": "http://localhost:3000",
            "Access-Control-Request-Method": "GET",
        },
    )

    assert response.status_code == 200
    assert response.headers["access-control-allow-origin"] == "http://localhost:3000"
    assert "OPTIONS" in response.headers["access-control-allow-methods"]
