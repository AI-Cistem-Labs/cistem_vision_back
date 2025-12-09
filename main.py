# main.py
import time
import config
from modules.vision import VisionManager
from modules.communication import CommunicationManager  # <--- Nuevo import


def main():
    print("=== INICIANDO SISTEMA CISTEM VISION (INTEGRACIÓN) ===")

    # 1. Iniciar Módulo de Visión (Hilo independiente)
    print("[MAIN] Iniciando Visión...")
    vision_module = VisionManager(
        source=config.CAMERA_INDEX,
        model_path=config.MODEL_PATH,
        csv_output=config.CSV_FILE
    )
    vision_module.start()

    # 2. Iniciar Módulo de Comunicación (Hilo principal / Bloqueante)
    # Le pasamos 'vision_module' para que pueda acceder a los frames
    print("[MAIN] Iniciando Comunicación...")
    comms_module = CommunicationManager(
        port=config.PORT,
        vision_module=vision_module
    )

    try:
        # Este método es bloqueante, el programa se quedará aquí
        # sirviendo la web hasta que se detenga.
        comms_module.start()

    except KeyboardInterrupt:
        print("\n[SISTEMA] Interrupción recibida. Deteniendo...")

    finally:
        print("[SISTEMA] Deteniendo hilos...")
        vision_module.stop()
        vision_module.join()
        print("[SISTEMA] Apagado completo.")


if __name__ == "__main__":
    main()