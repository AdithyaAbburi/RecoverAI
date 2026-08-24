import os
import argparse
import pandas as pd

# Add root folder to sys.path
import sys
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app.db.database import SessionLocal
from app.db import models
from app.services.recovery_service import process_transaction_recovery
from app.simulator.payment_simulator import simulate_recovery_attempt

def run_evaluation_batch(limit: int, llm_limit: int):
    """
    Run evaluation batch. The multi-step loops are self-contained inside process_transaction_recovery.
    Ensures identical simulator seeds across runs for mathematical validity.
    """
    db = SessionLocal()
    
    # Fetch transactions to process
    transactions = db.query(models.Transaction).order_by(models.Transaction.transaction_id.asc()).limit(limit).all()
    
    if not transactions:
        print("Error: No transactions found in database. Run generate_data.py first.")
        db.close()
        return

    print(f"Loaded {len(transactions)} transactions for evaluation.")
    base_seed = 42

    # ------------------------------------
    # 1. NAIVE BASELINE RUN (1 Attempt Max)
    # ------------------------------------
    print("Starting Naive Baseline Run...")
    baseline_results = []
    
    for idx, tx in enumerate(transactions):
        customer = db.query(models.Customer).filter(models.Customer.customer_id == tx.customer_id).first()
        contact_pref = customer.contact_preference.lower() if customer else "email"
        seed_val = base_seed + idx
        
        # Naive: try one retry if amount < 25k and not opted out
        if tx.amount >= 25000.0 or contact_pref == "none":
            status = "FAILED"
            recovered = 0.0
            action = "stop_recovery"
            attempts = 0
            desc = "Baseline stopped: high value or opted out."
        else:
            sim = simulate_recovery_attempt("retry_payment", tx, customer, seed=seed_val)
            status = sim["status"]
            recovered = sim["amount_recovered"]
            action = "retry_payment"
            attempts = 1
            desc = sim["description"]
            
        baseline_results.append({
            "transaction_id": tx.transaction_id,
            "amount": tx.amount,
            "failure_code": tx.failure_code,
            "action_taken": action,
            "status": status,
            "amount_recovered": recovered,
            "attempts": attempts,
            "description": desc
        })
    print("Baseline Run complete.")

    # ------------------------------------
    # 2. RULES-ONLY RUN (2 Attempts Max, ERV-Optimized)
    # ------------------------------------
    print("Starting Rules-Only Run...")
    rules_results = []
    
    # Reset DB state before rules run
    for tx in transactions:
        tx.status = "FAILED"
        tx.retry_count = 0
    db.commit()
    
    try:
        db.query(models.AuditLog).delete()
        db.commit()
    except Exception as e:
        db.rollback()

    for idx, tx in enumerate(transactions):
        seed_val = base_seed + idx
        
        # Process transaction once. It owns the loop internally!
        res = process_transaction_recovery(tx.transaction_id, db, seed=seed_val, use_llm=False, rules_only=True)
        
        # Count execution attempts logged in DB
        execution_count = db.query(models.AuditLog).filter(
            models.AuditLog.transaction_id == tx.transaction_id,
            models.AuditLog.stage == "execution"
        ).count()

        rules_results.append({
            "transaction_id": tx.transaction_id,
            "amount": tx.amount,
            "failure_code": tx.failure_code,
            "risk_score": res["risk_score"],
            "risk_level": res["risk_level"],
            "final_action": res["final_action"],
            "status": res["execution_status"],
            "amount_recovered": res["amount_recovered"],
            "attempts": execution_count,
            "description": res["description"]
        })
    print("Rules-Only Run complete.")

    # ------------------------------------
    # 3. RECOVERAI AGENT RUN (2 Attempts Max + LLM)
    # ------------------------------------
    print(f"Starting RecoverAI Agent Run (LLM Limit: {llm_limit})...")
    agent_results = []
    
    # Reset DB state before agent run
    for tx in transactions:
        tx.status = "FAILED"
        tx.retry_count = 0
    db.commit()
    
    try:
        db.query(models.AuditLog).delete()
        db.commit()
    except Exception as e:
        db.rollback()

    for idx, tx in enumerate(transactions):
        seed_val = base_seed + idx
        use_llm = idx < llm_limit
        
        # Process transaction once. It owns the loop internally!
        res = process_transaction_recovery(tx.transaction_id, db, seed=seed_val, use_llm=use_llm, rules_only=False)
        
        # Count execution attempts logged in DB
        execution_count = db.query(models.AuditLog).filter(
            models.AuditLog.transaction_id == tx.transaction_id,
            models.AuditLog.stage == "execution"
        ).count()

        agent_results.append({
            "transaction_id": tx.transaction_id,
            "amount": tx.amount,
            "failure_code": tx.failure_code,
            "risk_score": res["risk_score"],
            "risk_level": res["risk_level"],
            "root_cause": res.get("root_cause", "unknown"),
            "recommended_action": res.get("recommended_action", "escalate_to_human"),
            "policy_result": res.get("policy_result", "APPROVED"),
            "final_action": res["final_action"],
            "status": res["execution_status"],
            "amount_recovered": res["amount_recovered"],
            "attempts": execution_count,
            "description": res["description"]
        })
        
        if (idx + 1) % 1000 == 0 or (idx + 1) == len(transactions):
            print(f"Agent processed {idx + 1}/{len(transactions)} cases...")

    db.close()

    # Save all results to data/evaluation/
    os.makedirs("data/evaluation", exist_ok=True)
    
    baseline_df = pd.DataFrame(baseline_results)
    rules_df = pd.DataFrame(rules_results)
    agent_df = pd.DataFrame(agent_results)
    
    baseline_df.to_csv("data/evaluation/baseline_results.csv", index=False)
    rules_df.to_csv("data/evaluation/rules_only_results.csv", index=False)
    agent_df.to_csv("data/evaluation/agent_results.csv", index=False)
    
    print("\nBatch Evaluation complete!")
    print(f"Baseline recovered: INR {baseline_df['amount_recovered'].sum():,.2f}")
    print(f"Rules-Only recovered: INR {rules_df['amount_recovered'].sum():,.2f}")
    print(f"RecoverAI Agent recovered: INR {agent_df['amount_recovered'].sum():,.2f}")
    print(f"Uplift over Baseline: INR {(agent_df['amount_recovered'].sum() - baseline_df['amount_recovered'].sum()):,.2f}")
    print(f"Uplift over Rules-Only: INR {(agent_df['amount_recovered'].sum() - rules_df['amount_recovered'].sum()):,.2f}")

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Run multi-step batch evaluation of baseline vs rules vs RecoverAI.")
    parser.add_argument("--limit", type=int, default=5000, help="Number of records to process.")
    parser.add_argument("--llm-limit", type=int, default=50, help="Number of records to analyze with Ollama. The rest use fallback.")
    args = parser.parse_args()
    
    run_evaluation_batch(args.limit, args.llm_limit)
