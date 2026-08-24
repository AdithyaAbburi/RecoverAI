import pytest
from app.db.models import Transaction, Customer
from app.policy.policy_engine import check_policy

class MockObject:
    def __init__(self, **kwargs):
        for k, v in kwargs.items():
            setattr(self, k, v)

def test_policy_high_value_escalation():
    # Transaction >= ₹25,000
    tx = MockObject(amount=30000, retry_count=0, status="FAILED")
    customer = MockObject(risk_flag=False, contact_preference="email")
    
    res = check_policy("retry_payment", tx, customer, attempts_count=0)
    assert res["result"] == "ESCALATE"
    assert "high-value" in res["reason"]

def test_policy_max_attempts_escalation():
    # Transaction attempts count >= 2
    tx = MockObject(amount=5000, retry_count=2, status="FAILED")
    customer = MockObject(risk_flag=False, contact_preference="email")
    
    res = check_policy("retry_payment", tx, customer, attempts_count=2)
    assert res["result"] == "ESCALATE"
    assert "Maximum automated recovery attempts" in res["reason"]

def test_policy_opt_out_communications():
    # Customer contact preference is set to 'none'
    tx = MockObject(amount=5000, retry_count=0, status="FAILED")
    customer = MockObject(risk_flag=False, contact_preference="none")
    
    # reminders and payment links should be blocked
    res1 = check_policy("send_payment_reminder", tx, customer, attempts_count=0)
    assert res1["result"] == "REJECTED"
    assert "preference is set to 'none'" in res1["reason"]
    
    res2 = check_policy("create_payment_link", tx, customer, attempts_count=0)
    assert res2["result"] == "REJECTED"

def test_policy_fraud_escalation():
    # Customer risk_flag is set to True
    tx = MockObject(amount=5000, retry_count=0, status="FAILED")
    customer = MockObject(risk_flag=True, contact_preference="email")
    
    res = check_policy("retry_payment", tx, customer, attempts_count=0)
    assert res["result"] == "ESCALATE"
    assert "high-risk/suspicious" in res["reason"]

def test_policy_already_successful():
    tx = MockObject(amount=5000, retry_count=0, status="SUCCESS")
    customer = MockObject(risk_flag=False, contact_preference="email")
    
    res = check_policy("retry_payment", tx, customer, attempts_count=0)
    assert res["result"] == "STOP"
