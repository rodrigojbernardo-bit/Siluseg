# Siluseg

Bot de acceso automático al portal de **Federación Patronal** usando Playwright.

## El problema

Cloudflare bloqueaba el acceso automático porque Playwright abría un navegador
"limpio", sin historial ni cookies, y eso lo identificaba como bot.

## La solución

Usar un **perfil de Chrome dedicado** que ya pasó el desafío de Cloudflare una
vez de forma manual, lanzado con Chrome real (no Chromium) y sesión persistente.

### Claves del éxito

- `channel="chrome"` → usa el Chrome real instalado, no el Chromium de Playwright.
- `launch_persistent_context` → mantiene cookies y sesión entre ejecuciones.
- Perfil copiado a una carpeta separada → no entra en conflicto con tu Chrome normal.
- `headless=False` → ventana visible para resolver el Cloudflare a mano si hace falta.
- `wait_for_selector("#usuario", timeout=60000)` → espera paciente hasta que Cloudflare libera el paso.
- Pausa extra antes de completar credenciales → deja que el portal se estabilice.

## Setup (una sola vez)

1. **Creá un perfil nuevo en Chrome** llamado `SILUSEG BOT`.
2. Desde ese perfil, **entrá manualmente** al portal de Federación Patronal y
   **pasá el Cloudflare** una vez.
3. **Copiá ese perfil** a una carpeta exclusiva del bot, por ejemplo:
   `C:\Users\User\Desktop\SVO AUTOMATICO\chrome_perfil_bot`
   (no debe compartirse con tu Chrome normal: no pueden estar abiertos a la vez).

## Instalación

```bash
pip install -r requirements.txt
playwright install chrome
```

## Configuración

Copiá `.env.example` a `.env` y completá:

```ini
FP_CHROME_PERFIL=C:\Users\User\Desktop\SVO AUTOMATICO\chrome_perfil_bot
FP_USUARIO=tu_usuario
FP_PASSWORD=tu_password
```

> El `.env` y la carpeta del perfil **no se versionan** (ver `.gitignore`).

## Uso

```bash
python fp_bot.py
```

Si Cloudflare muestra un desafío, resolvelo en la ventana que se abre: el bot
espera hasta 60 segundos a que aparezca el formulario de login antes de
completar las credenciales automáticamente.
