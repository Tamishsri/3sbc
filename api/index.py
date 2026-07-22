"""
api/index.py
------------
Flask Serverless Handler for Vercel + Local Development.
3SBC Staffing Intelligence Platform — Commercial API
"""

import json
import sys
import os
import random
from pathlib import Path
from flask import Flask, jsonify, request, send_file

BASE_DIR = Path(__file__).parent.parent.resolve()
sys.path.insert(0, str(BASE_DIR))

app = Flask(__name__, static_folder=str(BASE_DIR), static_url_path="")

REPORT_FILE = BASE_DIR / "Sourced_Candidates_Report.xlsx"
DATA_FILE   = BASE_DIR / "candidates_data.json"

_candidate_status_cache: dict = {}


def _cors(response):
    response.headers["Access-Control-Allow-Origin"]  = "*"
    response.headers["Access-Control-Allow-Methods"] = "GET,POST,DELETE,OPTIONS"
    response.headers["Access-Control-Allow-Headers"] = "Content-Type,Authorization"
    return response


@app.after_request
def after_request(response):
    return _cors(response)


@app.route("/api/<path:path>", methods=["OPTIONS"])
def options_handler(path):
    return jsonify({}), 200


@app.route("/")
def serve_index():
    idx = BASE_DIR / "index.html"
    if idx.exists():
        with open(idx, "r", encoding="utf-8") as f:
            return f.read(), 200, {"Content-Type": "text/html; charset=utf-8"}
    return "<h1>3SBC Platform</h1>", 200


@app.route("/styles.css")
def serve_css():
    f = BASE_DIR / "styles.css"
    return (open(f).read(), 200, {"Content-Type": "text/css"}) if f.exists() else ("", 404)


@app.route("/app.js")
def serve_js():
    f = BASE_DIR / "app.js"
    return (open(f).read(), 200, {"Content-Type": "application/javascript"}) if f.exists() else ("", 404)


@app.route("/candidates_data.json")
def serve_data():
    if DATA_FILE.exists():
        with open(DATA_FILE, "r", encoding="utf-8") as f:
            return f.read(), 200, {"Content-Type": "application/json"}
    return "[]", 200


# ---------------------------------------------------------------------------
# Candidate helpers & Bench ATS
# ---------------------------------------------------------------------------

VISAS = ["H1B", "Green Card", "US Citizen", "OPT", "TN Visa"]

def _load_candidates():
    records = []
    if DATA_FILE.exists():
        try:
            with open(DATA_FILE, "r", encoding="utf-8") as f:
                records = json.load(f)
        except Exception as e:
            print(f"[api] candidates_data.json error: {e}")

    if not records and REPORT_FILE.exists():
        try:
            import pandas as pd
            df = pd.read_excel(REPORT_FILE)
            df.fillna("", inplace=True)
            records = df.to_dict(orient="records")
        except Exception as e:
            print(f"[api] Excel error: {e}")

    random.seed(42)
    for r in records:
        cid = f"{r.get('Team Name')}::{r.get('Candidate Name/Title')}".strip()
        r["Status"] = _candidate_status_cache.get(cid, r.get("Status", "Available"))
        if "Visa" not in r:
            r["Visa"] = random.choice(VISAS)
        if "PayRate" not in r:
            score = int(r.get("Match Score", 75))
            r["PayRate"] = 55 + (score // 3)

    return records


@app.route("/api/candidates", methods=["GET"])
def api_candidates():
    return jsonify(_load_candidates())


@app.route("/api/stats", methods=["GET"])
def api_stats():
    records = _load_candidates()
    scores  = [int(r.get("Match Score", 0)) for r in records]
    top     = sum(1 for s in scores if s >= 80)
    avg     = round(sum(scores) / len(scores), 1) if scores else 0
    return jsonify({
        "total_candidates": len(records),
        "top_matches":      top,
        "teams_count":      4,
        "avg_score":        avg,
    })


# ---------------------------------------------------------------------------
# JOB SEARCH API
# ---------------------------------------------------------------------------

@app.route("/api/jobs/search", methods=["GET"])
def api_jobs_search():
    skill    = request.args.get("skill", "").strip() or "SAP MM"
    location = request.args.get("location", "").strip() or "Philadelphia, PA"
    job_type = request.args.get("job_type", "contract").strip()
    days     = int(request.args.get("days", 3))
    boards   = [b.strip() for b in request.args.get("boards", "").split(",") if b.strip()] or None
    use_cache= request.args.get("cache", "1") != "0"

    try:
        from job_searcher import search_jobs
        result = search_jobs(
            skill=skill,
            location=location,
            job_type=job_type,
            days=days,
            boards=boards,
            use_cache=use_cache,
        )
        return jsonify(result)
    except Exception as e:
        print(f"[api] job search error: {e}")
        return jsonify({
            "boards": {b: [] for b in (boards or ["dice", "indeed", "linkedin", "ziprecruiter", "monster"])},
            "total": 0,
            "rate_intelligence": {},
            "error": str(e),
            "cached": False,
        }), 200


# ---------------------------------------------------------------------------
# AI BENCH MATCH & PITCH BULLET GENERATOR
# ---------------------------------------------------------------------------

@app.route("/api/jobs/match", methods=["POST"])
def api_jobs_match():
    try:
        data       = request.get_json(force=True)
        job        = data.get("job", {})
        candidates = data.get("candidates", [])

        if not job or not candidates:
            return jsonify({"error": "job and candidates required"}), 400

        job_text = f"{job.get('title','')} {job.get('description','')}".lower()
        scored   = []

        for c in candidates:
            skill_area = str(c.get("Target Skill (AREA)", "") or c.get("AREA", "")).lower()
            name       = str(c.get("Consultant Name", "") or c.get("NAME OF THE CONSULTANT", ""))
            location   = str(c.get("Target Location", "") or c.get("Location", "")).lower()
            team       = str(c.get("Team Name", ""))
            base_score = int(c.get("Match Score", 75))
            visa       = c.get("Visa", "H1B")
            pay_rate   = c.get("PayRate", 65)

            skill_words = [w for w in skill_area.split() if len(w) > 2]
            hit_count   = sum(1 for w in skill_words if w in job_text)
            max_hits    = max(len(skill_words), 1)
            kw_score    = round((hit_count / max_hits) * 100)

            job_loc   = job.get("location", "").lower()
            loc_boost = 10 if any(w in job_loc for w in location.split() if len(w) > 2) else 0

            final_score = min(round((kw_score * 0.6) + (base_score * 0.3) + loc_boost), 99)

            scored.append({
                "name":         name,
                "team":         team,
                "skill":        skill_area.upper(),
                "location":     location.title(),
                "visa":         visa,
                "pay_rate":     pay_rate,
                "fit_score":    final_score,
                "reason":       f"Matches {hit_count}/{max_hits} core skills with {visa} authorization",
            })

        scored.sort(key=lambda x: x["fit_score"], reverse=True)
        return jsonify({"matches": scored[:10], "job_title": job.get("title", "")})

    except Exception as e:
        return jsonify({"error": str(e)}), 500


# ---------------------------------------------------------------------------
# CLIENT-READY RESUME SUMMARY GENERATOR (New Feature!)
# ---------------------------------------------------------------------------

@app.route("/api/candidates/format-resume", methods=["POST"])
def api_format_resume():
    """Generates a 3SBC Branded Candidate Presentation Sheet ready to send to clients."""
    try:
        data       = request.get_json(force=True)
        c_name     = data.get("name", "Consultant")
        c_skill    = data.get("skill", "SAP MM")
        c_location = data.get("location", "Philadelphia, PA")
        c_visa     = data.get("visa", "US Citizen / H1B")
        c_rate     = data.get("rate", "90")

        resume_summary = f"""===================================================================
3SBC STAFFING SOLUTIONS — CLIENT CANDIDATE PRESENTATION SHEET
===================================================================

CANDIDATE SUMMARY:
• Candidate Name:  {c_name}
• Primary Skill:   {c_skill}
• Work Auth:       {c_visa}
• Location:        {c_location}
• Bill Rate:       ${c_rate}/hr (Contract)
• Availability:   Immediate (1 Week Notice)

EXECUTIVE OVERVIEW:
• 8+ years of hands-on experience in {c_skill} design, configuration, and testing.
• Successfully led 3 end-to-end enterprise implementations and post-go-live support.
• Expert in cross-functional integration, master data management, and user training.
• Strong communication skills with experience presenting to executive stakeholders.

SUMMARY OF QUALIFICATIONS:
1. Deep technical & functional expertise in {c_skill}.
2. Proven track record on complex, fast-paced contract projects.
3. Fully authorized to work for any employer in the United States.

===================================================================
Presented by 3SBC Staffing Solutions | tamish@3sbc.com
==================================================================="""

        return jsonify({"resume_summary": resume_summary})
    except Exception as e:
        return jsonify({"error": str(e)}), 500


# ---------------------------------------------------------------------------
# MARGIN CALCULATOR & EMAIL GENERATOR
# ---------------------------------------------------------------------------

@app.route("/api/submissions/email", methods=["POST"])
def api_submission_email():
    try:
        data           = request.get_json(force=True)
        consultant     = data.get("consultant", {})
        job            = data.get("job", {})
        vendor         = data.get("vendor", {})
        recruiter_name = data.get("recruiter_name", "Tamish Sridatta")

        c_name  = consultant.get("name", "Consultant")
        c_skill = consultant.get("skill", "IT Specialist")
        c_rate  = consultant.get("rate", "90")

        j_title   = job.get("title", "the position")
        j_company = job.get("company", "your organization")

        v_name  = vendor.get("name", "Hiring Manager")
        subject = f"3SBC Candidate Submission: {c_name} — {c_skill} | {j_title}"

        body = f"""Subject: {subject}

Hi {v_name},

I hope this email finds you well. I'm reaching out regarding the **{j_title}** position at {j_company}.

I am pleased to submit our consultant for your review:

• Candidate: {c_name}
• Skill:     {c_skill}
• Rate:      ${c_rate}/hr (Contract)
• Status:    Available Immediately

Please let me know if you would like to schedule an interview or review their candidate presentation sheet.

Best regards,
{recruiter_name}
3SBC Staffing Solutions | tamish@3sbc.com
"""

        return jsonify({"subject": subject, "body": body, "to": vendor.get("email", "")})
    except Exception as e:
        return jsonify({"error": str(e)}), 500


app_handler = app

if __name__ == "__main__":
    app.run(port=5000, debug=True)
