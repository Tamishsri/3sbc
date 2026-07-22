"""
firebase_db.py
--------------
Firebase Firestore operations for 3SBC Staffing Intelligence Platform.
Handles: candidates, submissions, saved jobs, vendor contacts, job cache.
"""

from __future__ import annotations

import hashlib
import os
import time
from pathlib import Path
from typing import Any

# ---------------------------------------------------------------------------
# Initialise Firebase Admin SDK (idempotent)
# ---------------------------------------------------------------------------

_firebase_initialised = False


def _init_firebase() -> None:
    global _firebase_initialised
    if _firebase_initialised:
        return
    try:
        import firebase_admin
        from firebase_admin import credentials, firestore

        if not firebase_admin._apps:
            key_path = Path(__file__).parent / "firebase-key.json"
            if key_path.exists():
                cred = credentials.Certificate(str(key_path))
                firebase_admin.initialize_app(cred, {
                    "databaseURL": "https://sbc-219bf-default-rtdb.firebaseio.com"
                })
            else:
                firebase_admin.initialize_app()
        _firebase_initialised = True
    except Exception as exc:
        print(f"[firebase_db] Init warning: {exc}")


def _db():
    _init_firebase()
    from firebase_admin import firestore
    return firestore.client()


# ---------------------------------------------------------------------------
# CANDIDATES (existing ATS data)
# ---------------------------------------------------------------------------

def get_candidates() -> list[dict]:
    """Fetch all candidates from Firestore."""
    try:
        db = _db()
        docs = db.collection("candidates").stream()
        records = []
        for doc in docs:
            data = doc.to_dict()
            data["_doc_id"] = doc.id
            records.append(data)
        return records
    except Exception as exc:
        print(f"[firebase_db] get_candidates error: {exc}")
        return []


def upload_candidates_to_firestore(evaluated_data: list[dict]) -> int:
    """Flatten and upload evaluated consultant/candidate data to Firestore."""
    try:
        db = _db()
        count = 0
        total = len(evaluated_data)

        for idx, consultant in enumerate(evaluated_data, 1):
            team = str(consultant.get("Team") or "").strip()
            area = str(consultant.get("AREA") or "").strip()
            location = str(consultant.get("Location") or "").strip()
            consultant_name = str(consultant.get("NAME OF THE CONSULTANT") or "").strip()

            print(f"[firebase] ({idx}/{total}) Uploading 3 candidate(s) for: {consultant_name!r}")

            for candidate in (consultant.get("sourced_candidates") or []):
                name_title = str(candidate.get("name_title") or "")
                linkedin_url = str(candidate.get("linkedin_url") or "")
                score = int(candidate.get("match_score") or 0)
                reasoning = str(candidate.get("reasoning") or "")

                safe_name = "".join(c if c.isalnum() else "_" for c in consultant_name)
                hash_part = hashlib.md5(f"{name_title}{linkedin_url}".encode()).hexdigest()[:16]
                doc_id = f"{safe_name}__{hash_part}"

                db.collection("candidates").document(doc_id).set({
                    "Team Name": team,
                    "Target Skill (AREA)": area,
                    "Target Location": location,
                    "Consultant Name": consultant_name,
                    "Candidate Name/Title": name_title,
                    "Candidate LinkedIn URL": linkedin_url,
                    "Match Score": score,
                    "AI Reasoning": reasoning,
                    "Status": "New",
                    "updated_at": time.time(),
                })
                print(f"  [firebase] Upserted doc {doc_id!r} (score={score}, candidate={name_title})")
                count += 1

        print(f"[firebase] [OK] Upload complete -- {count} document(s) written to Firestore collection 'candidates'.")
        return count
    except Exception as exc:
        print(f"[firebase_db] upload_candidates error: {exc}")
        raise


def update_candidate_status(candidate_id: str, status: str) -> bool:
    """Update a candidate's recruiter pipeline status."""
    try:
        db = _db()
        db.collection("candidates").document(candidate_id).update({"Status": status})
        return True
    except Exception:
        return False


# ---------------------------------------------------------------------------
# SUBMISSIONS (CRM)
# ---------------------------------------------------------------------------

def add_submission(data: dict) -> str:
    """Save a new consultant-to-job submission. Returns submission doc ID."""
    try:
        db = _db()
        sub_id = hashlib.md5(
            f"{data.get('consultant_name')}|{data.get('job_id')}|{time.time()}".encode()
        ).hexdigest()[:16]

        record = {
            "consultant_name":  str(data.get("consultant_name", "")),
            "consultant_skill": str(data.get("consultant_skill", "")),
            "job_id":           str(data.get("job_id", "")),
            "job_title":        str(data.get("job_title", "")),
            "company":          str(data.get("company", "")),
            "location":         str(data.get("location", "")),
            "board":            str(data.get("board", "")),
            "job_url":          str(data.get("job_url", "")),
            "salary":           str(data.get("salary", "")),
            "rate_offered":     str(data.get("rate_offered", "")),
            "vendor_email":     str(data.get("vendor_email", "")),
            "vendor_name":      str(data.get("vendor_name", "")),
            "notes":            str(data.get("notes", "")),
            "status":           "Submitted",
            "follow_up":        False,
            "submitted_by":     str(data.get("submitted_by", "Recruiter")),
            "user_id":          str(data.get("user_id", "")),
            "created_at":       time.time(),
            "updated_at":       time.time(),
        }
        db.collection("submissions").document(sub_id).set(record)
        return sub_id
    except Exception as exc:
        print(f"[firebase_db] add_submission error: {exc}")
        raise


def get_submissions(user_id: str | None = None, is_admin: bool = False) -> list[dict]:
    """Get all submissions. Admin sees all; recruiter sees only their own."""
    try:
        db = _db()
        ref = db.collection("submissions")
        if not is_admin and user_id:
            ref = ref.where("user_id", "==", user_id)
        docs = ref.order_by("created_at", direction="DESCENDING").stream()
        result = []
        for doc in docs:
            d = doc.to_dict()
            d["id"] = doc.id
            d["created_at_iso"] = _ts_to_iso(d.get("created_at"))
            result.append(d)
        return result
    except Exception as exc:
        print(f"[firebase_db] get_submissions error: {exc}")
        return []


def update_submission(sub_id: str, updates: dict) -> bool:
    """Update status, notes, follow_up flag on a submission."""
    try:
        db = _db()
        updates["updated_at"] = time.time()
        db.collection("submissions").document(sub_id).update(updates)
        return True
    except Exception:
        return False


def delete_submission(sub_id: str) -> bool:
    try:
        _db().collection("submissions").document(sub_id).delete()
        return True
    except Exception:
        return False


# ---------------------------------------------------------------------------
# SAVED JOBS (Hotlist)
# ---------------------------------------------------------------------------

def save_job(job: dict, user_id: str) -> str:
    try:
        db = _db()
        job_id = job.get("id") or hashlib.md5(job.get("url", "").encode()).hexdigest()[:12]
        doc_id = f"{user_id}_{job_id}"
        db.collection("saved_jobs").document(doc_id).set({
            **{k: str(v) for k, v in job.items()},
            "user_id":  user_id,
            "saved_at": time.time(),
        })
        return doc_id
    except Exception as exc:
        print(f"[firebase_db] save_job error: {exc}")
        raise


def get_saved_jobs(user_id: str) -> list[dict]:
    try:
        db = _db()
        docs = db.collection("saved_jobs").where("user_id", "==", user_id) \
                 .order_by("saved_at", direction="DESCENDING").stream()
        result = []
        for doc in docs:
            d = doc.to_dict()
            d["doc_id"] = doc.id
            result.append(d)
        return result
    except Exception:
        return []


def remove_saved_job(doc_id: str) -> bool:
    try:
        _db().collection("saved_jobs").document(doc_id).delete()
        return True
    except Exception:
        return False


# ---------------------------------------------------------------------------
# VENDOR CONTACTS (CRM)
# ---------------------------------------------------------------------------

def add_vendor(data: dict) -> str:
    try:
        db = _db()
        vid = hashlib.md5(
            f"{data.get('email', '')}|{data.get('company', '')}".encode()
        ).hexdigest()[:12]
        db.collection("vendors").document(vid).set({
            "name":            str(data.get("name", "")),
            "company":         str(data.get("company", "")),
            "email":           str(data.get("email", "")),
            "phone":           str(data.get("phone", "")),
            "skills":          str(data.get("skills", "")),
            "location":        str(data.get("location", "")),
            "notes":           str(data.get("notes", "")),
            "last_contacted":  "",
            "response_rate":   "Unknown",
            "created_at":      time.time(),
        })
        return vid
    except Exception as exc:
        print(f"[firebase_db] add_vendor error: {exc}")
        raise


def get_vendors() -> list[dict]:
    try:
        db = _db()
        docs = db.collection("vendors").order_by("company").stream()
        result = []
        for doc in docs:
            d = doc.to_dict()
            d["id"] = doc.id
            result.append(d)
        return result
    except Exception:
        return []


def update_vendor(vid: str, updates: dict) -> bool:
    try:
        _db().collection("vendors").document(vid).update(updates)
        return True
    except Exception:
        return False


def delete_vendor(vid: str) -> bool:
    try:
        _db().collection("vendors").document(vid).delete()
        return True
    except Exception:
        return False


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _ts_to_iso(ts: Any) -> str:
    if not ts:
        return ""
    try:
        from datetime import datetime, timezone
        return datetime.fromtimestamp(float(ts), tz=timezone.utc).strftime("%Y-%m-%d %H:%M UTC")
    except Exception:
        return str(ts)
