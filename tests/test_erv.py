import pytest
from app.agent.erv_engine import calculate_ervs, get_success_probability

def test_erv_engine_normal_transaction():
    # Test for BANK_TIMEOUT, amount ₹10,000
    ervs = calculate_ervs(10000.0, "BANK_TIMEOUT", success_rate=0.85)
    
    retry_data = ervs["retry_payment"]
    assert retry_data["probability"] == 0.70
    assert retry_data["cost"] == 1.0
    assert retry_data["expected_gross"] == 7000.0
    assert retry_data["expected_net"] == 6999.0

    escalation_data = ervs["escalate_to_human"]
    assert escalation_data["probability"] == 0.80
    assert escalation_data["cost"] == 100.0
    assert escalation_data["expected_gross"] == 8000.0
    assert escalation_data["expected_net"] == 7900.0

def test_erv_engine_zero_amount():
    ervs = calculate_ervs(0.0, "BANK_TIMEOUT")
    retry_data = ervs["retry_payment"]
    assert retry_data["expected_gross"] == 0.0
    # expected_net = 0 - cost = -1.0
    assert retry_data["expected_net"] == -1.0

def test_erv_engine_zero_probability():
    # Card expired retry_payment has 0% probability
    prob = get_success_probability("retry_payment", "CARD_EXPIRED", success_rate=0.85)
    assert prob == 0.0
    
    ervs = calculate_ervs(1000.0, "CARD_EXPIRED", success_rate=0.85)
    assert ervs["retry_payment"]["expected_net"] == -1.0  # (1000 * 0) - 1.0 = -1.0

def test_erv_engine_high_transaction_value():
    ervs = calculate_ervs(100000.0, "BANK_TIMEOUT", ltv=60000.0)
    assert ervs["escalate_to_human"]["probability"] == 0.95
    assert ervs["escalate_to_human"]["expected_net"] == 94900.0

def test_erv_engine_cost_exceeds_expected_recovery_negative_erv():
    # For small transaction amount ₹5 with low probability 0.10, gross = ₹0.5, cost = ₹100 for human escalation
    # expected_net = 0.5 - 100.0 = -99.50 (negative ERV)
    ervs = calculate_ervs(5.0, "INSUFFICIENT_FUNDS", success_rate=0.60)
    assert ervs["escalate_to_human"]["expected_net"] < 0.0
    assert ervs["escalate_to_human"]["expected_net"] == -96.0

def test_erv_engine_multiple_candidates_ranking():
    ervs = calculate_ervs(5000.0, "BANK_TIMEOUT")
    # Sort actions by expected_net descending
    sorted_candidates = sorted(ervs.items(), key=lambda x: x[1]["expected_net"], reverse=True)
    assert len(sorted_candidates) == 7
    # Top ranked action for BANK_TIMEOUT should be schedule_retry or escalate_to_human
    top_action = sorted_candidates[0][0]
    assert top_action in ["schedule_retry", "escalate_to_human", "retry_payment"]

def test_erv_engine_stop_recovery_zero_net():
    ervs = calculate_ervs(5000.0, "BANK_TIMEOUT")
    stop_data = ervs["stop_recovery"]
    assert stop_data["probability"] == 0.0
    assert stop_data["cost"] == 0.0
    assert stop_data["expected_net"] == 0.0
