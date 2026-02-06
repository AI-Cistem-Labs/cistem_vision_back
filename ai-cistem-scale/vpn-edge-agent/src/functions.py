import requests
from wireguard import generar_claves, escribir_config, levantar_tunel, generar_nuevas_claves, solicitar_rotacion, aplicar_nueva_clave
import time
import os
from dotenv import load_dotenv
from bootstrap import registrar_en_hub
import subprocess
import re

load_dotenv()

ROTATE_INTERVAL = int(os.getenv("ROTATE_INTERVAL", 86400))
HEARTBEAT_INTERVAL = int(os.getenv("HEARTBEAT_INTERVAL", 30))

def heartbeat(hub_url, nombre):
    requests.post(
        f"{hub_url}/heartbeat",
        json={"nombre": nombre, "latency_ms": medir_latencia()},
        timeout=5
    )

def heartbeat_loop(hub_url, nombre):
    while True:
        heartbeat(hub_url, nombre)
        time.sleep(HEARTBEAT_INTERVAL)

def rotation_loop(hub_url, nombre, token):
    while True:
        time.sleep(ROTATE_INTERVAL)
        print(f"Iniciando rotación de claves para el nodo '{nombre}'")
        generar_nuevas_claves()
        solicitar_rotacion(hub_url, nombre, token)
        aplicar_nueva_clave()
        print(f"Rotación de claves realizada para el nodo '{nombre}'")

def intentar_conexion(nombre, hub_url, token):
    try:
        private_key, public_key = generar_claves()
        data = registrar_en_hub(hub_url, nombre, public_key, token)
        escribir_config(data, private_key)
        levantar_tunel()
        print("Túnel VPN establecido correctamente")
        return True
    except Exception as e:
        print(f"[WARN] No se pudo establecer el túnel: {e}")
        return False

def loop_conexion(nombre, hub_url, token):
    retry = int(os.getenv("CONNECT_RETRY_INTERVAL", 15))

    while True:
        if intentar_conexion(nombre, hub_url, token):
            break
        print(f"Reintentando conexión en {retry}s...")
        time.sleep(retry)


def medir_latencia():
    result = subprocess.run(
        ["ping", "-c", "1", "-W", "1", "10.0.0.1"],
        capture_output=True,
        text=True
    )

    if result.returncode != 0:
        return None

    match = re.search(r'time=([\d\.]+)\s*ms', result.stdout)
    if match:
        return float(match.group(1))

    return None
