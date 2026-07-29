"""
3SBC Job Finder – API
Flask backend serving job search results.
Sources: LinkedIn Guest API + Dice JSON API (both confirmed working).
"""
import hashlib
import json
import os
import re
import time
import urllib.parse
from concurrent.futures import ThreadPoolExecutor, as_completed

import requests
from bs4 import BeautifulSoup
from dotenv import load_dotenv
from flask import Flask, jsonify, request
from flask_cors import CORS

load_dotenv()

app = Flask(__name__)
CORS(app)

GEMINI_API_KEY = os.getenv("GEMINI_API_KEY", "")
RAPIDAPI_KEY   = os.getenv("RAPIDAPI_KEY", "")

UA = ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
      "AppleWebKit/537.36 (KHTML, like Gecko) "
      "Chrome/125.0.0.0 Safari/537.36")

SESS = requests.Session()
SESS.headers.update({"User-Agent": UA, "Accept-Language": "en-US,en;q=0.9"})

# ── helpers ──────────────────────────────────────────────────────

def clean(t):
    return re.sub(r"\s+", " ", str(t or "")).strip()

def uid(board, title, company):
    raw = f"{board}|{title.lower()}|{company.lower()}"
    return board + "_" + hashlib.md5(raw.encode()).hexdigest()[:10]

def days_label(n):
    if n == 0: return "Today"
    if n == 1: return "1d ago"
    return f"{n}d ago"

# ── LinkedIn guest API ────────────────────────────────────────────

def scrape_linkedin(skill, location, job_type):
    jobs = []
    q   = urllib.parse.quote_plus(skill)
    loc = urllib.parse.quote_plus(location)
    for page in range(4):
        start = page * 25
        try:
            url = (f"https://www.linkedin.com/jobs-guest/jobs/api/seeMoreJobPostings/search"
                   f"?keywords={q}&location={loc}&f_TPR=r604800&start={start}")
            r = SESS.get(url, timeout=6)
            if r.status_code != 200 or not r.text.strip():
                break
            soup = BeautifulSoup(r.text, "html.parser")
            cards = soup.select("li")
            if not cards:
                break
            for card in cards:
                t_el  = card.select_one(".base-search-card__title")
                c_el  = card.select_one(".base-search-card__subtitle")
                l_el  = card.select_one(".job-search-card__location")
                a_el  = card.select_one("a.base-card__full-link")
                tm_el = card.select_one("time")
                if not t_el:
                    continue
                title   = clean(t_el.get_text())
                company = clean(c_el.get_text() if c_el else "")
                loc_str = clean(l_el.get_text() if l_el else location)
                job_url = a_el.get("href", "#") if a_el else "#"
                days_ago = 0
                if tm_el:
                    pt = clean(tm_el.get_text()).lower()
                    if "day" in pt:
                        m = re.search(r"(\d+)", pt)
                        days_ago = int(m.group(1)) if m else 1
                    elif "week" in pt:
                        m = re.search(r"(\d+)", pt)
                        days_ago = (int(m.group(1)) if m else 1) * 7
                    elif "month" in pt:
                        days_ago = 30
                jobs.append({
                    "id": uid("linkedin", title, company),
                    "board": "linkedin",
                    "board_label": "LinkedIn",
                    "title": title,
                    "company": company,
                    "location": loc_str,
                    "salary": "",
                    "job_type": job_type.title(),
                    "days_ago": days_ago,
                    "posted": days_label(days_ago),
                    "url": job_url,
                    "apply_url": job_url,
                })
        except Exception as e:
            print(f"[LinkedIn] page {page} error: {e}")
            break
    return jobs[:60]

# ── Dice JSON API ─────────────────────────────────────────────────

def scrape_dice(skill, location, job_type):
    jobs = []
    try:
        q = urllib.parse.quote_plus(skill)
        api = (f"https://job-search-api.svc.dhigroupinc.com/v1/dice/jobs/search"
               f"?q={q}&countryCode2=US&radius=50&radiusUnit=mi&page=1&pageSize=30"
               f"&filters.postedDate=THREE_DAYS&language=en")
        h = {**dict(SESS.headers), "x-api-key": "1YAt0R9wBg4WfsF9VB2778F5CHLAPMVW3WAZcKd8"}
        r = SESS.get(api, headers=h, timeout=6)
        if r.status_code != 200:
            return []
        for job in r.json().get("data", []):
            title   = clean(job.get("title", ""))
            company = clean(job.get("hiringOrganization", {}).get("name", "") if isinstance(job.get("hiringOrganization"), dict) else "")
            loc_str = clean(job.get("jobLocation", {}).get("displayName", location) if isinstance(job.get("jobLocation"), dict) else location)
            job_url = job.get("applyUrl") or f"https://www.dice.com/jobs?q={q}"
            days_ago = 0
            if job.get("datePosted"):
                try:
                    from datetime import datetime, timezone
                    dt = datetime.fromisoformat(job["datePosted"].replace("Z", "+00:00"))
                    days_ago = max(0, (datetime.now(timezone.utc) - dt).days)
                except Exception:
                    pass
            if not title:
                continue
            jobs.append({
                "id": uid("dice", title, company),
                "board": "dice",
                "board_label": "Dice",
                "title": title,
                "company": company,
                "location": loc_str,
                "salary": "",
                "job_type": job_type.title(),
                "days_ago": days_ago,
                "posted": days_label(days_ago),
                "url": job_url,
                "apply_url": job_url,
            })
    except Exception as e:
        print(f"[Dice] error: {e}")
    return jobs

# ── board dispatcher ──────────────────────────────────────────────

def fetch_board(board, skill, location, job_type):
    fn = {"linkedin": scrape_linkedin, "dice": scrape_dice}
    jobs = fn.get(board, lambda *a: [])(skill, location, job_type)
    jobs = [j for j in jobs if j.get("title") and len(j["title"]) > 3]
    jobs.sort(key=lambda x: x.get("days_ago", 999))
    print(f"[3SBC] {board.upper()}: {len(jobs)} jobs")
    return board, jobs[:30]

# ── routes ────────────────────────────────────────────────────────

@app.route("/")
def serve_index():
    try:
        with open("index.html", "r", encoding="utf-8") as f:
            from flask import Response
            return Response(f.read(), mimetype="text/html")
    except Exception as e:
        return f"<h1>Error loading index.html: {e}</h1>", 500


@app.route("/api/jobs/search")
def api_search():
    skill    = request.args.get("skill", "").strip() or "SAP MM"
    location = request.args.get("location", "").strip() or "United States of America"
    job_type = request.args.get("job_type", "contract").strip()

    t0 = time.time()
    boards_to_scrape = ["linkedin", "dice"]
    results = {b: [] for b in boards_to_scrape}

    with ThreadPoolExecutor(max_workers=2) as ex:
        futures = {ex.submit(fetch_board, b, skill, location, job_type): b for b in boards_to_scrape}
        for fut in as_completed(futures):
            k, jobs = fut.result()
            results[k] = jobs

    total   = sum(len(v) for v in results.values())
    elapsed = round(time.time() - t0, 1)

    return jsonify({
        "boards":  results,
        "total":   total,
        "elapsed": elapsed,
        "search":  {"skill": skill, "location": location, "job_type": job_type},
    })


@app.route("/api/health")
def health():
    return jsonify({"status": "ok", "version": "3.0"})


if __name__ == "__main__":
    app.run(debug=True, port=5000)
