# Expected Recovery Value (ERV) Engine

# Operational cost in INR for executing each intervention
INTERVENTION_COSTS = {
    "retry_payment": 1.0,
    "send_payment_reminder": 1.0,
    "create_payment_link": 2.0,
    "schedule_retry": 1.5,
    "mark_promise_to_pay": 0.0,
    "escalate_to_human": 100.0,
    "stop_recovery": 0.0
}

def get_success_probability(action: str, failure_code: str, success_rate: float = 0.85, ltv: float = 0.0) -> float:
    """
    Get the context-aware success probability of a recovery action.
    Leverages customer payment history and failure codes to optimize predictions.
    """
    code = (failure_code or "").upper()
    prob = 0.0
    
    if action == "retry_payment":
        if code in ["BANK_TIMEOUT", "TEMPORARY_BANK_ERROR"]:
            prob = 0.70
        elif code == "INSUFFICIENT_FUNDS":
            prob = 0.10
        elif code == "CARD_EXPIRED":
            prob = 0.00
        elif code == "LIMIT_EXCEEDED":
            prob = 0.05
        else:
            prob = 0.20
            
        # Retries are slightly more successful if the customer is historically reliable
        if success_rate >= 0.90:
            prob = min(0.95, prob + 0.05)
        elif success_rate < 0.70:
            prob = max(0.00, prob - 0.05)
        
    elif action == "send_payment_reminder":
        if code == "INSUFFICIENT_FUNDS":
            prob = 0.60
        elif code == "CARD_EXPIRED":
            prob = 0.00
        elif code == "CUSTOMER_DECLINED":
            prob = 0.30
        else:
            prob = 0.40
            
        # Reminders rely heavily on customer responsiveness/reliability
        if success_rate >= 0.90:
            prob = min(0.95, prob + 0.20)
        elif success_rate < 0.70:
            prob = max(0.10, prob - 0.20)
            
    elif action == "create_payment_link":
        if code == "INSUFFICIENT_FUNDS":
            prob = 0.65
        elif code == "CARD_EXPIRED":
            prob = 0.50
        elif code == "CUSTOMER_DECLINED":
            prob = 0.35
        else:
            prob = 0.45
            
        # Payment links rely heavily on customer trust & responsiveness
        if success_rate >= 0.90:
            prob = min(0.95, prob + 0.20)
        elif success_rate < 0.70:
            prob = max(0.10, prob - 0.20)
            
    elif action == "schedule_retry":
        if code in ["BANK_TIMEOUT", "TEMPORARY_BANK_ERROR"]:
            prob = 0.85
        else:
            prob = 0.30
            
        if success_rate >= 0.90:
            prob = min(0.95, prob + 0.05)
        elif success_rate < 0.70:
            prob = max(0.05, prob - 0.05)
            
    elif action == "mark_promise_to_pay":
        prob = 0.40
        if success_rate >= 0.90:
            prob = min(0.95, prob + 0.25)
        elif success_rate < 0.70:
            prob = max(0.05, prob - 0.25)
            
    elif action == "escalate_to_human":
        prob = 0.80
        # High value/LTV accounts get extra priority and success from human CS agent
        if ltv >= 50000.0:
            prob = 0.95
            
    elif action == "stop_recovery":
        prob = 0.00
        
    return round(prob, 2)

def calculate_ervs(amount: float, failure_code: str, success_rate: float = 0.85, ltv: float = 0.0) -> dict:
    """
    Calculate the Expected Recovery Value (ERV) and Net Expected Recovery (NER) for all candidate actions.
    Expected Net Recovery = (Success Probability * Transaction Amount) - Operational Cost.
    """
    erv_results = {}
    
    for action in INTERVENTION_COSTS.keys():
        prob = get_success_probability(action, failure_code, success_rate, ltv)
        cost = INTERVENTION_COSTS[action]
        expected_gross = amount * prob
        expected_net = expected_gross - cost
        
        erv_results[action] = {
            "probability": round(prob, 2),
            "cost": cost,
            "expected_gross": round(expected_gross, 2),
            "expected_net": round(expected_net, 2)
        }
        
    return erv_results
