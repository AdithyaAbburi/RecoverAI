from sqlalchemy import Column, String, Float, Integer, Boolean, DateTime, ForeignKey, Date
from sqlalchemy.orm import relationship
from app.db.database import Base

class Customer(Base):
    __tablename__ = "customers"

    customer_id = Column(String, primary_key=True, index=True)
    customer_type = Column(String, nullable=False) # e.g., 'new', 'returning'
    lifetime_value = Column(Float, default=0.0)
    previous_payment_success_rate = Column(Float, default=1.0)
    contact_preference = Column(String, default="email") # e.g., 'email', 'sms', 'none'
    risk_flag = Column(Boolean, default=False)

    transactions = relationship("Transaction", back_populates="customer")
    invoices = relationship("Invoice", back_populates="customer")

class Transaction(Base):
    __tablename__ = "transactions"

    transaction_id = Column(String, primary_key=True, index=True)
    customer_id = Column(String, ForeignKey("customers.customer_id"), nullable=False, index=True)
    amount = Column(Float, nullable=False)
    payment_method = Column(String, nullable=False) # e.g., 'UPI', 'CARD', 'NETBANKING'
    status = Column(String, nullable=False) # e.g., 'FAILED', 'SUCCESS', 'PENDING'
    failure_code = Column(String, nullable=True) # e.g., 'BANK_TIMEOUT', 'INSUFFICIENT_FUNDS', etc.
    retry_count = Column(Integer, default=0)
    timestamp = Column(DateTime, nullable=False)

    customer = relationship("Customer", back_populates="transactions")
    audit_logs = relationship("AuditLog", back_populates="transaction")

class Invoice(Base):
    __tablename__ = "invoices"

    invoice_id = Column(String, primary_key=True, index=True)
    customer_id = Column(String, ForeignKey("customers.customer_id"), nullable=False, index=True)
    amount_due = Column(Float, nullable=False)
    due_date = Column(Date, nullable=False)
    days_overdue = Column(Integer, default=0)
    promise_to_pay = Column(Boolean, default=False)

    customer = relationship("Customer", back_populates="invoices")

class AuditLog(Base):
    __tablename__ = "audit_logs"

    id = Column(Integer, primary_key=True, index=True, autoincrement=True)
    transaction_id = Column(String, ForeignKey("transactions.transaction_id"), nullable=False, index=True)
    timestamp = Column(DateTime, nullable=False)
    stage = Column(String, nullable=False) # e.g., 'risk_evaluation', 'root_cause_analysis', 'policy_guardrail', 'execution'
    agent_action = Column(String, nullable=True) # e.g., 'retry_payment', 'send_payment_reminder', etc.
    policy_result = Column(String, nullable=True) # e.g., 'APPROVED', 'REJECTED', 'ESCALATED'
    tool_result = Column(String, nullable=True) # e.g., 'SUCCESS', 'FAILURE'
    amount_recovered = Column(Float, default=0.0)
    reason = Column(String, nullable=True)

    transaction = relationship("Transaction", back_populates="audit_logs")
