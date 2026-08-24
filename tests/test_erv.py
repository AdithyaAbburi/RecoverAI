import pytest
from app.agent.erv_engine import calculate_ervs, get_success_probability

def test_erv_engine_calculations():
    # Test for BANK_TIMEOUT, amount ₹10,000
    ervs = calculate_ervs(10000.0, "BANK_TIMEOUT")
    
    # Retry payment probability for BANK_TIMEOUT should be 70%
    retry_data = ervs["retry_payment"]
    assert retry_data["probability"] == 0.70
    assert retry_data["cost"] == 1.0
    # expected_gross = 10000 * 0.7 = 7000. Expected net = 7000 - 1 = 6999
    assert retry_data["expected_net"] == 6999.0

    # Escalate to human cost should be 100
    escalation_data = ervs["escalate_to_human"]
    assert escalation_data["probability"] == 0.80
    assert escalation_data["cost"] == 100.0
    # expected gross = 10000 * 0.8 = 8000. Net = 8000 - 100 = 7900
    assert escalation_data["expected_net"] == 7900.0

def test_success_probabilities():
    assert get_success_probability("retry_payment", "BANK_TIMEOUT") == 0.70
    assert get_success_probability("retry_payment", "INSUFFICIENT_FUNDS") == 0.10
    assert get_success_probability("create_payment_link", "CARD_EXPIRED") == 0.50
    assert get_success_probability("create_payment_link", "INSUFFICIENT_FUNDS") == 0.65
