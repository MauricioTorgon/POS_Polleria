@echo off
title Sistema POS Verduleria
cd /d "%~dp0"

:: Si existe el entorno virtual venv, usarlo; si no, usar python del sistema
if exist "venv\Scripts\python.exe" (
    venv\Scripts\python.exe app.py
) else (
    python app.py
)

if %errorlevel% neq 0 (
    echo.
    echo Ocurrio un error al iniciar el sistema.
    pause
)
