import pytest
from datetime import datetime
from fastapi.testclient import TestClient

from app.main import app
from app.db.database import engine, Base, SessionLocal
from app.db.models import Customer, Transaction

@pytest.fixture
def api_client():
    # Ensure tables exist in engine
    Base.metadata.create_all(bind=engine)
    
    # Pre-seed DB
    db = SessionLocal()
    try:
        c = db.query(Customer).filter(Customer.customer_id == "C99901").first()
        if not c:
            c = Customer(
                customer_id="C99901",
                customer_type="returning",
                lifetime_value=5000.0,
                previous_payment_success_rate=0.85,
                contact_preference="email",
                risk_flag=False
            )
            db.add(c)
            
        t = db.query(Transaction).filter(Transaction.transaction_id == "TX99901").first()
        if not t:
            t = Transaction(
                transaction_id="TX99901",
                customer_id="C99901",
                amount=1500.0,
                payment_method="UPI",
                status="FAILED",
                failure_code="BANK_TIMEOUT",
                retry_count=0,
                timestamp=datetime.now()
            )
            db.add(t)
        else:
            t.status = "FAILED"
            t.retry_count = 0
            db.add(t)
        db.commit()
    finally:
        db.close()

    client = TestClient(app)
    yield client

def test_api_root_endpoint(api_client):
    response = api_client.get("/")
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "ONLINE"
    assert data["service"] == "RecoverAI"

def test_api_single_recovery_trigger(api_client):
    response = api_client.post("/api/recovery/trigger/TX99901")
    assert response.status_code == 200
    data = response.json()
    assert data.get("status") in ["SUCCESS", "FAILURE", "SKIPPED"] or "execution_status" in data

def test_api_nonexistent_transaction(api_client):
    response = api_client.post("/api/recovery/trigger/TX_DOES_NOT_EXIST")
    assert response.status_code == 404
    data = response.json()
    assert data["detail"] == "Transaction not found"
