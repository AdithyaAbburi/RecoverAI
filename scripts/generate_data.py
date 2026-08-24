import os
import random
import argparse
from datetime import datetime, timedelta
import pandas as pd
from faker import Faker

# Add root folder to sys.path so we can import app modules
import sys
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app.db.database import engine, SessionLocal, Base
from app.db.models import Customer, Transaction, Invoice

# Set a fixed seed for reproducible synthetic data generation
SEED = 42
random.seed(SEED)
fake = Faker()
Faker.seed(SEED)

def generate_synthetic_data(num_records: int):
    """
    Generate synthetic customers, transactions, and invoices.
    Populates the database and saves copy as CSVs in data/generated/.
    """
    # Create tables
    Base.metadata.create_all(bind=engine)
    
    db = SessionLocal()
    
    # Clean previous data to ensure a clean run
    try:
        db.query(Invoice).delete()
        db.query(Transaction).delete()
        db.query(Customer).delete()
        db.commit()
    except Exception as e:
        db.rollback()
        print(f"Warning: could not clean tables: {e}")

    print(f"Generating synthetic dataset of {num_records} failed transactions...")

    # 1. Generate unique customers (approx 0.7 * num_records to allow repeat customers)
    num_customers = int(num_records * 0.7)
    customers_list = []
    
    for i in range(1, num_customers + 1):
        cust_id = f"C{i:05d}"
        
        # Customer properties
        customer_type = random.choices(["new", "returning"], weights=[0.4, 0.6])[0]
        lifetime_value = 0.0 if customer_type == "new" else round(random.uniform(1000, 150000), 2)
        
        # Previous success rate
        if customer_type == "new":
            previous_payment_success_rate = 1.0
        else:
            previous_payment_success_rate = round(random.uniform(0.4, 0.98), 2)
            
        contact_preference = random.choices(["email", "sms", "none"], weights=[0.6, 0.3, 0.1])[0]
        
        # Fraud risk flag (2% chance of being high-risk fraud flag)
        risk_flag = random.random() < 0.02

        cust = Customer(
            customer_id=cust_id,
            customer_type=customer_type,
            lifetime_value=lifetime_value,
            previous_payment_success_rate=previous_payment_success_rate,
            contact_preference=contact_preference,
            risk_flag=risk_flag
        )
        db.add(cust)
        customers_list.append(cust)

    db.commit()
    print(f"Successfully generated {num_customers} customers.")

    # 2. Generate failed transactions
    failure_codes = [
        "BANK_TIMEOUT",
        "TEMPORARY_BANK_ERROR",
        "INSUFFICIENT_FUNDS",
        "CARD_EXPIRED",
        "LIMIT_EXCEEDED",
        "CUSTOMER_DECLINED"
    ]
    failure_weights = [0.20, 0.20, 0.30, 0.15, 0.10, 0.05]
    payment_methods = ["UPI", "CARD", "NETBANKING"]

    transactions_list = []
    invoices_list = []

    # Let's ensure some transactions are > ₹25,000 for high-value protection testing
    # 5% of transactions will be high-value
    for t_idx in range(1, num_records + 1):
        tx_id = f"TX{t_idx:05d}"
        cust = random.choice(customers_list)
        
        # Value logic
        is_high_value = random.random() < 0.05
        if is_high_value:
            amount = round(random.uniform(25000, 80000), 2)
        else:
            amount = round(random.uniform(500, 24900), 2)

        payment_method = random.choice(payment_methods)
        
        # failure distribution
        failure_code = random.choices(failure_codes, weights=failure_weights)[0]
        
        # Adjust payment method for CARD_EXPIRED
        if failure_code == "CARD_EXPIRED":
            payment_method = "CARD"
            
        timestamp = datetime.now() - timedelta(
            days=random.randint(1, 30),
            hours=random.randint(0, 23),
            minutes=random.randint(0, 59)
        )

        tx = Transaction(
            transaction_id=tx_id,
            customer_id=cust.customer_id,
            amount=amount,
            payment_method=payment_method,
            status="FAILED", # Synthesized failed batch
            failure_code=failure_code,
            retry_count=0,
            timestamp=timestamp
        )
        db.add(tx)
        transactions_list.append(tx)

        # 3. Create active invoices for overdue payments (e.g. INSUFFICIENT_FUNDS, CUSTOMER_DECLINED)
        # Represents B2B/Subscription receivables overdue context
        if failure_code in ["INSUFFICIENT_FUNDS", "CUSTOMER_DECLINED"] or random.random() < 0.20:
            inv_id = f"INV{t_idx:05d}"
            days_overdue = random.randint(1, 45)
            due_date = (timestamp - timedelta(days=days_overdue)).date()
            amount_due = amount

            inv = Invoice(
                invoice_id=inv_id,
                customer_id=cust.customer_id,
                amount_due=amount_due,
                due_date=due_date,
                days_overdue=days_overdue,
                promise_to_pay=False
            )
            db.add(inv)
            invoices_list.append(inv)

    db.commit()
    db.close()
    
    print(f"Successfully generated {num_records} failed transactions.")
    print(f"Successfully generated {len(invoices_list)} invoice records.")

    # Export to CSV for audit and dashboard use
    os.makedirs("data/generated", exist_ok=True)
    
    # Query back all records from database to build DataFrame
    db = SessionLocal()
    
    customers_df = pd.read_sql(db.query(Customer).statement, db.bind)
    transactions_df = pd.read_sql(db.query(Transaction).statement, db.bind)
    invoices_df = pd.read_sql(db.query(Invoice).statement, db.bind)
    
    db.close()
    
    customers_df.to_csv("data/generated/customers.csv", index=False)
    transactions_df.to_csv("data/generated/transactions.csv", index=False)
    invoices_df.to_csv("data/generated/invoices.csv", index=False)
    
    print("CSV data exports complete in data/generated/")

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Generate synthetic failed transaction dataset.")
    parser.add_argument("--count", type=int, default=5000, help="Number of failed transactions to generate.")
    args = parser.parse_args()
    
    generate_synthetic_data(args.count)
