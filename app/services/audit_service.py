from datetime import datetime
from sqlalchemy.orm import Session
from app.db.models import AuditLog

def log_audit(
    db: Session,
    transaction_id: str,
    stage: str,
    agent_action: str = None,
    policy_result: str = None,
    tool_result: str = None,
    amount_recovered: float = 0.0,
    reason: str = None
) -> AuditLog:
    """
    Log a record to the audit_logs table for audit trail tracking.
    """
    audit = AuditLog(
        transaction_id=transaction_id,
        timestamp=datetime.now(),
        stage=stage,
        agent_action=agent_action,
        policy_result=policy_result,
        tool_result=tool_result,
        amount_recovered=amount_recovered,
        reason=reason
    )
    db.add(audit)
    db.commit()
    return audit
