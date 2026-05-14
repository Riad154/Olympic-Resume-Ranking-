"""
Helper module to trigger GitHub Actions workflows from the Streamlit app.
"""
import os
import requests


def _get_token() -> str | None:
    """Read GH_TOKEN from os.environ or st.secrets."""
    token = os.environ.get("GH_TOKEN") or os.environ.get("GITHUB_TOKEN")
    if token:
        return token.strip()
    # Fallback: try st.secrets (Streamlit Cloud injects these too, but just in case)
    try:
        import streamlit as st
        token = st.secrets.get("GH_TOKEN") or st.secrets.get("GITHUB_TOKEN")
        if token:
            return str(token).strip()
    except Exception:
        pass
    return None


def _get_repo() -> str:
    """Read GH_REPO from os.environ or st.secrets."""
    repo = os.environ.get("GH_REPO")
    if repo:
        return repo.strip()
    try:
        import streamlit as st
        repo = st.secrets.get("GH_REPO")
        if repo:
            return str(repo).strip()
    except Exception:
        pass
    return "Riad154/Olympic-Resume-Ranking-"


def test_github_token() -> tuple[bool, str]:
    """Validate the GitHub token by making a simple API call."""
    token = _get_token()
    if not token:
        return False, "No GH_TOKEN found in environment or Streamlit secrets."
    if not token.startswith("ghp_"):
        return False, f"Token does not start with 'ghp_' (got '{token[:4]}...'). Use a classic PAT."
    headers = {
        "Authorization": f"Bearer {token}",
        "Accept": "application/vnd.github.v3+json",
    }
    try:
        resp = requests.get("https://api.github.com/user", headers=headers, timeout=30)
        if resp.status_code == 200:
            user = resp.json().get("login", "unknown")
            scopes = resp.headers.get("X-OAuth-Scopes", "none")
            return True, (
                f"Token is valid. Authenticated as **{user}**.\n\n"
                f"Granted scopes: `{scopes}`\n\n"
                f"Required scopes for workflow dispatch: `repo` + `workflow`"
            )
        elif resp.status_code == 401:
            return False, (
                "Token rejected by GitHub (401).\n\n"
                "Most likely causes:\n"
                "1. Token was copied incompletely (missing last few characters)\n"
                "2. Token was revoked by GitHub after creation\n"
                "3. Token is a fine-grained token (should be classic PAT)\n"
                "4. Token expired immediately (rare, but happens)\n\n"
                "Fix: Delete the token on GitHub, create a new one, copy it fully, update Streamlit secrets."
            )
        else:
            return False, f"GitHub API returned {resp.status_code}: {resp.text[:200]}"
    except Exception as e:
        return False, f"Network error: {e}"


def trigger_bdjobs_scrape(
    job_label: str,
    job_url: str,
    max_candidates: int = 0,
    department: str = "Uncategorized",
) -> tuple[bool, str]:
    """
    Trigger the BDJobs scraper GitHub Actions workflow.

    Returns (success: bool, message: str)
    """
    token = _get_token()
    repo = _get_repo()

    if not token:
        return False, (
            "GitHub token not configured.\n\n"
            "Go to your app on Streamlit Cloud → **⋮ → Settings → Secrets** and add:\n"
            '```\nGH_TOKEN = "ghp_your_classic_pat_here"\n```'
        )

    # Validate token format
    if not token.startswith("ghp_"):
        return False, (
            f"Invalid token format. Your token starts with '{token[:4]}...' but must start with 'ghp_' (classic PAT).\n\n"
            "Please create a **Personal Access Token (classic)** at:\n"
            "https://github.com/settings/tokens\n\n"
            "Required scopes: ✅ repo, ✅ workflow"
        )
    if len(token) < 30:
        return False, (
            f"Token looks too short ({len(token)} chars). "
            "Make sure you copied the FULL token from GitHub."
        )

    url = f"https://api.github.com/repos/{repo}/actions/workflows/bdjobs_scraper.yml/dispatches"
    headers = {
        "Authorization": f"Bearer {token}",
        "Accept": "application/vnd.github.v3+json",
    }
    payload = {
        "ref": "main",
        "inputs": {
            "job_label": job_label,
            "job_url": job_url,
            "max_candidates": str(max_candidates),
            "department": department,
        },
    }

    try:
        resp = requests.post(url, headers=headers, json=payload, timeout=30)
        if resp.status_code == 204:
            return True, (
                f"Scraper triggered for **{job_label}**. "
                f"Check [Actions tab](https://github.com/{repo}/actions) for progress. "
                f"CVs will appear in `downloaded_resumes/` after ~2-3 minutes."
            )
        elif resp.status_code == 404:
            return False, f"Workflow not found. Ensure `.github/workflows/bdjobs_scraper.yml` exists in `{repo}`."
        elif resp.status_code == 401:
            return False, (
                f"GitHub API error 401: Bad credentials.\n\n"
                "Your token is invalid or expired. Please:\n"
                "1. Go to https://github.com/settings/tokens\n"
                "2. Check if your token is expired (red dot = expired)\n"
                "3. Generate a new **classic** token with scopes: repo + workflow\n"
                "4. Update GH_TOKEN in Streamlit Cloud secrets and reboot the app."
            )
        else:
            return False, f"GitHub API error {resp.status_code}: {resp.text[:500]}"
    except requests.RequestException as e:
        return False, f"Network error: {e}"


def get_latest_run_status(repo: str, token: str) -> dict:
    """Fetch the latest workflow run status for BDJobs scraper."""
    url = f"https://api.github.com/repos/{repo}/actions/workflows/bdjobs_scraper.yml/runs?per_page=1"
    headers = {
        "Authorization": f"Bearer {token}",
        "Accept": "application/vnd.github.v3+json",
    }
    try:
        resp = requests.get(url, headers=headers, timeout=30)
        resp.raise_for_status()
        runs = resp.json().get("workflow_runs", [])
        if not runs:
            return {"status": "unknown", "msg": "No runs found"}
        run = runs[0]
        return {
            "status": run["status"],
            "conclusion": run.get("conclusion"),
            "created_at": run["created_at"],
            "html_url": run["html_url"],
        }
    except Exception as e:
        return {"status": "error", "msg": str(e)}
