# RecoverAI: Evaluation Methodology

This document outlines the evaluation framework for comparing **RecoverAI** against a baseline recovery mechanism.

---

## 1. Objectives

The primary goal of RecoverAI is to maximize the amount of revenue recovered from failed transactions while complying with regulatory, contact, and business policies. The evaluation metrics are designed to demonstrate a measurable and statistically significant uplift in recovered revenue.

---

## 2. Experimental Setup

### A. Dataset
We generate a batch of **5,000 synthetic transaction records** representing transaction failures from customers with varied profiles.
- 5% are high-value transactions (≥ ₹25,000).
- Customers have varied lifetime values (LTV), success rates, and contact preferences.
- Failures represent 6 distinct codes (e.g. `INSUFFICIENT_FUNDS`, `CARD_EXPIRED`, `BANK_TIMEOUT`, etc.).

### B. Seed-Based Repeatability
Both the baseline and RecoverAI run on the exact same dataset. More importantly, they run under **identical simulator seeds** for each case (`seed = 42 + transaction_index`). Both workflows use the same synthetic dataset and deterministic per-transaction seeds, making the comparison reproducible.

---

## 3. Metrics Evaluated

1. **Revenue at Risk**: Total value of all FAILED transactions in the evaluation batch.
2. **Revenue Recovered**: Sum of successful recoveries (₹) across the batch.
3. **Recovery Rate (%)**: `Recovered Revenue / Revenue at Risk * 100.0`.
4. **Baseline Uplift (₹)**: `Agent Recovered Revenue - Baseline Recovered Revenue`.
5. **Policy Violation Rate (%)**: Number of actions violating business policies (must be 0.0%).
6. **Escalation Rate (%)**: Percentage of transactions routed to human ops (due to fraud flag, max retries, or high-value threshold).

---

## 4. Execution Logic

### A. The Baseline
The baseline represents a typical naive automated recovery logic:
- For every failed transaction, it executes a single immediate retry (`retry_payment`).
- Exception: It stops if the transaction is high-value (≥ ₹25,000) or if the customer has opted out of communication.
- No other diagnosis or reminder actions are attempted.

### B. RecoverAI Agent
The agent applies intelligence:
1. **Risk Scoring**: Evaluates transaction risk level (LOW/MEDIUM/HIGH/CRITICAL).
2. **LLM Root Cause Diagnosis**: DeepSeek-Coder:6.7b running locally on Ollama analyzes customer/invoice context to identify the specific root cause and recommend the best tool.
3. **Deterministic Policies**: Validates the recommendation (max retries, high value limits, contact preferences, fraud checks). If validated, it approves; if not, it overrides the action (escalates or stops).
4. **Bounded Tools**: Executes the approved tool (reminders, payment links, delayed retries, promise to pay tracking) in the seeded simulator.

### C. The 50 LLM Limit
Because processing 5,000 records through a local LLM can take hours on standard machines, we introduce a parameter:
- **`--llm-limit 50`**
- The first 50 transactions are analyzed by Ollama.
- The remaining 4,950 transactions utilize the **Deterministic Fallback Engine**. The fallback maps failure codes to diagnoses instantly using python rules. This ensures the batch run completes within seconds while validating the LLM integration on representative cases.
