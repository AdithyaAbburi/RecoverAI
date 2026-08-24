import json
import requests
from app.config import settings
from app.agent.prompts import SYSTEM_PROMPT, get_transaction_prompt
from app.agent.schemas import RecoveryRecommendation

def get_deterministic_fallback(failure_code: str, attempts_history: list = None) -> dict:
    """
    Provide a robust deterministic diagnosis fallback when the LLM is unavailable or outputs malformed JSON.
    Uses attempt history to sequence interventions and avoid repeating failed actions.
    """
    code = (failure_code or "").upper()
    history_actions = [a.get("action") for a in (attempts_history or [])]
    
    if code in ["BANK_TIMEOUT", "TEMPORARY_BANK_ERROR"]:
        if "retry_payment" not in history_actions:
            return {
                "root_cause": "temporary_bank_failure",
                "confidence": 1.0,
                "recommended_action": "retry_payment",
                "reason": "Deterministic fallback: Bank/network issue detected. Recommend retry.",
                "why_not_alternatives": "Retry payment has the highest expected recovery probability (70%) for network timeouts."
            }
        else:
            return {
                "root_cause": "temporary_bank_failure",
                "confidence": 1.0,
                "recommended_action": "create_payment_link",
                "reason": "Deterministic fallback: Primary retry failed. Generating alternative payment link.",
                "why_not_alternatives": "Repeating retry_payment is bypassed because the first retry already failed."
            }
            
    elif code == "INSUFFICIENT_FUNDS":
        if "send_payment_reminder" not in history_actions:
            return {
                "root_cause": "insufficient_funds",
                "confidence": 1.0,
                "recommended_action": "send_payment_reminder",
                "reason": "Deterministic fallback: Customer lacks funds. Send payment reminder.",
                "why_not_alternatives": "Reminder has low cost (INR 1) and gives the customer time to fund their account."
            }
        else:
            return {
                "root_cause": "insufficient_funds",
                "confidence": 1.0,
                "recommended_action": "create_payment_link",
                "reason": "Deterministic fallback: Reminder went unheeded. Generate direct payment link.",
                "why_not_alternatives": "Bypassing reminder as it has already been sent once."
            }
            
    elif code == "CARD_EXPIRED":
        return {
            "root_cause": "expired_card",
            "confidence": 1.0,
            "recommended_action": "create_payment_link",
            "reason": "Deterministic fallback: Expired card. Generate link to update payment method.",
            "why_not_alternatives": "Retry payment is impossible on an expired card (0% probability)."
        }
        
    elif code == "LIMIT_EXCEEDED":
        return {
            "root_cause": "limit_exceeded",
            "confidence": 1.0,
            "recommended_action": "escalate_to_human",
            "reason": "Deterministic fallback: Transaction limit exceeded. Escalate to human operator.",
            "why_not_alternatives": "Automated retries will continue to fail (5% probability) until limit is cleared by bank/operator."
        }
        
    elif code == "CUSTOMER_DECLINED":
        if "send_payment_reminder" not in history_actions:
            return {
                "root_cause": "customer_declined",
                "confidence": 1.0,
                "recommended_action": "send_payment_reminder",
                "reason": "Deterministic fallback: Customer declined transaction. Query reason.",
                "why_not_alternatives": "Gentle nudge via reminder allows customer to authorize the charge."
            }
        else:
            return {
                "root_cause": "customer_declined",
                "confidence": 1.0,
                "recommended_action": "stop_recovery",
                "reason": "Deterministic fallback: Customer persistently declined. Terminate recovery.",
                "why_not_alternatives": "Escalating is too costly for a customer who has explicitly opted out/declined twice."
            }
            
    else:
        return {
            "root_cause": "unknown",
            "confidence": 0.5,
            "recommended_action": "escalate_to_human",
            "reason": "Deterministic fallback: Unrecognized error code. Escalate to human operator.",
            "why_not_alternatives": "Automated tools cannot diagnose unknown failures safely."
        }

def analyze_root_cause(
    transaction_data: dict, 
    customer_data: dict, 
    invoice_data: dict = None,
    attempts_history: list = None,
    erv_table: dict = None
) -> dict:
    """
    Diagnose the failure root cause and recommend an action using local Ollama.
    Falls back to deterministic rules if Ollama fails.
    """
    failure_code = transaction_data.get("failure_code", "")
    
    # Construct prompt with full history and ERVs
    prompt = get_transaction_prompt(transaction_data, customer_data, invoice_data, attempts_history, erv_table)
    
    payload = {
        "model": settings.OLLAMA_MODEL,
        "system": SYSTEM_PROMPT,
        "prompt": prompt,
        "format": "json",
        "stream": False,
        "options": {
            "temperature": 0.0
        }
    }
    
    try:
        url = f"{settings.OLLAMA_BASE_URL}/api/generate"
        response = requests.post(url, json=payload, timeout=12.0)
        
        if response.status_code == 200:
            result_json = response.json()
            response_text = result_json.get("response", "").strip()
            
            # Clean markdown wrappers if any
            if response_text.startswith("```"):
                lines = response_text.split("\n")
                if lines[0].startswith("```json") or lines[0].startswith("```"):
                    lines = lines[1:-1]
                response_text = "\n".join(lines).strip()
            
            data = json.loads(response_text)
            validated = RecoveryRecommendation(**data)
            return validated.model_dump()
        else:
            return get_deterministic_fallback(failure_code, attempts_history)
            
    except Exception as e:
        fallback_data = get_deterministic_fallback(failure_code, attempts_history)
        fallback_data["reason"] += f" (LLM Error: {str(e)[:50]})"
        return fallback_data
