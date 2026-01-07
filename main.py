# main.py
import config
from modules.vision.manager import VisionManager
from modules.comunication.manager import CommunicationManager
from modules.logs.manager import LogManager
from modules.analytics.manager import AnalyticsManager

def main():
    print(f"=== INICIANDO {config.DEVICE_NAME} ===")

    # 1. Iniciar Visión
    vision = VisionManager(source=config.CAMERA_INDEX)
    vision.start()

    # 2. Iniciar Comunicación
    comms = CommunicationManager(port=config.PORT, vision_module=vision)

    # 3. Iniciar Logs (Logger + Hardware)
    logs = LogManager(comms, vision)
    logs.start()

    # 4. Iniciar Analítica (Alertas)
    analytics = AnalyticsManager(comms, vision)
    analytics.start()

    try:
        # El servidor de comunicación mantiene vivo el hilo principal
        comms.start()
    except KeyboardInterrupt:
        print("\n[SISTEMA] Apagado seguro iniciado...")
        vision.stop()
        logs.stop()
        analytics.stop()
        print("[SISTEMA] ¡Hasta luego!")

if __name__ == "__main__":
    main()