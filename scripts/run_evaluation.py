import os
import sys
import argparse

# Add root folder to sys.path
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from scripts.generate_data import generate_synthetic_data
from scripts.run_batch import run_evaluation_batch
from scripts.evaluate import generate_report

def main():
    parser = argparse.ArgumentParser(description="Run complete reproducible RecoverAI evaluation pipeline.")
    parser.add_argument("--count", type=int, default=1000, help="Number of synthetic records to evaluate.")
    parser.add_argument("--llm-limit", type=int, default=2, help="Number of cases to evaluate with Ollama LLM directly.")
    args = parser.parse_args()

    print("=" * 60)
    print("      RECOVERAI REPRODUCIBLE EVALUATION PIPELINE")
    print("=" * 60)

    # 1. Generate data if missing or count requested
    print(f"\n[Step 1/3] Generating synthetic transaction dataset ({args.count} cases, seed=42)...")
    generate_synthetic_data(args.count)

    # 2. Run multi-step batch comparison
    print(f"\n[Step 2/3] Executing 3-way ablation study (Baseline vs Rules vs RecoverAI)...")
    run_evaluation_batch(args.count, args.llm_limit)

    # 3. Print report
    print(f"\n[Step 3/3] Generating executive summary report...")
    generate_report()

    print("\nEvaluation pipeline complete. Output saved to data/evaluation/evaluation_results.json")

if __name__ == "__main__":
    main()
