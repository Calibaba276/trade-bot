from backend.services.verdict import build_verdict

def test_verdict_creates_a_complete_deterministic_snapshot():
    verdict = build_verdict(
        symbol="EURUSD",
        direction="buy",
        entry=1.08490,
        sl=1.08200,
        tp=1.09360,
        risk=0.00290,
        rr=3.0,
        scenario="london_bullish",
        fvg_confirmed=True,
    )

    assert verdict.symbol == "EURUSD"
    assert verdict.direction == "buy"
    assert verdict.entry_price == 1.08490
    assert verdict.fvg_confirmed is True
    assert verdict.reward_risk_ratio == 3.0
