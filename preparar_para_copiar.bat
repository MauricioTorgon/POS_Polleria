@echo off
setlocal enabledelayedexpansion
title Herramienta de Limpieza y Empaquetado - POS Verduleria

cd /d "%~dp0"

echo =====================================================================
echo       EMPAQUETAR POS VERDULERIA PARA COPIAR A OTRA PC / USB
echo =====================================================================
echo.
echo ¿Como deseas preparar la carpeta para moverla a otra PC?
echo.
echo   [1] CON DATOS (Llevar ventas, caja, clientes y productos actuales)
echo   [2] SOLO ESTRUCTURA (Limpia: sin ventas ni historial, productos base)
echo   [3] Cancelar
echo.
set /p opc="Selecciona una opcion (1, 2 o 3): "

if "%opc%"=="1" (
    echo.
    echo [*] Limpiando carpetas temporales (conservando tu base de datos)...
    if exist "__pycache__" rmdir /s /q "__pycache__"
    if exist "venv" (
        echo [*] Quitando venv local para reducir peso (se regenera solo en la otra PC)...
        rmdir /s /q "venv"
    )
    echo.
    echo [EXITO] Carpeta lista para copiar CON TUS DATOS.
    echo Pasa esta carpeta al USB o a la otra PC y ejecuta 'instalar_y_ejecutar.bat'.
    echo.
    pause
    exit /b 0
)

if "%opc%"=="2" (
    echo.
    echo [*] Creando respaldo de seguridad de tu base de datos actual...
    if exist "instance\pos.db" (
        copy /y "instance\pos.db" "instance\pos_backup_antes_de_limpiar.db" >nul 2>&1
        del "instance\pos.db"
        echo [OK] Base de datos de trabajo eliminada para dejarla limpia.
    )
    if exist "backups" (
        echo [*] Vaciando copias locales de respaldo...
        del /q "backups\*.db" >nul 2>&1
    )
    if exist "__pycache__" rmdir /s /q "__pycache__"
    if exist "venv" rmdir /s /q "venv"
    echo.
    echo [EXITO] Carpeta lista para copiar SOLO ESTRUCTURA LIMPIA.
    echo En la nueva PC se generaran las tablas desde cero de forma automatica.
    echo.
    pause
    exit /b 0
)

echo Cancelado.
pause
