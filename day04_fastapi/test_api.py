from fastapi.testclient import TestClient
import day04_fastapi.api as api
import uuid

client = TestClient(api.app)


def test_health():
    response = client.get("/health")

    assert response.status_code == 200
    assert response.json() == {"status": "ok"}


def test_empty_prompt():
    response = client.post(
        "/analyze",
        json={"prompt": ""},
    )

    assert response.status_code == 422


def test_analyze_with_mock(monkeypatch):

    def fake_run_agent(prompt):
        assert prompt == "分析AEB案例"

        return {
            "tool_called": True,
            "tool_results": [
                {
                    "ttc": 0.8,
                    "risk": "HIGH",
                    "abnormal": True,
                }
            ],
            "answer": "该场景存在较高风险",
        }

    monkeypatch.setattr(
        api,
        "run_agent",
        fake_run_agent,
    )

    response = client.post(
        "/analyze",
        json={"prompt": "分析AEB案例"},
    )

    assert response.status_code == 200

    data = response.json()
    assert data["tool_called"] is True
    assert data["tool_results"][0]["ttc"] == 0.8
    assert data["answer"] == "该场景存在较高风险"
    
def test_analyze_failure_returns_500(monkeypatch):

    def fake_run_agent(prompt):
        raise RuntimeError("模拟模型服务故障")

    monkeypatch.setattr(
        api,
        "run_agent",
        fake_run_agent,
        )

    response = client.post(
        "/analyze",
        json={"prompt": "分析AEB场景"},
    )

    assert response.status_code == 500
    assert response.json()["detail"] == (
        "分析服务执行失败，请查看服务端日志"
    )
    assert "X-Request-ID" in response.headers
    assert "X-Process-Time-Ms" in response.headers
    
def test_request_trace_headers():

    response = client.get("/health")

    assert response.status_code == 200

    # 检查是否生成请求编号
    request_id = response.headers["X-Request-ID"]

    # 验证请求编号是否为合法 UUID
    uuid.UUID(request_id)

    # 检查耗时
    duration_ms = float(
        response.headers["X-Process-Time-Ms"]
    )

    assert duration_ms >= 0


def test_request_id_is_unique():

    response1 = client.get("/health")
    response2 = client.get("/health")

    request_id1 = response1.headers["X-Request-ID"]
    request_id2 = response2.headers["X-Request-ID"]

    # 两次请求应当有不同的 ID
    assert request_id1 != request_id2
    
    
def test_analyze_route_registered_once():
    routes = [
        route
        for route in api.app.routes
        if getattr(route, "path", None) == "/analyze"
        and "POST" in (
            getattr(route, "methods", set()) or set()
        )
    ]

    assert len(routes) == 1

def test_ready_when_config_exists(monkeypatch):
    monkeypatch.setenv("GLM_MODEL", "test-model")
    monkeypatch.setenv("GLM_API_KEY", "test-key")

    response = client.get("/ready")

    assert response.status_code == 200
    assert response.json() == {"status": "ready"}


def test_not_ready_when_api_key_missing(monkeypatch):
    monkeypatch.setenv("GLM_MODEL", "test-model")
    monkeypatch.delenv("GLM_API_KEY", raising=False)

    response = client.get("/ready")

    assert response.status_code == 503
    assert "GLM_API_KEY" in (
        response.json()["detail"]["missing_settings"]
    )