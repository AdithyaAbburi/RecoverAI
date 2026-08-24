import pytest
from app.db.models import Transaction, Customer, Invoice
from app.risk.risk_engine import calculate_risk_score

class MockObject:
    def __init__(self, **kwargs):
        for k, v in kwargs.items():
            setattr(self, k, v)

def test_calculate_risk_score_low():
    # Low risk transaction
    tx = MockObject(amount=1000, failure_code="BANK_TIMEOUT", retry_count=0)
    customer = MockObject(previous_payment_success_rate=0.98, customer_type="returning")
    invoice = None
    
    res = calculate_risk_score(tx, customer, invoice)
    assert res["risk_level"] == "LOW"
    # BANK_TIMEOUT: 5, Amount: ~0.6, Success rate: 0, Retry: 0, Overdue: 0 -> Risk score ~ 6
    assert 4 <= res["risk_score"] <= 10

def test_calculate_risk_score_critical_high_value_overdue():
    # Critical risk high-value transaction with overdue invoices
    tx = MockObject(amount=50000, failure_code="CARD_EXPIRED", retry_count=2)
    customer = MockObject(previous_payment_success_rate=0.45, customer_type="returning")
    invoice = MockObject(days_overdue=35)
    
    res = calculate_risk_score(tx, customer, invoice)
    assert res["risk_level"] == "CRITICAL"
    # Expired card: 20, Amount 50k: 30, Success rate: 25, Retry: 15, Overdue: 10 -> Score 100
    assert res["risk_score"] == 100
