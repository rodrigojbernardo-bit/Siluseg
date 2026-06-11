@echo off
title Chrome para el Cotizador (Federacion)
cd /d "%~dp0"

:: Abre un Chrome especial que el cotizador puede usar para entrar a
:: Federacion Patronal sin que lo frene la "verificacion de seguridad".
:: Usa un perfil propio (no toca tu Chrome de todos los dias).

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

echo.
echo  Abriendo Chrome para el cotizador...
echo.
echo  1) Cuando abra, entra a Federacion y pasa la verificacion de seguridad.
echo  2) Deja esta ventana de Chrome ABIERTA.
echo  3) Recien ahi corre el cotizador (iniciar_cotizador.bat).
echo.

start "" "%CHROME%" --remote-debugging-port=%PUERTO% --user-data-dir="%PERFIL%" "https://online.fedpat.com.ar/self/homeWin32.do"
