SYSTEM_PROMPT = """You are the AI Decision Orchestrator for RecoverAI, an autonomous revenue recovery agent.
Your goal is to optimize net recovered revenue from failed payments by selecting the most value-generating, safe intervention.

You MUST respond with a JSON object containing exactly these fields:
1. "root_cause": One of "temporary_bank_failure", "insufficient_funds", "expired_card", "customer_declined", "limit_exceeded", "unknown"
2. "confidence": A float between 0.0 and 1.0 representing your confidence in this diagnosis.
3. "recommended_action": One of "retry_payment", "send_payment_reminder", "create_payment_link", "schedule_retry", "mark_promise_to_pay", "escalate_to_human", "stop_recovery"
4. "reason": A brief explanation of your diagnosis and why this action maximizes recovery value given transaction context.
5. "why_not_alternatives": Explaining why other candidate actions with high Expected Net Recovery (like immediate retry or escalation) were bypassed.

Intervention Guidelines:
- Do not repeat a failed automated action (e.g. if retry_payment already failed in the retry history, try another action like create_payment_link or schedule_retry, rather than retrying again).
- Use Expected Net Recovery as a reference, but balance it with safety. Escalation is expensive (operational cost = INR 100), so favor automated tools if they have high probability and we have attempts remaining.
- If attempts are exhausted or the account is high-risk, recommend escalate_to_human.

Response MUST be a valid JSON object ONLY. Do not wrap in markdown or prefix with other text.
"""

def get_transaction_prompt(
    transaction_data: dict, 
    customer_data: dict, 
    invoice_data: dict = None, 
    attempts_history: list = None,
    erv_table: dict = None
) -> str:
    """
    Format transaction, customer profile, previous attempt history, and ERV calculations into a prompt for the LLM.
    """
    history_str = "No previous attempts made in this recovery loop."
    if attempts_history:
        history_parts = []
        for i, att in enumerate(attempts_history):
            history_parts.append(f"Attempt #{i+1}: Action '{att.get('action')}' -> Outcome: '{att.get('result')}' (Reason: {att.get('reason')})")
        history_str = "\n".join(history_parts)

    erv_str = ""
    if erv_table:
        erv_lines = ["Action | Prob | Cost | Net Recovery"]
        for act, vals in erv_table.items():
            erv_lines.append(f"{act} | {vals['probability']:.2f} | INR {vals['cost']:.1f} | INR {vals['expected_net']:.2f}")
        erv_str = "\n".join(erv_lines)

    prompt = f"""Analyze this transaction failure and select the best next recovery action:

[TRANSACTION]
ID: {transaction_data.get("transaction_id")}
Amount: INR {transaction_data.get("amount")}
Method: {transaction_data.get("payment_method")}
Failure Code: {transaction_data.get("failure_code")}
Timestamp: {transaction_data.get("timestamp")}
Risk Score: {transaction_data.get("risk_score")} ({transaction_data.get("risk_level")})

[CUSTOMER]
ID: {customer_data.get("customer_id")}
Type: {customer_data.get("customer_type")}
Lifetime Value: INR {customer_data.get("lifetime_value")}
Previous Payment Success Rate: {customer_data.get("previous_payment_success_rate")}
Contact Preference: {customer_data.get("contact_preference")}
Risk Flag: {customer_data.get("risk_flag")}

[RECOVERY HISTORY]
{history_str}

[EXPECTED NET RECOVERY VALUES]
{erv_str}
"""

    if invoice_data:
        prompt += f"""
[INVOICE]
ID: {invoice_data.get("invoice_id")}
Amount Due: INR {invoice_data.get("amount_due")}
Days Overdue: {invoice_data.get("days_overdue")}
Promise to Pay: {invoice_data.get("promise_to_pay")}
"""
    else:
        prompt += "\n[INVOICE]\nNo active invoice/receivables context."

    prompt += "\nReturn your structured diagnosis and decisions as JSON:"
    return prompt
