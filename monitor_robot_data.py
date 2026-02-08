#!/usr/bin/env python3
"""
Monitor de datos del robot en tiempo real
Muestra todos los datos que llegan del robot
"""
import sys
import os

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from flask import Flask
from flask_socketio import SocketIO
import json
import logging

logging.basicConfig(
    level=logging.INFO,
    format='%(message)s'  # Sin timestamp para output más limpio
)

app = Flask(__name__)
socketio = SocketIO(app, cors_allowed_origins="*", async_mode='threading')


def print_json(title, data):
    """Imprime JSON formateado"""
    print("\n" + "=" * 80)
    print(f"📦 {title}")
    print("=" * 80)
    print(json.dumps(data, indent=2, ensure_ascii=False))
    print("=" * 80 + "\n")


@socketio.on('connect')
def handle_connect():
    print("\n🤖 ✅ ROBOT CONECTADO\n")


@socketio.on('disconnect')
def handle_disconnect():
    print("\n🤖 ⚠️ ROBOT DESCONECTADO\n")


@socketio.on('camera_info')
def handle_camera_info(data):
    print_json("CAMERA INFO", data)


@socketio.on('alert')
def handle_alert(data):
    # Acortar base64 de imagen si existe
    if data.get('evidence') and data['evidence'].get('url', '').startswith('data:image'):
        data_copy = data.copy()
        data_copy['evidence'] = data['evidence'].copy()
        data_copy['evidence']['url'] = data['evidence']['url'][:100] + "... [IMAGEN BASE64 TRUNCADA]"
        print_json("ALERT", data_copy)
    else:
        print_json("ALERT", data)


@socketio.on('robot_info')
def handle_robot_info(data):
    print_json("ROBOT INFO", data)


if __name__ == '__main__':
    print("\n" + "=" * 80)
    print("🔍 MONITOR DE DATOS DEL ROBOT - Modo Verbose")
    print("=" * 80)
    print("Puerto: 5000")
    print("Mostrará TODOS los datos en formato JSON")
    print("=" * 80 + "\n")
    print("⏳ Esperando robot...\n")

    socketio.run(app, host='0.0.0.0', port=5000, debug=False, allow_unsafe_werkzeug=True)