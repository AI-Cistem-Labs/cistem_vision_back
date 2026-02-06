import os
import subprocess
import sqlite3
import time

def configurar_red_sistema():
    try:
        subprocess.run(["wg", "show", "wg0"], check=True, stdout=subprocess.DEVNULL)
    except subprocess.CalledProcessError:
        subprocess.run(["wg-quick", "up", "wg0"], check=True)

def agregar_peer_wireguard(public_key, ip_virtual):
    subprocess.run([
        "wg", "set", "wg0",
        "peer", public_key,
        "allowed-ips", f"{ip_virtual}/32"
    ], check=True)

def guards(nombre, token, public_key):
    if not nombre or not public_key:
        return jsonify({"error": "missing fields"}), 400

    if len(nombre) > 64 or len(public_key) > 64:
        return jsonify({"error": "invalid input"}), 400

    if token != os.getenv("BOOTSTRAP_TOKEN"):
        return jsonify({"error": "unauthorized"}), 401
    
    return None

