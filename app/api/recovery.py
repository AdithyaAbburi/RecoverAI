from fastapi import APIRouter, Depends, HTTPException, BackgroundTasks
from sqlalchemy.orm import Session
from app.db.database import get_db
from app.db import models
from app.services.recovery_service import process_transaction_recovery
from pydantic import BaseModel
from typing import List

router = APIRouter(prefix="/recovery", tags=["recovery"])

class BatchTriggerResponse(BaseModel):
    total_processed: int
    successful_recovery: int
    amount_recovered: float
    escalated_count: int
    stopped_count: int

@router.post("/trigger/{transaction_id}")
def trigger_recovery(transaction_id: str, db: Session = Depends(get_db)):
    """
    Trigger the recovery process for a single failed transaction.
    """
    transaction = db.query(models.Transaction).filter(models.Transaction.transaction_id == transaction_id).first()
    if not transaction:
        raise HTTPException(status_code=404, detail="Transaction not found")
        
    if transaction.status.upper() == "SUCCESS":
        return {"status": "SUCCESS", "message": "Transaction is already recovered/successful."}
        
    result = process_transaction_recovery(transaction_id, db)
    return result

@router.post("/trigger-batch", response_model=BatchTriggerResponse)
def trigger_batch_recovery(limit: int = 50, db: Session = Depends(get_db)):
    """
    Trigger recovery for a batch of failed transactions (capped to limit).
    """
    failed_transactions = db.query(models.Transaction).filter(
        models.Transaction.status == "FAILED"
    ).limit(limit).all()
    
    total_processed = 0
    successful_recovery = 0
    amount_recovered = 0.0
    escalated_count = 0
    stopped_count = 0
    
    for tx in failed_transactions:
        # Run recovery process
        res = process_transaction_recovery(tx.transaction_id, db)
        total_processed += 1
        
        if res.get("execution_status") == "SUCCESS":
            successful_recovery += 1
            amount_recovered += res.get("amount_recovered", 0.0)
        
        final_action = res.get("final_action")
        if final_action == "escalate_to_human":
            escalated_count += 1
        elif final_action == "stop_recovery":
            stopped_count += 1
            
    return {
        "total_processed": total_processed,
        "successful_recovery": successful_recovery,
        "amount_recovered": amount_recovered,
        "escalated_count": escalated_count,
        "stopped_count": stopped_count
    }
