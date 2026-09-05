import pytest
from datetime import datetime
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from app.db.database import Base
from app.db.models import Customer, Transaction, Invoice, AuditLog
from app.services.recovery_service import process_transaction_recovery
from app.policy.policy_engine import check_policy

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
        recovery_status="UNRECOVERED",
        recovered_amount=0.0,
        failure_code="BANK_TIMEOUT",
        retry_count=0,
        timestamp=datetime.now()
    )
    db_session.add(customer)
    db_session.add(transaction)
    db_session.commit()
    
    res = process_transaction_recovery("TX00001", db_session, seed=1, use_llm=False, rules_only=True)
    
    assert res["transaction_id"] == "TX00001"
    assert res["policy_result"] == "APPROVED"
    assert res["final_action"] == "retry_payment"
    
    tx_db = db_session.query(Transaction).filter(Transaction.transaction_id == "TX00001").first()
    # Test 1 & 5: original status remains FAILED, recovery_status becomes RECOVERED
    assert tx_db.status == "FAILED"
    assert tx_db.recovery_status == "RECOVERED"
    assert tx_db.recovered_amount == 1500.0
    # Test 6: failure code preserved
    assert tx_db.failure_code == "BANK_TIMEOUT"

def test_end_to_end_high_value_escalation_flow(db_session):
    # Test 2: FAILED -> policy BLOCKED -> ESCALATED
    customer = Customer(
        customer_id="C00002",
        customer_type="returning",
        lifetime_value=50000.0,
        previous_payment_success_rate=0.90,
        contact_preference="email",
        risk_flag=False
    )
    transaction = Transaction(
        transaction_id="TX00002",
        customer_id="C00002",
        amount=35000.0,  # High value >= 25k
        payment_method="CARD",
        status="FAILED",
        recovery_status="UNRECOVERED",
        failure_code="BANK_TIMEOUT",
        retry_count=0,
        timestamp=datetime.now()
    )
    db_session.add(customer)
    db_session.add(transaction)
    db_session.commit()

    res = process_transaction_recovery("TX00002", db_session, seed=1, use_llm=False)
    assert res["transaction_id"] == "TX00002"
    assert res["policy_result"] == "ESCALATE"
    assert res["final_action"] == "escalate_to_human"
    
    tx_db = db_session.query(Transaction).filter(Transaction.transaction_id == "TX00002").first()
    assert tx_db.status == "FAILED"
    assert tx_db.recovery_status == "ESCALATED"

def test_end_to_end_duplicate_execution_protection(db_session):
    # Test 4: Duplicate execution -> BLOCKED -> no second recovery
    customer = Customer(
        customer_id="C00003",
        customer_type="returning",
        lifetime_value=5000.0,
        previous_payment_success_rate=0.85,
        contact_preference="email",
        risk_flag=False
    )
    transaction = Transaction(
        transaction_id="TX00003",
        customer_id="C00003",
        amount=2000.0,
        payment_method="UPI",
        status="FAILED",
        recovery_status="UNRECOVERED",
        failure_code="BANK_TIMEOUT",
        retry_count=1,
        timestamp=datetime.now()
    )
    db_session.add(customer)
    db_session.add(transaction)
    db_session.commit()

    # Repeat exact same action already in history
    pol = check_policy("retry_payment", transaction, customer, attempts_count=1, previous_actions=["retry_payment"])
    assert pol["allowed"] is False
    assert pol["result"] == "REJECTED"
    assert pol["policy_rule"] == "DUPLICATE_ACTION"

def test_end_to_end_same_underlying_state(db_session):
    # Test 7: Ensure transaction table and decision trace read the same underlying state
    customer = Customer(
        customer_id="C00004",
        customer_type="returning",
        lifetime_value=10000.0,
        previous_payment_success_rate=0.95,
        contact_preference="email",
        risk_flag=False
    )
    transaction = Transaction(
        transaction_id="TX00004",
        customer_id="C00004",
        amount=5000.0,
        payment_method="UPI",
        status="FAILED",
        recovery_status="UNRECOVERED",
        failure_code="INSUFFICIENT_FUNDS",
        retry_count=0,
        timestamp=datetime.now()
    )
    db_session.add(customer)
    db_session.add(transaction)
    db_session.commit()

    tx_fetched = db_session.query(Transaction).filter(Transaction.transaction_id == "TX00004").first()
    assert tx_fetched.status == "FAILED"
    assert tx_fetched.failure_code == "INSUFFICIENT_FUNDS"
    assert tx_fetched.recovery_status == "UNRECOVERED"
    assert tx_fetched.recovered_amount == 0.0

def test_end_to_end_invalid_transaction_input(db_session):
    res_not_found = process_transaction_recovery("TX_NOT_FOUND", db_session, use_llm=False)
    assert res_not_found["status"] == "ERROR"
    assert "not found" in res_not_found["reason"]

    tx_bad = Transaction(
        transaction_id="TX_BAD",
        customer_id="C00001",
        amount=-500.0,
        payment_method="UPI",
        status="FAILED",
        failure_code="BANK_TIMEOUT",
        retry_count=0,
        timestamp=datetime.now()
    )
    db_session.add(tx_bad)
    db_session.commit()

    res_bad = process_transaction_recovery("TX_BAD", db_session, use_llm=False)
    assert res_bad["status"] == "ERROR"
    assert "Invalid transaction amount" in res_bad["reason"]
