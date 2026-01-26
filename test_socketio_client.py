# test_socketio_client.py
"""
Cliente de prueba para conectarse al backend y probar eventos
"""
import socketio
import time
import json

# Crear cliente SocketIO
sio = socketio.Client()

# Variables globales
token = None


# ============================================================================
# EVENTOS
# ============================================================================

@sio.on('connect')
def on_connect():
    print("✅ Conectado al servidor")
    print()


@sio.on('disconnect')
def on_disconnect():
    print("❌ Desconectado del servidor")


@sio.on('login_response')
def on_login_response(data):
    global token
    print("📨 Respuesta de login:")
    print(json.dumps(data, indent=2))

    if data.get('success'):
        token = data.get('token')
        print(f"✅ Token obtenido: {token[:50]}...")
    print()


@sio.on('get_profile_response')
def on_get_profile_response(data):
    print("📨 Respuesta de get_profile:")
    print(json.dumps(data, indent=2))
    print()


@sio.on('get_stations_response')
def on_get_stations_response(data):
    print("📨 Respuesta de get_stations:")
    print(json.dumps(data, indent=2))
    print()


@sio.on('get_logs_response')
def on_get_logs_response(data):
    print("📨 Respuesta de get_logs:")
    if 'data' in data:
        print(f"   Logs recibidos: {len(data['data'])}")
        if len(data['data']) > 0:
            print(f"   Último log: {data['data'][-1]}")
    else:
        print(json.dumps(data, indent=2))
    print()


@sio.on('get_alerts_response')
def on_get_alerts_response(data):
    print("📨 Respuesta de get_alerts:")
    if 'data' in data:
        print(f"   Alertas recibidas: {len(data['data'])}")
        if len(data['data']) > 0:
            print(f"   Última alerta: {data['data'][-1]}")
    else:
        print(json.dumps(data, indent=2))
    print()


@sio.on('update_camera_status_response')
def on_update_camera_status_response(data):
    print("📨 Respuesta de update_camera_status:")
    print(json.dumps(data, indent=2))
    print()


@sio.on('select_processor_response')
def on_select_processor_response(data):
    print("📨 Respuesta de select_processor:")
    print(json.dumps(data, indent=2))
    print()


@sio.on('new_log')
def on_new_log(data):
    print(f"📢 NUEVO LOG: [{data['label']}] {data['msg']}")


@sio.on('new_alert')
def on_new_alert(data):
    print(f"🚨 NUEVA ALERTA: [{data['label']}] {data['msg']}")


# ============================================================================
# FUNCIÓN PRINCIPAL
# ============================================================================

def main():
    print("=" * 70)
    print("🧪 CLIENTE DE PRUEBA - CISTEM VISION BACKEND")
    print("=" * 70)
    print()

    # Conectar al servidor
    print("🔌 Conectando a ws://localhost:5000...")
    try:
        sio.connect('http://localhost:5000')
    except Exception as e:
        print(f"❌ Error al conectar: {e}")
        return

    time.sleep(1)

    # ========================================================================
    # 1. LOGIN
    # ========================================================================
    print("📋 PASO 1: Login")
    print("-" * 70)
    sio.emit('login', {
        'email': 'admin@cistemlabs.ai',
        'password': '123456'
    })
    time.sleep(2)

    if not token:
        print("❌ No se pudo obtener token, abortando pruebas")
        sio.disconnect()
        return

    # ========================================================================
    # 2. GET PROFILE
    # ========================================================================
    print("📋 PASO 2: Obtener perfil")
    print("-" * 70)
    sio.emit('get_profile', {'token': token})
    time.sleep(1)

    # ========================================================================
    # 3. GET STATIONS
    # ========================================================================
    print("📋 PASO 3: Obtener estaciones")
    print("-" * 70)
    sio.emit('get_stations', {'token': token})
    time.sleep(1)

    # ========================================================================
    # 4. GET LOGS
    # ========================================================================
    print("📋 PASO 4: Obtener logs")
    print("-" * 70)
    sio.emit('get_logs', {
        'token': token,
        'location_id': 1,
        'device_id': 101,
        'cam_id': 1001
    })
    time.sleep(1)

    # ========================================================================
    # 5. GET ALERTS
    # ========================================================================
    print("📋 PASO 5: Obtener alertas")
    print("-" * 70)
    sio.emit('get_alerts', {
        'token': token,
        'location_id': 1,
        'device_id': 101,
        'cam_id': 1001
    })
    time.sleep(1)

    # ========================================================================
    # 6. UPDATE CAMERA STATUS
    # ========================================================================
    print("📋 PASO 6: Encender cámara")
    print("-" * 70)
    sio.emit('update_camera_status', {
        'token': token,
        'location_id': 1,
        'device_id': 101,
        'cam_id': 1001,
        'active': True
    })
    time.sleep(1)

    # ========================================================================
    # 7. SELECT PROCESSOR
    # ========================================================================
    print("📋 PASO 7: Seleccionar procesador")
    print("-" * 70)
    sio.emit('select_processor', {
        'token': token,
        'location_id': 1,
        'device_id': 101,
        'cam_id': 1001,
        'processor_id': 1
    })
    time.sleep(2)

    # ========================================================================
    # MANTENER CONEXIÓN PARA RECIBIR EVENTOS EN TIEMPO REAL
    # ========================================================================
    print("=" * 70)
    print("✅ PRUEBAS COMPLETADAS")
    print("📡 Escuchando eventos en tiempo real (Ctrl+C para salir)...")
    print("=" * 70)
    print()

    try:
        while True:
            time.sleep(1)
    except KeyboardInterrupt:
        print("\n👋 Desconectando...")
        sio.disconnect()


if __name__ == '__main__':
    main()