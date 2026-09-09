from backend.services.audit_log import log_filter_result
from tests.test_setup_filter_models import make_setup
from backend.strategies.setup_filter import FilterCheckResult, FilterResult


class FakeTable:
    def __init__(self) -> None:
        self.inserted: dict[str, object] | None = None
        self.executed = False

    def insert(self, values: dict[str, object]) -> "FakeTable":
        self.inserted = values
        return self

    def execute(self) -> object:
        self.executed = True
        return {"data": [], "error": None}


class FakeSupabase:
    def __init__(self) -> None:
        self.table_name: str | None = None
        self.table_instance = FakeTable()

    def table(self, name: str) -> FakeTable:
        self.table_name = name
        return self.table_instance


def test_log_filter_result_serializes_audit_row() -> None:
    result = FilterResult(
        setup=make_setup(),
        passed=False,
        composite_score=0.5,
        checks=[
            FilterCheckResult(
                check_name="check_confluence",
                passed=False,
                score=0.33,
                weight=1.0,
                reason="1/3 independent categories met",
            )
        ],
        rejected_by="check_confluence",
    )
    client = FakeSupabase()

    log_filter_result(result, "account-123", client)

    assert client.table_name == "audit_log"
    assert client.table_instance.executed is True
    assert client.table_instance.inserted is not None
    assert client.table_instance.inserted["account_id"] == "account-123"
    assert client.table_instance.inserted["extract_fvg_and_order_block"] == "both"
    assert client.table_instance.inserted["reward_risk_ratio"] == 4.142857142857142
    assert client.table_instance.inserted["checks_detail"] == [
        {
            "check_name": "check_confluence",
            "passed": False,
            "score": 0.33,
            "weight": 1.0,
            "reason": "1/3 independent categories met",
        }
    ]
