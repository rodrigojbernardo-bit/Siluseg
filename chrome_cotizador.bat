@echo off
title Chrome Cotizador Siluseg (perfil independiente)
cd /d "%~dp0"

:: El cotizador necesita un Chrome con SU PROPIA carpeta de datos, para
:: que no choque con tu Chrome personal (si comparten carpeta, Windows
:: los une en un solo proceso y el puerto de conexion no se abre).
::
:: La PRIMERA vez copiamos tu perfil "Siluseg BOOT" (Profile 5) a una
:: carpeta propia, asi hereda la confianza de Cloudflare. Despues arranca
:: siempre desde esa carpeta, independiente de tu Chrome de todos los dias.

set "PUERTO=9222"
if not defined COTI_CHROME_USERDATA set "COTI_CHROME_USERDATA=%LocalAppData%\Google\Chrome\User Data"
if not defined COTI_CHROME_PROFILE_DIR set "COTI_CHROME_PROFILE_DIR=Profile 5"
set "BOOTDIR=%~dp0.chrome_boot"

:: Ubicar chrome.exe
set "CHROME=%ProgramFiles%\Google\Chrome\Application\chrome.exe"
if not exist "%CHROME%" set "CHROME=%ProgramFiles(x86)%\Google\Chrome\Application\chrome.exe"
if not exist "%CHROME%" set "CHROME=%LocalAppData%\Google\Chrome\Application\chrome.exe"
if not exist "%CHROME%" (
  echo No encontre Google Chrome instalado.
  echo Instalalo desde https://www.google.com/chrome y volve a intentar.
  pause
  exit /b 1
)

:: ── Primer uso: copiar el perfil Siluseg BOOT a la carpeta propia ──────────
if not exist "%BOOTDIR%\Default\Cookies" (
  echo ============================================================
  echo  PRIMER USO - Preparando el perfil del cotizador
  echo.
  echo  Voy a copiar tu perfil "Siluseg BOOT" a una carpeta propia
  echo  para que el cotizador funcione sin chocar con tu Chrome.
  echo.
  echo  IMPORTANTE: cerra TODAS las ventanas de Chrome antes de seguir
  echo  (sino algunos archivos quedan bloqueados y no se copian).
  echo ============================================================
  echo.
  pause
  echo Copiando perfil, aguarda...
  robocopy "%COTI_CHROME_USERDATA%\%COTI_CHROME_PROFILE_DIR%" "%BOOTDIR%\Default" /E /R:1 /W:1 /NFL /NDL /NJH /NJS >nul
  copy /Y "%COTI_CHROME_USERDATA%\Local State" "%BOOTDIR%\Local State" >nul 2>&1
  echo Perfil preparado en: %BOOTDIR%
  echo.
)

echo Abriendo Chrome del cotizador (carpeta propia, perfil con Cloudflare OK)...
start "" /min "%CHROME%" --remote-debugging-port=%PUERTO% --user-data-dir="%BOOTDIR%" "https://online.fedpat.com.ar/self/homeWin32.do"
