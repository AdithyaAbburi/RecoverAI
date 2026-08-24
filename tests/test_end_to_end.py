import pytest
from datetime import datetime
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from app.db.database import Base
from app.db.models import Customer, Transaction, Invoice, AuditLog
from app.services.recovery_service import process_transaction_recovery

# Setup in-memory sqlite for integration testing
TEST_DATABASE_URL = "sqlite:///:memory:"

@pytest.fixture
def db_session():
    engine = create_engine(TEST_DATABASE_URL, connect_args={"check_same_thread": False})
    TestingSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
    
    Base.metadata.create_all(bind=engine)
    db = TestingSessionLocal()
    
    try:
        yield db
    finally:
        db.close()
        Base.metadata.drop_all(bind=engine)

def test_end_to_end_successful_recovery_flow(db_session):
    # 1. Create customer and transaction
    customer = Customer(
        customer_id="C00001",
        customer_type="returning",
        lifetime_value=5000.0,
        previous_payment_success_rate=0.85,
        contact_preference="email",
        risk_flag=False
    )
    transaction = Transaction(
        transaction_id="TX00001",
        customer_id="C00001",
        amount=1500.0,
        payment_method="UPI",
        status="FAILED",
        failure_code="BANK_TIMEOUT",
        retry_count=0,
        timestamp=datetime.now()
    )
    db_session.add(customer)
    db_session.add(transaction)
    db_session.commit()
    
    # 2. Run recovery (we force use_llm=False to run deterministic fallback instantly in test)
    # Seed 1 gives a SUCCESS result in retry_payment for BANK_TIMEOUT in simulator
    res = process_transaction_recovery("TX00001", db_session, seed=1, use_llm=False, rules_only=True)
    
    # 3. Assertions on orchestrator response
    assert res["transaction_id"] == "TX00001"
    assert res["risk_level"] in ["LOW", "MEDIUM", "HIGH", "CRITICAL"]
    assert res["root_cause"] == "temporary_bank_failure"
    assert res["recommended_action"] == "retry_payment"
    assert res["policy_result"] == "APPROVED"
    assert res["final_action"] == "retry_payment"
    
    # Verify DB updates
    tx_db = db_session.query(Transaction).filter(Transaction.transaction_id == "TX00001").first()
    assert tx_db.retry_count == 1
    
    # Verify audit logs are created
    audits = db_session.query(AuditLog).filter(AuditLog.transaction_id == "TX00001").all()
    assert len(audits) >= 3  # risk_evaluation, root_cause_analysis, policy_guardrail, execution
    stages = [a.stage for a in audits]
    assert "risk_evaluation" in stages
    assert "root_cause_analysis" in stages
    assert "policy_guardrail" in stages
    assert "execution" in stages
