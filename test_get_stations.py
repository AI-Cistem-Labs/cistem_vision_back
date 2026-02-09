#!/usr/bin/env python3
"""
test_get_stations.py
Prueba el endpoint get_stations y verifica el campo 'type'
"""
import socketio
import json
import time

# Configuración
BACKEND_URL = "http://localhost:5000"
EMAIL = "admin@cistemlabs.ai"  # ⭐ CAMBIADO: era 'username'
PASSWORD = "123456"  # ⭐ CAMBIADO: era 'admin'


def main():
    print("\n" + "=" * 70)
    print("🧪 TEST: get_stations - Verificar campo 'type'")
    print("=" * 70 + "\n")

    # Crear cliente SocketIO
    sio = socketio.Client()

    # Variable para almacenar respuesta
    response_data = {}

    @sio.on('connect')
    def on_connect():
        print("✅ Conectado al servidor")
        print("🔑 Obteniendo token de autenticación...\n")

        # Solicitar token con EMAIL y PASSWORD
        sio.emit('login', {
            'email': EMAIL,  # ⭐ CAMBIADO
            'password': PASSWORD
        })

    @sio.on('login_response')
    def on_login_response(data):
        if data.get('success'):
            token = data.get('token')
            print(f"✅ Token obtenido: {token[:20]}...\n")
            print("📡 Solicitando estaciones...\n")

            # Solicitar estaciones
            sio.emit('get_stations', {'token': token})
        else:
            print(f"❌ Error login: {data.get('error')}")
            sio.disconnect()

    @sio.on('get_stations_response')
    def on_stations_response(data):
        print("✅ Respuesta recibida!\n")
        print("=" * 70)

        if 'error' in data:
            print(f"❌ Error: {data['error']}")
        else:
            # Extraer cámaras
            cameras = []
            for location in data.get('data', []):
                for device in location.get('devices', []):
                    cameras.extend(device.get('cameras', []))

            print(f"📹 Total de cámaras: {len(cameras)}\n")

            # Agrupar por tipo
            cameras_by_type = {'Camera': [], 'Robot': [], 'Unknown': []}

            for cam in cameras:
                cam_type = cam.get('type', 'Unknown')
                cam_id = cam.get('cam_id')
                cam_label = cam.get('label')
                cam_status = cam.get('status')

                if cam_type not in cameras_by_type:
                    cameras_by_type[cam_type] = []

                cameras_by_type[cam_type].append({
                    'cam_id': cam_id,
                    'label': cam_label,
                    'status': cam_status
                })

                # Mostrar detalle de cada cámara
                status_icon = "🟢" if cam_status else "🔴"
                print(f"  📷 cam_id: {cam_id}")
                print(f"     type: {cam_type}")  # ⭐ CAMPO A VERIFICAR
                print(f"     label: {cam_label}")
                print(f"     status: {status_icon} {cam_status}")
                print()

            # Resumen por tipo
            print("=" * 70)
            print("📊 RESUMEN POR TIPO:")
            print("=" * 70)

            print(f"🏢 Cámaras tipo 'Camera': {len(cameras_by_type['Camera'])}")
            for cam in cameras_by_type['Camera']:
                status_icon = "🟢" if cam['status'] else "🔴"
                print(f"   {status_icon} [{cam['cam_id']}] {cam['label']}")

            print(f"\n🤖 Cámaras tipo 'Robot': {len(cameras_by_type['Robot'])}")
            if cameras_by_type['Robot']:
                for cam in cameras_by_type['Robot']:
                    status_icon = "🟢" if cam['status'] else "🔴"
                    print(f"   {status_icon} [{cam['cam_id']}] {cam['label']}")
            else:
                print("   (Ninguna cámara del robot conectada)")

            if cameras_by_type['Unknown']:
                print(f"\n❓ Cámaras sin tipo: {len(cameras_by_type['Unknown'])}")
                for cam in cameras_by_type['Unknown']:
                    print(f"   ⚠️ [{cam['cam_id']}] {cam['label']}")

            print("=" * 70)

            # Verificación del campo type
            print("\n🔍 VERIFICACIÓN:")
            all_have_type = all('type' in cam for cam in cameras)

            if all_have_type:
                print("✅ ÉXITO: Todas las cámaras tienen el campo 'type'")
            else:
                print("❌ FALLO: Algunas cámaras NO tienen el campo 'type'")
                for cam in cameras:
                    if 'type' not in cam:
                        print(f"   - cam_id {cam.get('cam_id')} sin 'type'")

            print("\n" + "=" * 70)

            # Guardar respuesta completa en archivo
            with open('stations_response.json', 'w', encoding='utf-8') as f:
                json.dump(data, f, indent=2, ensure_ascii=False)

            print("💾 Respuesta completa guardada en: stations_response.json")
            print("=" * 70 + "\n")

        # Desconectar
        sio.disconnect()

    @sio.on('disconnect')
    def on_disconnect():
        print("👋 Desconectado del servidor\n")

    # Conectar
    try:
        print(f"🔌 Conectando a {BACKEND_URL}...")
        sio.connect(BACKEND_URL)
        sio.wait()
    except Exception as e:
        print(f"❌ Error: {e}")


if __name__ == '__main__':
    main()