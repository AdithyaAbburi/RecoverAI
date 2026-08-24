# RecoverAI: 5-Minute Demo Pitch Script

Use this outline and script to record your 5-minute presentation video for the Razorpay AI Buildathon submission.

---

## Part 1: Problem Definition (0:00 - 0:30)
- **Visuals**: Show a slide with payment failure stats or code/invoice leakage.
- **Narrative**:
  > "Hi, today I'm presenting RecoverAI, an autonomous revenue recovery agent built for the Razorpay Buildathon under Track 03: AI Revenue Recovery.
  > In digital commerce, payment failures are a silent killer. Up to 15% of transactions fail, but not all failures are equal. Naive retry rules spam users or trigger repeat bank failures, leading to poor customer experience and lost revenue.
  > RecoverAI solves this by executing autonomous diagnosis, economic optimization, and policy-bounded recovery actions."

---

## Part 2: Architecture & Guardrails (0:30 - 1:00)
- **Visuals**: Show the architecture flow or diagram from `docs/architecture.md`.
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
- **Visuals**: Open the Streamlit dashboard case viewer. Filter to transaction `TX00014` and show the audit timeline.
- **Narrative**:
  > "Let's look at Scenario A: Successful Recovery. 
  > Transaction TX00014 failed due to a BANK_TIMEOUT. The risk engine scored it as Medium.
  > The LLM Root Cause Analyzer diagnosed a temporary bank failure.
  > The ERV Engine calculated a high success probability (85%) for scheduling a retry, which maximized expected net recovery.
  > The Policy Engine approved it because retry count was 0 and value was under the ₹25k limit.
  > The tool was executed through the simulator, succeeded, and recovered the payment."

---

## Part 4: Failure & Escalation Demos (2:45 - 3:30)
- **Visuals**: Select transaction `TX00005` (max retries) and `TX00001` (high value threshold).
- **Narrative**:
  > "What about safety? 
  > In Scenario B (Maximum-Attempt Escalation), transaction TX00005 failed with INSUFFICIENT_FUNDS. The agent attempted two retries. When a third retry was recommended, the Policy Engine intercepted and returned REJECTED: Maximum retries reached. The agent automatically triggered `escalate_to_human`.
  > In Scenario C (High-Value Protection), transaction TX00001 is for ₹75,000. Because it exceeds our ₹25,000 safety threshold, the Policy Engine blocked automatic capture and escalated it immediately to human review, preventing unauthorized money movement."

---

## Part 5: Batch Metrics & Baseline Comparison (3:30 - 4:20)
- **Visuals**: Show the top metrics panel of the Streamlit dashboard and the comparison bar chart.
- **Narrative**:
  > "RecoverAI doesn't just work on cherry-picked examples. We ran a batch evaluation of 1,000 synthetic transactions under identical simulator seeds.
  > On a reproducible 1,000-transaction evaluation batch, RecoverAI recovered 59.0% of revenue at risk, compared with 29.3% for the naive retry-once baseline and 46.5% for the rules-only approach.
  > This represents a net financial uplift of INR 4,351,097.07 (+29.70%) over the naive baseline, and INR 1,827,921.09 (+12.48%) over the static rules approach, with 100% stopping rule compliance and zero policy violations."

---

## Part 6: Engineering Rationale & Conclusion (4:20 - 5:00)
- **Visuals**: Show the github repository files, terminal showing pytest suite passing.
- **Narrative**:
  > "We built RecoverAI using FastAPI, SQLite, and Streamlit, with unit and integration tests covering all risk, policy, and agent workflows.
  > By bridging LLM reasoning with a deterministic guardrail engine, we show that agents can be safely deployed in high-stakes financial pipelines.
  > Thank you! All code is pushed to public GitHub, and instructions to reproduce this run locally are in the README."
