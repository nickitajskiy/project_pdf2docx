"""python run.py — один запуск, только localhost."""
from pathlib import Path
import subprocess
import sys

if __name__=='__main__':
    root=Path(__file__).resolve().parent
    raise SystemExit(subprocess.call([sys.executable,'-m','streamlit','run',str(root/'app.py'),
                                     '--server.address=127.0.0.1','--browser.gatherUsageStats=false'],cwd=root))
