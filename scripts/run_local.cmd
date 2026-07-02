@echo off
set "PYTHONPATH=%~dp0..\.streamlit_deps"
cd /d "%~dp0.."
"C:\Users\Lenovo\.cache\codex-runtimes\codex-primary-runtime\dependencies\python\python.exe" -m streamlit.web.cli run streamlit_app.py --global.developmentMode false --server.port 8502 --server.address 127.0.0.1 --server.headless true --server.fileWatcherType none
