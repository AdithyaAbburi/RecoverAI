import pytest
from app.db.models import Transaction, Customer
from app.simulator.payment_simulator import simulate_recovery_attempt

class MockObject:
    def __init__(self, **kwargs):
        for k, v in kwargs.items():
            setattr(self, k, v)

def test_simulator_reproducibility():
    tx = MockObject(amount=1000, failure_code="BANK_TIMEOUT")
    customer = MockObject(contact_preference="email")
    
    # Run twice with the exact same seed
    res1 = simulate_recovery_attempt("retry_payment", tx, customer, seed=123)
    res2 = simulate_recovery_attempt("retry_payment", tx, customer, seed=123)
    
    assert res1["status"] == res2["status"]
    assert res1["amount_recovered"] == res2["amount_recovered"]
    assert res1["description"] == res2["description"]

def test_simulator_retry_bank_timeout():
    tx = MockObject(amount=2499, failure_code="BANK_TIMEOUT")
    customer = MockObject(contact_preference="email")
    
    # Run 100 times to verify statistical bounds (optional), but let's test specific actions
    res = simulate_recovery_attempt("retry_payment", tx, customer, seed=42)
    assert res["status"] in ["SUCCESS", "FAILURE"]
    if res["status"] == "SUCCESS":
        assert res["amount_recovered"] == 2499.0
    else:
        assert res["amount_recovered"] == 0.0
