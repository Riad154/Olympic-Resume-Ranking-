"""
Root entry point for Streamlit Cloud.
Redirects to resume_app/Home.py which contains the actual dashboard.
"""
import sys
from pathlib import Path

# Add resume_app to Python path so imports resolve
app_dir = Path(__file__).parent / "resume_app"
sys.path.insert(0, str(app_dir))

# Change working directory so relative paths in db.py etc. resolve
import os
os.chdir(str(app_dir))

# Run the actual Home.py
exec(open(app_dir / "Home.py", encoding="utf-8").read())
