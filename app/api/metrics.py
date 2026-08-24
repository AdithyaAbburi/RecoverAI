from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session
from sqlalchemy import func
from app.db.database import get_db
from app.db import models

router = APIRouter(prefix="/metrics", tags=["metrics"])

@router.get("/")
def get_dashboard_metrics(db: Session = Depends(get_db)):
    """
    Calculate and return key performance indicators (KPIs) for recovery ops.
    """
    # 1. Total transactions and revenue at risk
    # Revenue at risk includes any transaction that started as FAILED.
    # Since our database starts with all FAILED transactions, total revenue at risk is sum of all transactions.
    total_tx = db.query(models.Transaction).count()
    total_revenue_at_risk = db.query(func.sum(models.Transaction.amount)).scalar() or 0.0
    
    # 2. Recovered Transactions & Revenue
    recovered_tx = db.query(models.Transaction).filter(models.Transaction.status == "SUCCESS").count()
    recovered_revenue = db.query(func.sum(models.Transaction.amount)).filter(
        models.Transaction.status == "SUCCESS"
    ).scalar() or 0.0
    
    # 3. Recovery rates
    recovery_rate_pct = (recovered_revenue / total_revenue_at_risk * 100.0) if total_revenue_at_risk > 0 else 0.0
    tx_recovery_rate_pct = (recovered_tx / total_tx * 100.0) if total_tx > 0 else 0.0
    
    # 4. Action execution breakdown from AuditLog (filtering stage = 'execution')
    action_counts = db.query(
        models.AuditLog.agent_action,
        func.count(models.AuditLog.id)
    ).filter(models.AuditLog.stage == "execution").group_by(models.AuditLog.agent_action).all()
    
    actions_breakdown = {action: count for action, count in action_counts}
    
    # 5. Policy results breakdown (stage = 'policy_guardrail')
    policy_counts = db.query(
        models.AuditLog.policy_result,
        func.count(models.AuditLog.id)
    ).filter(models.AuditLog.stage == "policy_guardrail").group_by(models.AuditLog.policy_result).all()
    
    policy_breakdown = {res: count for res, count in policy_counts if res}
    
    # 6. Failure codes breakdown
    failure_counts = db.query(
        models.Transaction.failure_code,
        func.count(models.Transaction.transaction_id)
    ).group_by(models.Transaction.failure_code).all()
    
    failure_breakdown = {code: count for code, count in failure_counts if code}

    return {
        "total_transactions": total_tx,
        "revenue_at_risk": total_revenue_at_risk,
        "recovered_transactions": recovered_tx,
        "recovered_revenue": recovered_revenue,
        "recovery_rate_percentage": round(recovery_rate_pct, 2),
        "transaction_recovery_rate_percentage": round(tx_recovery_rate_pct, 2),
        "actions_breakdown": actions_breakdown,
        "policy_breakdown": policy_breakdown,
        "failure_breakdown": failure_breakdown
    }
