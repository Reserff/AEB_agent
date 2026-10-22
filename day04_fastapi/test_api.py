from fastapi.testclient import TestClient
import day04_fastapi.api as api


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