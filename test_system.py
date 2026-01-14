# test_system.py
import time
import os
import pandas as pd
from modules.vision.manager import VisionManager
from modules.storage.specialists.csv_specialist import CSVStorageSpecialist
from modules.analytics.manager import AnalyticsManager


def run_test():
    print("🧪 Test de Integración: Generando datos para Postman...")

    vision = VisionManager()
    storage = CSVStorageSpecialist()
    # No necesitamos SocketIO para este test funcional de archivos
    analytics = AnalyticsManager(vision, storage, None)

    cam_id = 1001
    vision.set_camera_active(cam_id, True)

    # Simular detección para forzar la alerta
    print(f"📸 Simulando detección en Cámara {cam_id}...")
    with vision.cameras[cam_id]["lock"]:
        vision.cameras[cam_id]["metadata"]["count"] = 15

    analytics.start()
    time.sleep(6)  # Esperar ciclo de guardado

    alert_file = f"data/cam_{cam_id}_alert.csv"
    if os.path.exists(alert_file):
        df = pd.read_csv(alert_file)
        print(f"✅ CSV generado con {len(df)} alertas.")
        print(df.tail(1)[['alert_id', 'level', 'msg', 'read']])
    else:
        print("❌ Error: No se generó el archivo de alertas.")

    analytics.running = False
    print("🏁 Test finalizado.")


if __name__ == "__main__":
    run_test()