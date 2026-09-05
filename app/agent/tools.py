from datetime import datetime
from sqlalchemy.orm import Session
from app.db.models import Transaction, Customer, AuditLog, Invoice
from app.simulator.payment_simulator import simulate_recovery_attempt

def execute_tool(action: str, transaction_id: str, db: Session, seed: int = None, latency_ms: float = 0.0) -> dict:
    """
    Execute a recovery tool on a transaction.
    Interfaced with the simulator, updates DB records, and logs the execution stage.
    Preserves original transaction.status ('FAILED') and sets transaction.recovery_status.
    """
    transaction = db.query(Transaction).filter(Transaction.transaction_id == transaction_id).first()
    if not transaction:
        return {"status": "FAILURE", "amount_recovered": 0.0, "description": "Transaction not found."}
        
    customer = db.query(Customer).filter(Customer.customer_id == transaction.customer_id).first()
    
    # 2. Update transaction pre-action counters if relevant
    if action == "retry_payment":
        transaction.retry_count = (transaction.retry_count or 0) + 1
        db.add(transaction)
        db.flush()
        
    # 3. Simulate recovery action outcome
    sim_result = simulate_recovery_attempt(action, transaction, customer, seed)
    
    # 4. Handle recovery state updates (PRESERVING transaction.status as FAILED)
    if sim_result["status"] == "SUCCESS":
        transaction.recovery_status = "SUCCESS"
        transaction.recovered_amount = sim_result["amount_recovered"]
        db.add(transaction)
        
        # If there are active invoices, mark them resolved
        if customer:
            invoices = db.query(Invoice).filter(Invoice.customer_id == customer.customer_id).all()
            for inv in invoices:
                inv.days_overdue = 0
                if action == "mark_promise_to_pay":
                    inv.promise_to_pay = True
                db.add(inv)
    elif action == "escalate_to_human":
        transaction.recovery_status = "ESCALATED"
        db.add(transaction)
    elif action == "stop_recovery":
        transaction.recovery_status = "STOPPED"
        db.add(transaction)
            
    # 5. Log action execution stage in audit log
    audit_log = AuditLog(
        transaction_id=transaction.transaction_id,
        timestamp=datetime.now(),
        stage="execution",
        agent_action=action,
        policy_result="APPROVED",
        tool_result=sim_result["status"],
        amount_recovered=sim_result["amount_recovered"],
        reason=sim_result["description"],
        latency_ms=latency_ms
    )
    db.add(audit_log)
    
    db.commit()
    
    return sim_result
