# RecoverAI: System Architecture

This document describes the design and technical architecture of **RecoverAI**, an autonomous revenue recovery system for enterprise payment operations.

---

## 1. System Overview

RecoverAI is structured to close the loop from payment failure detection to bounded recovery action. The system guarantees monetary safety by isolating the generative AI (which diagnoses and recommends actions) behind a strictly deterministic policy and guardrail engine.

```
+-----------------------------------------------------------+
|                     Synthetic Dataset                     |
|            (1,000+ Transactions, Customers, Invoices)     |
|                   (Using Seeded Repeatability)            |
+----------------------------+------------------------------+
                             |
                             v
+----------------------------+------------------------------+
|                     FastAPI Ingestion                     |
|           (Reads FAILED transaction context)             |
+----------------------------+------------------------------+
                             |
                             v
+----------------------------+------------------------------+
|                    1. Revenue Risk Engine                 |
|             (Rule-based Scoring: 0 - 100)                 |
+----------------------------+------------------------------+
                             |
                             v
+----------------------------+------------------------------+
|                  2. LLM Root-Cause Analyzer               |
|            (Ollama deepseek-coder:6.7b / Fallback)        |
|             (Diagnoses cause based on context)            |
+----------------------------+------------------------------+
                             |
                             v
+----------------------------+------------------------------+
|                    3. ERV Ranking Engine                  |
|          (Ranks candidate actions by Expected Net Value)  |
+----------------------------+------------------------------+
                             |
                             v
+----------------------------+------------------------------+
|            4. Deterministic Policy Guardrail Engine       |
|    (Enforces Retries <= 2, Limit < ₹25k, Opt-out checking) |
+----------------------------+------------------------------+
                             |
                             +-------------------+
                             | Approved          | Escalated / Rejected
                             v                   v
+----------------------------+----+     +--------+----------+
|       5. Payment Simulator      |     |  Human Operator   |
|  (Represents external gateways) |     |   / Manual Ops    |
+----------------------------+----+     +-------------------+
                             |
                             v
+----------------------------+------------------------------+
|                   6. Audit Trail Logger                   |
|          (Writes every decision stage to SQLite)          |
+----------------------------+------------------------------+
                             |
                             v
+----------------------------+------------------------------+
|                Streamlit Operations Control               |
|           (Real-time charts, metrics & comparisons)       |
+-----------------------------------------------------------+
```

---

## 2. Core Components

### A. Ingestion & API Layer (FastAPI)
Acts as the central router for processing transaction requests and retrieving metrics. 
- `/api/transactions`: Retrieves transaction state and full audit trails.
- `/api/recovery/trigger-batch`: Triggers batch recovery.
- `/api/metrics`: Calculates total revenue at risk, recovered revenue, and recovery rates.

### B. Risk Engine
Determines the business severity of the payment failure using a scoring matrix:
- **Severity**: Scored by failure code (e.g., card expired is more severe than a temporary bank timeout).
- **Transaction Amount**: Linear scale up to ₹50,000.
- **Customer History**: Historical payment success rates.
- **Overdue Invoices**: Subscriptions/invoices days overdue.

### C. LLM Root-Cause Analyzer
Queries a local instance of **Ollama** running `deepseek-coder:6.7b`.
- **Contextual Reasoning**: The LLM analyzes the customer profile, invoice days overdue, and transaction history to diagnose the root cause (e.g., distinguishing temporary bank errors from chronic liquidity issues).
- **Fallback Engine**: If Ollama fails, times out, or returns invalid JSON, a local rule-based mapper instantly intercepts and supplies a safe diagnosis. This guarantees 100% service availability.

### D. ERV Ranking Engine
Ranks the candidate actions based on the LLM's diagnosed root cause.
- **Expected Net Recovery (ERV)** = `(Success Probability * Amount) - Operational Cost`.
- The engine uses the customer's historical success rate and payment amount to compute candidate ERVs, choosing the recovery tool that maximizes net value.

### E. Policy Guardrail Engine
The absolute defense layer of the system. **No LLM or ERV recommendation can bypass this engine.**
- **Retry Limit**: Restricts retries to a maximum of 2.
- **High-Value Protection**: Any transaction ≥ ₹25,000 is blocked from automated retries/payments and escalated to human review.
- **Opt-Out Checking**: Checks customer's preference. If contact is opted-out (`none`), communications tools like `send_payment_reminder` are blocked.
- **High-Risk Flag**: If a customer has a fraud flag, automated recovery is completely disabled.

### F. Payment Simulator
A mock gateway that outputs outcomes based on action type and failure code. To make evaluation batch runs repeatable and verifiable, the simulator supports seeded random values. Under a fixed seed, every single execution returns identical outcomes.
