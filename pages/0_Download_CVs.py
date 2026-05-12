import sys
from pathlib import Path
import runpy

app_dir = Path(__file__).parent.parent / "resume_app"
sys.path.insert(0, str(app_dir))

runpy.run_path(str(app_dir / "pages" / "0_Download_CVs.py"), run_name="__main__")
