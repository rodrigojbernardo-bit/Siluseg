"""
Script standalone para probar scrapers/meridional.py sin necesidad de Flask.
Uso: python test_meridional.py
"""
import queue
import threading
from scrapers import meridional

# ── Datos de prueba — modificar según necesidad ───────────────────────────────
DNI              = "12345678"
ANIO             = "2020"
MARCA            = "VOLKSWAGEN"
MODELO_BUSQUEDA  = "GOLF"
PROVINCIA        = "BUENOS AIRES"
LOCALIDAD        = "HAEDO"
# ─────────────────────────────────────────────────────────────────────────────

SESSION_ID = "test_session"

sessions = {
    SESSION_ID: {
        "queue":   queue.Queue(),
        "status":  "running",
        "resultados": {},
    }
}

def imprimir_logs():
    q = sessions[SESSION_ID]["queue"]
    while True:
        try:
            item = q.get(timeout=5)
            if item.get("type") == "log":
                print(f"  {item['msg']}")
            elif item.get("type") == "error":
                print(f"  ERROR: {item['msg']}")
        except queue.Empty:
            if not hilo.is_alive():
                break

hilo = threading.Thread(
    target=meridional.run,
    args=(SESSION_ID, sessions, DNI, ANIO, MARCA, MODELO_BUSQUEDA, PROVINCIA, LOCALIDAD),
    daemon=True,
)

print("Iniciando test de Meridional...")
print(f"  DNI={DNI} | Año={ANIO} | Marca={MARCA} | Modelo={MODELO_BUSQUEDA}")
print(f"  Provincia={PROVINCIA} | Localidad={LOCALIDAD}")
print("-" * 60)

hilo.start()
imprimir_logs()
hilo.join()

print("-" * 60)
resultado = sessions[SESSION_ID]["resultados"].get("Meridional", {})
print(f"Resultado final: ok={resultado.get('ok')} | coberturas={len(resultado.get('coberturas', []))}")
if not resultado.get("ok"):
    print(f"Error: {resultado.get('error', 'desconocido')}")
