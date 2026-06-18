@echo off
title Cotizador Siluseg
cd /d "%~dp0"

:: ── Configuración (sacar los "::" para activar) ─────────────────
:: Clave para entrar a la web del cotizador (default: siluseg2026)
:: set COTI_CLAVE=TuClaveSecreta123

:: Email que envía las cotizaciones (contraseña de aplicación de Gmail,
:: ver DESPLIEGUE.md punto 3)
:: set SMTP_USER=rodrigojbernardo@gmail.com
:: set SMTP_PASS=xxxxxxxxxxxxxxxx

:: Navegadores ocultos (sin ventanas). Recomendado al usarlo a distancia,
:: para que nadie cierre las ventanas por accidente mientras cotiza.
:: set COTI_HEADLESS=1
:: ────────────────────────────────────────────────────────────────

echo.
echo  =========================================
echo   Cotizador Siluseg - Iniciando...
echo  =========================================
echo.

:: Iniciar Flask en segundo plano
start "Flask - Siluseg" cmd /k "python app.py"

:: Esperar que Flask levante
timeout /t 3 /nobreak >nul

:: Iniciar ngrok
start "ngrok - Tunnel" cmd /k "ngrok http 5001"

echo.
echo  Flask corriendo en: http://127.0.0.1:5001
echo  Abriendo ngrok...  (buscá la URL "Forwarding" en la ventana de ngrok)
echo.
echo  Desde cualquier dispositivo usas la URL https://xxxx.ngrok-free.app
echo.
pause
