import subprocess
import os

cwd = r"F:\Projects\resume_ranking\resume_app"
proc = subprocess.Popen(
    ["streamlit", "run", "Home.py",
     "--server.port", "8501",
     "--server.headless", "true",
     "--server.enableCORS", "false",
     "--server.enableXsrfProtection", "false"],
    cwd=cwd,
    stdout=open(r"F:\Projects\resume_ranking\_server_out.txt", "w"),
    stderr=open(r"F:\Projects\resume_ranking\_server_err.txt", "w"),
)
print(f"Started server PID {proc.pid}")
