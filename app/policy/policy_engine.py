from app.db.models import Transaction, Customer

# Deterministic Safety Limits
MAX_ATTEMPTS = 2
HIGH_VALUE_THRESHOLD = 25000.0  # INR

def check_policy(action: str, transaction: Transaction, customer: Customer, attempts_count: int = 0, previous_actions: list = None) -> dict:
    """
    Apply deterministic business policies to validate an agent's recommended action.
    Returns a dictionary containing:
      - allowed (bool): whether the action is permitted
      - action (str): the evaluated action
      - result (str): 'APPROVED', 'REJECTED', 'STOP', or 'ESCALATE'
      - reason (str): description of why the decision was made
      - policy_rule (str): rule code identifier for audit tracking
    """
    prev_actions = previous_actions or []

    # Rule 0: Already successful transaction protection
    if transaction.status.upper() == "SUCCESS":
        return {
            "allowed": False,
            "action": action,
            "result": "STOP",
            "reason": "Transaction is already successful. Recovery process terminated.",
            "policy_rule": "ALREADY_SUCCESSFUL"
        }

    # Rule 1: High-Value protection
    if transaction.amount >= HIGH_VALUE_THRESHOLD:
        return {
            "allowed": False,
            "action": action,
            "result": "ESCALATE",
            "reason": f"Amount (₹{transaction.amount:,.2f}) meets or exceeds high-value threshold (₹{HIGH_VALUE_THRESHOLD:,.2f}). Escalating for human operations review.",
            "policy_rule": "HIGH_VALUE_THRESHOLD"
        }

    # Rule 2: Customer Fraud/High-Risk flag check
    if customer and customer.risk_flag:
        return {
            "allowed": False,
            "action": action,
            "result": "ESCALATE",
            "reason": "Customer is flagged as high-risk/suspicious. Automated recovery is disabled. Escalating for human operations review.",
            "policy_rule": "CUSTOMER_FRAUD_FLAG"
        }

    # Rule 3: Attempt budget stopping rule (MAX_ATTEMPTS = 2)
    if attempts_count >= MAX_ATTEMPTS and action not in ["escalate_to_human", "stop_recovery"]:
        return {
            "allowed": False,
            "action": action,
            "result": "ESCALATE",
            "reason": f"Maximum automated recovery attempts ({MAX_ATTEMPTS}) reached. Escalating for human review.",
            "policy_rule": "MAX_ATTEMPTS_EXHAUSTED"
        }

    # Rule 4: Duplicate action protection (Idempotency)
    if action in prev_actions and action not in ["escalate_to_human", "stop_recovery"]:
        return {
            "allowed": False,
            "action": action,
            "result": "REJECTED",
            "reason": f"Action '{action}' was already executed for transaction '{transaction.transaction_id}'. Duplicate action blocked.",
            "policy_rule": "DUPLICATE_ACTION"
        }

    # Rule 5: Contact preference/Opt-out check
    contact_actions = ["send_payment_reminder", "create_payment_link"]
    if action in contact_actions:
        preference = (customer.contact_preference or "").lower() if customer else "email"
        if preference == "none":
            return {
                "allowed": False,
                "action": action,
                "result": "REJECTED",
                "reason": f"Action '{action}' rejected. Customer contact preference is set to 'none' (opted out of communications).",
                "policy_rule": "COMMUNICATION_OPT_OUT"
            }

    # Rule 6: Default safety exit actions
    if action in ["escalate_to_human", "stop_recovery"]:
        return {
            "allowed": True,
            "action": action,
            "result": "APPROVED",
            "reason": f"Action '{action}' is a default safety exit action and is allowed.",
            "policy_rule": "SAFETY_EXIT"
        }

    # Rule 7: List of allowed bounded tools
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
            "action": action,
            "result": "REJECTED",
            "reason": f"Action '{action}' is not in the list of allowed bounded recovery actions.",
            "policy_rule": "UNSUPPORTED_ACTION"
        }

    return {
        "allowed": True,
        "action": action,
        "result": "APPROVED",
        "reason": f"Action '{action}' approved under current deterministic policy limits.",
        "policy_rule": "POLICY_APPROVED"
    }
