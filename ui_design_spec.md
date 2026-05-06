# AI Resume Ranking System — UI Design Specification
## Olympic Industries PLC | Streamlit Intranet Dashboard

---

## 1. Overview

This is an **intranet-only** Streamlit web application used by the HR department of Olympic Industries PLC. It runs on the company's local server and is accessed by HR staff via browser on the company LAN. No internet access required for the UI — all processing happens on the server.

**Users:** HR managers and recruiters (non-technical). The UI must be simple, professional, and self-explanatory.

**Purpose:** Submit job descriptions, view AI-ranked candidate shortlists, export reports, and audit AI decisions.

---

## 2. Tech Stack

- **Framework:** Streamlit (Python)
- **Backend API:** FastAPI (REST) — the UI calls this for all data operations
- **Database:** PostgreSQL — stores jobs, candidates, scores, audit logs
- **Auth:** Simple intranet access control (Phase 8 — can use basic password or IP-based initially)
- **Export:** Excel (.xlsx) download + optional Odoo/HRIS webhook
- **Binding:** Must bind to LAN IP (not just localhost) so HR can access from other machines

---

## 3. Navigation Structure

The app has a **sidebar navigation** with these pages:

```
📋 Dashboard          (home — overview of all jobs and pipeline status)
📝 New Job Posting     (JD intake form — submit a new job for AI ranking)
📊 Ranking Results     (view ranked candidates per job)
📄 Candidate Detail    (individual candidate deep-dive)
⚙️ Settings            (model config, weight defaults, system health)
```

---

## 4. Page Specifications

### 4.1 Dashboard (Home)

**Purpose:** At-a-glance view of all active job postings and their ranking pipeline status.

**Layout:**

- **Top row:** 3-4 metric cards
  - Total active jobs
  - Total candidates processed (all jobs)
  - Candidates pending processing
  - Average AI score across all jobs

- **Main content:** Table/list of all job postings with columns:
  - Job Title
  - Department
  - Date Posted
  - Total Applicants
  - Processed / Total (progress bar or fraction)
  - Pipeline Status: `Downloading` | `Processing` | `Ranking Complete` | `Error`
  - Action: `View Results` button → navigates to Ranking Results for that job

- **Style:** Clean card-based layout. Corporate blue/gray palette. No clutter.

---

### 4.2 New Job Posting (JD Intake Form)

**Purpose:** HR submits a new job for AI resume ranking. This form dynamically builds the scoring prompt sent to the LLM.

**Form Fields:**

| Field | Type | Required | Notes |
|-------|------|----------|-------|
| Job Title | Text input | ✅ Required | e.g., "Sr. Executive — AI & Digital Transformation" |
| Department | Dropdown | Optional | Predefined list: HR, Finance, Marketing, Sales, IT, Production, Supply Chain, Quality, Admin, Other |
| Full JD Text | Large text area | Optional | Paste the full job description. AI extracts requirements if provided. |
| Required Skills | Multi-select tags + custom input | Optional | Quick-select from common skills + ability to type custom ones. Predefined tags should include relevant industry skills. |
| Minimum Experience | Dropdown | Optional | Options: Any, 1 year, 2 years, 3 years, 5 years, 7 years, 10 years, 15+ years |
| Education Requirement | Dropdown | Optional | Options: Any, SSC, HSC, Diploma, Bachelor's, Master's, PhD, Professional Certification |
| Priority Weights | Slider group | Optional | Three sliders for Skills / Experience / Education. Default: 50% / 30% / 20%. Must sum to 100%. Sliders are linked — adjusting one auto-adjusts others. |
| Red Flags | Multi-select tags + custom input | Optional | See preset list below |
| Interviewer Notes | Large text area | Optional | Freeform notes appended to the system prompt for this job |
| Resume Source Folder | Text input or file browser | Optional | Path to the SMB folder containing downloaded resumes. Can default to most recent download folder. |

**Red Flag Presets (multi-select):**
- Frequent job changes
- Short tenures (<1yr)
- No FMCG experience
- Employment gaps
- No relevant degree
- Missing certifications
- Overqualified
- Underqualified
- No leadership experience
- No SAP/ERP exposure
- Vague job descriptions
- No measurable achievements
- Career regression
- Skills mismatch
- No references listed

**Behavior:**
- All optional fields degrade gracefully — missing fields are omitted from the scoring prompt, never penalized.
- On submit: job is created in PostgreSQL, processing pipeline is triggered.
- Show a confirmation with job ID and estimated processing time.
- Form should have a "Preview Prompt" button that shows what the AI scoring prompt will look like before submitting.

---

### 4.3 Ranking Results

**Purpose:** View the AI-ranked shortlist for a specific job posting.

**Top section:**
- Job title, department, date, total candidates
- Filter controls: filter by Recommendation (Shortlist / Maybe / Reject), score range slider, search by name
- Export button: "Download Excel Report" → generates .xlsx with all columns

**Main content:** Sortable data table with these columns (matching the final report spec):

| # | Column | Source | Notes |
|---|--------|--------|-------|
| 1 | Rank | Computed | Based on overall_score descending |
| 2 | Candidate Name | AI + metadata | |
| 3 | AI Overall Score | AI output | Weighted score (0-100). Color-coded: green ≥70, yellow 50-69, red <50 |
| 4 | Recommendation | AI output | Badge/chip: 🟢 Shortlist, 🟡 Maybe, 🔴 Reject |
| 5 | Skill Match Score | AI output | 0-100 |
| 6 | Experience Score | AI output | 0-100 |
| 7 | Education Score | AI output | 0-100 |
| 8 | Strengths | AI output | Truncated list, expandable |
| 9 | Weaknesses | AI output | Truncated list, expandable |
| 10 | Risk Flags | AI output | Red badges for each flag |
| 11 | AI Reasoning | AI output | Truncated, click to expand full text |
| 12 | BDJobs Match Score | Metadata | Reference only — clearly labeled as "BDJobs Score (ref)" |
| 13 | Application Date | Metadata | |
| 14 | Age | Metadata | |
| 15 | Expected Salary | Metadata | |
| 16 | Current Salary | Metadata | |
| 17 | Resume File | Link | Click to open/download the PDF |

**Row click:** Navigates to Candidate Detail page.

**Visual emphasis:**
- Top 10 candidates highlighted with a subtle border or background
- Recommendation column uses color-coded badges
- Score columns use horizontal bar charts or color gradients
- Risk flags shown as small red chips/tags

---

### 4.4 Candidate Detail

**Purpose:** Deep-dive into a single candidate's AI evaluation.

**Layout — two columns:**

**Left column (60%):**
- Candidate name (large heading)
- Contact info: email, phone, location
- Education: degree, university
- Experience: formatted from the `Exps` field (company + role + duration)
- Embedded PDF viewer: show the candidate's resume (both profile PDF and uploaded CV if available, as tabs)

**Right column (40%):**
- **Score card:** Donut chart or radial chart showing overall score
- **Score breakdown:** Three horizontal bars for Skill / Experience / Education scores, with the weights shown
- **Recommendation:** Large colored badge (Shortlist / Maybe / Reject)
- **Strengths:** Bulleted list (green)
- **Weaknesses:** Bulleted list (amber)
- **Risk Flags:** Bulleted list (red)
- **AI Reasoning:** Full text in an expandable card
- **BDJobs Match Score:** Small reference note at bottom (gray, de-emphasized)

**Actions:**
- "Override Recommendation" dropdown — HR can manually change to Shortlist/Maybe/Reject with a reason field
- "Add Note" — HR can add internal notes
- "Download Resume" button
- Navigation: Previous / Next candidate buttons

---

### 4.5 Settings

**Purpose:** System configuration and health monitoring.

**Sections:**

**Model Configuration:**
- Current LLM model: display name and status (e.g., "qwen3:8b-q4_K_M — Running")
- Ollama connection status: green/red indicator
- OpenClaw connection status: green/red indicator
- Test button: "Send Test Prompt" — sends a simple prompt to verify the pipeline works

**Default Weights:**
- Default skill/experience/education weight sliders (applied to new jobs unless overridden)

**System Health:**
- PostgreSQL status
- n8n workflow status
- SMB folder watch status
- Queue depth (pending resumes)
- Last processing timestamp

**Data Management:**
- "Reprocess Job" — re-run AI scoring for a specific job (useful after model changes)
- "Clear Queue" — cancel pending processing

---

## 5. AI Scoring Schema (Enforced Output Format)

The LLM must return this exact JSON structure for every candidate. The UI displays these fields directly.

```json
{
  "candidate_name": "",
  "skill_match_score": 0-100,
  "experience_score": 0-100,
  "education_score": 0-100,
  "overall_score": 0-100,
  "strengths": [],
  "weaknesses": [],
  "risk_flags": [],
  "recommendation": "Shortlist | Maybe | Reject",
  "reasoning": ""
}
```

**Scoring weights (default):** Skills 50%, Experience 30%, Education 20%. Dynamically adjusted based on `priority_weights[]` set in the JD form.

**Critical rule:** The LLM evaluates but never decides freely — always structured JSON output. Every evaluation stored with full reasoning for auditability.

---

## 6. Final Report Columns (Excel Export)

When HR clicks "Download Excel Report" on the Ranking Results page, the exported .xlsx contains:

1. Rank
2. Candidate Name
3. AI Overall Score (weighted)
4. Recommendation (Shortlist / Maybe / Reject)
5. AI Skill Match Score
6. AI Experience Score
7. AI Education Score
8. Strengths
9. Weaknesses
10. Risk Flags
11. AI Reasoning (full text)
12. BDJobs Match Score (reference only — clearly labeled)
13. Application Date
14. Age
15. Expected Salary
16. Current Salary
17. Resume Filename

---

## 7. Design Guidelines

### Color Palette
- **Primary:** Corporate blue (#1E3A5F or similar)
- **Secondary:** Slate gray (#64748B)
- **Success/Shortlist:** Green (#16A34A)
- **Warning/Maybe:** Amber (#D97706)
- **Danger/Reject:** Red (#DC2626)
- **Background:** White (#FFFFFF) with light gray sections (#F8FAFC)
- **Text:** Dark charcoal (#1E293B)

### Typography
- Clean sans-serif (Streamlit default or Inter/Segoe UI)
- Headings: Bold, larger size
- Data tables: Compact, readable at small sizes

### General Principles
- **Professional corporate look** — this is for a manufacturing company's HR department, not a startup
- **Minimal clutter** — HR staff are not technical users
- **Clear visual hierarchy** — scores and recommendations should be immediately scannable
- **Mobile-responsive is NOT required** — this is an intranet desktop app
- **Loading states** — show progress indicators when AI is processing (processing a batch of 184 resumes will take minutes)
- **Error states** — clear error messages when pipeline components are down

### Accessibility
- Color-coded elements should also have text labels (don't rely on color alone)
- Sufficient contrast ratios
- Readable font sizes (minimum 14px for body text)

---

## 8. Data Flow (UI Context)

```
HR fills JD intake form
    → FastAPI creates job in PostgreSQL
    → n8n triggers resume processing pipeline
    → OpenClaw + Ollama scores each resume
    → Scores written to PostgreSQL
    → Streamlit reads from PostgreSQL and displays ranked results
    → HR reviews, overrides, exports Excel report
```

The UI is a **read-heavy consumer** of data produced by the backend pipeline. The only write operations from the UI are:
- Creating new jobs (JD intake form)
- Manual recommendation overrides
- Adding HR notes
- Triggering reprocessing

---

## 9. Candidate Metadata Available from BDJobs API

The following fields are available per candidate from the BDJobs list API and can be displayed in the UI:

- Name, Email, Mobile, Location
- Applied Date, Age
- Expected Salary, Current Salary
- Degree, University
- Total Experience (e.g., "3+ Years")
- Experience Details (company + role + duration, pipe-separated)
- BDJobs Matching Score (0-100, reference only)
- AttachedCV flag (has uploaded CV or not)
- Resume file(s): profile PDF and/or uploaded CV
