import pytest
from app.risk.risk_engine import calculate_risk_score

class MockObject:
    def __init__(self, **kwargs):
        for k, v in kwargs.items():
            setattr(self, k, v)

def test_calculate_risk_score_low():
    tx = MockObject(amount=1000, failure_code="BANK_TIMEOUT", retry_count=0)
    customer = MockObject(previous_payment_success_rate=0.98, customer_type="returning", risk_flag=False)
    invoice = None
    
    res = calculate_risk_score(tx, customer, invoice)
    assert res["risk_level"] == "LOW"
    assert 0 <= res["risk_score"] <= 30
    assert isinstance(res["signals"], list)

def test_calculate_risk_score_medium():
    tx = MockObject(amount=15000, failure_code="INSUFFICIENT_FUNDS", retry_count=1)
    customer = MockObject(previous_payment_success_rate=0.85, risk_flag=False)
    invoice = MockObject(days_overdue=5)
    
    res = calculate_risk_score(tx, customer, invoice)
    assert res["risk_level"] in ["LOW", "MEDIUM"]

def test_calculate_risk_score_critical_high_value_overdue():
    tx = MockObject(amount=50000, failure_code="CARD_EXPIRED", retry_count=2)
    customer = MockObject(previous_payment_success_rate=0.45, risk_flag=True)
    invoice = MockObject(days_overdue=35)
    
    res = calculate_risk_score(tx, customer, invoice)
    assert res["risk_level"] == "CRITICAL"
    assert res["risk_score"] == 100
    assert "Customer account has active fraud/risk flag" in res["signals"]

def test_calculate_risk_score_missing_and_malformed_inputs():
    # Test with None customer and invoice
    tx = MockObject(amount=None, failure_code=None, retry_count=None)
    res = calculate_risk_score(tx, None, None)
    assert res["risk_level"] == "LOW"
    assert res["risk_score"] == 0

    # Negative amount and retry count
    tx_bad = MockObject(amount=-500, failure_code="BANK_TIMEOUT", retry_count=-2)
    res_bad = calculate_risk_score(tx_bad, None, None)
    assert res_bad["risk_score"] >= 0
