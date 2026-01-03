# main.py
import time
import config
from modules.vision.manager import VisionManager
from modules.comunication.manager import CommunicationManager
from modules.logs.manager import LogManager
from modules.analytics.alerts_engine import AlertsEngine


def main():
    print("=== INICIANDO ECOSISTEMA CISTEM VISION (VERSION ROBUSTA) ===")

    # 1. Visión (Cámara y Procesadores)
    vision_module = VisionManager(source=config.CAMERA_INDEX)
    vision_module.start()

    # 2. Comunicación (Servidor SocketIO)
    comms_module = CommunicationManager(port=config.PORT, vision_module=vision_module)

    # 3. Monitor de Salud (Logs y GPIO)
    logs_module = LogManager(comms_module=comms_module, vision_module=vision_module)
    logs_module.start()

    # 4. Motor de Alertas Inteligentes
    alerts_module = AlertsEngine(comms_module=comms_module, vision_module=vision_module)
    alerts_module.start()

    try:
        # Iniciar servidor (Este método bloquea el hilo principal)
        comms_module.start()

    except KeyboardInterrupt:
        print("\n[SISTEMA] Deteniendo módulos...")
        vision_module.stop()
        logs_module.stop()
        alerts_module.running = False

        vision_module.join()
        logs_module.join()
        alerts_module.join()
        print("[SISTEMA] Apagado completo.")


if __name__ == "__main__":
    main()