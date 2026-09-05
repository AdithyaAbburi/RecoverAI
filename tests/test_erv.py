import pytest
from app.agent.erv_engine import calculate_ervs, get_success_probability
from app.agent.orchestrator import select_best_mathematical_action

class MockObject:
    def __init__(self, **kwargs):
        for k, v in kwargs.items():
            setattr(self, k, v)

def test_erv_engine_normal_transaction():
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
    assert retry_data["expected_net"] == -1.0

def test_erv_engine_zero_probability():
    prob = get_success_probability("retry_payment", "CARD_EXPIRED", success_rate=0.85)
    assert prob == 0.0
    
    ervs = calculate_ervs(1000.0, "CARD_EXPIRED", success_rate=0.85)
    assert ervs["retry_payment"]["expected_net"] == -1.0

def test_erv_engine_high_transaction_value():
    ervs = calculate_ervs(100000.0, "BANK_TIMEOUT", ltv=60000.0)
    assert ervs["escalate_to_human"]["probability"] == 0.95
    assert ervs["escalate_to_human"]["expected_net"] == 94900.0

def test_erv_engine_cost_exceeds_expected_recovery_negative_erv():
    ervs = calculate_ervs(5.0, "INSUFFICIENT_FUNDS", success_rate=0.60)
    assert ervs["escalate_to_human"]["expected_net"] < 0.0
    assert ervs["escalate_to_human"]["expected_net"] == -96.0

def test_erv_engine_multiple_candidates_ranking():
    ervs = calculate_ervs(5000.0, "BANK_TIMEOUT")
    sorted_candidates = sorted(ervs.items(), key=lambda x: x[1]["expected_net"], reverse=True)
    assert len(sorted_candidates) == 7
    top_action = sorted_candidates[0][0]
    assert top_action in ["schedule_retry", "escalate_to_human", "retry_payment"]

def test_erv_engine_stop_recovery_zero_net():
    ervs = calculate_ervs(5000.0, "BANK_TIMEOUT")
    stop_data = ervs["stop_recovery"]
    assert stop_data["probability"] == 0.0
    assert stop_data["cost"] == 0.0
    assert stop_data["expected_net"] == 0.0

def test_displayed_selected_erv_equals_maximum_candidate_erv():
    tx = MockObject(transaction_id="TX999", amount=10000.0, retry_count=0, status="FAILED", recovery_status="UNRECOVERED")
    customer = MockObject(risk_flag=False, contact_preference="email")
    erv_table = calculate_ervs(10000.0, "BANK_TIMEOUT", success_rate=0.85)
    
    selected_action = select_best_mathematical_action(erv_table, tx, customer, attempts_count=0)
    
    # Filter candidates allowed by policy
    allowed_candidates = {
        act: erv_table[act]
        for act in erv_table.keys()
        if act not in ["escalate_to_human", "stop_recovery"]
    }
    max_expected_net = max(c["expected_net"] for c in allowed_candidates.values())
    selected_expected_net = erv_table[selected_action]["expected_net"]
    
    # Selected action MUST equal the candidate with maximum expected_net
    assert selected_expected_net == max_expected_net
