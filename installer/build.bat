@echo off
REM ============================================================
REM SATRI v2 — Build Script (PyInstaller)
REM ============================================================
REM Genera el ejecutable .exe de la app de escritorio.
REM Prerequisito: pip install pyinstaller
REM ============================================================

echo ========================================
echo SATRI v2 - Generando ejecutable...
echo ========================================

cd /d "%~dp0\.."

REM Instalar dependencias
pip install -r desktop-agent\requirements.txt
pip install pyinstaller

REM Generar .exe
pyinstaller --onefile ^
  --name "SATRI_Protection" ^
  --add-data "desktop-agent\modules;desktop-agent\modules" ^
  --hidden-import pystray ^
  --hidden-import PIL ^
  --hidden-import psutil ^
  --hidden-import watchdog ^
  --hidden-import requests ^
  --windowed ^
  --noconfirm ^
  desktop-agent\main.py

echo.
if exist "dist\SATRI_Protection.exe" (
    echo ✅ Ejecutable generado: dist\SATRI_Protection.exe
    echo Tamaño:
    for %%A in (dist\SATRI_Protection.exe) do echo   %%~zA bytes
) else (
    echo ❌ Error generando ejecutable
    exit /b 1
)

echo.
echo Para crear el instalador, ejecuta Inno Setup con:
echo   iscc installer\satri_installer.iss
echo.
