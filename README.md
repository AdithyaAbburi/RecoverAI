# RecoverAI: Bounded Autonomous Revenue Recovery Agent

RecoverAI is an autonomous agent designed to detect payment failures, diagnose root causes, optimize recovery paths through Expected Recovery Value (ERV) calculations, and execute actions under strict deterministic policy guardrails. This project was built for the Razorpay AI Buildathon under Track 03 (AI Revenue Recovery).

---

## Evaluation and Business Impact

RecoverAI was evaluated on a reproducible batch of 1,000 synthetic transaction failures. All workflows were executed under identical simulator seeds to ensure a direct, scientific comparison:

| Metric | Naive Baseline (Retry-Once) | Rules-Only (Static Mapping) | RecoverAI Agent (AI-Optimized) |
| :--- | :--- | :--- | :--- |
| Transactions Successfully Recovered | 321 / 1000 | 515 / 1000 | 660 / 1000 |
| Transaction Recovery Rate | 32.1% | 51.5% | 66.0% |
| Total Revenue Recovered | INR 4,292,057.07 | INR 6,815,233.05 | INR 8,647,258.31 |
| Revenue Recovery Rate | 29.30% | 46.53% | 59.00% |
| Financial Uplift vs. Baseline | — | +17.22% | +29.70% (INR 4,355,201.24 Saved) |
| Financial Uplift vs. Rules-Only | — | — | +12.48% (INR 1,832,025.26 Saved) |
| Policy Violation Rate | 0.0% | 0.0% | 0.0% (100% Compliant) |
| Stopping Rule Compliance | 100.0% | 100.0% | 100.0% (MAX_ATTEMPTS=2 Enforced) |

*Note: The transaction recovery rate represents the percentage of transactions successfully resolved, while the revenue recovery rate represents the percentage of financial value recovered from the total revenue at risk (INR 14,648,500.39).*

---

## System Architecture

RecoverAI is built on a pipeline designed to isolate generative AI decisions behind a strictly deterministic policy and guardrail engine. 

```
                  [ Transaction Failure Ingestion ]
                                  |
                                  v
                  [ 1. Deterministic Risk Engine ]
                      (Scores severity: 0-100)
                                  |
                                  v
                  [ 2. LLM Root-Cause Diagnosis ]
                 (Local DeepSeek-Coder:6.7b on CPU)
                                  |
                                  v
                    [ 3. ERV Ranking Optimizer ]
                   (Calculates Expected Net Value)
                                  |
                                  v
                  [ 4. Deterministic Policy Engine ]
                  (Safety constraints & limits check)
                                  |
                       Approved   +   Rejected / Escalated
                    +-------------+-------------+
                    |                           |
                    v                           v
         [ 5. Bounded Tool Exec ]       [ Human Ops Queue ]
             (Seeded Simulator)
                    |
                    v
         [ 6. Immutable Audit Trail ]
              (SQLite DB Logs)
```

### Architectural Pipeline Details

1. **Revenue Risk Engine**: Computes a risk score (0-100) based on transaction amount, historical failure frequency, and active overdue customer invoices.
2. **LLM Diagnosis Module**: Analyzes customer metadata, lifetime value (LTV), overdue invoices, and transaction logs to diagnose the root cause of the failure.
3. **Expected Recovery Value (ERV) Optimizer**: Selects the candidate action that mathematically maximizes net recovery:  
   $$\text{Expected Net Recovery} = (\text{Success Probability} \times \text{Amount}) - \text{Operational Cost}$$
4. **Policy Guardrail Engine**: The final safety layer. Validates the action against business constraints (capping retries to `MAX_ATTEMPTS = 2`, blocking contact actions for opted-out users, and routing transactions >= INR 25,000 to manual review).
5. **Bounded Tool Execution**: Executes the action in a seeded payment simulator.
6. **Immutable Audit Trail**: Records a step-by-step trace of every decision stage to SQLite for compliance and auditability.

---

## Codebase Structure

```
RecoverAI/
├── app/
│   ├── main.py                 # FastAPI Web API
│   ├── config.py               # Env Configuration
│   ├── agent/                  # Agent orchestrator, tools, and prompts
│   ├── risk/                   # Transaction Risk Scoring Engine
│   ├── diagnosis/              # LLM root-cause analyzer (Ollama)
│   ├── policy/                 # Hardcoded business policy guardrails
│   ├── simulator/              # Seeded repeatable payment simulator
│   ├── services/               # DB interaction services
│   └── db/                     # DB schemas and database session setup
├── dashboard/                  # Streamlit Operations Control Room (app.py)
├── scripts/                    # CLI tools (generate_data.py, run_batch.py, evaluate.py)
├── tests/                      # Pytest automation suite
└── docs/                       # Architectural & evaluation details
```

---

## Getting Started and Local Reproduction

### 1. Prerequisites
- **Python**: 3.13+ installed.
- **Ollama**: Installed and running locally. Pull the model before starting:
  ```bash
  ollama pull deepseek-coder:6.7b
  ```

### 2. Installation
Clone the repository, install Python dependencies, and set up your environment variables:
```bash
pip install -r requirements.txt
cp .env.example .env
```

### 3. Run Automated Tests
Verify code integrity and safety guardrail assertions:
```bash
python -m pytest tests/
```

### 4. Replicate the Ablation Study (1,000 Transactions)
Initialize the database and execute the comparative evaluation runs:
```bash
# 1. Generate clean synthetic transaction dataset
python scripts/generate_data.py --count 1000

# 2. Run baseline, rules-only, and AI recovery workflows
python scripts/run_batch.py --limit 1000 --llm-limit 2

# 3. Print the final metrics summary
python scripts/evaluate.py
```

### Evaluation Performance Optimization (--llm-limit)
Running LLM inference locally on standard CPU hardware takes approximately 30-45 seconds per transaction. Processing a batch of 1,000 transactions entirely through the LLM would require over 10 hours. 

To support quick evaluation and verification, we run the batch script with `--llm-limit 2`. This performs active LLM-based root-cause diagnosis on the first 2 transactions (demonstrating the prompt, model reasoning, and structured output parsing in the audit logs) and automatically falls back to the deterministic ERV optimizer for the remaining 998 transactions.

If you are running Ollama with GPU acceleration, you can scale the LLM limit by increasing the parameter (e.g., `--llm-limit 100` or `--llm-limit 1000`).

### 5. Launch the Streamlit Dashboard Control Room
Inspect interactive charts, recovery metric breakdowns, and detailed audit timelines:
```bash
streamlit run dashboard/app.py
```

---

## Core Engineering Rationales

* **Defensive Guardrails**: LLMs are creative and prone to hallucination. RecoverAI addresses this by using the LLM strictly as a *context diagnostic tool* to label the failure. The actual recovery action is chosen by a mathematical optimization function and validated against a compiled Python rules engine.
* **Local Inference Efficiency**: To scale to thousands of transactions on standard hardware, the agent supports a `--llm-limit` parameter. Only initial transactions run LLM inference to demonstrate capability, while the rest fall back to the ERV optimizer, completing large batches in seconds.
* **Write-Ahead Logging (WAL) Mode**: Integrated database connection event listeners to set SQLite pragmas (`PRAGMA journal_mode = WAL` and `PRAGMA synchronous = NORMAL`). This resolves lock timeouts and allows Streamlit to perform concurrent reads during batch evaluation writes.
