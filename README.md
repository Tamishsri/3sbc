# ⚡ Recruitment Automation System & Enterprise ATS Dashboard

An end-to-end, AI-powered recruitment automation platform that parses consultant rosters from Excel, sources candidates, performs candidate matching & scoring using **Gemini AI**, syncs live records to **Google Cloud Firestore**, and delivers an interactive **Enterprise Applicant Tracking System (ATS) Web Dashboard**.

---

## 🌟 Key Features

- **📊 Automated Excel Extraction (`excel_parser.py`)**: Reads & cleans complex team-wise consultant spreadsheets, forward-fills team titles and status ditto marks (`"`), and trims whitespace.
- **🎯 Candidate Sourcing Engine (`linkedin_sourcer.py`)**: Sources 3 matching candidates per consultant role/location with valid live LinkedIn search links.
- **🤖 AI Recruiter Evaluation (`ai_evaluator.py`)**: Uses **Gemini 3.5 Flash** to calculate match scores (`0–100%`) and concise recruiter justifications with automatic domain heuristic fallback.
- **🔥 Cloud Firestore Integration (`firebase_db.py`)**: Live upserts candidate documents into Google Cloud Firestore (`candidates` collection) with deduplicated SHA-256 document keys.
- **📈 Formatted Report Generation (`report_generator.py`)**: Exports formatted Excel reports with navy headers, frozen panes, auto-fit columns, and score cell color-coding.
- **💻 Enterprise Web Dashboard (`server.py`, `index.html`)**: Interactive dark-slate ATS interface featuring candidate search, team filters, live status selectors (`New`, `Shortlisted`, `Interviewing`, `Hired`), score badges, and 1-click execution.

---

## 🏗️ Architecture & Data Flow

```
[Excel Roster] ──> [excel_parser.py] ──> [linkedin_sourcer.py] ──> [ai_evaluator.py]
                                                                        │
                                                ┌───────────────────────┴───────────────────────┐
                                                ▼                                               ▼
                                      [firebase_db.py]                                [report_generator.py]
                                                │                                               │
                                                ▼                                               ▼
                                   (Google Cloud Firestore DB)                   (Sourced_Candidates_Report.xlsx)
                                                │                                               │
                                                └───────────────────────┬───────────────────────┘
                                                                        ▼
                                                       [Web Dashboard (http://localhost:5000)]
```

---

## 🚀 Quick Start Guide

### 1. Prerequisites
- Python 3.9+ installed
- Google Gemini API Key
- Firebase Service Account Key (`firebase-key.json`)

### 2. Installation & Setup
```bash
# Clone the repository
git clone https://github.com/Tamishsri/3sbc.git
cd 3sbc

# Install dependencies
pip install -r requirements.txt
```

### 3. Environment Configuration
Create a `.env` file in the root folder:
```env
GEMINI_API_KEY=your_gemini_api_key_here
```

Place your Firebase service account private key file named `firebase-key.json` in the root folder.

---

## 💻 Running the Application

### Option A: Interactive Web UI Command Center
```bash
python server.py
```
Open your browser to **`http://localhost:5000`** to view the live ATS command center, trigger pipeline runs, and export Excel reports.

### Option B: Master Orchestrator CLI
```bash
python main.py
```

---

## 📁 Repository Structure

```
3sbc/
├── main.py                          # Master execution orchestrator
├── server.py                        # REST API & Web UI server
├── excel_parser.py                  # Excel extraction & data cleaning engine
├── linkedin_sourcer.py              # Candidate sourcing module
├── ai_evaluator.py                  # Gemini AI evaluation engine
├── firebase_db.py                   # Google Cloud Firestore SDK integration
├── report_generator.py              # Excel report generator (openpyxl)
├── index.html                       # Enterprise Web UI layout
├── styles.css                       # Enterprise ATS design system
├── app.js                           # Dashboard frontend logic
├── setup_env.py                     # Environment initialization script
├── requirements.txt                 # Python dependencies manifest
└── Marketing Consultants - Team...  # Input consultant roster spreadsheet
```

---

## 📜 License
MIT License. Created for Recruitment Automation & AI Talent Sourcing.
