def calculate_risk_score(transaction, customer=None, invoice=None) -> dict:
    """
    Calculate a deterministic, explainable risk score (0-100) and risk level.
    Returns a dictionary containing:
      - risk_score (int): 0 to 100
      - risk_level (str): 'LOW', 'MEDIUM', 'HIGH', 'CRITICAL'
      - signals (list): list of active risk signal descriptions
      - breakdown (dict): detailed numerical breakdown
      - reason (str): human-readable explanation
    """
    signals = []

    # Safe property extraction
    failure_code = getattr(transaction, "failure_code", "") or ""
    code = failure_code.upper()

    amount_val = getattr(transaction, "amount", 0.0) or 0.0
    amount = max(0.0, float(amount_val))

    retry_count_val = getattr(transaction, "retry_count", 0) or 0
    retry_count = max(0, int(retry_count_val))

    success_rate = 1.0
    risk_flag = False
    if customer:
        success_rate = float(getattr(customer, "previous_payment_success_rate", 1.0) or 1.0)
        risk_flag = bool(getattr(customer, "risk_flag", False))

    days_overdue = 0
    if invoice:
        days_overdue = max(0, int(getattr(invoice, "days_overdue", 0) or 0))

    # 1. Failure Severity (Max 20)
    failure_severity = 0
    if code in ["CARD_EXPIRED", "LIMIT_EXCEEDED"]:
        failure_severity = 20
        signals.append(f"High severity failure category: {code}")
    elif code in ["CUSTOMER_DECLINED", "UNKNOWN_ERROR"]:
        failure_severity = 15
        signals.append(f"Moderate severity failure category: {code}")
    elif code == "INSUFFICIENT_FUNDS":
        failure_severity = 10
        signals.append("Liquidity failure: INSUFFICIENT_FUNDS")
    elif code in ["BANK_TIMEOUT", "TEMPORARY_BANK_ERROR"]:
        failure_severity = 5
        signals.append("Transient infrastructure timeout")

    # 2. Amount Factor (Max 30) - Linear scale up to ₹50,000
    amount_factor = min(amount / 50000.0, 1.0) * 30.0
    amount_factor = round(amount_factor, 1)
    if amount >= 25000.0:
        signals.append(f"High value transaction amount: ₹{amount:,.2f}")

    # 3. Customer History Factor (Max 25)
    customer_history_factor = 0
    if risk_flag:
        customer_history_factor = 25
        signals.append("Customer account has active fraud/risk flag")
    elif success_rate < 0.5:
        customer_history_factor = 25
        signals.append(f"Low customer historical success rate: {success_rate*100:.0f}%")
    elif success_rate < 0.8:
        customer_history_factor = 15
        signals.append(f"Sub-optimal customer success rate: {success_rate*100:.0f}%")
    elif success_rate < 0.95:
        customer_history_factor = 5

    # 4. Retry Factor (Max 15)
    retry_factor = 0
    if retry_count == 1:
        retry_factor = 10
        signals.append("Previous attempt failed (Retry count: 1)")
    elif retry_count >= 2:
        retry_factor = 15
        signals.append(f"Multiple previous retries failed (Retry count: {retry_count})")

    # 5. Overdue Factor (Max 10)
    overdue_factor = 0
    if days_overdue > 30:
        overdue_factor = 10
        signals.append(f"Severely overdue customer invoice ({days_overdue} days)")
    elif days_overdue > 10:
        overdue_factor = 7
        signals.append(f"Moderately overdue invoice ({days_overdue} days)")
    elif days_overdue > 0:
        overdue_factor = 3
        signals.append(f"Recently overdue invoice ({days_overdue} days)")

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
        f"Severity: {failure_severity} ({code or 'UNKNOWN'})",
        f"Amount: {amount_factor} (₹{amount:,.2f})",
        f"History: {customer_history_factor} (Success rate {success_rate:.2f})",
        f"Retry: {retry_factor} (Count {retry_count})",
        f"Overdue: {overdue_factor} ({days_overdue} days overdue)"
    ]
    reason = ", ".join(reason_parts)

    return {
        "risk_score": risk_score,
        "risk_level": risk_level,
        "signals": signals,
        "breakdown": breakdown,
        "reason": reason
    }
