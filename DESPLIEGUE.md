# Guía: publicar el cotizador en la web y trabajar a distancia

## Cómo funciona la arquitectura

El cotizador **tiene que seguir corriendo en tu PC** (o en una máquina propia),
porque abre navegadores reales (Playwright) que entran a los portales de
Sancor, Federación Patronal y Meridional con tus credenciales de productor.
Un hosting web común (como el de siluseg.com.ar) no puede ejecutar eso.

La solución es un **túnel**: tu PC queda conectada a internet de forma segura y
una dirección web fija apunta a ella. Vos entrás desde cualquier lado
(celular, casa, oficina) a esa dirección.

```
[Celular / casa]  →  coti.siluseg.com.ar  →  túnel  →  tu PC (Flask puerto 5001)
```

---

## 1. Dirección web fija: `coti.siluseg.com.ar` (recomendado)

Sobre `www.siluseg.com.ar/coti`: técnicamente se puede, pero requiere
configurar un "reverse proxy" en el servidor de tu página y tocar la app.
Un **subdominio** (`coti.siluseg.com.ar`) es igual de privado, mucho más
simple, y gratis con **Cloudflare Tunnel**:

1. Creá una cuenta gratis en https://dash.cloudflare.com
2. Agregá el dominio `siluseg.com.ar` (Cloudflare te da 2 servidores DNS;
   los cambiás donde registraste el dominio, por ej. NIC.ar o tu hosting).
   *La página actual sigue funcionando igual, no se toca nada.*
3. En tu PC (Windows), descargá `cloudflared`:
   https://developers.cloudflare.com/cloudflare-one/connections/connect-networks/downloads/
4. En una terminal (CMD):
   ```
   cloudflared tunnel login
   cloudflared tunnel create siluseg-coti
   cloudflared tunnel route dns siluseg-coti coti.siluseg.com.ar
   ```
5. Creá el archivo `C:\Users\User\.cloudflared\config.yml`:
   ```yaml
   tunnel: siluseg-coti
   credentials-file: C:\Users\User\.cloudflared\<ID-del-tunel>.json
   ingress:
     - hostname: coti.siluseg.com.ar
       service: http://127.0.0.1:5001
     - service: http_status:404
   ```
6. Instalalo como servicio de Windows (arranca solo al prender la PC):
   ```
   cloudflared service install
   ```

Listo: `https://coti.siluseg.com.ar` siempre apunta a tu PC, con HTTPS, gratis
y sin que la URL cambie nunca.

### Alternativa rápida mientras tanto: ngrok con dominio fijo

ngrok regala **un dominio estático por cuenta** (tipo
`algo-fijo.ngrok-free.app`). En https://dashboard.ngrok.com/domains lo creás,
y en `iniciar_cotizador.bat` cambiás la línea de ngrok por:

```
ngrok http --url=TU-DOMINIO.ngrok-free.app 5001
```

Así la URL deja de cambiar en cada arranque. Sirve para probar ya mismo,
sin tocar el DNS de siluseg.com.ar.

---

## 2. Acceso solo para vos: clave de ingreso

Ahora la app pide una **clave** antes de mostrar el cotizador (aunque alguien
descubra la dirección, no puede usarlo). La sesión queda recordada 30 días
en cada dispositivo.

- Clave por defecto: `siluseg2026` — **cambiala**.
- Para cambiarla, definí la variable de entorno `COTI_CLAVE` antes de
  arrancar la app. En `iniciar_cotizador.bat` podés agregar arriba:
  ```bat
  set COTI_CLAVE=TuClaveSecreta123
  ```

---

## 3. Envío de la cotización

Al terminar una cotización, debajo del botón "Descargar PDF" aparecen:

### WhatsApp
Poné el número del cliente (o dejalo vacío para elegir el contacto) y tocá
**WhatsApp**: se abre WhatsApp con un mensaje armado que incluye un **link de
descarga del PDF**. El link es único e imposible de adivinar, y funciona sin
clave, así el cliente descarga el PDF directo. (Requiere que la app esté
publicada en la web con el túnel del punto 1.)

### Email
Poné el email del cliente y tocá **Enviar email**: el PDF va **adjunto**.
Para que funcione hay que configurar la casilla que envía, una sola vez:

1. En tu cuenta de Gmail, activá la verificación en 2 pasos.
2. Generá una "contraseña de aplicación" en
   https://myaccount.google.com/apppasswords (16 letras).
3. En `iniciar_cotizador.bat` agregá arriba:
   ```bat
   set SMTP_USER=rodrigojbernardo@gmail.com
   set SMTP_PASS=xxxxxxxxxxxxxxxx
   ```

---

## 4. Acceso remoto a tu PC desde casa

Para manejar la PC de la oficina desde tu casa, lo más simple y gratis:

**RustDesk** (recomendado: gratis, sin límites, sin cuenta obligatoria)
1. Descargalo en las dos máquinas: https://rustdesk.com
2. En la PC de la oficina: abrilo, anotá el **ID**, y en
   Configuración → Seguridad activá "Contraseña permanente" y poné una clave fuerte.
3. Desde casa: abrís RustDesk, ponés el ID y la clave, y ves el escritorio
   de la oficina como si estuvieras ahí.

**Alternativas:** Chrome Remote Desktop (gratis, atado a tu cuenta de Google,
muy fácil: https://remotedesktop.google.com) o AnyDesk (gratis para uso personal).

**Importante para que funcione siempre:**
- La PC de la oficina tiene que quedar **prendida**.
- En Windows: Configuración → Energía → "Suspender: Nunca"
  (la pantalla sí se puede apagar).
- Configurá el programa de acceso remoto para que arranque con Windows.

---

## 5. Seguridad (pendiente, importante)

Las claves de los portales de Sancor, Federación y Meridional están escritas
dentro del código (`app.py` y `scrapers/`), y este repositorio las contiene.
Al exponer la app a internet conviene:

1. Mover esas claves a variables de entorno (como hicimos con `COTI_CLAVE`).
2. Cambiar las contraseñas en los portales de las aseguradoras.
3. Si el repositorio de GitHub es público, hacerlo **privado** ya mismo.

Pedímelo y lo hago en un próximo paso.
