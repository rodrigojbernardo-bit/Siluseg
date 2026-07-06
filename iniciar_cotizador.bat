@echo off
title Cotizador Siluseg
cd /d "%~dp0"

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
