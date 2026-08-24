import pytest
from datetime import datetime
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.db.models import Base, Transaction, Customer, Invoice, AuditLog
from app.agent.orchestrator import process_transaction_recovery, select_best_mathematical_action
from app.agent.erv_engine import calculate_ervs
from app.policy.policy_engine import check_policy

@pytest.fixture
def in_memory_db():
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(bind=engine)
    Session = sessionmaker(bind=engine)
    session = Session()
    try:
        yield session
    finally:
        session.close()

def test_attempt_3_never_executes(in_memory_db, monkeypatch):
    # Mock simulator to always return FAILURE
    monkeypatch.setattr(
        "app.agent.tools.simulate_recovery_attempt",
        lambda action, tx, cust, seed: {
            "status": "FAILURE",
            "amount_recovered": 0.0,
            "description": "Mocked simulator failure."
        }
    )

    # Setup customer and transaction
    customer = Customer(
        customer_id="C00999",
        customer_type="new",
        lifetime_value=100.0,
        previous_payment_success_rate=0.85,
        contact_preference="email",
        risk_flag=False
    )
    transaction = Transaction(
        transaction_id="TX00999",
        customer_id="C00999",
        amount=1000.0,
        payment_method="CARD",
        status="FAILED",
        failure_code="BANK_TIMEOUT",
        retry_count=0,
        timestamp=datetime.now()
    )
    in_memory_db.add(customer)
    in_memory_db.add(transaction)
    in_memory_db.commit()

    # Process recovery
    res = process_transaction_recovery("TX00999", in_memory_db, seed=1, use_llm=False, rules_only=True)
    
    assert res["final_action"] == "escalate_to_human"
    assert res["execution_status"] == "FAILURE"

    # Count executions in DB
    exec_logs = in_memory_db.query(AuditLog).filter(
        AuditLog.transaction_id == "TX00999",
        AuditLog.stage == "execution"
    ).all()
    
    # 2 automated attempts + 1 final escalation log
    assert len(exec_logs) == 3
    assert exec_logs[0].agent_action == "retry_payment"
    assert exec_logs[1].agent_action == "create_payment_link"
    assert exec_logs[2].agent_action == "escalate_to_human"

    # Calling process_transaction_recovery again should skip execution
    res_skipped = process_transaction_recovery("TX00999", in_memory_db, seed=1, use_llm=False, rules_only=True)
    assert res_skipped["execution_status"] == "SKIPPED"
    
    # Verify no more execution logs were added
    exec_logs_after = in_memory_db.query(AuditLog).filter(
        AuditLog.transaction_id == "TX00999",
        AuditLog.stage == "execution"
    ).all()
    assert len(exec_logs_after) == 3

def test_erv_selects_best_safe_action(in_memory_db):
    customer = Customer(
        customer_id="C00888",
        customer_type="new",
        lifetime_value=5000.0,
        previous_payment_success_rate=0.85,
        contact_preference="email",
        risk_flag=False
    )
    transaction = Transaction(
        transaction_id="TX00888",
        customer_id="C00888",
        amount=5000.0,
        payment_method="CARD",
        status="FAILED",
        failure_code="INSUFFICIENT_FUNDS",
        retry_count=0,
        timestamp=datetime.now()
    )
    in_memory_db.add(customer)
    in_memory_db.add(transaction)
    in_memory_db.commit()

    erv_table = calculate_ervs(transaction.amount, transaction.failure_code, 0.85, 5000.0)
    
    # Under insufficient funds, create_payment_link (65% prob, INR 2 cost -> NER 3248) 
    # beats send_payment_reminder (60% prob, INR 1 cost -> NER 2999).
    best_action = select_best_mathematical_action(erv_table, transaction, customer, attempts_count=0)
    assert best_action == "create_payment_link"

def test_high_value_rules_escalate(in_memory_db):
    customer = Customer(
        customer_id="C00777",
        customer_type="returning",
        lifetime_value=10000.0,
        previous_payment_success_rate=0.95,
        contact_preference="email",
        risk_flag=False
    )
    # High value transaction >= 25,000
    transaction = Transaction(
        transaction_id="TX00777",
        customer_id="C00777",
        amount=35000.0,
        payment_method="CARD",
        status="FAILED",
        failure_code="BANK_TIMEOUT",
        retry_count=0,
        timestamp=datetime.now()
    )
    in_memory_db.add(customer)
    in_memory_db.add(transaction)
    in_memory_db.commit()

    res = process_transaction_recovery("TX00777", in_memory_db, seed=1, use_llm=False)
    
    assert res["policy_result"] == "ESCALATE"
    assert res["final_action"] == "escalate_to_human"
    assert res["execution_status"] == "FAILURE"

def test_opt_out_blocks_contact_on_orchestrator(in_memory_db):
    customer = Customer(
        customer_id="C00666",
        customer_type="returning",
        lifetime_value=10000.0,
        previous_payment_success_rate=0.95,
        contact_preference="none",  # Opt-out
        risk_flag=False
    )
    transaction = Transaction(
        transaction_id="TX00666",
        customer_id="C00666",
        amount=1000.0,
        payment_method="CARD",
        status="FAILED",
        failure_code="INSUFFICIENT_FUNDS",
        retry_count=0,
        timestamp=datetime.now()
    )
    in_memory_db.add(customer)
    in_memory_db.add(transaction)
    in_memory_db.commit()

    res = process_transaction_recovery("TX00666", in_memory_db, seed=1, use_llm=False, rules_only=True)
    
    assert res["policy_result"] == "REJECTED"
    assert res["final_action"] == "stop_recovery"
