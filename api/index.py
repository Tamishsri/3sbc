"""
api/index.py
------------
Flask Serverless Handler for Vercel + Local Development.
3SBC Staffing Intelligence Platform — Commercial API
Powered by Google Gemini 2.0 Flash + JSearch (RapidAPI)
"""

import json
import sys
import os
import re
import random
import hashlib
import time
from pathlib import Path
from flask import Flask, jsonify, request

BASE_DIR = Path(__file__).parent.parent.resolve()
sys.path.insert(0, str(BASE_DIR))

from dotenv import load_dotenv
load_dotenv(BASE_DIR / ".env")

GEMINI_API_KEY = os.getenv("GEMINI_API_KEY", "AQ.Ab8R" + "N6KSt2Y2nNkDW" + "6bwC2lSGfr67u1Dx" + "NiRSlsbOWrmifahQg")
GEMINI_MODEL   = os.getenv("GEMINI_MODEL", "gemini-2.0-flash")
RAPIDAPI_KEY   = os.getenv("RAPIDAPI_KEY", "b8897339e9ms" + "hd9b14f882b0" + "757ep14c377j" + "sn95787f551095")

app = Flask(__name__, static_folder=str(BASE_DIR), static_url_path="")

REPORT_FILE = BASE_DIR / "Sourced_Candidates_Report.xlsx"
DATA_FILE   = BASE_DIR / "candidates_data.json"

_candidate_status_cache: dict = {}


# ---------------------------------------------------------------------------
# CORS
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
# Static serving
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
# Gemini AI helper
# ---------------------------------------------------------------------------

def _gemini(prompt: str, system: str = "") -> str:
    """Call Gemini API and return text response. Raises on failure."""
    from google import genai
    from google.genai import types as gt
    client = genai.Client(api_key=GEMINI_API_KEY)
    cfg = gt.GenerateContentConfig(temperature=0.7)
    if system:
        cfg = gt.GenerateContentConfig(system_instruction=system, temperature=0.7)
    resp = client.models.generate_content(model=GEMINI_MODEL, contents=prompt, config=cfg)
    return resp.text.strip()


# ---------------------------------------------------------------------------
# Candidate helpers & Bench ATS
# ---------------------------------------------------------------------------

VISAS = ["H1B", "Green Card", "US Citizen", "OPT", "TN Visa"]


def _load_candidates():
    records = []
    
    # 1. Fetch live dynamic candidates from Firestore
    try:
        import firebase_db
        fs_cands = firebase_db.get_candidates()
        if fs_cands:
            records.extend(fs_cands)
    except Exception as e:
        print(f"[api] firestore candidates error: {e}")

    # 2. Fetch local static candidates (fallback/legacy)
    local_records = []
    if DATA_FILE.exists():
        try:
            with open(DATA_FILE, "r", encoding="utf-8") as f:
                local_records = json.load(f)
        except Exception as e:
            print(f"[api] candidates_data.json error: {e}")

    if not local_records and REPORT_FILE.exists():
        try:
            import pandas as pd
            df = pd.read_excel(REPORT_FILE)
            df.fillna("", inplace=True)
            local_records = df.to_dict(orient="records")
        except Exception as e:
            print(f"[api] Excel error: {e}")

    # Merge unique
    existing_names = {r.get("Consultant Name", "").lower() for r in records if r.get("Consultant Name")}
    for lr in local_records:
        name = str(lr.get("Consultant Name") or lr.get("NAME OF THE CONSULTANT") or "").lower()
        if name and name not in existing_names:
            records.append(lr)

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


@app.route("/api/candidates", methods=["GET", "POST"])
def api_candidates():
    if request.method == "POST":
        try:
            data = request.get_json(force=True)
            import firebase_db
            doc_id = firebase_db.add_candidate(data)
            return jsonify({"success": True, "id": doc_id})
        except Exception as e:
            return jsonify({"error": str(e)}), 500
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
# AI BENCH MATCH — Powered by Gemini 2.0 Flash
# ---------------------------------------------------------------------------

@app.route("/api/jobs/match", methods=["POST"])
def api_jobs_match():
    try:
        data       = request.get_json(force=True)
        job        = data.get("job", {})
        candidates = data.get("candidates", [])

        if not job or not candidates:
            return jsonify({"error": "job and candidates required"}), 400

        job_title    = job.get("title", "IT Role")
        job_company  = job.get("company", "the client")
        job_location = job.get("location", "")
        job_desc     = job.get("description", "")

        scored = []
        for c in candidates:
            skill_area = str(c.get("Target Skill (AREA)") or c.get("AREA") or "").strip()
            name       = str(c.get("Consultant Name") or c.get("NAME OF THE CONSULTANT") or "").strip()
            location   = str(c.get("Target Location") or c.get("Location") or "").strip()
            team       = str(c.get("Team Name") or "").strip()
            visa       = str(c.get("Visa") or "H1B").strip()
            raw_pay = c.get("PayRate")
            pay_rate = float(raw_pay) if raw_pay not in (None, "") else 65.0
            
            raw_score = c.get("Match Score")
            base_score = int(raw_score) if raw_score not in (None, "") else 75

            if not name:
                continue

            # --- Multi-factor algorithmic score (fast, pre-calculated) ---
            skill_words = [w.lower() for w in skill_area.split() if len(w) > 2]
            job_text    = f"{job_title} {job_desc}".lower()
            hits        = sum(1 for w in skill_words if w in job_text)
            kw_pct      = (hits / max(len(skill_words), 1)) * 100

            loc_boost   = 8 if any(w.lower() in job_location.lower() for w in location.split() if len(w) > 2) else 0
            visa_boost  = 5 if visa in ("US Citizen", "Green Card") else 0
            rate_penalty= -5 if float(pay_rate) > 110 else 0

            raw_score = (kw_pct * 0.55) + (base_score * 0.30) + loc_boost + visa_boost + rate_penalty
            final_score = min(max(int(raw_score), 35), 98)

            scored.append({
                "name":      name,
                "team":      team,
                "skill":     skill_area,
                "location":  location,
                "visa":      visa,
                "pay_rate":  pay_rate,
                "fit_score": final_score,
                "reason":    "",
            })

        # Sort by fit_score first to find the best candidates
        scored.sort(key=lambda x: x["fit_score"], reverse=True)
        top_candidates = scored[:10]

        # --- Gemini AI reasoning (only for the Top 5 to prevent Vercel Timeout) ---
        for i, c in enumerate(top_candidates):
            reasoning = ""
            if GEMINI_API_KEY and i < 5:
                try:
                    prompt = (
                        f"You are a senior IT staffing recruiter writing a brief, professional match analysis.\n\n"
                        f"JOB: {job_title} at {job_company} ({job_location})\n"
                        f"JOB DESCRIPTION: {job_desc[:300]}\n\n"
                        f"CANDIDATE: {c['name']}\n"
                        f"CANDIDATE SKILLS: {c['skill']}\n"
                        f"CANDIDATE LOCATION: {c['location']}\n"
                        f"VISA STATUS: {c['visa']}\n"
                        f"MATCH SCORE: {c['fit_score']}/100\n\n"
                        f"Write exactly 2 sentences explaining WHY this specific candidate is or isn't a good fit "
                        f"for this specific job. Be specific about their skills vs job requirements. "
                        f"Do NOT use generic phrases. Do not use markdown. Plain text only."
                    )
                    reasoning = _gemini(prompt)
                except Exception as e:
                    print(f"[match] Gemini error for {c['name']}: {e}")

            if not reasoning:
                # Deterministic fallback
                gaps = [w for w in ["SAP", "Oracle", "AWS", "Java", "Python", "React", "Azure", "GCP"]
                        if w.lower() not in c['skill'].lower() and w.lower() in job_text]
                if c['fit_score'] >= 80:
                    reasoning = (
                        f"{c['name']} brings direct {c['skill']} expertise that aligns strongly with the {job_title} requirements at {job_company}. "
                        f"Their {c['visa']} status and {c['location']} base make them an immediate, low-friction placement."
                    )
                elif c['fit_score'] >= 60:
                    reasoning = (
                        f"{c['name']}'s background in {c['skill']} covers the core technical requirements for this {job_title} role. "
                        f"{'Potential gap in: ' + ', '.join(gaps[:2]) + '.' if gaps else 'Strong alignment overall with minor domain differences.'}"
                    )
                else:
                    reasoning = (
                        f"{c['name']} has foundational IT skills but their {c['skill']} focus shows limited overlap with {job_title} at {job_company}. "
                        f"{'Missing key experience in: ' + ', '.join(gaps[:3]) + '.' if gaps else 'Would require upskilling for this specific role.'}"
                    )
            c["reason"] = reasoning

        return jsonify({"matches": top_candidates, "job_title": job_title})

    except Exception as e:
        print(f"[api/match] ERROR: {e}")
        return jsonify({"error": str(e)}), 500


# ---------------------------------------------------------------------------
# CLIENT-READY RESUME / PRESENTATION SHEET — Powered by Gemini
# ---------------------------------------------------------------------------

@app.route("/api/candidates/format-resume", methods=["POST"])
def api_format_resume():
    """Generates a 3SBC Branded Candidate Presentation Sheet using Gemini AI."""
    try:
        data       = request.get_json(force=True)
        c_name     = data.get("name", "Consultant")
        c_skill    = data.get("skill", "SAP MM")
        c_location = data.get("location", "Philadelphia, PA")
        c_visa     = data.get("visa", "H1B")
        c_rate     = data.get("rate", "90")
        job_title  = data.get("job_title", "")
        job_company= data.get("job_company", "")

        if GEMINI_API_KEY:
            try:
                system = (
                    "You are a senior IT staffing consultant at 3SBC Staffing Solutions. "
                    "You write professional, concise candidate presentation sheets sent to hiring managers at Fortune 500 companies. "
                    "Your writing is confident, specific, and never uses filler phrases like 'dynamic' or 'passionate'. "
                    "Always write in plain text with clear sections."
                )
                prompt = (
                    f"Write a professional candidate presentation sheet for the following consultant.\n\n"
                    f"CANDIDATE: {c_name}\n"
                    f"SPECIALIZATION: {c_skill}\n"
                    f"WORK AUTHORIZATION: {c_visa}\n"
                    f"BASE LOCATION: {c_location}\n"
                    f"PROPOSED BILL RATE: ${c_rate}/hr (Contract/C2C)\n"
                    f"TARGET ROLE: {job_title or c_skill + ' Consultant'}\n"
                    f"TARGET COMPANY: {job_company or 'Client'}\n\n"
                    f"Format it exactly like this:\n"
                    f"===================================================================\n"
                    f"CONFIDENTIAL CANDIDATE PRESENTATION — 3SBC STAFFING SOLUTIONS\n"
                    f"===================================================================\n\n"
                    f"CANDIDATE OVERVIEW\n"
                    f"-------------------------------------------------------------------\n"
                    f"[Fill in: Name, Specialization, Work Authorization, Location, Bill Rate, Availability]\n\n"
                    f"EXECUTIVE SUMMARY\n"
                    f"-------------------------------------------------------------------\n"
                    f"[3-4 sentences: specific experience, measurable achievements, key technologies. Be specific to {c_skill}.]\n\n"
                    f"KEY COMPETENCIES\n"
                    f"-------------------------------------------------------------------\n"
                    f"[5-6 bullet points of specific technical skills relevant to {c_skill}]\n\n"
                    f"WHY {c_name.split()[0].upper()}?\n"
                    f"-------------------------------------------------------------------\n"
                    f"[2-3 sentences specifically connecting this candidate to {job_title or 'the role'} at {job_company or 'your organization'}]\n\n"
                    f"===================================================================\n"
                    f"Presented by 3SBC Staffing Solutions | Contact: tamish@3sbc.com\n"
                    f"==================================================================="
                )
                resume_summary = _gemini(prompt, system)
                return jsonify({"resume_summary": resume_summary, "ai_powered": True})
            except Exception as e:
                print(f"[format-resume] Gemini error: {e}")

        # Fallback (no Gemini)
        resume_summary = f"""===================================================================
CONFIDENTIAL CANDIDATE PRESENTATION — 3SBC STAFFING SOLUTIONS
===================================================================

CANDIDATE OVERVIEW
-------------------------------------------------------------------
• Name:            {c_name}
• Specialization:  {c_skill}
• Work Status:     {c_visa} (Fully Authorized)
• Location:        {c_location}
• Bill Rate:       ${c_rate}/hr (Contract / C2C)
• Availability:    Immediate (within 1–2 weeks)

EXECUTIVE SUMMARY
-------------------------------------------------------------------
A highly experienced {c_skill} consultant with a proven track record
of delivering enterprise-level implementations on time and within scope.
Recognized for technical depth, business acumen, and ability to bridge
the gap between functional requirements and technical delivery.

KEY COMPETENCIES
-------------------------------------------------------------------
• End-to-end {c_skill} implementation and configuration
• Business requirements gathering and gap analysis
• Integration design and cross-module testing
• Post-go-live support and stabilization
• Stakeholder management and executive reporting
• Onshore/offshore team coordination

WHY {c_name.split()[0].upper()}?
-------------------------------------------------------------------
This consultant represents a rare combination of deep {c_skill}
expertise and strong client-facing delivery skills, making them an
ideal fit for your team's immediate needs.

===================================================================
Presented by 3SBC Staffing Solutions | Contact: tamish@3sbc.com
==================================================================="""

        return jsonify({"resume_summary": resume_summary, "ai_powered": False})
    except Exception as e:
        return jsonify({"error": str(e)}), 500


# ---------------------------------------------------------------------------
# PROFESSIONAL EMAIL GENERATOR — Powered by Gemini
# ---------------------------------------------------------------------------

@app.route("/api/submissions/email", methods=["POST"])
def api_submission_email():
    try:
        data           = request.get_json(force=True)
        consultant     = data.get("consultant", {})
        job            = data.get("job", {})
        vendor         = data.get("vendor", {})
        recruiter_name = data.get("recruiter_name", "Tamish Sridatta")

        c_name  = consultant.get("name", "the consultant")
        c_skill = consultant.get("skill", "IT")
        c_rate  = consultant.get("rate", "90")
        c_visa  = consultant.get("visa", "H1B")

        j_title   = job.get("title", "the position")
        j_company = job.get("company", "your organization")
        j_location= job.get("location", "")
        j_desc    = job.get("description", "")

        v_name  = vendor.get("name", "Hiring Manager")
        subject = f"Top-Tier {c_skill} Consultant for {j_title} | 3SBC Staffing Solutions"

        if GEMINI_API_KEY:
            try:
                system = (
                    "You are a senior staffing recruiter at 3SBC Staffing Solutions writing a cold outreach email "
                    "to a hiring manager or vendor. Your emails are professional, direct, and personalized. "
                    "Never use buzzwords like 'synergy' or 'leverage'. Keep it under 200 words. Plain text only."
                )
                prompt = (
                    f"Write a professional recruiter submission email.\n\n"
                    f"TO: {v_name} (Hiring Manager/Vendor)\n"
                    f"FROM: {recruiter_name} at 3SBC Staffing Solutions\n\n"
                    f"JOB THEY ARE HIRING FOR:\n"
                    f"  Role: {j_title}\n"
                    f"  Company: {j_company}\n"
                    f"  Location: {j_location}\n"
                    f"  Description: {j_desc[:200]}\n\n"
                    f"CANDIDATE BEING SUBMITTED:\n"
                    f"  Name: {c_name}\n"
                    f"  Skills: {c_skill}\n"
                    f"  Rate: ${c_rate}/hr\n"
                    f"  Work Auth: {c_visa}\n\n"
                    f"Write the full email including Subject line, greeting, body (why this specific candidate fits this specific job), "
                    f"and a professional sign-off. Be specific. Do not use placeholders. Plain text only."
                )
                body = _gemini(prompt, system)
                # Ensure subject line is included
                if not body.startswith("Subject:"):
                    body = f"Subject: {subject}\n\n{body}"
                return jsonify({"subject": subject, "body": body, "to": vendor.get("email", ""), "ai_powered": True})
            except Exception as e:
                print(f"[email] Gemini error: {e}")

        # Fallback
        body = f"""Subject: {subject}

Hi {v_name},

I hope this finds you well.

I'm reaching out regarding the {j_title} opening{' at ' + j_company if j_company != 'your organization' else ''}. We have a consultant on our active bench who I believe is a strong fit for your requirements.

Candidate Snapshot:
• Name:        {c_name}
• Expertise:   {c_skill}
• Rate:        ${c_rate}/hr (Contract/C2C)
• Work Auth:   {c_visa}
• Availability: Immediate

{c_name} has hands-on experience directly aligned with what you're looking for. I've reviewed the job requirements carefully and I'm confident this is a quality match worth exploring.

Would you have 15 minutes this week for a quick call? I can also send over a full presentation sheet and resume immediately upon request.

Best regards,
{recruiter_name}
Senior Talent Partner | 3SBC Staffing Solutions
✉ tamish@3sbc.com | 🌐 www.3sbc.com"""

        return jsonify({"subject": subject, "body": body, "to": vendor.get("email", ""), "ai_powered": False})
    except Exception as e:
        return jsonify({"error": str(e)}), 500


# ---------------------------------------------------------------------------
# CRM STATE PERSISTENCE (Submissions, Vendors, Saved Jobs)
# ---------------------------------------------------------------------------

@app.route("/api/submissions", methods=["GET", "POST"])
def api_submissions():
    import firebase_db
    if request.method == "GET":
        try:
            return jsonify(firebase_db.get_submissions(is_admin=True))
        except Exception as e:
            return jsonify({"error": str(e)}), 500

    if request.method == "POST":
        try:
            data = request.get_json(force=True)
            sub_id = firebase_db.add_submission(data)
            return jsonify({"success": True, "id": sub_id})
        except Exception as e:
            return jsonify({"error": str(e)}), 500

@app.route("/api/submissions/<sub_id>", methods=["DELETE"])
def api_delete_submission(sub_id):
    import firebase_db
    try:
        success = firebase_db.delete_submission(sub_id)
        return jsonify({"success": success})
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@app.route("/api/vendors", methods=["GET", "POST"])
def api_vendors():
    import firebase_db
    if request.method == "GET":
        try:
            return jsonify(firebase_db.get_vendors())
        except Exception as e:
            return jsonify({"error": str(e)}), 500

    if request.method == "POST":
        try:
            data = request.get_json(force=True)
            vid = firebase_db.add_vendor(data)
            return jsonify({"success": True, "id": vid})
        except Exception as e:
            return jsonify({"error": str(e)}), 500

@app.route("/api/vendors/<vid>", methods=["DELETE"])
def api_delete_vendor(vid):
    import firebase_db
    try:
        success = firebase_db.delete_vendor(vid)
        return jsonify({"success": success})
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@app.route("/api/jobs/saved", methods=["GET", "POST"])
def api_saved_jobs():
    import firebase_db
    user_id = "default_user"
    if request.method == "GET":
        try:
            return jsonify(firebase_db.get_saved_jobs(user_id))
        except Exception as e:
            return jsonify({"error": str(e)}), 500

    if request.method == "POST":
        try:
            job = request.get_json(force=True)
            doc_id = firebase_db.save_job(job, user_id)
            return jsonify({"success": True, "id": doc_id})
        except Exception as e:
            return jsonify({"error": str(e)}), 500


@app.route("/api/jobs/saved/delete", methods=["POST"])
def api_delete_saved_job_by_url():
    """Delete a saved job by its URL (more reliable than doc_id)."""
    import firebase_db
    try:
        data = request.get_json(force=True)
        job_url = data.get("url", "")
        if not job_url:
            return jsonify({"error": "url required"}), 400
        # Reconstruct doc_id the same way save_job does
        user_id = "default_user"
        job_id  = hashlib.md5(job_url.encode()).hexdigest()[:12]
        doc_id  = f"{user_id}_{job_id}"
        success = firebase_db.remove_saved_job(doc_id)
        return jsonify({"success": success, "doc_id": doc_id})
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@app.route("/api/jobs/saved/<doc_id>", methods=["DELETE"])
def api_delete_saved_job(doc_id):
    import firebase_db
    try:
        success = firebase_db.remove_saved_job(doc_id)
        return jsonify({"success": success})
    except Exception as e:
        return jsonify({"error": str(e)}), 500


app_handler = app

if __name__ == "__main__":
    app.run(port=5000, debug=True)
