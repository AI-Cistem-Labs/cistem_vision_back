import os
import subprocess
from flask import Flask, request, jsonify
from dotenv import load_dotenv
from src.functions import configurar_red_sistema, agregar_peer_wireguard, guards
from src.database import iniciar_db, asignar_ip_dinamica
import time
from datetime import datetime
import threading

load_dotenv()
app = Flask(__name__)
conn = iniciar_db()

def marcar_offline():
    cursor = conn.cursor()
    cursor.execute("""
        UPDATE jetsons
        SET status = 'offline'
        WHERE last_seen < datetime('now', '-30 seconds')
    """)
    conn.commit()

def offline_worker():
    while True:
        marcar_offline()
        time.sleep(30)

@app.route('/registrar', methods=['POST'])
def registrar_jetson():
    datos = request.json or {}

    nombre = datos.get('nombre')
    public_key = datos.get('public_key')
    token = datos.get('token')

    respuesta_guard = guards(nombre, token, public_key)
    if respuesta_guard:
        return respuesta_guard
    
    ip_asignada = asignar_ip_dinamica(conn, nombre, public_key)
    try:
        agregar_peer_wireguard(public_key, ip_asignada)
    except subprocess.CalledProcessError:
        return jsonify({"error": "wireguard failure"}), 500

    return jsonify({
        "ip_virtual": ip_asignada,
        "hub_public_key": os.getenv("HUB_PUBLIC_KEY"),
        "hub_endpoint": f"{os.getenv('HUB_ENDPOINT')}:{os.getenv('HUB_PORT', '51820')}"
    })

@app.route("/agents", methods=["GET"])
def listar_agentes():
    cursor = conn.cursor()
    cursor.execute("""
        SELECT nombre, ip_virtual, last_seen, status, latency_ms
        FROM jetsons
    """)
    rows = cursor.fetchall()

    return jsonify([
        {
            "nombre": r["nombre"],
            "ip": r["ip_virtual"],
            "status": r["status"],
            "latency_ms": r["latency_ms"],
            "last_seen": r["last_seen"]
        }
        for r in rows
    ])

@app.route("/active_agents", methods=["GET"])
def listar_agentes_activos():
    cursor = conn.cursor()
    cursor.execute("""
        SELECT nombre, ip_virtual, last_seen, status, latency_ms
        FROM jetsons
        WHERE status = 'connected'
    """)
    rows = cursor.fetchall()

    return jsonify([
        {
            "nombre": r["nombre"],
            "ip": r["ip_virtual"],
            "status": r["status"],
            "latency_ms": r["latency_ms"],
            "last_seen": r["last_seen"]
        }
        for r in rows
    ])

@app.route("/heartbeat", methods=["POST"])
def heartbeat():
    nombre = request.json.get("nombre")
    latency_ms = request.json.get("latency_ms")

    if not nombre:
        return "", 400
    
    cursor = conn.cursor()
    cursor.execute("""
        UPDATE jetsons
        SET last_seen = ?, status = 'connected', latency_ms = ?
        WHERE nombre = ?
    """, (datetime.utcnow(), latency_ms, nombre))
    conn.commit()

    return "", 204

@app.route("/rotate", methods=["POST"])
def rotate_key():
    data = request.json or {}

    nombre = data.get("nombre")
    new_public_key = data.get("public_key")

    if not nombre or not new_public_key:
        return jsonify({"error": "missing fields"}), 400

    cursor = conn.cursor()
    cursor.execute(
        "SELECT ip_virtual FROM jetsons WHERE nombre=?",
        (nombre,)
    )
    row = cursor.fetchone()

    if not row:
        return jsonify({"error": "unknown node"}), 404

    ip = row["ip_virtual"]

    cursor.execute("""
        UPDATE jetsons
        SET public_key = ?
        WHERE nombre = ?
    """, (new_public_key, nombre))
    conn.commit()

    subprocess.run([
        "wg", "set", "wg0",
        "peer", new_public_key,
        "allowed-ips", f"{ip}/32"
    ], check=True)

    return "", 204

if __name__ == '__main__':
    configurar_red_sistema()
    offline_thread = threading.Thread(target=offline_worker)
    offline_thread.start()
    app.run(host='0.0.0.0', port=5000)