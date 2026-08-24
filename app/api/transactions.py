from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from typing import List
from app.db.database import get_db
from app.db import models
from pydantic import BaseModel
from datetime import datetime

router = APIRouter(prefix="/transactions", tags=["transactions"])

class TransactionSchema(BaseModel):
    transaction_id: str
    customer_id: str
    amount: float
    payment_method: str
    status: str
    failure_code: str = None
    retry_count: int = 0
    timestamp: datetime

    class Config:
        from_attributes = True

@router.get("/", response_model=List[TransactionSchema])
def list_transactions(db: Session = Depends(get_db)):
    transactions = db.query(models.Transaction).all()
    return transactions

@router.get("/{transaction_id}")
def get_transaction_details(transaction_id: str, db: Session = Depends(get_db)):
    transaction = db.query(models.Transaction).filter(models.Transaction.transaction_id == transaction_id).first()
    if not transaction:
        raise HTTPException(status_code=404, detail="Transaction not found")
        
    customer = db.query(models.Customer).filter(models.Customer.customer_id == transaction.customer_id).first()
    invoice = db.query(models.Invoice).filter(models.Invoice.customer_id == transaction.customer_id).first()
    
    # Audit log trail
    audits = db.query(models.AuditLog).filter(models.AuditLog.transaction_id == transaction_id).order_by(models.AuditLog.id.asc()).all()
    
    return {
        "transaction": transaction,
        "customer": customer,
        "invoice": invoice,
        "audit_trail": [
            {
                "id": a.id,
                "timestamp": a.timestamp,
                "stage": a.stage,
                "agent_action": a.agent_action,
                "policy_result": a.policy_result,
                "tool_result": a.tool_result,
                "amount_recovered": a.amount_recovered,
                "reason": a.reason
            }
            for a in audits
        ]
    }
