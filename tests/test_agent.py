import pytest
from app.diagnosis.root_cause import get_deterministic_fallback, analyze_root_cause

def test_deterministic_fallback_bank_timeout():
    res = get_deterministic_fallback("BANK_TIMEOUT")
    assert res["root_cause"] == "temporary_bank_failure"
    assert res["recommended_action"] == "retry_payment"
    assert res["confidence"] == 1.0

def test_deterministic_fallback_insufficient_funds():
    res = get_deterministic_fallback("INSUFFICIENT_FUNDS")
    assert res["root_cause"] == "insufficient_funds"
    assert res["recommended_action"] == "send_payment_reminder"

def test_deterministic_fallback_expired_card():
    res = get_deterministic_fallback("CARD_EXPIRED")
    assert res["root_cause"] == "expired_card"
    assert res["recommended_action"] == "create_payment_link"

def test_deterministic_fallback_unknown():
    res = get_deterministic_fallback("RANDOM_CODE")
    assert res["root_cause"] == "unknown"
    assert res["recommended_action"] == "escalate_to_human"
