"""
excel_parser.py
---------------
Reads and cleans 'Marketing Consultants - Team wise (22).xlsx'.

Cleaning rules applied:
  1. Derives a 'Team' column by detecting header rows in 'SNO' and forward-filling.
  2. Drops separator rows where 'NAME OF THE CONSULTANT' is NaN.
  3. Replaces ditto marks (") in 'STATUS' with the previous valid value (forward-fill).
  4. Strips leading/trailing whitespace from 'AREA' and 'Location'.
"""

from __future__ import annotations

import os
from pathlib import Path
from typing import Any

import pandas as pd

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------
EXCEL_FILENAME = "Marketing Consultants - Team wise (22).xlsx"
EXPECTED_COLUMNS = ["SNO", "NAME OF THE CONSULTANT", "AREA", "E-MAIL", "PHONE", "STATUS", "Location"]


def _resolve_excel_path() -> Path:
    """Return the absolute path to the Excel file (next to this script)."""
    script_dir = Path(__file__).parent
    excel_path = script_dir / EXCEL_FILENAME
    if not excel_path.exists():
        raise FileNotFoundError(
            f"Excel file not found at: {excel_path}\n"
            "Ensure '{EXCEL_FILENAME}' is in the same folder as excel_parser.py."
        )
    return excel_path


def parse_excel(excel_path: str | Path | None = None) -> list[dict[str, Any]]:
    """
    Parse and clean the marketing consultants Excel spreadsheet.

    Parameters
    ----------
    excel_path : str or Path, optional
        Override path to the Excel file. Defaults to the file next to this script.

    Returns
    -------
    list[dict]
        A list of cleaned consultant records as Python dictionaries.
    """
    path = Path(excel_path) if excel_path else _resolve_excel_path()

    # ------------------------------------------------------------------
    # 1. Load the workbook – read everything as strings initially so we
    #    can inspect the SNO column before pandas coerces types.
    # ------------------------------------------------------------------
    df = pd.read_excel(path, dtype=str)

    # Normalise column names (strip whitespace)
    df.columns = [str(c).strip() for c in df.columns]

    # Validate expected columns
    missing = [c for c in EXPECTED_COLUMNS if c not in df.columns]
    if missing:
        raise ValueError(f"Excel file is missing expected columns: {missing}")

    # ------------------------------------------------------------------
    # 2. Derive 'Team' column from separator rows in 'SNO'
    #    A separator row looks like: SNO contains "Team …" and
    #    'NAME OF THE CONSULTANT' is NaN / empty.
    # ------------------------------------------------------------------
    team_values: list[str | None] = []
    current_team: str | None = None

    for _, row in df.iterrows():
        sno_val = str(row["SNO"]).strip() if pd.notna(row["SNO"]) else ""
        name_val = row["NAME OF THE CONSULTANT"]

        if "team" in sno_val.lower() and (pd.isna(name_val) or str(name_val).strip() == ""):
            # This is a team header row – capture the team name
            current_team = sno_val
            team_values.append(current_team)
        else:
            team_values.append(current_team)

    df["Team"] = team_values

    # ------------------------------------------------------------------
    # 3. Drop separator rows where 'NAME OF THE CONSULTANT' is NaN/empty
    # ------------------------------------------------------------------
    df = df[df["NAME OF THE CONSULTANT"].notna()].copy()
    df = df[df["NAME OF THE CONSULTANT"].str.strip() != ""].copy()
    df.reset_index(drop=True, inplace=True)

    # ------------------------------------------------------------------
    # 4. Handle ditto marks (") in 'STATUS' via forward-fill
    #    A ditto mark means "same as the row above".
    # ------------------------------------------------------------------
    status_values: list[str | None] = []
    last_valid_status: str | None = None

    for val in df["STATUS"]:
        cleaned = str(val).strip() if pd.notna(val) else ""
        if cleaned == '"' or cleaned == "":
            status_values.append(last_valid_status)
        else:
            last_valid_status = cleaned
            status_values.append(cleaned)

    df["STATUS"] = status_values

    # ------------------------------------------------------------------
    # 5. Strip whitespace from 'AREA' and 'Location'
    # ------------------------------------------------------------------
    for col in ("AREA", "Location"):
        df[col] = df[col].apply(
            lambda v: str(v).strip() if pd.notna(v) and str(v).strip() != "nan" else ""
        )

    # ------------------------------------------------------------------
    # 6. General cleanup – strip remaining string columns, convert NaN → ""
    # ------------------------------------------------------------------
    str_cols = ["SNO", "NAME OF THE CONSULTANT", "E-MAIL", "PHONE", "Team"]
    for col in str_cols:
        if col in df.columns:
            df[col] = df[col].apply(
                lambda v: str(v).strip() if pd.notna(v) and str(v) != "nan" else ""
            )

    # Convert to list of dicts
    records: list[dict[str, Any]] = df.to_dict(orient="records")
    return records


# ---------------------------------------------------------------------------
# Standalone verification
# ---------------------------------------------------------------------------
if __name__ == "__main__":
    print("=" * 60)
    print("excel_parser.py – Standalone Verification")
    print("=" * 60)

    records = parse_excel()

    print(f"\n[OK] Total cleaned records: {len(records)}")
    print("\nFirst 2 records:")
    for i, record in enumerate(records[:2], start=1):
        print(f"\n--- Record {i} ---")
        for key, value in record.items():
            print(f"  {key:30s}: {value}")
