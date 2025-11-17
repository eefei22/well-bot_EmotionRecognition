# tests/test_emotion.py
from fastapi.testclient import TestClient
from app.main import app

client = TestClient(app)

def test_create_emotion():
    payload = {"user_id": "testuser", "heart_rate": 85.0, "emotion": "happy"}
    response = client.post("/emotions", json=payload)
    assert response.status_code == 200
