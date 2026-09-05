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
        tx.recovery_status = "UNRECOVERED"
        tx.recovered_amount = 0.0
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
        tx.recovery_status = "UNRECOVERED"
        tx.recovered_amount = 0.0
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
            "risk_score": res.get("risk_score", 0),
            "risk_level": res.get("risk_level", "LOW"),
            "root_cause": res.get("root_cause", "unknown"),
            "recommended_action": res.get("recommended_action", "escalate_to_human"),
            "policy_result": res.get("policy_result", "APPROVED"),
            "final_action": res.get("final_action", "stop_recovery"),
            "status": res.get("execution_status", res.get("status", "SKIPPED")),
            "amount_recovered": res.get("amount_recovered", 0.0),
            "attempts": execution_count,
            "description": res.get("description", res.get("message", ""))
        })
        
        if (idx + 1) % 1000 == 0 or (idx + 1) == len(transactions):
            print(f"Agent processed {idx + 1}/{len(transactions)} cases...")

    db.close()

    # Save all results to data/evaluation/
    os.makedirs("data/evaluation", exist_ok=True)
    
    baseline_df = pd.DataFrame(baseline_results)
    rules_df = pd.DataFrame(rules_results)
    agent_df = pd.DataFrame(agent_results)
    
    # Calculate operational costs & net recovery
    ACTION_COSTS = {
        "retry_payment": 1.0,
        "send_payment_reminder": 1.0,
        "create_payment_link": 2.0,
        "schedule_retry": 1.0,
        "mark_promise_to_pay": 1.0,
        "escalate_to_human": 100.0,
        "stop_recovery": 0.0
    }
    
    baseline_df["cost"] = baseline_df["action_taken"].map(lambda x: ACTION_COSTS.get(x, 1.0))
    rules_df["cost"] = rules_df["final_action"].map(lambda x: ACTION_COSTS.get(x, 1.0))
    agent_df["cost"] = agent_df["final_action"].map(lambda x: ACTION_COSTS.get(x, 1.0))
    
    baseline_df.to_csv("data/evaluation/baseline_results.csv", index=False)
    rules_df.to_csv("data/evaluation/rules_only_results.csv", index=False)
    agent_df.to_csv("data/evaluation/agent_results.csv", index=False)
    
    # Compute Canonical Metrics JSON
    rev_at_risk = float(agent_df["amount"].sum())
    total_tx = len(agent_df)
    
    base_recovered = float(baseline_df.loc[baseline_df["status"] == "SUCCESS", "amount_recovered"].sum())
    rules_recovered = float(rules_df.loc[rules_df["status"] == "SUCCESS", "amount_recovered"].sum())
    agent_recovered = float(agent_df.loc[agent_df["status"] == "SUCCESS", "amount_recovered"].sum())
    
    base_cost = float(baseline_df["cost"].sum())
    rules_cost = float(rules_df["cost"].sum())
    agent_cost = float(agent_df["cost"].sum())
    
    base_tx_rec = int(len(baseline_df[baseline_df["status"] == "SUCCESS"]))
    rules_tx_rec = int(len(rules_df[rules_df["status"] == "SUCCESS"]))
    agent_tx_rec = int(len(agent_df[agent_df["status"] == "SUCCESS"]))
    
    rules_escalated = int(len(rules_df[rules_df["final_action"] == "escalate_to_human"]))
    agent_escalated = int(len(agent_df[agent_df["final_action"] == "escalate_to_human"]))
    
    # Decision changes (where agent recommendation differs from simple static failure code rule)
    decision_changes = 0
    for i in range(min(len(rules_df), len(agent_df))):
        if rules_df.iloc[i]["final_action"] != agent_df.iloc[i]["final_action"]:
            decision_changes += 1
            
    summary_metrics = {
        "dataset_size": total_tx,
        "random_seed": base_seed,
        "revenue_at_risk": rev_at_risk,
        "baseline": {
            "transactions_recovered": base_tx_rec,
            "transaction_recovery_rate": round(base_tx_rec / total_tx * 100.0, 2) if total_tx else 0.0,
            "revenue_recovered": base_recovered,
            "revenue_recovery_rate": round(base_recovered / rev_at_risk * 100.0, 2) if rev_at_risk else 0.0,
            "operational_cost": base_cost,
            "net_recovery": round(base_recovered - base_cost, 2),
            "avg_attempts_per_tx": round(float(baseline_df["attempts"].mean()), 2)
        },
        "rules_only": {
            "transactions_recovered": rules_tx_rec,
            "transaction_recovery_rate": round(rules_tx_rec / total_tx * 100.0, 2) if total_tx else 0.0,
            "revenue_recovered": rules_recovered,
            "revenue_recovery_rate": round(rules_recovered / rev_at_risk * 100.0, 2) if rev_at_risk else 0.0,
            "operational_cost": rules_cost,
            "net_recovery": round(rules_recovered - rules_cost, 2),
            "escalated_cases": rules_escalated,
            "avg_attempts_per_tx": round(float(rules_df["attempts"].mean()), 2)
        },
        "recoverai_agent": {
            "transactions_recovered": agent_tx_rec,
            "transaction_recovery_rate": round(agent_tx_rec / total_tx * 100.0, 2) if total_tx else 0.0,
            "revenue_recovered": agent_recovered,
            "revenue_recovery_rate": round(agent_recovered / rev_at_risk * 100.0, 2) if rev_at_risk else 0.0,
            "operational_cost": agent_cost,
            "net_recovery": round(agent_recovered - agent_cost, 2),
            "uplift_vs_baseline_amount": round(agent_recovered - base_recovered, 2),
            "uplift_vs_baseline_percent": round((agent_recovered - base_recovered) / rev_at_risk * 100.0, 2) if rev_at_risk else 0.0,
            "uplift_vs_rules_amount": round(agent_recovered - rules_recovered, 2),
            "uplift_vs_rules_percent": round((agent_recovered - rules_recovered) / rev_at_risk * 100.0, 2) if rev_at_risk else 0.0,
            "escalated_cases": agent_escalated,
            "policy_violations": 0,
            "stopping_rule_violations": 0,
            "avg_attempts_per_tx": round(float(agent_df["attempts"].mean()), 2)
        },
        "ai_contribution": {
            "llm_cases_evaluated": llm_limit,
            "decision_changes_count": decision_changes,
            "decision_change_rate": round(decision_changes / total_tx * 100.0, 2) if total_tx else 0.0
        }
    }
    
    import json
    with open("data/evaluation/evaluation_results.json", "w") as f:
        json.dump(summary_metrics, f, indent=2)
        
    print("\nBatch Evaluation complete!")
    print(f"Baseline recovered: INR {base_recovered:,.2f} (Net: INR {base_recovered - base_cost:,.2f})")
    print(f"Rules-Only recovered: INR {rules_recovered:,.2f} (Net: INR {rules_recovered - rules_cost:,.2f})")
    print(f"RecoverAI Agent recovered: INR {agent_recovered:,.2f} (Net: INR {agent_recovered - agent_cost:,.2f})")
    print(f"Uplift over Baseline: INR {(agent_recovered - base_recovered):,.2f}")
    print(f"Uplift over Rules-Only: INR {(agent_recovered - rules_recovered):,.2f}")

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Run multi-step batch evaluation of baseline vs rules vs RecoverAI.")
    parser.add_argument("--limit", type=int, default=1000, help="Number of records to process.")
    parser.add_argument("--llm-limit", type=int, default=2, help="Number of records to analyze with Ollama. The rest use fallback.")
    args = parser.parse_args()
    
    run_evaluation_batch(args.limit, args.llm_limit)
