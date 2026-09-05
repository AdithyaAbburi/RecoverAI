# RecoverAI: 5-Minute Demo Presentation Script

Use this outline and script to record a 5-minute technical demo video of RecoverAI.

---

## Part 1: Problem Definition (0:00 - 0:30)
- **Visuals**: Show slide with payment failure statistics and revenue leakage.
- **Narrative**:
  > "Hi, today I'm presenting RecoverAI, an autonomous revenue recovery system for enterprise payment operations.
  > In digital commerce, payment failures are a silent killer. Up to 15% of transactions fail, but not all failures are equal. Naive retry rules spam users or trigger repeat bank failures, leading to poor customer experience and lost revenue.
  > RecoverAI solves this by executing autonomous diagnosis, economic optimization, and policy-bounded recovery actions."

---

## Part 2: Architecture & Safety Guardrails (0:30 - 1:00)
- **Visuals**: Show architecture diagram from `docs/architecture.png` or README.
- **Narrative**:
  > "RecoverAI follows a strict engineering principle: **AI diagnoses, but deterministic systems enforce.**
  > 1. Ingestion: Failed payments are fetched with customer profile and overdue invoice context.
  > 2. Risk Engine: Assigns a rule-based risk score (0-100).
  > 3. AI Root-Cause: A local LLM (DeepSeek-Coder:6.7b via Ollama) diagnoses the failure and resolves ambiguity from transaction/customer history.
  > 4. Economic Ranking: The Expected Recovery Value (ERV) engine calculates success probabilities and operational costs for candidate actions, selecting the optimal recovery path.
  > 5. Policy Guardrails: Validates the action against strict safety guardrails (Max 2 retries, ₹25k limit, contact opt-outs, fraud risk flags).
  > 6. Bounded Execution & Audit: Executes the action and registers an immutable audit trace in SQLite."

---

## Part 3: Live Successful Recovery Demo (1:00 - 2:45)
- **Visuals**: Open Streamlit dashboard. Select transaction `TX00014` (₹11,094.49) and inspect the audit timeline.
- **Narrative**:
  > "Let's look at Scenario A: Successful Recovery. 
  > Transaction TX00014 failed due to a BANK_TIMEOUT. The risk engine scored it as LOW risk (Score: 17).
  > The LLM Root Cause Analyzer diagnosed a temporary bank failure.
  > The ERV Engine calculated a high success probability (85%) for scheduling a retry, which maximized expected net recovery.
  > The Policy Engine approved it because retry count was 0 and value was under the ₹25k limit.
  > The tool was executed through the simulator, succeeded, and recovered the payment."

---

## Part 4: Failure & Safety Escalation Demos (2:45 - 3:30)
- **Visuals**: Select transaction `TX00005` (max retries exhausted) and `TX00001` (high value threshold).
- **Narrative**:
  > "What about safety? 
  > In Scenario B (Maximum-Attempt Budget Exhaustion), transaction TX00005 failed with CARD_EXPIRED. The agent attempted two distinct bounded recovery actions (`create_payment_link` followed by `mark_promise_to_pay`). When automated attempts reached MAX_ATTEMPTS = 2, the Policy Engine intercepted and automatically triggered `escalate_to_human`.
  > In Scenario C (High-Value Protection), transaction TX00001 is for ₹51,289.39. Because it exceeds our ₹25,000 safety threshold, the Policy Engine blocked automatic capture and escalated it immediately to human review, preventing unauthorized money movement."

---

## Part 5: Batch Metrics & Baseline Comparison (3:30 - 4:20)
- **Visuals**: Show top metrics panel of the Streamlit dashboard and comparative bar charts.
- **Narrative**:
  > "RecoverAI doesn't just work on cherry-picked examples. We ran a batch evaluation of 1,000 synthetic transactions under identical simulator seeds.
  > On a reproducible 1,000-transaction evaluation batch, RecoverAI recovered 59.03% of revenue at risk (INR 8,647,258.31 Gross / INR 8,612,463.31 Net), compared with 29.30% (INR 4,292,057.07 Gross / INR 4,291,218.07 Net) for the naive retry-once baseline and 46.53% (INR 6,815,233.05 Gross / INR 6,790,461.05 Net) for the static rules approach.
  > This represents a net financial uplift of INR 4,355,201.24 (+29.73%) over the naive baseline, and INR 1,832,025.26 (+12.51%) over the static rules approach, with 100% stopping rule compliance and zero policy violations."

---

## Part 6: Engineering Rationale & Conclusion (4:20 - 5:00)
- **Visuals**: Show GitHub repository structure, terminal displaying test suite passing (pytest 34 passed).
- **Narrative**:
  > "We built RecoverAI using FastAPI, SQLite, and Streamlit, with 34 automated unit and integration tests covering all risk, policy, ERV, and agent workflows.
  > By bridging LLM reasoning with a deterministic guardrail engine, we show that agents can be safely deployed in high-stakes financial pipelines.
  > Thank you! All code is pushed to public GitHub, and instructions to reproduce this run locally are in the README."
