from sqlalchemy.orm import Session
from app.db.models import Transaction, Customer, Invoice, AuditLog
from app.risk.risk_engine import calculate_risk_score
from app.agent.erv_engine import calculate_ervs
from app.diagnosis.root_cause import analyze_root_cause
from app.policy.policy_engine import check_policy, MAX_ATTEMPTS
from app.agent.tools import execute_tool
from app.services.audit_service import log_audit

def get_root_cause_by_failure_code(failure_code: str) -> str:
    """
    Map failure code to standard root cause string for deterministic rules.
    """
    code = (failure_code or "").upper()
    if code in ["BANK_TIMEOUT", "TEMPORARY_BANK_ERROR"]:
        return "temporary_bank_failure"
    elif code == "INSUFFICIENT_FUNDS":
        return "insufficient_funds"
    elif code == "CARD_EXPIRED":
        return "expired_card"
    elif code == "LIMIT_EXCEEDED":
        return "limit_exceeded"
    elif code == "CUSTOMER_DECLINED":
        return "customer_declined"
    else:
        return "unknown"

def get_standard_failure_code_from_cause(root_cause: str) -> str:
    """
    Map a diagnosed root cause string back to a standard uppercase failure code
    to rank candidates in the ERV engine.
    """
    cause = (root_cause or "").lower()
    if "temporary_bank_failure" in cause or "bank_timeout" in cause or "temporary_bank_error" in cause:
        return "BANK_TIMEOUT"
    elif "insufficient" in cause:
        return "INSUFFICIENT_FUNDS"
    elif "expired" in cause:
        return "CARD_EXPIRED"
    elif "limit" in cause:
        return "LIMIT_EXCEEDED"
    elif "decline" in cause:
        return "CUSTOMER_DECLINED"
    else:
        return "UNKNOWN"

def get_simple_rules_action(failure_code: str, attempts_count: int) -> str:
    """
    Static, simple rule-based mapping (Ablation B).
    Does not use context-aware ERV calculations or customer history.
    """
    code = (failure_code or "").upper()
    if code in ["BANK_TIMEOUT", "TEMPORARY_BANK_ERROR"]:
        return "retry_payment" if attempts_count == 0 else "create_payment_link"
    elif code == "INSUFFICIENT_FUNDS":
        return "send_payment_reminder" if attempts_count == 0 else "stop_recovery"
    elif code == "CARD_EXPIRED":
        return "create_payment_link"
    elif code == "LIMIT_EXCEEDED":
        return "escalate_to_human"
    elif code == "CUSTOMER_DECLINED":
        return "send_payment_reminder" if attempts_count == 0 else "stop_recovery"
    else:
        return "escalate_to_human"

def select_best_mathematical_action(erv_table: dict, transaction: Transaction, customer: Customer, attempts_count: int) -> str:
    """
    Select the action that maximizes Expected Net Recovery, filtered by policy validation.
    This acts as our intelligent, context-aware ERV-driven decision maker.
    """
    best_action = "stop_recovery"
    best_ner = -9999999.0
    
    # Evaluate every candidate action against deterministic policy rules
    for action in erv_table.keys():
        if action in ["escalate_to_human", "stop_recovery"]:
            continue
            
        policy = check_policy(action, transaction, customer, attempts_count=attempts_count)
        if policy["allowed"] and policy["result"] == "APPROVED":
            ner = erv_table[action]["expected_net"]
            if ner > best_ner:
                best_ner = ner
                best_action = action
                
    return best_action

def process_transaction_recovery(transaction_id: str, db: Session, seed: int = None, use_llm: bool = True, rules_only: bool = False) -> dict:
    """
    Orchestrate the complete multi-step recovery workflow for a failed transaction.
    Runs a self-contained agent loop (up to 2 automated attempts) internally.
    Follows: Risk scoring -> LLM Diagnosis -> ERV Ranking (using LLM cause) -> Policy Guardrails -> Tool.
    """
    transaction = db.query(Transaction).filter(Transaction.transaction_id == transaction_id).first()
    if not transaction:
        return {"status": "ERROR", "reason": "Transaction not found."}

    if transaction.status.upper() == "SUCCESS":
        return {"status": "SUCCESS", "message": "Transaction is already successful."}

    customer = db.query(Customer).filter(Customer.customer_id == transaction.customer_id).first()
    invoice = db.query(Invoice).filter(Invoice.customer_id == transaction.customer_id).first()

    # Query any previous attempts logged in the DB
    execution_attempts = db.query(AuditLog).filter(
        AuditLog.transaction_id == transaction_id,
        AuditLog.stage == "execution"
    ).order_by(AuditLog.id.asc()).all()
    
    attempts_count = len(execution_attempts)
    
    # If already escalated or stopped in previous runs, exit early
    if any(a.agent_action in ["escalate_to_human", "stop_recovery"] for a in execution_attempts):
        return {
            "transaction_id": transaction_id,
            "execution_status": "SKIPPED",
            "amount_recovered": 0.0,
            "description": "Recovery already in terminal state."
        }

    last_res = None

    # Run the self-contained multi-step loop (up to MAX_ATTEMPTS = 2)
    while attempts_count < MAX_ATTEMPTS:
        db.refresh(transaction)
        if transaction.status.upper() == "SUCCESS":
            break

        # --- STEP 1: RISK ENGINE ---
        risk_result = calculate_risk_score(transaction, customer, invoice)
        log_audit(
            db=db,
            transaction_id=transaction_id,
            stage="risk_evaluation",
            reason=f"Risk Score: {risk_result['risk_score']} ({risk_result['risk_level']}). Attempts count: {attempts_count}."
        )

        success_rate = customer.previous_payment_success_rate if customer else 0.85
        ltv = customer.lifetime_value if customer else 0.0

        # --- STEP 2: DIAGNOSIS & RE-CALCULATING ERVs ---
        # Build attempts history context
        history_logs = db.query(AuditLog).filter(
            AuditLog.transaction_id == transaction_id,
            AuditLog.stage == "execution"
        ).order_by(AuditLog.id.asc()).all()
        history_list = [{"action": h.agent_action, "result": h.tool_result, "reason": h.reason} for h in history_logs]

        if rules_only:
            # Rules-Only Run uses the simple, static mapping
            recommended_action = get_simple_rules_action(transaction.failure_code, attempts_count)
            root_cause = get_root_cause_by_failure_code(transaction.failure_code)
            std_code = get_standard_failure_code_from_cause(root_cause)
            erv_table = calculate_ervs(transaction.amount, std_code, success_rate, ltv)
            reason = f"Rules-Only selected standard intervention based on error code: {transaction.failure_code}."
            why_not_alternatives = "ERV optimizations and customer context were bypassed."
        else:
            # RecoverAI Agent (either LLM or dynamic ERV solver fallback)
            # 1. Base ERV table using raw processor code
            raw_erv_table = calculate_ervs(transaction.amount, transaction.failure_code, success_rate, ltv)
            
            if use_llm:
                tx_dict = {
                    "transaction_id": transaction.transaction_id,
                    "amount": transaction.amount,
                    "payment_method": transaction.payment_method,
                    "failure_code": transaction.failure_code,
                    "retry_count": transaction.retry_count,
                    "timestamp": transaction.timestamp.isoformat() if transaction.timestamp else "",
                    "risk_score": risk_result["risk_score"],
                    "risk_level": risk_result["risk_level"]
                }
                cust_dict = {
                    "customer_id": customer.customer_id if customer else "",
                    "customer_type": customer.customer_type if customer else "new",
                    "lifetime_value": customer.lifetime_value if customer else 0.0,
                    "previous_payment_success_rate": success_rate,
                    "contact_preference": customer.contact_preference if customer else "email",
                    "risk_flag": customer.risk_flag if customer else False
                }
                inv_dict = {
                    "invoice_id": invoice.invoice_id,
                    "amount_due": invoice.amount_due,
                    "days_overdue": invoice.days_overdue,
                    "promise_to_pay": invoice.promise_to_pay
                } if invoice else None

                diagnosis = analyze_root_cause(tx_dict, cust_dict, inv_dict, history_list, raw_erv_table)
                root_cause = diagnosis["root_cause"]
                
                # Re-calculate ERVs based on the LLM's diagnosed root cause
                std_code = get_standard_failure_code_from_cause(root_cause)
                erv_table = calculate_ervs(transaction.amount, std_code, success_rate, ltv)
                
                # Economic Ranking selects the action that maximizes net recovery value
                recommended_action = select_best_mathematical_action(erv_table, transaction, customer, attempts_count)
                reason = diagnosis["reason"]
                why_not_alternatives = diagnosis.get("why_not_alternatives", "")
            else:
                # Fallback to context-aware ERV optimizer
                root_cause = get_root_cause_by_failure_code(transaction.failure_code)
                std_code = get_standard_failure_code_from_cause(root_cause)
                erv_table = calculate_ervs(transaction.amount, std_code, success_rate, ltv)
                recommended_action = select_best_mathematical_action(erv_table, transaction, customer, attempts_count)
                reason = f"ERV optimizer selected action with highest Expected Net Recovery (₹{erv_table[recommended_action]['expected_net']:,.2f}) based on cause: {root_cause}."
                why_not_alternatives = "Other actions have lower expected net recovery or are blocked by safety policies."

        log_audit(
            db=db,
            transaction_id=transaction_id,
            stage="root_cause_analysis",
            agent_action=recommended_action,
            reason=f"Diagnosed cause: {root_cause}. Reason: {reason} | Alternatives reasoning: {why_not_alternatives}"
        )

        # --- STEP 3: POLICY GUARDRAILS ---
        policy = check_policy(recommended_action, transaction, customer, attempts_count=attempts_count)
        log_audit(
            db=db,
            transaction_id=transaction_id,
            stage="policy_guardrail",
            agent_action=recommended_action,
            policy_result=policy["result"],
            reason=policy["reason"]
        )

        # Enforce policy checks
        final_action = recommended_action
        if policy["result"] == "ESCALATE":
            final_action = "escalate_to_human"
        elif policy["result"] in ["REJECTED", "STOP"]:
            final_action = "stop_recovery"

        # --- STEP 4: BOUNDED EXECUTION ---
        execution_result = execute_tool(final_action, transaction_id, db, seed)
        
        last_res = {
            "transaction_id": transaction_id,
            "risk_score": risk_result["risk_score"],
            "risk_level": risk_result["risk_level"],
            "root_cause": root_cause,
            "recommended_action": recommended_action,
            "policy_result": policy["result"],
            "final_action": final_action,
            "execution_status": execution_result["status"],
            "amount_recovered": execution_result["amount_recovered"],
            "description": execution_result["description"]
        }

        # Increment attempts counter
        attempts_count += 1

        # Break early if attempt succeeded or terminal action was executed
        if execution_result["status"] == "SUCCESS" or final_action in ["escalate_to_human", "stop_recovery"]:
            break

    # If the budget of 2 attempts was exhausted and transaction is still failed, escalate
    db.refresh(transaction)
    if transaction.status.upper() == "FAILED" and last_res and last_res["final_action"] not in ["escalate_to_human", "stop_recovery"]:
        # Execute terminal safety escalation
        log_audit(
            db=db,
            transaction_id=transaction_id,
            stage="policy_guardrail",
            agent_action="escalate_to_human",
            policy_result="APPROVED",
            reason="Automated recovery attempts exhausted (MAX_ATTEMPTS=2). Triggering safety escalation."
        )
        execution_result = execute_tool("escalate_to_human", transaction_id, db, seed)
        last_res = {
            "transaction_id": transaction_id,
            "risk_score": last_res["risk_score"],
            "risk_level": last_res["risk_level"],
            "root_cause": last_res["root_cause"],
            "recommended_action": last_res["recommended_action"],
            "policy_result": "APPROVED",
            "final_action": "escalate_to_human",
            "execution_status": "FAILURE",
            "amount_recovered": 0.0,
            "description": execution_result["description"]
        }

    return last_res or {
        "status": "SKIPPED",
        "description": "No attempts executed."
    }
