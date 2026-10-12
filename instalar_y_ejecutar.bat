@echo off
setlocal enabledelayedexpansion
title Sistema POS Verduleria - Auto Instalador e Inicio

cd /d "%~dp0"

echo =====================================================================
echo                 SISTEMA POS VERDULERIA - AUTO SETUP
echo =====================================================================
echo.

:: ----------------------------------------------------------------------
:: 1. VERIFICAR O INSTALAR PYTHON (Version 3.13.1)
:: ----------------------------------------------------------------------
python --version >nul 2>&1
if %errorlevel% neq 0 (
    echo [!] Python NO esta detectado en el sistema.
    echo [*] Descargando e instalando Python 3.13.1 automaticamente...
    
    set "PY_INSTALLER=%TEMP%\python_installer_3.13.1.exe"
    set "PY_URL=https://www.python.org/ftp/python/3.13.1/python-3.13.1-amd64.exe"
    
    echo [*] Descargando desde python.org...
    powershell -Command "Invoke-WebRequest -Uri '!PY_URL!' -OutFile '!PY_INSTALLER!'"
    if not exist "!PY_INSTALLER!" (
        echo [ERROR] No se pudo descargar el instalador de Python.
        echo Por favor verifica tu conexion a internet o descarga Python manualmente desde https://www.python.org/
        pause
        exit /b 1
    )
    
    echo [*] Instalando Python silenciosamente con PATH habilitado (esto puede tardar unos segundos)...
    "!PY_INSTALLER!" /quiet InstallAllUsers=0 PrependPath=1 Include_test=0
    del "!PY_INSTALLER!" >nul 2>&1
    
    :: Actualizar la variable PATH en la sesion actual de CMD
    for /f "tokens=*" %%a in ('powershell -Command "[Environment]::GetEnvironmentVariable('Path', 'User') + ';' + [Environment]::GetEnvironmentVariable('Path', 'Machine')"') do set "PATH=%%a"
    
    python --version >nul 2>&1
    if !errorlevel! neq 0 (
        echo.
        echo [!] La instalacion termino. Si este aviso persiste, por favor cierra y vuelve a abrir este archivo.
        pause
        exit /b 1
    )
    echo [OK] Python instalado correctamente.
) else (
    for /f "tokens=*" %%v in ('python --version') do echo [OK] %%v detectado.
)
echo.

:: ----------------------------------------------------------------------
:: 2. GESTION DE LA BASE DE DATOS (Mover con datos o empezar limpia)
:: ----------------------------------------------------------------------
if exist "instance\pos.db" (
    echo [?] Se encontro una Base de Datos existente en 'instance\pos.db'.
    echo     1. Conservar los datos actuales (Continuar normal)
    echo     2. Reiniciar base de datos desde cero (Solo estructura limpia)
    echo.
    set /p db_choice="Elige una opcion [1 o 2, Enter para 1]: "
    if "!db_choice!"=="2" (
        echo [*] Creando respaldo previo en instance\pos_backup.db...
        copy /y "instance\pos.db" "instance\pos_backup_%date:~-4,4%%date:~-7,2%%date:~-10,2%_%time:~0,2%%time:~3,2%.db" >nul 2>&1
        del "instance\pos.db"
        echo [OK] Base de datos reiniciada. Se creara una limpia al iniciar.
    ) else (
        echo [OK] Se conservan los datos existentes.
    )
    echo.
) else (
    echo [*] No hay base de datos previa. Se creara una nueva con estructura limpia.
    echo.
)

:: ----------------------------------------------------------------------
:: 3. ENTORNO VIRTUAL Y DEPENDENCIAS
:: ----------------------------------------------------------------------
if not exist "venv\Scripts\python.exe" (
    echo [*] Creando entorno virtual aislado (venv)...
    python -m venv venv
    if !errorlevel! neq 0 (
        echo [ERROR] No se pudo crear el entorno virtual venv.
        pause
        exit /b 1
    )
    echo [OK] Entorno virtual creado.
    echo [*] Instalando librerias del POS...
    venv\Scripts\python.exe -m pip install --upgrade pip >nul 2>&1
    venv\Scripts\pip.exe install -r requirements.txt
    if !errorlevel! neq 0 (
        echo [ERROR] Fallo la instalacion de dependencias.
        pause
        exit /b 1
    )
    echo [OK] Librerias instaladas con exito.
    echo.
)

:: ----------------------------------------------------------------------
:: 4. HABILITAR PUERTO EN EL FIREWALL DE WINDOWS (Para acceso remoto)
:: ----------------------------------------------------------------------
netsh advfirewall firewall show rule name="POS Verduleria (Puerto 5000)" >nul 2>&1
if %errorlevel% neq 0 (
    echo [*] Agregando regla al Firewall de Windows para permitir conexion desde celular/otra PC (Puerto 5000)...
    powershell -Command "Start-Process netsh -ArgumentList 'advfirewall firewall add rule name=\"POS Verduleria (Puerto 5000)\" dir=in action=allow protocol=TCP localport=5000' -Verb RunAs" >nul 2>&1
)

:: ----------------------------------------------------------------------
:: 5. INICIAR EL SISTEMA
:: ----------------------------------------------------------------------
echo =====================================================================
echo  INICIANDO SISTEMA POS VERDULERIA...
echo =====================================================================
venv\Scripts\python.exe app.py

pause
