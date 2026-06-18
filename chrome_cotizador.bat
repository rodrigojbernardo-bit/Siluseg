@echo off
title Preparar perfil del Cotizador Siluseg
cd /d "%~dp0"

:: Este .bat ahora SOLO sirve para preparar (una vez) el perfil del
:: cotizador, copiando tu perfil "Siluseg BOOT" a una carpeta propia con
:: la confianza de Cloudflare ya hecha.
::
:: YA NO hace falta abrir Chrome a mano: el cotizador abre solo el Chrome
:: correcto cuando cotiza Federacion.

if not defined COTI_CHROME_USERDATA set "COTI_CHROME_USERDATA=%LocalAppData%\Google\Chrome\User Data"
if not defined COTI_CHROME_PROFILE_DIR set "COTI_CHROME_PROFILE_DIR=Profile 5"
set "BOOTDIR=%~dp0.chrome_boot"

if exist "%BOOTDIR%\Default\Cookies" (
  echo El perfil del cotizador ya esta preparado en:
  echo   %BOOTDIR%
  echo.
  echo No hace falta hacer nada mas. Cerra esta ventana y usa el cotizador
  echo normalmente: el abre solo el Chrome correcto para Federacion.
  echo.
  pause
  exit /b 0
)

echo ============================================================
echo  Preparar el perfil del cotizador (una sola vez)
echo.
echo  Voy a copiar tu perfil "Siluseg BOOT" a una carpeta propia
echo  para que Federacion pase Cloudflare sin molestar.
echo.
echo  IMPORTANTE: cerra TODAS las ventanas de Chrome antes de seguir.
echo ============================================================
echo.
pause
echo Copiando perfil, aguarda...
robocopy "%COTI_CHROME_USERDATA%\%COTI_CHROME_PROFILE_DIR%" "%BOOTDIR%\Default" /E /R:1 /W:1 /NFL /NDL /NJH /NJS >nul
copy /Y "%COTI_CHROME_USERDATA%\Local State" "%BOOTDIR%\Local State" >nul 2>&1
echo.
echo Listo. Perfil preparado en: %BOOTDIR%
echo Ya podes usar el cotizador normalmente.
echo.
pause
