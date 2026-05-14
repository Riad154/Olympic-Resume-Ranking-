"""
Helper module to trigger GitHub Actions workflows from the Streamlit app.
"""
import os
import requests


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
    token = os.environ.get("GH_TOKEN") or os.environ.get("GITHUB_TOKEN")
    repo = os.environ.get("GH_REPO", "Riad154/Olympic-Resume-Ranking-")

    if not token:
        return False, "GitHub token not configured. Set GH_TOKEN in Streamlit secrets."

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
