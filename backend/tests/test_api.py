import json
from collections import Counter
from pathlib import Path

from fastapi.testclient import TestClient

from api.main import app

ROOT = Path(__file__).resolve().parents[1]
client = TestClient(app)


def test_health_returns_200():
    res = client.get("/api/v1/health")
    assert res.status_code == 200
    assert res.json()["status"] == "ok"


def test_dashboard_returns_200():
    res = client.get("/api/v1/dashboard")
    assert res.status_code == 200


def test_dashboard_payment_count_matches_dev_artifact():
    raw = json.loads((ROOT / "data/dev/m6_final.json").read_text())
    res = client.get("/api/v1/dashboard")
    assert res.json()["metrics"]["transactions_processed"] == len(raw)


def test_dashboard_status_distribution_matches_dev_artifact():
    raw = json.loads((ROOT / "data/dev/m6_final.json").read_text())
    expected = Counter(d["status"] for d in raw.values())
    actual = {x["status"]: x["count"] for x in client.get("/api/v1/dashboard").json()["status_breakdown"]}
    assert actual == dict(expected)


def test_reconciliation_returns_records():
    data = client.get("/api/v1/reconciliation?page=1&page_size=5").json()
    assert len(data["items"]) == 5
    assert set(data["items"][0]) == {
        "payment_id", "order_id", "settlement_id", "payment_amount",
        "settlement_amount", "payment_date", "settlement_date", "currency",
        "source", "status", "confidence",
    }


def test_reconciliation_pagination_works():
    a = client.get("/api/v1/reconciliation?page=1&page_size=5").json()
    b = client.get("/api/v1/reconciliation?page=2&page_size=5").json()
    assert a["pagination"]["page"] == 1
    assert b["pagination"]["page"] == 2
    assert a["items"][0]["payment_id"] != b["items"][0]["payment_id"]
    assert a["pagination"]["total"] == 129


def test_reconciliation_status_filter_works():
    data = client.get("/api/v1/reconciliation?page=1&page_size=100&status=AMBIGUOUS").json()
    assert data["pagination"]["total"] == 12
    assert all(i["status"] == "AMBIGUOUS" for i in data["items"])


def test_reconciliation_detail_works():
    data = client.get("/api/v1/reconciliation/PAY_00001").json()
    assert data["payment"]["payment_id"] == "PAY_00001"
    assert data["final_decision"]["settlement_id"] == "STL_00001"
    assert data["final_decision"]["status"] == "MATCH"


def test_nonexistent_payment_returns_404():
    res = client.get("/api/v1/reconciliation/NON_EXISTENT_ID")
    assert res.status_code == 404


def test_exceptions_returns_real_dev_exceptions():
    data = client.get("/api/v1/exceptions").json()
    assert data["summary"]["total"] == 36
    assert len(data["items"]) == 36
    assert {i["payment_id"] for i in data["items"]} >= {"PAY_00005", "PAY_00007", "PAY_00016"}


def test_exception_detail_works():
    res = client.get("/api/v1/exceptions/CASE_00005")
    assert res.status_code == 200
    data = res.json()
    assert data["case_id"] == "CASE_00005"
    assert data["payment"]["payment_id"] == "PAY_00005"


def test_audit_returns_actual_events():
    raw_lines = (ROOT / "audit_log_m6.jsonl").read_text().splitlines()
    raw = [json.loads(x) for x in raw_lines if x.strip() and json.loads(x).get("record_id") == "PAY_00035"]
    data = client.get("/api/v1/audit/PAY_00035").json()
    assert len(data["events"]) == len(raw)
    assert data["events"] == sorted(data["events"], key=lambda e: e["timestamp"])
    assert data["events"][0]["rule_id"] == raw[0]["rule_id"]


def test_evaluation_dev_works():
    data = client.get("/api/v1/evaluation?dataset=dev").json()
    assert data["dataset"] == "DEV"
    assert data["metrics"]["match_rate"] == 1.0
    assert len(data["confusion_matrix"]) == 8


def test_holdout_cannot_be_exposed():
    res = client.get("/api/v1/evaluation?dataset=holdout")
    assert res.status_code == 403
    assert "holdout" in res.json()["detail"].lower()


def test_actual_m6_dict_artifact_is_adapted_to_frontend_list():
    raw = json.loads((ROOT / "data/dev/m6_final.json").read_text())
    assert isinstance(raw, dict)
    data = client.get("/api/v1/reconciliation?page=1&page_size=129").json()
    assert isinstance(data["items"], list)
    assert len(data["items"]) == len(raw)


def test_api_can_serialize_decimal_backed_financial_data():
    data = client.get("/api/v1/reconciliation/PAY_00015").json()
    assert isinstance(data["payment"]["amount"], (int, float))
    assert isinstance(data["settlement"]["gross_amount"], (int, float))
