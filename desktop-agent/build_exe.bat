@echo off
echo ==============================================
echo   Generando SATRI_Agent.exe...
echo ==============================================
echo.

python -m pip install -r requirements.txt
if %errorlevel% neq 0 (
    echo [ERROR] No se pudieron instalar las dependencias.
    pause
    exit /b %errorlevel%
)

echo [*] Empaquetando con PyInstaller...
pyinstaller --onefile --name SATRI_Agent satri_agent.py

if %errorlevel% equ 0 (
    echo.
    echo ==============================================
    echo [OK] El ejecutable se ha creado con exito!
    echo Ubicacion: dist\SATRI_Agent.exe
    echo ==============================================
) else (
    echo [ERROR] Hubo un problema al crear el ejecutable.
)

pause
