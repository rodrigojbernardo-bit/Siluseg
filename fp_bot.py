"""Bot de acceso automático al portal de Federación Patronal.

Problema que resuelve
---------------------
Cloudflare bloqueaba el acceso automático porque Playwright abría un navegador
"limpio", sin historial ni cookies, y eso lo delataba como bot.

Estrategia
----------
1. Usar un perfil de Chrome dedicado ("SILUSEG BOT"), copiado a una carpeta
   exclusiva del bot, que ya pasó el desafío de Cloudflare una vez de forma
   manual. Así conserva cookies y reputación entre ejecuciones.
2. Lanzar Chrome real (no Chromium) con `launch_persistent_context`, de modo
   que la sesión persista.
3. Esperar pacientemente a que aparezca el formulario de login: si Cloudflare
   muestra un desafío, hay tiempo de sobra para resolverlo a mano.

Ver `config.py` para los parámetros (rutas, credenciales, timeouts).
"""

import sys
import time

from playwright.sync_api import TimeoutError as PlaywrightTimeoutError
from playwright.sync_api import sync_playwright

import config


def abrir_navegador(p):
    """Lanza Chrome con el perfil persistente del bot.

    `channel="chrome"` fuerza el Chrome real instalado en el sistema (no el
    Chromium que trae Playwright), que es menos sospechoso para Cloudflare.
    """
    return p.chromium.launch_persistent_context(
        user_data_dir=config.CHROME_PERFIL,
        channel="chrome",
        headless=config.HEADLESS,
        slow_mo=config.SLOW_MO_MS,
        accept_downloads=True,
        viewport={"width": 1280, "height": 800},
        args=["--disable-blink-features=AutomationControlled"],
    )


def login(page, usuario, password):
    """Navega al portal y completa el login.

    Espera hasta `TIMEOUT_LOGIN_MS` a que aparezca el campo de usuario. Ese
    margen permite resolver el Cloudflare manualmente si llega a aparecer.
    """
    page.goto(config.URL_LOGIN)

    try:
        page.wait_for_selector("#usuario", timeout=config.TIMEOUT_LOGIN_MS)
    except PlaywrightTimeoutError:
        raise RuntimeError(
            "No apareció el formulario de login dentro del tiempo de espera. "
            "Puede que Cloudflare siga bloqueando o que el perfil del bot no "
            "haya pasado el desafío todavía. Resolvé el Cloudflare a mano en la "
            "ventana y volvé a intentar."
        )

    # Pausa extra para que el portal termine de estabilizarse.
    time.sleep(config.PAUSA_ESTABILIZACION_S)

    page.fill("#usuario", usuario)
    page.fill("#password", password)
    page.click("input[name='Aceptar']")


def main():
    if not config.FP_USUARIO or not config.FP_PASSWORD:
        print(
            "ERROR: faltan credenciales. Definí FP_USUARIO y FP_PASSWORD "
            "(en variables de entorno o en un archivo .env).",
            file=sys.stderr,
        )
        sys.exit(1)

    with sync_playwright() as p:
        browser = abrir_navegador(p)
        try:
            page = browser.new_page()
            login(page, config.FP_USUARIO, config.FP_PASSWORD)
            print("Login completado. Sesión lista para que el cotizador opere.")

            # Este archivo resuelve SOLO el acceso a Federación (sortear el
            # Cloudflare y loguear). La automatización del cotizador importa
            # `abrir_navegador` y `login` desde acá y sigue con su propia lógica
            # sobre la misma `page`. Por ahora dejamos la ventana abierta para
            # verificar que el acceso funciona.
            input("Presioná ENTER para cerrar el navegador...")
        finally:
            browser.close()


if __name__ == "__main__":
    main()
