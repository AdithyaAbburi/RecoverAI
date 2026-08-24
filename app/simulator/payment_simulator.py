import random
from app.db.models import Transaction, Customer
from app.agent.erv_engine import get_success_probability

def simulate_recovery_attempt(action: str, transaction: Transaction, customer: Customer, seed: int = None) -> dict:
    """
    Simulate the outcome of a recovery action using context-aware probabilities from the ERV engine.
    Uses seeded random for reproducible evaluation.
    """
    if seed is not None:
        random.seed(seed)
        
    amount = float(transaction.amount or 0)
    
    # Safe retrieval of customer metrics (supports mock objects in tests)
    success_rate = getattr(customer, "previous_payment_success_rate", 0.85) if customer else 0.85
    ltv = getattr(customer, "lifetime_value", 0.0) if customer else 0.0
    
    prob = get_success_probability(action, transaction.failure_code, success_rate, ltv)
    
    # Default safety exit actions are terminal (they register as failure/unrecovered in automated batch)
    if action == "escalate_to_human":
        return {
            "status": "FAILURE",
            "amount_recovered": 0.0,
            "description": "Case escalated to human review. Automated recovery paused."
        }
    elif action == "stop_recovery":
        return {
            "status": "FAILURE",
            "amount_recovered": 0.0,
            "description": "Recovery terminated by policy or customer preference."
        }
        
    # Execute random roll based on ERV probability
    if random.random() < prob:
        return {
            "status": "SUCCESS",
            "amount_recovered": amount,
            "description": f"Action '{action}' executed successfully. Recovered INR {amount:,.2f}."
        }
    else:
        return {
            "status": "FAILURE",
            "amount_recovered": 0.0,
            "description": f"Action '{action}' executed but failed to recover funds (probability {prob*100:.0f}%)."
        }
