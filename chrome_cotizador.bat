@echo off
title Chrome Siluseg (cotizador + uso diario)
cd /d "%~dp0"

:: Abre un Chrome REAL que el cotizador puede usar para Federacion.
:: Este Chrome es para USO DIARIO: dejalo abierto y trabaja en el
:: normalmente (carga de datos, portales, lo que necesites).
:: Inicia sesion con tu cuenta de Google una sola vez y vas a tener
:: tus contrasenias y favoritos de siempre.
::
:: El cotizador le abre una PESTANIA nueva cuando cotiza Federacion
:: y la cierra al terminar: no toca tus pestanias.

set "PERFIL=%~dp0.chrome_fedpat"
set "PUERTO=9222"

set "CHROME=%ProgramFiles%\Google\Chrome\Application\chrome.exe"
if not exist "%CHROME%" set "CHROME=%ProgramFiles(x86)%\Google\Chrome\Application\chrome.exe"
if not exist "%CHROME%" set "CHROME=%LocalAppData%\Google\Chrome\Application\chrome.exe"

if not exist "%CHROME%" (
  echo No encontre Google Chrome instalado.
  echo Instalalo desde https://www.google.com/chrome y volve a intentar.
  pause
  exit /b 1
)

:: /min abre la ventana minimizada para que no te moleste; sigue
:: disponible en la barra de tareas por si Cloudflare pide verificacion.
start "" /min "%CHROME%" --remote-debugging-port=%PUERTO% --user-data-dir="%PERFIL%" --window-position=2000,2000 "https://online.fedpat.com.ar/self/homeWin32.do"
