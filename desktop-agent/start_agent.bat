@echo off
echo ==============================================
echo   Instalando SATRI Endpoint Agent...
echo ==============================================
echo.

python -m pip install -r requirements.txt
if %errorlevel% neq 0 (
    echo [ERROR] No se pudieron instalar las dependencias. Verifica que Python esta instalado.
    pause
    exit /b %errorlevel%
)

echo.
echo [OK] Dependencias instaladas. Iniciando Agente...
echo.

python main.py
pause
