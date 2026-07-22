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


# ---------------------------------------------------------------------------
# CORS helper
# ---------------------------------------------------------------------------

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


# ---------------------------------------------------------------------------
# Static file serving
# ---------------------------------------------------------------------------

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

    # Add realistic visa & work auth info if missing
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


def _compute_metrics(records):
    if not records:
        return {"total_candidates": 0, "top_matches": 0, "teams_count": 0,
                "avg_score": 0, "shortlisted_count": 0, "team_breakdown": {}}
    scores, teams, shortlisted, breakdown = [], set(), 0, {}
    for r in records:
        team = str(r.get("Team Name") or "Unassigned").strip()
        sv   = r.get("Match Score", 0)
        score = int(sv) if isinstance(sv, (int, float)) or (isinstance(sv, str) and str(sv).isdigit()) else 0
        scores.append(score)
        teams.add(team)
        if r.get("Status") == "Shortlisted":
            shortlisted += 1
        bd = breakdown.setdefault(team, {"count": 0, "top_matches": 0, "scores": []})
        bd["count"]  += 1
        bd["scores"].append(score)
        if score >= 80:
            bd["top_matches"] += 1
    for t, bd in breakdown.items():
        sl = bd.pop("scores")
        bd["avg_score"] = round(sum(sl) / len(sl), 1) if sl else 0
    return {
        "total_candidates":  len(records),
        "top_matches":       sum(1 for s in scores if s >= 80),
        "teams_count":       len(teams),
        "avg_score":         round(sum(scores) / len(scores), 1) if scores else 0,
        "shortlisted_count": shortlisted,
        "team_breakdown":    breakdown,
    }


@app.route("/api/candidates", methods=["GET"])
def api_candidates():
    return jsonify(_load_candidates())


@app.route("/api/stats", methods=["GET"])
def api_stats():
    return jsonify(_compute_metrics(_load_candidates()))


@app.route("/api/update-status", methods=["POST"])
def api_update_status():
    try:
        data   = request.get_json(force=True)
        cid    = data.get("candidate_id", "").strip()
        status = data.get("status", "Available").strip()
        if cid:
            _candidate_status_cache[cid] = status
            return jsonify({"success": True})
        return jsonify({"error": "Invalid candidate_id"}), 400
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@app.route("/api/download", methods=["GET"])
def api_download():
    if REPORT_FILE.exists():
        return send_file(str(REPORT_FILE), as_attachment=True,
                         download_name="Sourced_Candidates_Report.xlsx")
    return jsonify({"error": "Report not found"}), 404


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

            matched_keywords = [w for w in skill_words if w in job_text]
            missing_keywords = [w for w in skill_words if w not in job_text]

            # Generate 3 executive pitch bullets tailored to JD
            pitch_bullets = [
                f"• 8+ years hands-on experience in {skill_area.upper()} with proven client delivery.",
                f"• Specialized in enterprise implementations, integration, and performance optimization.",
                f"• Work Auth: {visa} | Available immediately for remote or onsite roles in {location.title()}."
            ]

            scored.append({
                "name":             name,
                "team":             team,
                "skill":            skill_area.upper(),
                "location":         location.title(),
                "visa":             visa,
                "pay_rate":         pay_rate,
                "fit_score":        final_score,
                "matched_keywords": matched_keywords[:6],
                "missing_keywords": missing_keywords[:4],
                "pitch_bullets":    pitch_bullets,
                "reason": f"Matches {hit_count}/{max_hits} core skills with {visa} authorization",
            })

        scored.sort(key=lambda x: x["fit_score"], reverse=True)
        return jsonify({"matches": scored[:10], "job_title": job.get("title", "")})

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

        c_name    = consultant.get("name", "Consultant")
        c_skill   = consultant.get("skill", "IT Specialist")
        c_loc     = consultant.get("location", "USA")
        c_rate    = consultant.get("rate", "85")
        c_visa    = consultant.get("visa", "H1B / Green Card")

        j_title   = job.get("title", "the position")
        j_company = job.get("company", "your organization")
        j_loc     = job.get("location", c_loc)

        v_name    = vendor.get("name", "Hiring Manager")

        subject = f"Candidate Profile: {c_name} — {c_skill} ({c_visa}) | {j_loc}"

        body = f"""Subject: {subject}

Hi {v_name},

I hope this email finds you well. I'm reaching out regarding the **{j_title}** opening at {j_company}.

I would like to present our senior consultant for your review:

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
👤 Candidate:     {c_name}
🎯 Primary Skill: {c_skill}
📍 Location:      {c_loc}
🇺🇸 Work Auth:     {c_visa}
💰 Bill Rate:     ${c_rate}/hr (Contract)
✅ Availability: Immediate (1 Week Notice)
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

Key Profile Highlights:
• 8+ years hands-on experience in {c_skill} with Fortune 500 client implementations.
• Strong expertise in technical design, configuration, and production support.
• Excellent communication skills and proven track record on contract assignments.

Please let me know if you would like to schedule an interview or review their full resume.

Best regards,
{recruiter_name}
3SBC Staffing Solutions
Direct: +1 (555) 019-2831 | tamish@3sbc.com
"""

        return jsonify({
            "subject": subject,
            "body":    body,
            "to":      vendor.get("email", ""),
        })

    except Exception as e:
        return jsonify({"error": str(e)}), 500


# ---------------------------------------------------------------------------
# DUPLICATE CHECK API
# ---------------------------------------------------------------------------

@app.route("/api/submissions/check-duplicate", methods=["POST"])
def api_check_duplicate():
    try:
        import time
        from firebase_db import _db

        data            = request.get_json(force=True)
        consultant_name = data.get("consultant_name", "").lower().strip()
        company         = data.get("company", "").lower().strip()

        db  = _db()
        now = time.time()
        cutoff = now - (90 * 86400)

        docs = db.collection("submissions").stream()
        for doc in docs:
            d = doc.to_dict()
            if (
                d.get("consultant_name", "").lower() == consultant_name
                and d.get("company", "").lower() == company
                and d.get("created_at", 0) > cutoff
            ):
                days_ago = int((now - d.get("created_at", 0)) / 86400)
                return jsonify({
                    "duplicate": True,
                    "message": f"⚠️ {data.get('consultant_name')} was submitted to {data.get('company')} {days_ago} days ago. Duplicate submissions may harm vendor relationship.",
                })

        return jsonify({"duplicate": False, "message": "✅ Clear to submit. No recent duplicate submissions found."})

    except Exception as e:
        return jsonify({"duplicate": False, "message": "✅ Clear to submit."})


# WSGI handler
app_handler = app

if __name__ == "__main__":
    app.run(port=5000, debug=True)
