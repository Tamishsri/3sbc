"""
server.py
---------
Production-Grade REST API & Web Server for the Recruitment Automation Platform.

Features:
  - Serves the Enterprise Recruitment Command Center Web App (index.html).
  - Handles candidate candidate pipeline queries, status updates, metrics, and report downloads.
  - Supports live execution of the main.py pipeline orchestrator.
"""

from __future__ import annotations

import json
import os
import subprocess
import sys
from http.server import HTTPServer, SimpleHTTPRequestHandler
from pathlib import Path
from urllib.parse import parse_qs, urlparse

# ---------------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------------
PORT = 5000
BASE_DIR = Path(__file__).parent.resolve()
REPORT_FILE = BASE_DIR / "Sourced_Candidates_Report.xlsx"

# In-memory candidate status cache for interactive ATS workflow
_candidate_status_cache: dict[str, str] = {}


def load_candidate_records() -> list[dict]:
    """Read the latest candidate records from Excel report or Firestore."""
    if not REPORT_FILE.exists():
        return []

    try:
        import pandas as pd
        df = pd.read_excel(REPORT_FILE)
        df.fillna("", inplace=True)
        records = df.to_dict(orient="records")

        # Inject ATS candidate status
        for r in records:
            cand_id = f"{r.get('Team Name')}::{r.get('Candidate Name/Title')}".strip()
            r["Status"] = _candidate_status_cache.get(cand_id, "New")
        return records
    except Exception as exc:
        print(f"[server] Error reading candidate report: {exc}")
        return []


def compute_metrics(records: list[dict]) -> dict:
    """Compute enterprise dashboard metrics."""
    if not records:
        return {
            "total_candidates": 0,
            "top_matches": 0,
            "teams_count": 0,
            "avg_score": 0,
            "shortlisted_count": 0,
        }

    scores = []
    teams = set()
    shortlisted = 0

    for r in records:
        score_val = r.get("Match Score")
        if isinstance(score_val, (int, float)) or (isinstance(score_val, str) and score_val.isdigit()):
            scores.append(int(score_val))
        if r.get("Team Name"):
            teams.add(str(r.get("Team Name")).strip())
        if r.get("Status") == "Shortlisted":
            shortlisted += 1

    top_count = sum(1 for s in scores if s >= 80)
    avg_score = round(sum(scores) / len(scores), 1) if scores else 0

    return {
        "total_candidates": len(records),
        "top_matches": top_count,
        "teams_count": len(teams),
        "avg_score": avg_score,
        "shortlisted_count": shortlisted,
    }


class EnterpriseRecruitmentHandler(SimpleHTTPRequestHandler):
    """Production HTTP Handler for static assets and REST API endpoints."""

    def __init__(self, *args, **kwargs):
        super().__init__(*args, directory=str(BASE_DIR), **kwargs)

    def _send_json(self, data: dict | list, status: int = 200):
        body = json.dumps(data, default=str).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Access-Control-Allow-Origin", "*")
        self.end_headers()
        self.wfile.write(body)

    def do_GET(self):
        parsed = urlparse(self.path)

        if parsed.path == "/api/candidates":
            records = load_candidate_records()
            self._send_json(records)
            return

        if parsed.path == "/api/stats":
            records = load_candidate_records()
            stats = compute_metrics(records)
            self._send_json(stats)
            return

        if parsed.path == "/api/download":
            if REPORT_FILE.exists():
                self.send_response(200)
                self.send_header("Content-Type", "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")
                self.send_header("Content-Disposition", f'attachment; filename="{REPORT_FILE.name}"')
                self.send_header("Content-Length", str(REPORT_FILE.stat().st_size))
                self.end_headers()
                with open(REPORT_FILE, "rb") as f:
                    self.wfile.write(f.read())
            else:
                self._send_json({"error": "Report file not found. Run pipeline first."}, status=404)
            return

        return super().do_GET()

    def do_POST(self):
        parsed = urlparse(self.path)

        if parsed.path == "/api/run-pipeline":
            print("[server] Triggering pipeline run via main.py ...")
            try:
                proc = subprocess.run(
                    [sys.executable, str(BASE_DIR / "main.py")],
                    capture_output=True,
                    text=True,
                    timeout=300,
                )
                output = proc.stdout + "\n" + proc.stderr
                success = (proc.returncode == 0)
                self._send_json({
                    "success": success,
                    "output": output,
                    "message": "Pipeline completed successfully." if success else "Pipeline execution completed with warnings."
                })
            except Exception as exc:
                self._send_json({"success": False, "error": str(exc)}, status=500)
            return

        if parsed.path == "/api/update-status":
            try:
                content_length = int(self.headers.get("Content-Length", 0))
                body = self.rfile.read(content_length).decode("utf-8")
                payload = json.loads(body)

                cand_id = payload.get("candidate_id", "").strip()
                status = payload.get("status", "New").strip()

                if cand_id:
                    _candidate_status_cache[cand_id] = status
                    self._send_json({"success": True, "candidate_id": cand_id, "status": status})
                else:
                    self._send_json({"error": "Invalid candidate ID"}, status=400)
            except Exception as exc:
                self._send_json({"error": str(exc)}, status=500)
            return

        self._send_json({"error": "Endpoint not found"}, status=404)


def run_server():
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")

    server_address = ("", PORT)
    httpd = HTTPServer(server_address, EnterpriseRecruitmentHandler)
    print("=" * 65)
    print(f"  [OK] RECRUITMENT PLATFORM WEB SERVER RUNNING")
    print(f"  [OK] Access URL: http://localhost:{PORT}")
    print("=" * 65)
    try:
        httpd.serve_forever()
    except KeyboardInterrupt:
        print("\n[server] Shutting down server.")
        httpd.server_close()


if __name__ == "__main__":
    run_server()
