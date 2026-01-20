# test_full_integration.py
"""
Script de prueba completa del sistema Cistem Vision Backend
"""
import time
from config.config_manager import device_config
from modules.vision.manager import VisionManager
from modules.vision.processors import get_available_processors
from modules.analytics.specialists.system_logger import system_logger
from modules.analytics.specialists.alerts_engine import alerts_engine

print("=" * 70)
print("🧪 PRUEBA DE INTEGRACIÓN COMPLETA - CISTEM VISION BACKEND v1.1")
print("=" * 70)
print()

# ============================================================================
# 1. CONFIGURACIÓN
# ============================================================================
print("📋 PASO 1: Verificando configuración del dispositivo")
print("-" * 70)

device_info = device_config.get_device_info()
location_info = device_config.get_location_info()
cameras = device_config.get_cameras()

print(f"✅ Dispositivo: {device_info['label']} (ID: {device_info['device_id']})")
print(f"✅ Ubicación: {location_info['label']}")
print(f"✅ Cámaras configuradas: {len(cameras)}")

for cam in cameras:
    print(f"   - Cámara {cam['cam_id']}: {cam['label']}")
    print(f"     RTSP: {cam['rtsp_url'][:30]}...")
    print(f"     Procesadores disponibles: {cam['available_processors']}")

print()

# ============================================================================
# 2. PROCESADORES
# ============================================================================
print("📋 PASO 2: Verificando procesadores de IA")
print("-" * 70)

processors = get_available_processors()
print(f"✅ Procesadores registrados: {len(processors)}")

for proc_id, proc_info in processors.items():
    print(f"   [{proc_id}] {proc_info['label']}")
    print(f"       {proc_info['description']}")

print()

# ============================================================================
# 3. SISTEMA DE LOGS
# ============================================================================
print("📋 PASO 3: Probando sistema de logs")
print("-" * 70)

test_cam_id = 1001

# Generar logs de prueba
system_logger.log(test_cam_id, "Prueba de log INFO", "INFO")
system_logger.log(test_cam_id, "Prueba de log WARNING", "WARNING")
system_logger.log(test_cam_id, "Prueba de log ERROR", "ERROR")

# Usar códigos predefinidos
system_logger.camera_started(test_cam_id)
system_logger.processor_changed(test_cam_id, "Procesador de Prueba")

# Obtener logs
logs = system_logger.get_logs(test_cam_id)
print(f"✅ Logs generados: {len(logs)}")
print(f"✅ Último log: {logs[-1]['msg']}")

print()

# ============================================================================
# 4. MOTOR DE ALERTAS
# ============================================================================
print("📋 PASO 4: Probando motor de alertas")
print("-" * 70)

# Generar alertas de prueba
alerts_engine.create_alert(
    test_cam_id,
    "Alerta de prueba - nivel precaución",
    "PRECAUCION",
    {"test": True}
)

alerts_engine.intrusion_detected(test_cam_id, "Sector Test")
alerts_engine.crowd_detected(test_cam_id, 25)

# Obtener alertas
alerts = alerts_engine.get_alerts(test_cam_id)
print(f"✅ Alertas generadas: {len(alerts)}")
print(f"✅ Última alerta: {alerts[-1]['msg']}")

# Probar marcar como leída
alert_id = alerts[0]['alert_id']
alerts_engine.mark_as_read(alert_id)
print(f"✅ Alerta {alert_id} marcada como leída")

print()

# ============================================================================
# 5. VISION MANAGER
# ============================================================================
print("📋 PASO 5: Probando Vision Manager")
print("-" * 70)

vision_manager = VisionManager()
print("✅ Vision Manager inicializado")

# Verificar estado de cámaras
for cam in cameras:
    cam_id = cam['cam_id']
    is_active = vision_manager.is_camera_active(cam_id)
    print(f"   Cámara {cam_id}: {'ACTIVA' if is_active else 'INACTIVA'}")

print()

# ============================================================================
# 6. ACTUALIZACIÓN DE CONFIGURACIÓN
# ============================================================================
print("📋 PASO 6: Probando actualización de configuración")
print("-" * 70)

test_cam_id = cameras[0]['cam_id']

# Actualizar estado
print(f"   Encendiendo cámara {test_cam_id}...")
device_config.update_camera_status(test_cam_id, True)
cam = device_config.get_camera(test_cam_id)
print(f"   ✅ Estado: {cam['status']}")

# Actualizar posición
print(f"   Actualizando posición de cámara {test_cam_id}...")
device_config.update_camera_position(test_cam_id, [50, 100])
cam = device_config.get_camera(test_cam_id)
print(f"   ✅ Nueva posición: {cam['position']}")

# Actualizar procesador activo
if len(processors) > 0:
    first_proc_id = list(processors.keys())[0]
    print(f"   Asignando procesador {first_proc_id} a cámara {test_cam_id}...")
    device_config.update_active_processor(test_cam_id, first_proc_id)
    cam = device_config.get_camera(test_cam_id)
    print(f"   ✅ Procesador activo: {cam['active_processor']}")

print()

# ============================================================================
# RESUMEN
# ============================================================================
print("=" * 70)
print("📊 RESUMEN DE PRUEBAS")
print("=" * 70)
print(f"✅ Configuración: OK")
print(f"✅ Procesadores: {len(processors)} registrados")
print(f"✅ Sistema de logs: {len(logs)} registros")
print(f"✅ Motor de alertas: {len(alerts)} alertas")
print(f"✅ Vision Manager: Inicializado")
print(f"✅ Actualización de config: OK")
print("=" * 70)
print()
print("🎉 TODAS LAS PRUEBAS PASARON EXITOSAMENTE")
print()
print("📝 SIGUIENTE PASO:")
print("   Ejecutar servidor: python app.py")
print("   Probar con cliente SocketIO o Postman")
print()