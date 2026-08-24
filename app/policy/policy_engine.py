from app.db.models import Transaction, Customer

# Deterministic Safety Limits
MAX_ATTEMPTS = 2
HIGH_VALUE_THRESHOLD = 25000.0  # INR

def check_policy(action: str, transaction: Transaction, customer: Customer, attempts_count: int = 0) -> dict:
    """
    Apply deterministic business policies to validate an agent's recommended action.
    Returns a dictionary containing:
      - allowed (bool): whether the action is permitted
      - result (str): 'APPROVED', 'REJECTED', or 'ESCALATE'
      - reason (str): description of why the decision was made
    """
    # Rule 0: If the transaction is already successful, stop recovery
    if transaction.status.upper() == "SUCCESS":
        return {
            "allowed": False,
            "result": "STOP",
            "reason": "Transaction is already successful. Recovery process terminated."
        }

    # Rule 1: High-Value protection
    if transaction.amount >= HIGH_VALUE_THRESHOLD:
        return {
            "allowed": False,
            "result": "ESCALATE",
            "reason": f"Amount (₹{transaction.amount}) meets or exceeds high-value threshold (₹{HIGH_VALUE_THRESHOLD}). Escalating for human operations review."
        }

    # Rule 2: Customer Fraud/High-Risk flag check
    if customer and customer.risk_flag:
        return {
            "allowed": False,
            "result": "ESCALATE",
            "reason": "Customer is flagged as high-risk/suspicious. Automated recovery is disabled. Escalating for human operations review."
        }

    # Rule 3: Attempt budget stopping rule (MAX_ATTEMPTS = 2)
    # If the transaction has already undergone 2 or more attempts, automated tools are blocked.
    if attempts_count >= MAX_ATTEMPTS and action not in ["escalate_to_human", "stop_recovery"]:
        return {
            "allowed": False,
            "result": "ESCALATE",
            "reason": f"Maximum automated recovery attempts ({MAX_ATTEMPTS}) reached. Escalating for human review."
        }

    # Rule 4: Contact preference/Opt-out check
    contact_actions = ["send_payment_reminder", "create_payment_link"]
    if action in contact_actions:
        preference = (customer.contact_preference or "").lower() if customer else "email"
        if preference == "none":
            return {
                "allowed": False,
                "result": "REJECTED",
                "reason": f"Action '{action}' rejected. Customer contact preference is set to 'none' (opted out of communications)."
            }

    # Safety defaults
    if action in ["escalate_to_human", "stop_recovery"]:
        return {
            "allowed": True,
            "result": "APPROVED",
            "reason": f"Action '{action}' is a default safety exit action and is allowed."
        }

    # List of allowed tools
    allowed_actions = [
        "retry_payment",
        "send_payment_reminder",
        "create_payment_link",
        "schedule_retry",
        "mark_promise_to_pay"
    ]
    if action not in allowed_actions:
        return {
            "allowed": False,
            "result": "REJECTED",
            "reason": f"Action '{action}' is not in the list of allowed bounded recovery actions."
        }

    return {
        "allowed": True,
        "result": "APPROVED",
        "reason": f"Action '{action}' approved under current deterministic policy limits."
    }
