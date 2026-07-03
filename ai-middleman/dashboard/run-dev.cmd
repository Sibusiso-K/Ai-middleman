@echo off
cd /d "%~dp0\.."
python -m streamlit run dashboard/app.py --server.port %PORT% --server.headless true
