"""
Root entry point for Streamlit Cloud.
Redirects to resume_app/Home.py which contains the actual dashboard.
"""
import sys
from pathlib import Path
import runpy

# Add resume_app to Python path so imports resolve
app_dir = Path(__file__).parent / "resume_app"
sys.path.insert(0, str(app_dir))

# Run the actual Home.py with proper __file__ context
runpy.run_path(str(app_dir / "Home.py"), run_name="__main__")
