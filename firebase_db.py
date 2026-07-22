"""
firebase_db.py
--------------
Firebase Admin SDK integration for the Recruitment Automation Pipeline.

Responsibilities:
  - Initialise the Firebase Admin SDK using a local service-account key file
    (firebase-key.json in the same directory as this script).
  - Connect to Cloud Firestore.
  - Expose `upload_candidates_to_firestore(evaluated_data)` which flattens
    the nested pipeline output and upserts one document per sourced candidate
    into the Firestore 'candidates' collection.

Document structure (per candidate):
  - team          : str   – e.g. "Mahesh & Team"
  - target_area   : str   – required skill/role, e.g. "SAP MM/ Ariba"
  - location      : str   – target geography, e.g. "Philadelphia, PA"
  - candidate_url : str   – LinkedIn profile URL
  - candidate_name: str   – Full name / headline
  - match_score   : int   – 0-100 AI fit score
  - reasoning     : str   – 1-2 sentence AI justification
  - created_at    : timestamp – server-side Firestore timestamp
"""

from __future__ import annotations

import hashlib
import os
from pathlib import Path
from typing import Any

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------
KEY_FILE = Path(__file__).parent / "firebase-key.json"
COLLECTION_NAME = "candidates"

# Module-level singleton so we only initialise Firebase once per process
_db = None


# ---------------------------------------------------------------------------
# Initialisation
# ---------------------------------------------------------------------------

def _init_firebase():
    """
    Initialise Firebase Admin SDK (idempotent – safe to call multiple times).

    Uses the service-account JSON file at `firebase-key.json` in the project
    root. Raises FileNotFoundError with a descriptive message if the key file
    is missing so the caller can surface a clear error.

    Returns
    -------
    google.cloud.firestore.Client
        A ready-to-use Firestore client.
    """
    global _db  # noqa: PLW0603

    if _db is not None:
        return _db

    try:
        import firebase_admin
        from firebase_admin import credentials, firestore
    except ImportError as exc:
        raise ImportError(
            "firebase-admin is not installed. "
            "Run: pip install firebase-admin"
        ) from exc

    if not KEY_FILE.exists():
        raise FileNotFoundError(
            f"Firebase service-account key not found at: {KEY_FILE}\n"
            "Steps to fix:\n"
            "  1. Go to Firebase Console -> Project Settings -> Service accounts.\n"
            "  2. Click 'Generate new private key' and download the JSON file.\n"
            "  3. Rename it 'firebase-key.json' and place it in the project root.\n"
            "  4. Make sure 'firebase-key.json' is listed in .gitignore!"
        )

    # Only initialise the default app if it hasn't been done yet
    if not firebase_admin._apps:
        cred = credentials.Certificate(str(KEY_FILE))
        firebase_admin.initialize_app(cred)
        print(f"[firebase] Firebase Admin SDK initialised (key: {KEY_FILE.name})")
    else:
        print("[firebase] Firebase Admin SDK already initialised -- reusing existing app.")

    _db = firestore.client()
    print("[firebase] Connected to Cloud Firestore.")
    return _db


# ---------------------------------------------------------------------------
# Document ID helper
# ---------------------------------------------------------------------------

def _make_doc_id(consultant_name: str, candidate_url: str) -> str:
    """
    Derive a stable, Firestore-safe document ID from the consultant name and
    candidate LinkedIn URL so that re-runs upsert (overwrite) instead of
    creating duplicates.

    Firestore document IDs must be <= 1500 bytes and cannot contain '/'.
    We use a short SHA-256 prefix to keep IDs compact and collision-resistant.
    """
    raw = f"{consultant_name}::{candidate_url}".lower().strip()
    digest = hashlib.sha256(raw.encode()).hexdigest()[:16]
    # Build a human-readable prefix (safe chars only) + hash suffix
    safe_name = "".join(c if c.isalnum() or c in "-_" else "_" for c in consultant_name[:30])
    return f"{safe_name}__{digest}"


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def upload_candidates_to_firestore(
    evaluated_data: list[dict[str, Any]],
) -> int:
    """
    Flatten the nested pipeline output and upsert every sourced candidate
    into the Firestore 'candidates' collection.

    Parameters
    ----------
    evaluated_data : list[dict]
        Full output from `ai_evaluator.evaluate_candidates()`.  Each element
        is a consultant dict that contains a `'sourced_candidates'` list.

    Returns
    -------
    int
        Total number of documents written to Firestore.
    """
    from google.cloud import firestore as fs  # type: ignore[import]

    db = _init_firebase()
    collection = db.collection(COLLECTION_NAME)

    total_written = 0
    total_consultants = len(evaluated_data)

    print(f"[firebase] Starting Firestore upload for {total_consultants} consultant records ...")

    for c_idx, consultant in enumerate(evaluated_data, start=1):
        consultant_name: str = str(consultant.get("NAME OF THE CONSULTANT") or "").strip()
        team: str            = str(consultant.get("Team") or "").strip()
        target_area: str     = str(consultant.get("AREA") or "").strip()
        location: str        = str(consultant.get("Location") or "").strip()

        candidates: list[dict[str, Any]] = consultant.get("sourced_candidates") or []

        print(
            f"[firebase] ({c_idx}/{total_consultants}) Uploading {len(candidates)} "
            f"candidate(s) for: {consultant_name!r}"
        )

        for candidate in candidates:
            candidate_url:  str = str(candidate.get("linkedin_url") or "").strip()
            candidate_name: str = str(candidate.get("name_title") or "").strip()
            match_score:    int = int(candidate.get("match_score") or 0)
            reasoning:      str = str(candidate.get("reasoning") or "").strip()

            doc_id = _make_doc_id(consultant_name, candidate_url)

            document_data: dict[str, Any] = {
                "team":           team,
                "target_area":    target_area,
                "location":       location,
                "candidate_url":  candidate_url,
                "candidate_name": candidate_name,
                "match_score":    match_score,
                "reasoning":      reasoning,
                # SERVER_TIMESTAMP is set by Firestore on first write;
                # merge=True preserves it on subsequent upserts.
                "created_at":     fs.SERVER_TIMESTAMP,
            }

            try:
                collection.document(doc_id).set(document_data, merge=True)
                total_written += 1
                print(
                    f"  [firebase] Upserted doc '{doc_id}' "
                    f"(score={match_score}, candidate={candidate_name[:50]})"
                )
            except Exception as exc:  # noqa: BLE001
                print(f"  [firebase] ERROR writing doc '{doc_id}': {exc}")

    print(
        f"[firebase] [OK] Upload complete -- {total_written} document(s) written "
        f"to Firestore collection '{COLLECTION_NAME}'."
    )
    return total_written


# ---------------------------------------------------------------------------
# Standalone smoke-test
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    # Minimal fake data – does NOT hit the real Proxycurl / Gemini APIs.
    SAMPLE: list[dict[str, Any]] = [
        {
            "NAME OF THE CONSULTANT": "Test Consultant",
            "Team": "Test Team",
            "AREA": "Azure Data Engineer",
            "Location": "New York, NY",
            "sourced_candidates": [
                {
                    "linkedin_url": "https://www.linkedin.com/in/test-user-1",
                    "name_title": "Test User 1 -- Azure Data Engineer",
                    "match_score": 92,
                    "reasoning": "Strong ADF and Databricks background, direct match.",
                },
                {
                    "linkedin_url": "https://www.linkedin.com/in/test-user-2",
                    "name_title": "Test User 2 -- Cloud Engineer",
                    "match_score": 55,
                    "reasoning": "General cloud skills but limited Azure-specific experience.",
                },
            ],
        }
    ]

    count = upload_candidates_to_firestore(SAMPLE)
    print(f"\nSmoke-test complete: {count} document(s) written.")
