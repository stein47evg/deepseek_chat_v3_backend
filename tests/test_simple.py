# Простейший тест для проверки работоспособности pytest
import pytest
from fastapi.testclient import TestClient
from app.main import app


def test_simple():
    assert 1 + 1 == 2


def test_health_endpoint():
    client = TestClient(app)
    response = client.get("/health")
    assert response.status_code == 200
    assert response.json() == {"status": "healthy"}


def test_root_endpoint():
    client = TestClient(app)
    response = client.get("/")
    assert response.status_code == 200
    assert response.json()["status"] == "ok"
