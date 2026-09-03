import pytest
from app.policy.policy_engine import check_policy

class MockObject:
    def __init__(self, **kwargs):
        for k, v in kwargs.items():
            setattr(self, k, v)

def test_policy_high_value_escalation():
    tx = MockObject(transaction_id="TX001", amount=30000, retry_count=0, status="FAILED")
    customer = MockObject(risk_flag=False, contact_preference="email")
    
    res = check_policy("retry_payment", tx, customer, attempts_count=0)
    assert res["allowed"] is False
    assert res["result"] == "ESCALATE"
    assert res["policy_rule"] == "HIGH_VALUE_THRESHOLD"
    assert "high-value threshold" in res["reason"]

def test_policy_max_attempts_escalation():
    tx = MockObject(transaction_id="TX001", amount=5000, retry_count=2, status="FAILED")
    customer = MockObject(risk_flag=False, contact_preference="email")
    
    res = check_policy("retry_payment", tx, customer, attempts_count=2)
    assert res["allowed"] is False
    assert res["result"] == "ESCALATE"
    assert res["policy_rule"] == "MAX_ATTEMPTS_EXHAUSTED"
    assert "Maximum automated recovery attempts" in res["reason"]

def test_policy_opt_out_communications():
    tx = MockObject(transaction_id="TX001", amount=5000, retry_count=0, status="FAILED")
    customer = MockObject(risk_flag=False, contact_preference="none")
    
    res1 = check_policy("send_payment_reminder", tx, customer, attempts_count=0)
    assert res1["allowed"] is False
    assert res1["result"] == "REJECTED"
    assert res1["policy_rule"] == "COMMUNICATION_OPT_OUT"
    assert "preference is set to 'none'" in res1["reason"]
    
    res2 = check_policy("create_payment_link", tx, customer, attempts_count=0)
    assert res2["result"] == "REJECTED"

def test_policy_fraud_escalation():
    tx = MockObject(transaction_id="TX001", amount=5000, retry_count=0, status="FAILED")
    customer = MockObject(risk_flag=True, contact_preference="email")
    
    res = check_policy("retry_payment", tx, customer, attempts_count=0)
    assert res["allowed"] is False
    assert res["result"] == "ESCALATE"
    assert res["policy_rule"] == "CUSTOMER_FRAUD_FLAG"
    assert "high-risk/suspicious" in res["reason"]

def test_policy_already_successful():
    tx = MockObject(transaction_id="TX001", amount=5000, retry_count=0, status="SUCCESS")
    customer = MockObject(risk_flag=False, contact_preference="email")
    
    res = check_policy("retry_payment", tx, customer, attempts_count=0)
    assert res["allowed"] is False
    assert res["result"] == "STOP"
    assert res["policy_rule"] == "ALREADY_SUCCESSFUL"

def test_policy_duplicate_action_protection():
    tx = MockObject(transaction_id="TX001", amount=5000, retry_count=1, status="FAILED")
    customer = MockObject(risk_flag=False, contact_preference="email")
    
    # First execution attempt
    res1 = check_policy("send_payment_reminder", tx, customer, attempts_count=0, previous_actions=[])
    assert res1["allowed"] is True
    assert res1["result"] == "APPROVED"
    assert res1["policy_rule"] == "POLICY_APPROVED"

    # Repeated execution request with duplicate action
    res2 = check_policy("send_payment_reminder", tx, customer, attempts_count=1, previous_actions=["send_payment_reminder"])
    assert res2["allowed"] is False
    assert res2["result"] == "REJECTED"
    assert res2["policy_rule"] == "DUPLICATE_ACTION"
    assert "Duplicate action blocked" in res2["reason"]

def test_policy_unsupported_action():
    tx = MockObject(transaction_id="TX001", amount=5000, retry_count=0, status="FAILED")
    customer = MockObject(risk_flag=False, contact_preference="email")
    
    res = check_policy("unauthorized_action_xyz", tx, customer, attempts_count=0)
    assert res["allowed"] is False
    assert res["result"] == "REJECTED"
    assert res["policy_rule"] == "UNSUPPORTED_ACTION"
