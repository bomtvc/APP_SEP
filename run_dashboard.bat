@echo off
REM Mo Dashboard EHS. Lan dau chay can co .venv (xem README_APP.md).
cd /d "%~dp0"
.venv\Scripts\streamlit.exe run app\main.py
