from pydantic import BaseModel, Field
from typing import Literal

class RecoveryRecommendation(BaseModel):
    root_cause: Literal[
        "temporary_bank_failure",
        "insufficient_funds",
        "expired_card",
        "customer_declined",
        "limit_exceeded",
        "unknown"
    ] = Field(description="The diagnosed root cause of the payment failure")
    confidence: float = Field(description="Confidence score between 0.0 and 1.0")
    recommended_action: Literal[
        "retry_payment",
        "send_payment_reminder",
        "create_payment_link",
        "schedule_retry",
        "mark_promise_to_pay",
        "escalate_to_human",
        "stop_recovery"
    ] = Field(description="The action recommended to recover the payment")
    reason: str = Field(description="Brief reason explaining the root cause and why the selected intervention maximizes net value")
    why_not_alternatives: str = Field(description="Explanation of why other candidate interventions (such as immediate retry or manual escalation) were bypassed in this step")
