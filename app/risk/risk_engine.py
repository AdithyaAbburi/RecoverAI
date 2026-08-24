def calculate_risk_score(transaction, customer, invoice=None) -> dict:
    """
    Calculate a rule-based risk score (0-100) and risk level.
    Returns a dictionary containing:
      - risk_score (int)
      - risk_level (str): 'LOW', 'MEDIUM', 'HIGH', 'CRITICAL'
      - breakdown (dict): detailed scores for each factor
      - reason (str): human-readable summary of risk scoring
    """
    # 1. Failure Severity (Max 20)
    failure_severity = 0
    code = (transaction.failure_code or "").upper()
    if code in ["CARD_EXPIRED", "LIMIT_EXCEEDED"]:
        failure_severity = 20
    elif code in ["CUSTOMER_DECLINED", "UNKNOWN_ERROR"]:
        failure_severity = 15
    elif code == "INSUFFICIENT_FUNDS":
        failure_severity = 10
    elif code in ["BANK_TIMEOUT", "TEMPORARY_BANK_ERROR"]:
        failure_severity = 5
    
    # 2. Amount Factor (Max 30)
    # Linear scale up to ₹50,000
    amount = float(transaction.amount or 0)
    amount_factor = min(amount / 50000.0, 1.0) * 30.0
    amount_factor = round(amount_factor, 1)

    # 3. Customer History (Max 25)
    customer_history_factor = 0
    success_rate = float(customer.previous_payment_success_rate if customer else 1.0)
    if success_rate < 0.5:
        customer_history_factor = 25
    elif success_rate < 0.8:
        customer_history_factor = 15
    elif success_rate < 0.95:
        customer_history_factor = 5

    # 4. Retry Factor (Max 15)
    retry_count = int(transaction.retry_count or 0)
    if retry_count == 0:
        retry_factor = 0
    elif retry_count == 1:
        retry_factor = 10
    else:
        retry_factor = 15

    # 5. Overdue Factor (Max 10)
    overdue_factor = 0
    days_overdue = 0
    if invoice:
        days_overdue = int(invoice.days_overdue or 0)
        if days_overdue > 30:
            overdue_factor = 10
        elif days_overdue > 10:
            overdue_factor = 7
        elif days_overdue > 0:
            overdue_factor = 3

    # Total score calculation
    raw_score = failure_severity + amount_factor + customer_history_factor + retry_factor + overdue_factor
    risk_score = min(int(round(raw_score)), 100)

    # Determine risk level
    if risk_score <= 30:
        risk_level = "LOW"
    elif risk_score <= 60:
        risk_level = "MEDIUM"
    elif risk_score <= 80:
        risk_level = "HIGH"
    else:
        risk_level = "CRITICAL"

    breakdown = {
        "failure_severity": failure_severity,
        "amount_factor": amount_factor,
        "customer_history_factor": customer_history_factor,
        "retry_factor": retry_factor,
        "overdue_factor": overdue_factor
    }

    reason_parts = [
        f"Severity: {failure_severity} ({code})",
        f"Amount: {amount_factor} (₹{amount})",
        f"History: {customer_history_factor} (Success rate {success_rate:.2f})",
        f"Retry: {retry_factor} (Count {retry_count})",
        f"Overdue: {overdue_factor} ({days_overdue} days overdue)"
    ]
    reason = ", ".join(reason_parts)

    return {
        "risk_score": risk_score,
        "risk_level": risk_level,
        "breakdown": breakdown,
        "reason": reason
    }
