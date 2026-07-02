@echo off
cd /d "%~dp0.."
start "" /B cmd /c ""%~dp0run_local.cmd" 1>work\streamlit.bg.out 2>work\streamlit.bg.err"
