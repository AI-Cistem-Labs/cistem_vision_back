import os
from dotenv import load_dotenv
from src.functions import heartbeat
from src.functions import heartbeat_loop, rotation_loop, loop_conexion
import threading
import time

load_dotenv()

def main():
    global nombre, hub_url, token

    nombre = os.getenv("NODE_NAME")
    hub_url = os.getenv("HUB_URL")
    token = os.getenv("BOOTSTRAP_TOKEN")

    print(f"Iniciando agente '{nombre}'")

    loop_conexion(nombre, hub_url, token)

    threading.Thread(target=heartbeat_loop, args=(hub_url, nombre), daemon=True).start()
    threading.Thread(target=rotation_loop, args=(hub_url, nombre, token), daemon=True).start()

    while True:
        time.sleep(3600)

if __name__ == "__main__":
    main()
