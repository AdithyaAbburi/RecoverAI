# RecoverAI: Autonomous AI Revenue Recovery Agent

RecoverAI is an AI-powered revenue recovery agent designed to detect, diagnose, and recover revenue from failed and at-risk payments. It is built as a submission for the Razorpay AI Buildathon under Track 03: AI Revenue Recovery.

By combining generative AI (running locally via Ollama) with a strictly deterministic policy guardrail engine, RecoverAI ensures compliance, safety, and auditability while maximizing revenue recovery.

---

## Architectural Flow
```
Transaction (Failure)
      ↓
Risk Engine (Evaluate risk levels)
      ↓
LLM Diagnosis (Local DeepSeek-Coder:6.7b refines root cause from context)
      ↓
Candidate Actions
      ↓
ERV Ranking (Selects action that maximizes Expected Net Recovery)
      ↓
Policy Guardrails (Validates bounds: limits, opt-outs, fraud)
      ↓
Approved Action
      ↓
Bounded Tool (Executes contact or retry in simulator)
      ↓
Audit Log (Registers immutable audit trace in DB)
```

RecoverAI uses a local LLM for contextual diagnosis, with a deterministic fallback for reliability and large-scale evaluation. The same policy engine governs both paths, so no LLM output can bypass safety controls.

---

## Key Features
- **Deterministic Risk Engine**: Rule-based transaction risk scoring (0-100) based on amount, frequency, failure code, and overdue invoices.
- **LLM Root-Cause Analyzer**: Interfaces with local Ollama (deepseek-coder:6.7b) to diagnose root causes based on customer history, invoice status, and transaction details.
- **Economic Optimizer (ERV Ranking)**: Ranks and selects the candidate action that maximizes Expected Net Recovery Value (ERV) based on the diagnosed cause.
- **Deterministic Guardrails**: Guarantees that no automated money or communication action violates business policies (e.g., maximum 2 retries, INR 25,000 high-value threshold, customer opt-outs, fraud risk flags).
- **Payment & Recovery Simulator**: Recreates payment gate outcomes with seeded repeatability for valid evaluation comparisons.
- **Seeded Batch Evaluation**: Automatically runs and compares RecoverAI against a naive baseline (retry-once) and a static rules-only approach.
- **Interactive Control Room Dashboard**: Streamlit interface visualizing financial uplift, recovery rates, action breakdowns, and interactive audit trails.

---

## Codebase Structure
```
recoverai/
├── app/
│   ├── main.py                 # FastAPI API Entrypoint
│   ├── config.py               # Env Configuration
│   ├── api/                    # API Routers (transactions, recovery, metrics)
│   ├── agent/                  # Agent logic (orchestrator, tools, schemas, prompts)
│   ├── risk/                   # Risk engine (risk_engine.py)
│   ├── diagnosis/              # LLM root-cause (root_cause.py)
│   ├── policy/                 # Deterministic guardrails (policy_engine.py)
│   ├── simulator/              # Seeded payment simulator (payment_simulator.py)
│   ├── services/               # Services (recovery_service.py, audit_service.py)
│   └── db/                     # DB Layer (database.py, models.py)
├── data/                       # Generated dataset & evaluation output files
├── scripts/                    # CLI scripts (generate_data.py, run_batch.py, evaluate.py)
├── dashboard/                  # Streamlit Control Room (app.py)
├── tests/                      # Unit & integration test suite (pytest)
└── docs/                       # System & evaluation documentation
```

---

## Installation & Setup

### 1. Prerequisites
- **Python**: 3.13+ installed.
- **Ollama**: Installed and running locally. Pull the model before running:
  ```bash
  ollama pull deepseek-coder:6.7b
  ```

### 2. Install Python Dependencies
```bash
```bash
pip install -r requirements.txt
```

### 3. Setup Configuration
Copy the `.env.example` file to `.env`:
```bash
cp .env.example .env
```
Ensure your `.env` contains:
```env
DATABASE_URL=sqlite:///./recoverai.db
OLLAMA_BASE_URL=http://localhost:11434
OLLAMA_MODEL=deepseek-coder:6.7b
PORT=8000
HOST=127.0.0.1
```

---

## Running the Verification

### 1. Run Automated Test Suite
Verify that all core components (risk calculations, guardrails, simulator, in-memory DB integration) work correctly:
```bash
python -m pytest tests/
```

### 2. Generate Synthetic Dataset (1,000 Records)
Generate 1,000 synthetic transaction records, customers, and active overdue invoices:
```bash
python scripts/generate_data.py --count 1000
```
This initializes the SQLite database (`recoverai.db`) and exports copies as CSVs under `data/generated/`.

### 3. Run Batch Evaluation & Compare
Execute both the baseline retry-once workflow and the RecoverAI agent workflow over the 1,000 record batch:
```bash
python scripts/run_batch.py --limit 1000 --llm-limit 2
```
*Note: To ensure fast execution during review, the first 2 transactions query the local Ollama LLM directly, while the remaining 998 transactions utilize the Deterministic Fallback Engine to map failure codes instantly. Both runs utilize matching seeds to ensure a scientific, reproducible comparison.*

### 4. Launch Streamlit Operations Control Room
Launch the interactive dashboard to view KPI stats, comparison bar charts, and detailed transaction audit timelines:
```bash
streamlit run dashboard/app.py
```
Open [http://localhost:8501](http://localhost:8501) in your browser.

---

## Demo Scenarios to Verify in Dashboard

Select these transaction IDs in the dashboard Case Viewer to inspect policy guardrails:
1. **Scenario A (Successful Recovery) - e.g., `TX00014`**: Failed with `BANK_TIMEOUT`. RecoverAI recommends retry, policy approves, and simulator recovers the amount.
2. **Scenario B (Maximum-Attempt Escalation) - e.g., `TX00005`**: Failed with `INSUFFICIENT_FUNDS`. After two unsuccessful retries, policy blocks the third retry and triggers `escalate_to_human`.
3. **Scenario C (High-Value Protection) - e.g., `TX00001`**: Transaction exceeds the INR 25,000 threshold. The policy blocks automated retry and routes it immediately to human review.
