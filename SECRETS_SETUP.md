# Secrets Setup Guide

This document explains how to configure the secrets required for the BDJobs scraper to work.

## Required Secrets

### 1. GitHub Actions Secrets (for the scraper workflow)

Go to: **GitHub repo → Settings → Secrets and variables → Actions → New repository secret**

Add these 7 secrets:

| Secret Name | Description | Example |
|-------------|-------------|---------|
| `BDJOBS_USER` | Your BDJobs recruiter login username/email | `olympicbd` |
| `BDJOBS_PASS` | Your BDJobs recruiter password | `your_password` |
| `PG_HOST` | PostgreSQL database host | `ep-spring-sea-xxx-pooler.c-2.ap-southeast-1.aws.neon.tech` |
| `PG_PORT` | PostgreSQL port | `5432` |
| `PG_DBNAME` | PostgreSQL database name | `neondb` |
| `PG_USER` | PostgreSQL username | `neondb_owner` |
| `PG_PASSWORD` | PostgreSQL password | `your_db_password` |

### 2. Streamlit Cloud Secrets (for the web app)

Go to: **Streamlit Cloud → Your App → Settings → Secrets**

Add these in TOML format:

```toml
[github]
token = "ghp_xxxxxxxxxxxxxxxxxxxx"
repo = "Riad154/Olympic-Resume-Ranking-"

[postgresql]
host = "your-db-host.neon.tech"
port = "5432"
dbname = "neondb"
user = "neondb_owner"
password = "your-db-password"

[bdjobs]
username = "your_bdjobs_username"
password = "your_bdjobs_password"
```

### 3. GitHub Token Requirements

- Use a **Classic Personal Access Token** (not fine-grained)
- Scopes required: `repo` and `workflow`
- The token must have access to the repository

## Troubleshooting

### "No BDJobs credentials available in headless mode"
- This means `BDJOBS_USER` and/or `BDJOBS_PASS` secrets are not set
- Go to GitHub Settings → Secrets → Actions and verify they exist

### "invalid literal for int() with base 10"
- This means `PG_PORT` is empty
- Make sure all PostgreSQL secrets are set

### "401 Bad credentials"
- Your GitHub token is invalid or expired
- Generate a new classic PAT at https://github.com/settings/tokens
