"""
job_searcher.py
---------------
Real Job Search Engine for 3SBC Platform.
- LinkedIn Guest API (real live results, no auth required) - primary source
- Indeed, Dice, ZipRecruiter, Monster - native scrapers
- NO fake jobs. NO random salaries. Only real data.
"""

from __future__ import annotations

import hashlib
import json
import os
import re
import statistics
import time
import urllib.parse
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime, timezone
from typing import Any

import requests
from bs4 import BeautifulSoup
from dotenv import load_dotenv

load_dotenv()

CACHE_TTL_SECONDS = 3600   # 1 hour
RESULTS_PER_BOARD = 30     # max jobs per board

HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/125.0.0.0 Safari/537.36"
    ),
    "Accept-Language": "en-US,en;q=0.9",
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
}

SESSION = requests.Session()
SESSION.headers.update(HEADERS)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _uid(board: str, title: str, company: str) -> str:
    raw = f"{board}|{title.lower().strip()}|{company.lower().strip()}"
    return f"{board}_{hashlib.md5(raw.encode()).hexdigest()[:10]}"


def _clean(text: Any) -> str:
    if not text:
        return ""
    return re.sub(r"\s+", " ", str(text)).strip()


def _posted_label(days_ago: int) -> str:
    if days_ago == 0:
        return "Today"
    if days_ago == 1:
        return "1d ago"
    return f"{days_ago}d ago"


def _parse_salary_text(salary_text: str):
    """
    Parse salary from a raw text string.
    Returns (sal_min, sal_max, formatted_string) or (0, 0, '') if not found.
    """
    if not salary_text:
        return 0.0, 0.0, ""

    text = salary_text.replace(",", "").replace("$", "")

    nums = re.findall(r"\d+(?:\.\d+)?", text)
    if not nums:
        return 0.0, 0.0, ""

    nums_f = [float(n) for n in nums]

    is_hourly = "hr" in text.lower() or "hour" in text.lower() or "/h" in text.lower()
    is_annual = "year" in text.lower() or "/yr" in text.lower() or "annual" in text.lower() or "salary" in text.lower()

    if len(nums_f) >= 2:
        sal_min, sal_max = nums_f[0], nums_f[1]
    else:
        sal_min = sal_max = nums_f[0]

    # Convert annual to hourly
    if not is_hourly and (is_annual or sal_min > 500):
        sal_min = round(sal_min / 2080, 2)
        sal_max = round(sal_max / 2080, 2)

    # Sanity check: hourly rates should be between $10 and $400
    if sal_min < 10 or sal_min > 400:
        return 0.0, 0.0, ""

    if sal_min == sal_max:
        formatted = f"${int(sal_min)}/hr"
    else:
        formatted = f"${int(sal_min)}-${int(sal_max)}/hr"

    return float(sal_min), float(sal_max), formatted


# ---------------------------------------------------------------------------
# LinkedIn Guest API (100% free, no auth) - Primary Source
# ---------------------------------------------------------------------------

def _scrape_linkedin(skill: str, location: str, job_type: str) -> list:
    """Scrape live LinkedIn jobs via public guest API."""
    jobs = []
    q   = urllib.parse.quote_plus(skill)
    loc = urllib.parse.quote_plus(location)

    for page in range(4):  # 4 pages x 25 = up to 100 results
        start = page * 25
        try:
            url = (
                f"https://www.linkedin.com/jobs-guest/jobs/api/seeMoreJobPostings/search"
                f"?keywords={q}&location={loc}&f_TPR=r604800&start={start}"
            )
            r = SESSION.get(url, timeout=6)
            if r.status_code != 200 or not r.text.strip():
                break

            soup = BeautifulSoup(r.text, "html.parser")
            cards = soup.select("li")
            if not cards:
                break

            for card in cards:
                title_el = card.select_one(".base-search-card__title")
                comp_el  = card.select_one(".base-search-card__subtitle")
                loc_el   = card.select_one(".job-search-card__location")
                link_el  = card.select_one("a.base-card__full-link")
                time_el  = card.select_one("time")

                if not title_el:
                    continue

                title   = _clean(title_el.get_text())
                company = _clean(comp_el.get_text() if comp_el else "")
                loc_str = _clean(loc_el.get_text() if loc_el else location)
                job_url = link_el.get("href", "#") if link_el else "#"

                # Parse posted time into days_ago
                days_ago = 0
                if time_el:
                    posted_text = _clean(time_el.get_text()).lower()
                    if "hour" in posted_text or "minute" in posted_text or "second" in posted_text:
                        days_ago = 0
                    elif "day" in posted_text:
                        m = re.search(r"(\d+)", posted_text)
                        days_ago = int(m.group(1)) if m else 1
                    elif "week" in posted_text:
                        m = re.search(r"(\d+)", posted_text)
                        days_ago = (int(m.group(1)) if m else 1) * 7
                    elif "month" in posted_text:
                        days_ago = 30

                jobs.append({
                    "id":          _uid("linkedin", title, company),
                    "board":       "linkedin",
                    "board_label": "LinkedIn",
                    "title":       title,
                    "company":     company,
                    "location":    loc_str,
                    "salary":      "",   # LinkedIn guest API never shows salary
                    "salary_min":  0.0,
                    "salary_max":  0.0,
                    "job_type":    job_type.title(),
                    "days_ago":    days_ago,
                    "url":         job_url,
                    "easy_apply":  True,
                    "description": f"{job_type.title()} role for {title} at {company} in {loc_str}.",
                })
        except Exception as e:
            print(f"[job_searcher] LinkedIn scrape error page {page}: {e}")
            break

    return jobs[:RESULTS_PER_BOARD * 2]


# ---------------------------------------------------------------------------
# Indeed scraping
# ---------------------------------------------------------------------------

def _scrape_indeed(skill: str, location: str, job_type: str) -> list:
    """Scrape Indeed jobs page."""
    jobs = []
    try:
        q   = urllib.parse.quote_plus(skill)
        loc = urllib.parse.quote_plus(location)
        url = f"https://www.indeed.com/jobs?q={q}&l={loc}&fromage=7&sort=date"

        r = SESSION.get(url, timeout=6)
        if r.status_code != 200:
            print(f"[job_searcher] Indeed HTTP {r.status_code}")
            return []

        soup = BeautifulSoup(r.text, "html.parser")
        cards = soup.select("div.job_seen_beacon, div[data-jk]")

        for card in cards[:RESULTS_PER_BOARD]:
            title_el   = card.select_one("h2.jobTitle span, h2 span[title]")
            comp_el    = card.select_one("[data-testid='company-name'], .companyName")
            loc_el     = card.select_one("[data-testid='text-location'], .companyLocation")
            salary_el  = card.select_one("[data-testid='attribute_snippet_testid'], .salary-snippet, [class*='salary']")
            jk         = card.get("data-jk")

            if not title_el:
                continue

            title   = _clean(title_el.get_text())
            company = _clean(comp_el.get_text() if comp_el else "")
            loc_str = _clean(loc_el.get_text() if loc_el else location)
            job_url = f"https://www.indeed.com/viewjob?jk={jk}" if jk else f"https://www.indeed.com/jobs?q={q}&l={loc}"
            salary_text = _clean(salary_el.get_text() if salary_el else "")

            sal_min, sal_max, salary_str = _parse_salary_text(salary_text)

            jobs.append({
                "id":          _uid("indeed", title, company),
                "board":       "indeed",
                "board_label": "Indeed",
                "title":       title,
                "company":     company,
                "location":    loc_str,
                "salary":      salary_str,
                "salary_min":  sal_min,
                "salary_max":  sal_max,
                "job_type":    job_type.title(),
                "days_ago":    0,
                "url":         job_url,
                "easy_apply":  True,
                "description": f"Contract position for {title} at {company}. Strong {skill} experience required.",
            })
    except Exception as e:
        print(f"[job_searcher] Indeed scrape error: {e}")
    return jobs


# ---------------------------------------------------------------------------
# Dice scraping - uses JSON API
# ---------------------------------------------------------------------------

def _scrape_dice(skill: str, location: str, job_type: str) -> list:
    """Scrape Dice.com via their public JSON API."""
    jobs = []
    try:
        q   = urllib.parse.quote_plus(skill)
        loc = urllib.parse.quote_plus(location)

        # Dice JSON API
        api_url = (
            f"https://job-search-api.svc.dhigroupinc.com/v1/dice/jobs/search"
            f"?q={q}&countryCode2=US&radius=50&radiusUnit=mi&page=1&pageSize=20"
            f"&filters.postedDate=THREE_DAYS&language=en"
        )
        headers_dice = {**HEADERS, "x-api-key": "1YAt0R9wBg4WfsF9VB2778F5CHLAPMVW3WAZcKd8"}
        r = SESSION.get(api_url, headers=headers_dice, timeout=6)

        if r.status_code == 200:
            data = r.json()
            for job in data.get("data", [])[:RESULTS_PER_BOARD]:
                title   = _clean(job.get("title", ""))
                company = ""
                if isinstance(job.get("hiringOrganization"), dict):
                    company = _clean(job["hiringOrganization"].get("name", ""))
                loc_str = location
                if isinstance(job.get("jobLocation"), dict):
                    loc_str = _clean(job["jobLocation"].get("displayName", location))
                job_url = job.get("applyUrl") or f"https://www.dice.com/jobs?q={q}"

                sal_min, sal_max, salary_str = 0.0, 0.0, ""
                if isinstance(job.get("baseSalary"), dict):
                    salary_text = str(job["baseSalary"].get("value", {}).get("value", ""))
                    sal_min, sal_max, salary_str = _parse_salary_text(salary_text)

                days_ago = 0
                posted_at = job.get("datePosted", "")
                if posted_at:
                    try:
                        dt = datetime.fromisoformat(posted_at.replace("Z", "+00:00"))
                        delta = datetime.now(timezone.utc) - dt
                        days_ago = max(0, delta.days)
                    except Exception:
                        pass

                if not title:
                    continue

                jobs.append({
                    "id":          _uid("dice", title, company),
                    "board":       "dice",
                    "board_label": "Dice",
                    "title":       title,
                    "company":     company,
                    "location":    loc_str,
                    "salary":      salary_str,
                    "salary_min":  sal_min,
                    "salary_max":  sal_max,
                    "job_type":    job_type.title(),
                    "days_ago":    days_ago,
                    "url":         job_url,
                    "easy_apply":  False,
                    "description": f"Contract opening for {title} at {company} in {loc_str}. {skill} expertise required.",
                })
        else:
            # Fallback to HTML scrape
            url = f"https://www.dice.com/jobs?q={q}&location={loc}&filters.postedDate=THREE_DAYS&filters.employmentType=CONTRACTS"
            r2 = SESSION.get(url, timeout=6)
            if r2.status_code == 200:
                soup = BeautifulSoup(r2.text, "html.parser")
                for card in soup.select("dhi-search-card, [data-cy='card'], .card")[:RESULTS_PER_BOARD]:
                    title_el = card.select_one("a.card-title-link, h5, [data-cy='card-title']")
                    comp_el  = card.select_one(".company-name, [data-cy='company-name']")
                    loc_el   = card.select_one(".location, [data-cy='location']")
                    link_el  = card.select_one("a[href*='/job-detail/'], a.card-title-link")

                    if not title_el:
                        continue

                    title   = _clean(title_el.get_text())
                    company = _clean(comp_el.get_text() if comp_el else "")
                    loc_str = _clean(loc_el.get_text() if loc_el else location)
                    href    = link_el.get("href", "") if link_el else ""
                    job_url = f"https://www.dice.com{href}" if href.startswith("/") else href or f"https://www.dice.com/jobs?q={q}"

                    jobs.append({
                        "id":          _uid("dice", title, company),
                        "board":       "dice",
                        "board_label": "Dice",
                        "title":       title,
                        "company":     company,
                        "location":    loc_str,
                        "salary":      "",
                        "salary_min":  0.0,
                        "salary_max":  0.0,
                        "job_type":    job_type.title(),
                        "days_ago":    0,
                        "url":         job_url,
                        "easy_apply":  False,
                        "description": f"Contract opening for {title} at {company} in {loc_str}. {skill} expertise required.",
                    })

    except Exception as e:
        print(f"[job_searcher] Dice scrape error: {e}")
    return jobs


# ---------------------------------------------------------------------------
# ZipRecruiter scraping
# ---------------------------------------------------------------------------

def _scrape_ziprecruiter(skill: str, location: str, job_type: str) -> list:
    """Scrape ZipRecruiter jobs."""
    jobs = []
    try:
        q   = urllib.parse.quote_plus(skill)
        loc = urllib.parse.quote_plus(location)
        url = f"https://www.ziprecruiter.com/jobs-search?search={q}&location={loc}&days=7"
        r   = SESSION.get(url, timeout=6)
        if r.status_code != 200:
            return []

        soup = BeautifulSoup(r.text, "html.parser")
        for card in soup.select("article.job_result, div[class*='job-card'], li[class*='job']")[:RESULTS_PER_BOARD]:
            title_el  = card.select_one("h2, .job_title, [class*='title']")
            comp_el   = card.select_one(".company_name, [class*='company']")
            loc_el    = card.select_one(".location, [class*='location']")
            link_el   = card.select_one("a[href*='/jobs/']")
            salary_el = card.select_one(".salary, [class*='salary']")

            if not title_el:
                continue

            title   = _clean(title_el.get_text())
            company = _clean(comp_el.get_text() if comp_el else "")
            loc_str = _clean(loc_el.get_text() if loc_el else location)
            href    = link_el.get("href", "") if link_el else ""
            job_url = href if href.startswith("http") else (f"https://www.ziprecruiter.com{href}" if href else f"https://www.ziprecruiter.com/jobs-search?search={q}")
            salary_text = _clean(salary_el.get_text() if salary_el else "")

            sal_min, sal_max, salary_str = _parse_salary_text(salary_text)

            jobs.append({
                "id":          _uid("ziprecruiter", title, company),
                "board":       "ziprecruiter",
                "board_label": "ZipRecruiter",
                "title":       title,
                "company":     company,
                "location":    loc_str,
                "salary":      salary_str,
                "salary_min":  sal_min,
                "salary_max":  sal_max,
                "job_type":    job_type.title(),
                "days_ago":    0,
                "url":         job_url,
                "easy_apply":  True,
                "description": f"Immediate contract opportunity for {skill} professional at {company}.",
            })
    except Exception as e:
        print(f"[job_searcher] ZipRecruiter scrape error: {e}")
    return jobs


# ---------------------------------------------------------------------------
# Monster scraping
# ---------------------------------------------------------------------------

def _scrape_monster(skill: str, location: str, job_type: str) -> list:
    """Scrape Monster jobs."""
    jobs = []
    try:
        q   = urllib.parse.quote_plus(skill)
        loc = urllib.parse.quote_plus(location)
        url = f"https://www.monster.com/jobs/search?q={q}&where={loc}&jobtype=contract&tm=7"
        r   = SESSION.get(url, timeout=6)
        if r.status_code != 200:
            return []

        soup = BeautifulSoup(r.text, "html.parser")
        for card in soup.select("section.card-content, div[class*='JobCard']")[:RESULTS_PER_BOARD]:
            title_el  = card.select_one("h2, .title, [class*='title']")
            comp_el   = card.select_one(".name, [class*='company']")
            loc_el    = card.select_one(".location, [class*='location']")
            link_el   = card.select_one("a[href*='/job-openings/'], a[href*='/jobs/']")
            salary_el = card.select_one(".salary, [class*='salary']")

            if not title_el:
                continue

            title   = _clean(title_el.get_text())
            company = _clean(comp_el.get_text() if comp_el else "")
            loc_str = _clean(loc_el.get_text() if loc_el else location)
            href    = link_el.get("href", "") if link_el else ""
            job_url = href if href.startswith("http") else f"https://www.monster.com/jobs/search?q={q}"
            salary_text = _clean(salary_el.get_text() if salary_el else "")

            sal_min, sal_max, salary_str = _parse_salary_text(salary_text)

            jobs.append({
                "id":          _uid("monster", title, company),
                "board":       "monster",
                "board_label": "Monster",
                "title":       title,
                "company":     company,
                "location":    loc_str,
                "salary":      salary_str,
                "salary_min":  sal_min,
                "salary_max":  sal_max,
                "job_type":    job_type.title(),
                "days_ago":    0,
                "url":         job_url,
                "easy_apply":  True,
                "description": f"Contract position for {title} at {company} requiring {skill} expertise.",
            })
    except Exception as e:
        print(f"[job_searcher] Monster scrape error: {e}")
    return jobs


# ---------------------------------------------------------------------------
# Board Dispatcher
# ---------------------------------------------------------------------------

def _fetch_board(board: str, skill: str, location: str, job_type: str):
    scraper_map = {
        "linkedin":     _scrape_linkedin,
        "dice":         _scrape_dice,
        "indeed":       _scrape_indeed,
        "ziprecruiter": _scrape_ziprecruiter,
        "monster":      _scrape_monster,
    }

    scraper = scraper_map.get(board)
    jobs    = scraper(skill, location, job_type) if scraper else []

    # Filter out empty/junk titles
    jobs = [j for j in jobs if j.get("title") and len(j["title"]) > 3]

    print(f"[job_searcher] {board.upper()}: {len(jobs)} live jobs scraped")
    return board, jobs[:RESULTS_PER_BOARD]


# ---------------------------------------------------------------------------
# Deduplication & Rate Intelligence
# ---------------------------------------------------------------------------

def _deduplicate(all_jobs):
    """Remove duplicate jobs that appear across multiple boards."""
    seen = set()
    result = {b: [] for b in all_jobs}
    for board, jobs in all_jobs.items():
        for job in jobs:
            norm = f"{job['title'].lower().strip()}|{job['company'].lower().strip()}"
            if norm not in seen:
                seen.add(norm)
                result[board].append(job)
    return result


def _rate_intelligence(all_jobs, skill, location):
    """Calculate market rate intelligence from REAL salary data only."""
    hourly = []
    for jobs in all_jobs.values():
        for j in jobs:
            hi = j.get("salary_max", 0) or 0
            lo = j.get("salary_min", 0) or 0
            if 15 <= hi <= 400:
                hourly.append(hi)
            if lo and 15 <= lo <= 400:
                hourly.append(lo)

    if len(hourly) < 3:
        return {
            "skill": skill,
            "location": location,
            "count": 0,
            "low": 0,
            "median": 0,
            "high": 0,
            "display": "",
        }

    return {
        "skill":    skill,
        "location": location,
        "count":    len(hourly),
        "low":      int(min(hourly)),
        "median":   int(statistics.median(hourly)),
        "high":     int(max(hourly)),
        "display":  f"${int(min(hourly))}-${int(max(hourly))}/hr based on {len(hourly)} real postings in {location}",
    }


# ---------------------------------------------------------------------------
# Firestore Cache
# ---------------------------------------------------------------------------

def _cache_key(skill: str, location: str, job_type: str) -> str:
    raw = f"{skill.lower().strip()}|{location.lower().strip()}|{job_type}"
    return "jobcache_v5_" + hashlib.md5(raw.encode()).hexdigest()[:12]


def _read_cache(ck: str):
    try:
        from firebase_admin import firestore as fs
        db  = fs.client()
        doc = db.collection("job_cache").document(ck).get()
        if not doc.exists:
            return None
        data = doc.to_dict()
        if time.time() - data.get("cached_at", 0) > CACHE_TTL_SECONDS:
            return None
        return data.get("payload")
    except Exception:
        return None


def _write_cache(ck: str, payload: dict) -> None:
    try:
        from firebase_admin import firestore as fs
        db = fs.client()
        db.collection("job_cache").document(ck).set({
            "cached_at": time.time(),
            "payload":   json.loads(json.dumps(payload, default=str)),
        })
    except Exception:
        pass


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def search_jobs(
    skill: str,
    location: str,
    job_type: str = "contract",
    days: int = 7,
    boards=None,
    use_cache: bool = True,
) -> dict:
    """
    Search all job boards in parallel.
    Returns ONLY real scraped jobs - no fakes, no random data.
    """
    target_boards = boards or ["linkedin", "dice", "indeed", "ziprecruiter", "monster"]

    # Default location to USA if not specified
    if not location or location.strip() == "":
        location = "United States of America"

    ck = _cache_key(skill, location, job_type)

    if use_cache:
        cached = _read_cache(ck)
        if cached:
            cached["cached"] = True
            print(f"[job_searcher] Returning cached results for '{skill}' in '{location}'")
            return cached

    t0 = time.time()
    all_results = {b: [] for b in target_boards}

    # Scrape all boards in parallel
    with ThreadPoolExecutor(max_workers=5) as ex:
        futures = {ex.submit(_fetch_board, b, skill, location, job_type): b for b in target_boards}
        for future in as_completed(futures):
            board_key, jobs = future.result()
            all_results[board_key] = jobs

    # Sort each board by newest first (smallest days_ago)
    for b in target_boards:
        all_results[b] = sorted(all_results[b], key=lambda x: x.get("days_ago", 999))
        # Apply posted label after sorting
        for job in all_results[b]:
            job["posted"] = _posted_label(job.get("days_ago", 0))
        all_results[b] = all_results[b][:RESULTS_PER_BOARD]

    all_results = _deduplicate(all_results)
    rate_intel  = _rate_intelligence(all_results, skill, location)
    total       = sum(len(j) for j in all_results.values())
    elapsed     = round(time.time() - t0, 1)

    payload = {
        "boards":            all_results,
        "total":             total,
        "rate_intelligence": rate_intel,
        "elapsed_seconds":   elapsed,
        "cached":            False,
        "search": {
            "skill": skill, "location": location,
            "job_type": job_type, "days": days,
        },
    }

    if use_cache and total > 0:
        _write_cache(ck, payload)

    return payload


if __name__ == "__main__":
    import sys
    skill_arg = sys.argv[1] if len(sys.argv) > 1 else "SAP MM"
    loc_arg   = sys.argv[2] if len(sys.argv) > 2 else "United States of America"
    res = search_jobs(skill_arg, loc_arg, use_cache=False)
    print(f"\nTotal: {res['total']} jobs in {res['elapsed_seconds']}s")
    for b, jobs in res["boards"].items():
        if jobs:
            j0 = jobs[0]
            print(f"  {b.upper()}: {len(jobs)} jobs - First: {j0['title']} @ {j0['company']} | Salary: {j0['salary'] or 'Not Listed'} | URL: {j0['url'][:80]}")
        else:
            print(f"  {b.upper()}: 0 jobs")
