"""
main.py
-------
Master pipeline orchestrator for the Recruitment Automation System.

Execution order:
  Step 1  – Initialize environment & verify API keys      (setup_env)
  Step 2  – Parse & clean the Excel consultant list       (excel_parser)
  Step 3  – Source matching candidates from LinkedIn      (linkedin_sourcer)
  Step 4  – Score candidates with Gemini AI               (ai_evaluator)
  Step 5  – Upload evaluated candidates to Firestore      (firebase_db)
  Step 6  – Generate formatted Excel report               (report_generator)
"""

from __future__ import annotations

import sys
import time
from pathlib import Path

# Ensure UTF-8 output on Windows consoles (avoids cp1252 UnicodeEncodeError)
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")


# ---------------------------------------------------------------------------
# Logging helpers
# ---------------------------------------------------------------------------

SEPARATOR = "=" * 70

def _banner(step: int, title: str) -> None:
    print(f"\n{SEPARATOR}")
    print(f"  STEP {step}: {title.upper()}")
    print(SEPARATOR)


def _log(msg: str) -> None:
    print(f"  {msg}")


# ---------------------------------------------------------------------------
# Main pipeline
# ---------------------------------------------------------------------------

def main() -> None:
    pipeline_start = time.time()

    print(SEPARATOR)
    print("  RECRUITMENT AUTOMATION PIPELINE – STARTING")
    print(SEPARATOR)

    # -----------------------------------------------------------------------
    # STEP 1: Environment Initialization
    # -----------------------------------------------------------------------
    _banner(1, "Initialize Environment & Verify API Keys")

    import setup_env  # noqa: PLC0415

    keys_valid = setup_env.initialize()
    if not keys_valid:
        _log("⚠  One or more API keys are missing or set to placeholder values.")
        _log("   The pipeline will continue but API-dependent steps may be skipped.")
    else:
        _log("✅ Environment initialized. All API keys are set.")

    # -----------------------------------------------------------------------
    # STEP 2: Parse & Clean Excel
    # -----------------------------------------------------------------------
    _banner(2, "Parse & Clean Excel Consultant List")

    from excel_parser import parse_excel  # noqa: PLC0415

    excel_file = Path(__file__).parent / "Marketing Consultants - Team wise (22).xlsx"
    _log(f"Reading: {excel_file}")

    try:
        consultant_records = parse_excel(excel_path=excel_file)
        _log(f"✅ Parsed {len(consultant_records)} consultant records successfully.")
    except FileNotFoundError as exc:
        _log(f"❌ Excel file not found: {exc}")
        sys.exit(1)
    except Exception as exc:  # noqa: BLE001
        _log(f"❌ Failed to parse Excel: {exc}")
        raise

    if not consultant_records:
        _log("❌ No records found in the Excel file. Aborting.")
        sys.exit(1)

    # -----------------------------------------------------------------------
    # STEP 3: LinkedIn Candidate Sourcing
    # -----------------------------------------------------------------------
    _banner(3, "Source Matching Candidates from LinkedIn (Proxycurl)")

    from linkedin_sourcer import source_candidates  # noqa: PLC0415

    _log(f"Sourcing candidates for {len(consultant_records)} records …")
    sourcing_start = time.time()

    try:
        sourced_data = source_candidates(consultant_records)
    except Exception as exc:  # noqa: BLE001
        _log(f"❌ Sourcing failed: {exc}")
        raise

    sourcing_elapsed = time.time() - sourcing_start
    total_sourced = sum(len(c.get("sourced_candidates") or []) for c in sourced_data)
    _log(f"✅ Sourcing complete in {sourcing_elapsed:.1f}s – {total_sourced} total candidates retrieved.")

    # -----------------------------------------------------------------------
    # STEP 4: Gemini AI Evaluation & Scoring
    # -----------------------------------------------------------------------
    _banner(4, "AI Candidate Evaluation & Scoring (Gemini)")

    from ai_evaluator import evaluate_candidates  # noqa: PLC0415

    _log(f"Scoring {total_sourced} candidates with Gemini …")
    eval_start = time.time()

    try:
        evaluated_data = evaluate_candidates(sourced_data)
    except Exception as exc:  # noqa: BLE001
        _log(f"❌ AI evaluation failed: {exc}")
        raise

    eval_elapsed = time.time() - eval_start
    _log(f"✅ Evaluation complete in {eval_elapsed:.1f}s.")

    # -----------------------------------------------------------------------
    # STEP 5: Upload to Firebase Firestore
    # -----------------------------------------------------------------------
    _banner(5, "Upload Evaluated Candidates to Firebase Firestore")

    from firebase_db import upload_candidates_to_firestore  # noqa: PLC0415

    firebase_start = time.time()
    try:
        firebase_uploaded = upload_candidates_to_firestore(evaluated_data)
        firebase_elapsed = time.time() - firebase_start
        _log(f"✅ Firestore upload complete in {firebase_elapsed:.1f}s – {firebase_uploaded} document(s) written.")
    except FileNotFoundError as exc:
        _log(f"⚠  Firebase key file missing – skipping Firestore upload: {exc}")
        firebase_uploaded = 0
    except Exception as exc:  # noqa: BLE001
        _log(f"⚠  Firestore upload failed (non-fatal) – pipeline will continue: {exc}")
        firebase_uploaded = 0

    # -----------------------------------------------------------------------
    # STEP 6: Generate Excel Report
    # -----------------------------------------------------------------------
    _banner(6, "Generate & Save Excel Report")

    from report_generator import generate_report  # noqa: PLC0415

    output_path = Path(__file__).parent / "Sourced_Candidates_Report.xlsx"
    _log(f"Saving report to: {output_path}")

    try:
        saved_path = generate_report(evaluated_data, output_filepath=output_path)
    except Exception as exc:  # noqa: BLE001
        _log(f"❌ Report generation failed: {exc}")
        raise

    # -----------------------------------------------------------------------
    # Final Summary
    # -----------------------------------------------------------------------
    total_elapsed = time.time() - pipeline_start

    print(f"\n{SEPARATOR}")
    print("  PIPELINE COMPLETE")
    print(SEPARATOR)
    _log(f"Total runtime        : {total_elapsed:.1f} seconds")
    _log(f"Consultant records   : {len(consultant_records)}")
    _log(f"Candidates sourced   : {total_sourced}")
    _log(f"Firestore docs saved : {firebase_uploaded}")
    _log(f"Output report saved  : {saved_path}")
    print(SEPARATOR)
    print()


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    main()
