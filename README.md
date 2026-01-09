# cistem-vision
Backend: Plataforma de Monitoreo con Visión Artificial (Cistem Vision)
Este proyecto es el núcleo de procesamiento de una plataforma de monitoreo basada en visión artificial. Está diseñado para ejecutarse en dispositivos de borde (como NVIDIA Jetson), capturando video en tiempo real, procesando detecciones mediante modelos de Deep Learning y comunicando los resultados a un dashboard externo vía WebSockets.

🚀 Requisitos del Sistema
Intérprete: Python 3.8.

Hardware Sugerido: Dispositivos con soporte GPIO (Jetson Nano/NX) para retroalimentación física.

Cámara: USB o CSI compatible con OpenCV.

🛠️ Instalación y Configuración
1. Preparar el Entorno Virtual
Se recomienda el uso de venv para aislar las dependencias:

Bash

python3.8 -m venv venv
source venv/bin/activate  # En Windows: venv\Scripts\activate
2. Instalar Librerías
Ejecuta el siguiente comando para instalar todas las dependencias necesarias:

Bash

pip install opencv-python flask flask-socketio python-dotenv ultralytics supervision pandas
Nota: Para el control de hardware en Jetson, se requiere la librería Jetson.GPIO.

3. Variables de Entorno
Crea un archivo .env en la raíz con la siguiente estructura:

Fragmento de código

DEVICE_NAME=Jetson-Aula-B
SERVER_PORT=5000
CAMERA_INDEX=0
MODELS_DIR=./models
DATA_DIR=./data
# Configuración de GPIO
PIN_LED_NET=18
PIN_LED_PWR=23
PIN_LED_CAM=24
PIN_BTN_OFF=25
📂 Árbol del Proyecto
Plaintext

.
├── main.py                 # Punto de entrada y orquestación de hilos
├── config.py               # Carga de configuración desde .env
├── .env                    # Configuración local del dispositivo
├── models/                 # Almacenamiento de modelos .pt (ej. bestpersonas.pt)
├── data/                   # Archivos de salida (CSV de detecciones)
└── modules/
    ├── vision/             # Captura y procesamiento de imagen
    ├── analytics/          # Motor de reglas y alertas
    ├── comunication/       # Servidor Flask-SocketIO
    └── logs/               # Gestión de logs y control de hardware (LEDs)
🧩 Infraestructura de Módulos
El sistema funciona mediante hilos concurrentes para asegurar que el procesamiento de video no bloquee las comunicaciones:

1. Visión (modules/vision/)
Manager: Gestiona el ciclo de captura de la cámara y permite el cambio dinámico de "especialistas" (procesadores) sin detener el flujo.

Processors: Contiene la lógica de detección. Por ejemplo, FlowPersonsProcessor utiliza YOLO y la librería Supervision para contar personas y anotar los cuadros.

Registry: Permite registrar nuevos tipos de análisis para que el dashboard pueda seleccionarlos.

2. Comunicación (modules/comunication/)
Implementa un servidor Flask con SocketIO.

Provee el endpoint /video_feed para streaming MJPEG y canales de eventos para enviar logs y alertas al dashboard en tiempo real.

3. Analítica (modules/analytics/)
AlertsEngine: Monitorea los datos generados por el procesador de visión activo (leyendo sus archivos CSV). Si detecta anomalías (ej. aforo > 10), dispara eventos de alerta vía comunicación.

4. Logs y Hardware (modules/logs/)
SystemLogger: Centraliza los mensajes de estado del sistema.

HardwareCtrl: Controla los LEDs de estado (Red, Power, Cámara) y monitorea el botón físico de apagado seguro mediante los pines GPIO definidos.

🏃 Ejecución
Para iniciar el sistema completo:

Bash

python main.py
El sistema iniciará automáticamente la cámara y el servidor en el puerto 5000 (o el configurado en el .env). Para detenerlo de forma segura, usa Ctrl+C.
