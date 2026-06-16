@echo off
title Chrome Cotizador Siluseg (perfil Siluseg BOOT)
cd /d "%~dp0"

:: Abre tu Chrome REAL con el perfil "Siluseg BOOT" (que ya pasa la
:: verificacion de Cloudflare de Federacion). Vos seguis usando tu
:: perfil normal en otra ventana; el cotizador usa este.
::
:: El cotizador le abre una PESTANIA nueva cuando cotiza Federacion
:: y la cierra al terminar.

:: --- Configuracion (se puede cambiar con variables de entorno) ---
:: COTI_CHROME_PROFILE_DIR es la CARPETA del perfil. Para "Siluseg BOOT"
:: es "Profile 5". Si la cambias, basta con editar esta linea.
if not defined COTI_CHROME_PROFILE_DIR set "COTI_CHROME_PROFILE_DIR=Profile 5"
if not defined COTI_CHROME_PROFILE      set "COTI_CHROME_PROFILE=Siluseg BOOT"
if not defined COTI_CHROME_USERDATA     set "COTI_CHROME_USERDATA=%LocalAppData%\Google\Chrome\User Data"
set "PUERTO=9222"

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

:: Carpeta del perfil: usamos la fijada arriba (Profile 5). Como respaldo,
:: si esa carpeta no existe, intentamos resolverla por el nombre visible.
set "PROFILEDIR=%COTI_CHROME_PROFILE_DIR%"
if not exist "%COTI_CHROME_USERDATA%\%PROFILEDIR%" (
  for /f "usebackq delims=" %%i in (`python "%~dp0resolver_perfil.py"`) do set "PROFILEDIR=%%i"
)

echo Perfil: %COTI_CHROME_PROFILE%  ^(carpeta: %PROFILEDIR%^)
echo Abriendo Chrome del cotizador...

:: /min: minimizado para no molestar; sigue disponible en la barra de tareas
start "" /min "%CHROME%" --remote-debugging-port=%PUERTO% --user-data-dir="%COTI_CHROME_USERDATA%" --profile-directory="%PROFILEDIR%" "https://online.fedpat.com.ar/self/homeWin32.do"
