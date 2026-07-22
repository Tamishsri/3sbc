"""
job_searcher.py
---------------
Multi-board job search engine using requests + BeautifulSoup.
Searches Dice, Indeed, LinkedIn, ZipRecruiter, Glassdoor simultaneously.
No external jobspy dependency needed.
"""

from __future__ import annotations

import hashlib
import json
import re
import statistics
import time
import urllib.parse
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime, timezone
from typing import Any

import requests
from bs4 import BeautifulSoup

CACHE_TTL_SECONDS = 7200  # 2 hours
RESULTS_PER_BOARD = 12

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

def _uid(board: str, url: str) -> str:
    return f"{board}_{hashlib.md5(url.encode()).hexdigest()[:8]}"


def _clean(text: Any) -> str:
    if not text:
        return ""
    return re.sub(r"\s+", " ", str(text)).strip()


def _posted_ago(text: str) -> str:
    text = text.lower().strip()
    if "just" in text or "moment" in text:
        return "< 1h ago"
    if "hour" in text:
        m = re.search(r"(\d+)", text)
        return f"{m.group(1)}h ago" if m else "Today"
    if "day" in text:
        m = re.search(r"(\d+)", text)
        return f"{m.group(1)}d ago" if m else "Few days ago"
    if "minute" in text:
        return "< 1h ago"
    if "week" in text:
        return "1w ago"
    return text[:20] if text else "Recently"


def _get(url: str, timeout: int = 10) -> BeautifulSoup | None:
    try:
        r = SESSION.get(url, timeout=timeout, allow_redirects=True)
        if r.status_code == 200:
            return BeautifulSoup(r.text, "html.parser")
    except Exception as e:
        print(f"[job_searcher] GET failed {url}: {e}")
    return None


# ---------------------------------------------------------------------------
# Board scrapers
# ---------------------------------------------------------------------------

def _scrape_dice(skill: str, location: str, days: int) -> list[dict]:
    jobs = []
    try:
        q = urllib.parse.quote_plus(skill)
        loc = urllib.parse.quote_plus(location)
        url = f"https://www.dice.com/jobs?q={q}&l={loc}&country=US&radius=30&radiusUnit=mi&page=1&pageSize={RESULTS_PER_BOARD}&filters.postedDate=ONE_DAY&language=en"
        # Use Dice API directly
        api_url = (
            f"https://job-search-api.svc.dhigroupinc.com/v1/dice/jobs/search"
            f"?q={q}&countryCode2=US&location={loc}&radius=30&radiusUnit=mi"
            f"&page=1&pageSize={RESULTS_PER_BOARD}&language=en&fields=id,title,company,location,postedDate,salary,employmentType,applyUrl"
        )
        r = SESSION.get(api_url, timeout=12)
        if r.status_code == 200:
            data = r.json()
            for item in data.get("data", [])[:RESULTS_PER_BOARD]:
                posted = item.get("postedDate", "")
                try:
                    dt = datetime.fromisoformat(posted.replace("Z", "+00:00"))
                    posted_label = _posted_ago_from_dt(dt)
                except Exception:
                    posted_label = "Recently"
                jobs.append({
                    "id":          _uid("dice", item.get("applyUrl", item.get("id", ""))),
                    "board":       "dice",
                    "board_label": "Dice",
                    "title":       _clean(item.get("title")),
                    "company":     _clean(item.get("company", {}).get("name") if isinstance(item.get("company"), dict) else item.get("company", "")),
                    "location":    _clean(item.get("location", location)),
                    "salary":      _clean(item.get("salary", "")),
                    "salary_min":  0.0,
                    "salary_max":  0.0,
                    "job_type":    _clean(item.get("employmentType", "Contract")),
                    "posted":      posted_label,
                    "url":         _clean(item.get("applyUrl", f"https://www.dice.com/job-detail/{item.get('id', '')}")),
                    "easy_apply":  False,
                    "description": "",
                })
        if not jobs:
            raise ValueError("No API results, fall back to HTML")
    except Exception:
        # HTML fallback
        try:
            q = urllib.parse.quote_plus(skill)
            loc = urllib.parse.quote_plus(location)
            soup = _get(f"https://www.dice.com/jobs?q={q}&l={loc}&radius=30&radiusUnit=mi&page=1&pageSize=12")
            if soup:
                for card in soup.select("div.card-title-link, a[data-cy='card-title-link']")[:RESULTS_PER_BOARD]:
                    title = _clean(card.get_text())
                    href = card.get("href", "")
                    if title and href:
                        jobs.append({
                            "id": _uid("dice", href),
                            "board": "dice", "board_label": "Dice",
                            "title": title, "company": "", "location": location,
                            "salary": "", "salary_min": 0.0, "salary_max": 0.0,
                            "job_type": "Contract", "posted": "Recently",
                            "url": href if href.startswith("http") else f"https://www.dice.com{href}",
                            "easy_apply": False, "description": "",
                        })
        except Exception as e:
            print(f"[job_searcher] dice html fallback error: {e}")
    return jobs


def _scrape_indeed(skill: str, location: str, days: int) -> list[dict]:
    jobs = []
    try:
        q = urllib.parse.quote_plus(skill)
        loc = urllib.parse.quote_plus(location)
        days_param = min(days, 14)
        soup = _get(
            f"https://www.indeed.com/jobs?q={q}&l={loc}&fromage={days_param}&limit=15&jt=contract"
        )
        if not soup:
            return []
        for card in soup.select("div.job_seen_beacon, div[data-testid='slider_item']")[:RESULTS_PER_BOARD]:
            title_el = card.select_one("h2.jobTitle span, h2[data-testid='jobTitle'] a, a.jcs-JobTitle")
            company_el = card.select_one("span[data-testid='company-name'], span.companyName")
            loc_el = card.select_one("div[data-testid='text-location'], span.companyLocation")
            salary_el = card.select_one("div[data-testid='attribute_snippet_testid'], span.salary-snippet-container")
            posted_el = card.select_one("span[data-testid='myJobsStateDate'], span.date")
            link_el = card.select_one("a[data-jk], h2 a[id]")

            if not title_el:
                continue

            href = ""
            if link_el:
                jk = link_el.get("data-jk") or link_el.get("id", "").replace("job_", "")
                href = f"https://www.indeed.com/viewjob?jk={jk}" if jk else link_el.get("href", "")

            salary_text = _clean(salary_el.get_text() if salary_el else "")
            sal_min, sal_max = _parse_salary(salary_text)

            jobs.append({
                "id":          _uid("indeed", href or _clean(title_el.get_text())),
                "board":       "indeed",
                "board_label": "Indeed",
                "title":       _clean(title_el.get_text()),
                "company":     _clean(company_el.get_text() if company_el else ""),
                "location":    _clean(loc_el.get_text() if loc_el else location),
                "salary":      salary_text,
                "salary_min":  sal_min,
                "salary_max":  sal_max,
                "job_type":    "Contract",
                "posted":      _posted_ago(_clean(posted_el.get_text() if posted_el else "")),
                "url":         href or f"https://www.indeed.com/jobs?q={q}&l={loc}",
                "easy_apply":  bool(card.select_one("span.iaLabel, button[data-testid='IndeedApplyButton']")),
                "description": "",
            })
    except Exception as e:
        print(f"[job_searcher] indeed error: {e}")
    return jobs


def _scrape_linkedin(skill: str, location: str, days: int) -> list[dict]:
    jobs = []
    try:
        q = urllib.parse.quote_plus(skill)
        loc = urllib.parse.quote_plus(location)
        # f_TPR: r86400=24h, r259200=3d, r604800=week
        tpr = "r86400" if days <= 1 else ("r259200" if days <= 3 else "r604800")
        soup = _get(
            f"https://www.linkedin.com/jobs/search/?keywords={q}&location={loc}"
            f"&f_TPR={tpr}&f_JT=C&sortBy=DD"
        )
        if not soup:
            return []
        for card in soup.select("div.base-card, li.jobs-search__results-list > div")[:RESULTS_PER_BOARD]:
            title_el = card.select_one("h3.base-search-card__title, h3.job-result-card__title")
            company_el = card.select_one("h4.base-search-card__subtitle, a.job-result-card__subtitle-link")
            loc_el = card.select_one("span.job-search-card__location")
            posted_el = card.select_one("time")
            link_el = card.select_one("a.base-card__full-link, a.result-card__full-card-link")

            if not title_el:
                continue

            url = link_el.get("href", "") if link_el else ""
            posted_text = posted_el.get("datetime", "") if posted_el else ""
            if posted_text:
                try:
                    dt = datetime.fromisoformat(posted_text)
                    posted_label = _posted_ago_from_dt(dt)
                except Exception:
                    posted_label = "Recently"
            else:
                posted_label = "Recently"

            jobs.append({
                "id":          _uid("linkedin", url or _clean(title_el.get_text())),
                "board":       "linkedin",
                "board_label": "LinkedIn",
                "title":       _clean(title_el.get_text()),
                "company":     _clean(company_el.get_text() if company_el else ""),
                "location":    _clean(loc_el.get_text() if loc_el else location),
                "salary":      "",
                "salary_min":  0.0,
                "salary_max":  0.0,
                "job_type":    "Contract",
                "posted":      posted_label,
                "url":         url or f"https://www.linkedin.com/jobs/search/?keywords={q}&location={loc}",
                "easy_apply":  bool(card.select_one("span.job-result-card__easy-apply-label")),
                "description": "",
            })
    except Exception as e:
        print(f"[job_searcher] linkedin error: {e}")
    return jobs


def _scrape_ziprecruiter(skill: str, location: str, days: int) -> list[dict]:
    jobs = []
    try:
        q = urllib.parse.quote_plus(skill)
        loc = urllib.parse.quote_plus(location)
        days_param = min(days, 30)
        soup = _get(
            f"https://www.ziprecruiter.com/jobs-search?search={q}&location={loc}"
            f"&days={days_param}&job_type=contract"
        )
        if not soup:
            return []
        for card in soup.select("article.job_result, div[data-testid='job-result-card']")[:RESULTS_PER_BOARD]:
            title_el = card.select_one("h2[itemprop='title'] a, a.job_link, h2.title a")
            company_el = card.select_one("a[itemprop='hiringOrganization'], span.company_name")
            loc_el = card.select_one("span[itemprop='addressLocality'], span.location")
            salary_el = card.select_one("span[itemprop='baseSalary'], li.salary")
            posted_el = card.select_one("span.posted_time, time")

            if not title_el:
                continue

            url = title_el.get("href", "")
            salary_text = _clean(salary_el.get_text() if salary_el else "")
            sal_min, sal_max = _parse_salary(salary_text)

            jobs.append({
                "id":          _uid("ziprecruiter", url),
                "board":       "ziprecruiter",
                "board_label": "ZipRecruiter",
                "title":       _clean(title_el.get_text()),
                "company":     _clean(company_el.get_text() if company_el else ""),
                "location":    _clean(loc_el.get_text() if loc_el else location),
                "salary":      salary_text,
                "salary_min":  sal_min,
                "salary_max":  sal_max,
                "job_type":    "Contract",
                "posted":      _posted_ago(_clean(posted_el.get_text() if posted_el else "")),
                "url":         url if url.startswith("http") else f"https://www.ziprecruiter.com{url}",
                "easy_apply":  True,
                "description": "",
            })
    except Exception as e:
        print(f"[job_searcher] ziprecruiter error: {e}")
    return jobs


def _scrape_monster(skill: str, location: str, days: int) -> list[dict]:
    jobs = []
    try:
        q = urllib.parse.quote_plus(skill)
        loc = urllib.parse.quote_plus(location)
        soup = _get(
            f"https://www.monster.com/jobs/search?q={q}&where={loc}&jobType=contract&tm={days}"
        )
        if not soup:
            return []
        for card in soup.select("div.job-cardstyle__JobCardComponent, section.card-content")[:RESULTS_PER_BOARD]:
            title_el = card.select_one("h2.title, a[data-testid='jobTitle']")
            company_el = card.select_one("span.company, div[data-testid='company']")
            loc_el = card.select_one("span.location, div[data-testid='jobLocation']")
            posted_el = card.select_one("time, span.posted")
            link_el = card.select_one("a[href*='/job-openings/']") or card.select_one("a")

            if not title_el:
                continue

            url = link_el.get("href", "") if link_el else ""
            jobs.append({
                "id":          _uid("monster", url or _clean(title_el.get_text())),
                "board":       "monster",
                "board_label": "Monster",
                "title":       _clean(title_el.get_text()),
                "company":     _clean(company_el.get_text() if company_el else ""),
                "location":    _clean(loc_el.get_text() if loc_el else location),
                "salary":      "",
                "salary_min":  0.0,
                "salary_max":  0.0,
                "job_type":    "Contract",
                "posted":      _posted_ago(_clean(posted_el.get_text() if posted_el else "")),
                "url":         url if url.startswith("http") else f"https://www.monster.com{url}",
                "easy_apply":  False,
                "description": "",
            })
    except Exception as e:
        print(f"[job_searcher] monster error: {e}")
    return jobs


# ---------------------------------------------------------------------------
# Salary parser + Rate intelligence
# ---------------------------------------------------------------------------

def _parse_salary(text: str) -> tuple[float, float]:
    if not text:
        return 0.0, 0.0
    try:
        nums = re.findall(r"\$?([\d,]+(?:\.\d+)?)", text)
        vals = [float(n.replace(",", "")) for n in nums if n]
        if len(vals) >= 2:
            return vals[0], vals[1]
        elif len(vals) == 1:
            return vals[0], vals[0]
    except Exception:
        pass
    return 0.0, 0.0


def _posted_ago_from_dt(dt: datetime) -> str:
    try:
        now = datetime.now(timezone.utc)
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=timezone.utc)
        delta = now - dt
        hours = int(delta.total_seconds() / 3600)
        if hours < 1:
            return "< 1h ago"
        if hours < 24:
            return f"{hours}h ago"
        return f"{hours // 24}d ago"
    except Exception:
        return "Recently"


def _compute_rate_intelligence(all_jobs: dict, skill: str, location: str) -> dict:
    hourly: list[float] = []
    for jobs in all_jobs.values():
        for job in jobs:
            hi = job.get("salary_max", 0)
            lo = job.get("salary_min", 0)
            # Convert yearly to hourly
            if hi > 30000:
                hi = round(hi / 2080, 1)
                lo = round(lo / 2080, 1)
            if 20 <= hi <= 350:
                hourly.append(hi)
            if lo and 20 <= lo <= 350:
                hourly.append(lo)

    if len(hourly) < 2:
        return {}

    return {
        "skill":   skill,
        "location": location,
        "count":   len(hourly),
        "low":     int(min(hourly)),
        "median":  int(statistics.median(hourly)),
        "high":    int(max(hourly)),
        "display": f"${int(min(hourly))}-${int(max(hourly))}/hr based on {len(hourly)} live postings",
    }


# ---------------------------------------------------------------------------
# Deduplication
# ---------------------------------------------------------------------------

def _deduplicate(all_jobs: dict) -> dict:
    seen: dict[str, str] = {}
    result: dict[str, list[dict]] = {b: [] for b in all_jobs}
    for board, jobs in all_jobs.items():
        for job in jobs:
            norm = f"{job['title'].lower().strip()}|{job['company'].lower().strip()}"
            if norm in seen and norm != "|":
                job["also_on"] = seen[norm]
            elif norm != "|":
                seen[norm] = job["board_label"]
            result[board].append(job)
    return result


# ---------------------------------------------------------------------------
# Cache
# ---------------------------------------------------------------------------

def _cache_key(skill: str, location: str, job_type: str, days: int) -> str:
    raw = f"{skill.lower().strip()}|{location.lower().strip()}|{job_type}|{days}"
    return "jobcache_" + hashlib.md5(raw.encode()).hexdigest()[:12]


def _read_cache(ck: str) -> dict | None:
    try:
        from firebase_admin import firestore as fs
        db = fs.client()
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

SCRAPERS = {
    "dice":         _scrape_dice,
    "indeed":       _scrape_indeed,
    "linkedin":     _scrape_linkedin,
    "ziprecruiter": _scrape_ziprecruiter,
    "monster":      _scrape_monster,
}


def search_jobs(
    skill: str,
    location: str,
    job_type: str = "contract",
    days: int = 3,
    boards: list[str] | None = None,
    use_cache: bool = True,
) -> dict:
    """
    Search all job boards in parallel threads.
    Returns unified results dict with per-board job cards,
    total count, rate intelligence, and cache status.
    """
    if boards is None:
        boards = list(SCRAPERS.keys())

    ck = _cache_key(skill, location, job_type, days)
    if use_cache:
        cached = _read_cache(ck)
        if cached:
            cached["cached"] = True
            print(f"[job_searcher] Cache HIT for '{skill}' in '{location}'")
            return cached

    print(f"[job_searcher] Searching {len(boards)} boards: '{skill}' in '{location}'")
    t0 = time.time()
    all_results: dict[str, list[dict]] = {b: [] for b in boards}

    with ThreadPoolExecutor(max_workers=len(boards)) as ex:
        futures = {
            ex.submit(SCRAPERS[b], skill, location, days): b
            for b in boards if b in SCRAPERS
        }
        for future in as_completed(futures):
            board_key = futures[future]
            try:
                jobs = future.result()
                all_results[board_key] = jobs
                print(f"[job_searcher]   {board_key}: {len(jobs)} jobs")
            except Exception as exc:
                print(f"[job_searcher]   {board_key}: ERROR {exc}")

    all_results = _deduplicate(all_results)
    rate_intel  = _compute_rate_intelligence(all_results, skill, location)
    total       = sum(len(j) for j in all_results.values())
    elapsed     = round(time.time() - t0, 1)

    print(f"[job_searcher] Done in {elapsed}s — {total} total jobs")

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


# ---------------------------------------------------------------------------
# Standalone test
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    result = search_jobs("SAP MM", "Philadelphia", "contract", days=7, use_cache=False)
    for board, jobs in result["boards"].items():
        print(f"\n{board.upper()} ({len(jobs)} jobs):")
        for j in jobs[:3]:
            print(f"  {j['title']} @ {j['company']} | {j['salary']} | {j['posted']}")
    ri = result.get("rate_intelligence", {})
    if ri:
        print(f"\nRate Intelligence: {ri['display']}")
    else:
        print("\nRate Intelligence: Not enough salary data from these boards")
