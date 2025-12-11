# main.py
import time
import config
from modules.vision import VisionManager
from modules.communication import CommunicationManager
from modules.analytics import AnalyticsManager
from modules.logs import LogManager  # <--- Nuevo Import


def main():
    print("=== INICIANDO SISTEMA CISTEM VISION (FULL STACK ETAPA 1) ===")

    # 1. Visión
    print("[MAIN] Iniciando Visión...")
    vision_module = VisionManager(
        source=config.CAMERA_INDEX,
        model_path=config.MODEL_PATH,
        csv_output=config.CSV_FILE
    )
    vision_module.start()

    # 2. Comunicación
    print("[MAIN] Iniciando Comunicación...")
    comms_module = CommunicationManager(
        port=config.PORT,
        vision_module=vision_module
    )

    # 3. Analítica
    print("[MAIN] Iniciando Analítica...")
    analytics_module = AnalyticsManager(
        csv_path=config.CSV_FILE,
        comms_module=comms_module,
        interval=5
    )
    analytics_module.start()

    # 4. Logs y Salud del Sistema
    print("[MAIN] Iniciando Monitor de Sistema...")
    logs_module = LogManager(
        comms_module=comms_module,
        interval=10  # Revisar salud cada 10 segundos
    )
    logs_module.start()

    try:
        # Iniciar servidor web (Bloqueante)
        comms_module.start()

    except KeyboardInterrupt:
        print("\n[SISTEMA] Interrupción recibida. Deteniendo todo...")

    finally:
        print("[SISTEMA] Apagando módulos...")
        logs_module.stop()  # Apagar monitor primero
        analytics_module.stop()
        vision_module.stop()

        logs_module.join()
        analytics_module.join()
        vision_module.join()
        print("[SISTEMA] Apagado completo y seguro.")


if __name__ == "__main__":
    main()