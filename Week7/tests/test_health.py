import pytest

def test_liveness_probe_healthz(client):
    """Kiểm thử /healthz trả về 200 nhanh không chạm DB (Bài tập 4, Slide 36, 37)."""
    res = client.get("/healthz")
    assert res.status_code == 200
    assert res.json == {"status": "ok"}

def test_readiness_probe_ready(client):
    """Kiểm thử /ready kiểm tra kết nối DB qua SELECT 1 (Bài tập 4, Slide 36, 37)."""
    res = client.get("/ready")
    assert res.status_code == 200
    assert res.json["status"] == "ok"
    assert res.json["checks"]["db"] == "ok"

