# Cistem Vision Backend

Plataforma de monitoreo inteligente con visión artificial. Sistema de procesamiento que captura video en tiempo real, aplica modelos de Deep Learning y gestiona retroalimentación digital (WebSockets) y física (GPIO en dispositivos de borde).

## 📋 Requisitos del Sistema

- **Python**: 3.8
- **Hardware**: NVIDIA Jetson (Nano, NX, etc.) para control GPIO. Funcional en PC para desarrollo.
- **Cámara**: USB o CSI compatible con OpenCV

## 🛠️ Instalación

### 1. Clonar el repositorio

```bash
git clone https://github.com/AI-Cistem-Labs/cistem_vision_back.git
cd cistem_vision_back
```

### 2. Crear entorno virtual

```bash
python3.8 -m venv venv
source venv/bin/activate  # Windows: venv\Scripts\activate
```

### 3. Instalar dependencias

```bash
pip install opencv-python flask flask-socketio python-dotenv ultralytics supervision pandas
```

**Nota para Jetson**: Instalar adicionalmente `Jetson.GPIO` para control de pines físicos.

### 4. Configurar variables de entorno

Crear archivo `.env` en la raíz:

```env
DEVICE_NAME=Jetson-Aula-B
SERVER_PORT=5000
CAMERA_INDEX=0
MODELS_DIR=./models
DATA_DIR=./data

# Configuración de pines GPIO
PIN_LED_NET=18
PIN_LED_PWR=23
PIN_LED_CAM=24
PIN_BTN_OFF=25
```

## 📂 Estructura del Proyecto

```
cistem_vision_back/
│
├── .env                        # Variables de entorno
├── config.py                   # Configuración centralizada
├── main.py                     # Punto de entrada y orquestador
├── README.md                   # Este archivo
│
├── data/                       # Logs y CSVs de detecciones
│   └── detecciones_log.csv
│
├── models/                     # Modelos YOLO (.pt)
│   ├── bestpersonas.pt         # Detección de personas
│   └── NixitoS.pt              # Modelo complementario
│
└── modules/
    │
    ├── analytics/              # Procesamiento y alertas
    │   ├── __init__.py
    │   ├── base.py             # Clase base analítica
    │   ├── manager.py          # Hilo gestor de analíticas
    │   └── specialists/
    │       ├── __init__.py
    │       └── alerts_engine.py # Motor de alertas de aforo
    │
    ├── comunication/           # Servidor Flask-SocketIO
    │   ├── __init__.py
    │   └── manager.py          # Streaming y WebSockets
    │
    ├── logs/                   # Estados y control de hardware
    │   ├── __init__.py
    │   ├── base.py             # Clase base de logs
    │   ├── manager.py          # Orquestador de logs y GPIO
    │   └── specialists/
    │       ├── __init__.py
    │       ├── hardware_ctrl.py # Control de LEDs y botón
    │       └── system_logger.py # Registro de eventos
    │
    └── vision/                 # Núcleo de visión artificial
        ├── __init__.py
        ├── manager.py          # Captura y procesamiento
        └── processors/
            ├── __init__.py
            ├── base.py         # Clase base de procesadores
            ├── flow_persons.py # Procesador YOLO de flujo
            └── registry.py     # Registro dinámico
```

## 🧩 Arquitectura del Sistema

Sistema multi-hilo con 4 módulos principales ejecutándose en paralelo:

### 1. Vision (`modules/vision/`)

**Manager** (`manager.py`):
- Gestiona conexión con cámara (USB/CSI)
- Controla cambio dinámico entre procesadores usando threading.Lock
- Coordina captura de frames en tiempo real

**Processors** (`processors/`):
- **base.py**: Clase abstracta para procesadores de imagen
- **flow_persons.py**: Implementa detección YOLO para conteo de personas. Realiza inferencia, anota frames y genera datos CSV
- **registry.py**: Registro dinámico para cargar procesadores sin modificar código base

### 2. Comunication (`modules/comunication/`)

**Manager** (`manager.py`):
- Servidor Flask-SocketIO en puerto configurado (default: 5000)
- Endpoint `/video_feed`: Stream MJPEG del video procesado
- WebSocket bidireccional: recibe comandos del dashboard (cambio de modelo) y envía eventos del sistema

### 3. Analytics (`modules/analytics/`)

**AlertsEngine** (`specialists/alerts_engine.py`):
- Analiza archivos CSV de detecciones cada 3 segundos
- Evalúa reglas de negocio (ej: aforo > 10 personas)
- Emite alertas instantáneas al dashboard vía WebSocket
- Funciona como sistema reactivo de eventos

### 4. Logs (`modules/logs/`)

**HardwareCtrl** (`specialists/hardware_ctrl.py`):
- Interfaz con GPIO de Jetson
- Control de LEDs indicadores:
  - LED_NET: Estado de conectividad
  - LED_PWR: Sistema encendido
  - LED_CAM: Cámara activa
- Monitoreo de botón de apagado seguro (ejecuta `sudo shutdown now`)

**SystemLogger** (`specialists/system_logger.py`):
- Estandariza formato de logs del sistema
- Envía eventos al dashboard en tiempo real

## 🔄 Flujo de Trabajo

```
[Cámara] → [Vision Manager]
              ↓
         [Processor YOLO] → Inferencia + Anotación
              ↓
         [CSV Output] → ./data/detecciones_log.csv
              ↓
    [Analytics Engine] → Lee CSV cada 3s
              ↓
    [Alerts] → WebSocket → [Dashboard]
              ↑
    [Communication Manager] ← Comandos del usuario
              ↓
    [Vision Manager] → Cambia procesador/modelo
```

## 🏃 Ejecución

Iniciar el sistema:

```bash
python main.py
```

El sistema mostrará el nombre del dispositivo e iniciará todos los módulos.

**Acceso local**:
- Video feed: `http://localhost:5000/video_feed`
- WebSocket: Conectar dashboard al puerto 5000

**Detener**: Presiona `Ctrl+C` para liberar recursos.

## 🔧 Dependencias Principales

```txt
opencv-python        # Captura y procesamiento de video
flask                # Servidor web
flask-socketio       # WebSockets bidireccionales
python-dotenv        # Gestión de variables de entorno
ultralytics          # Framework YOLO para detección
supervision          # Herramientas de visión artificial
pandas               # Análisis de datos CSV
Jetson.GPIO          # Control GPIO (solo en Jetson)
```

## 📊 Archivos de Datos

### `data/detecciones_log.csv`
Registro de detecciones con estructura:
- Timestamp
- Modelo utilizado
- Cantidad de objetos detectados
- Coordenadas de bounding boxes
- Nivel de confianza

## 🎯 Casos de Uso

1. **Monitoreo de aforo**: Alerta cuando se supera capacidad máxima
2. **Control de flujo**: Conteo de personas entrando/saliendo
3. **Análisis histórico**: Datos persistentes en CSV para reportes
4. **Integración física**: LEDs y botones para operación standalone

## 🔒 Consideraciones de Seguridad

- Comando `sudo shutdown now` requiere permisos sudoers configurados
- WebSocket expuesto: implementar autenticación en producción
- GPIO: verificar permisos de usuario para acceso a `/sys/class/gpio`

## 🐛 Troubleshooting

**Error: Camera not found**
```bash
# Verificar dispositivos disponibles
ls -la /dev/video*
# Ajustar CAMERA_INDEX en .env
```

**Error: GPIO permission denied** (Jetson)
```bash
sudo usermod -aG gpio $USER
# Reiniciar sesión
```

**Error: Module not found**
```bash
# Reinstalar dependencias
pip install --upgrade opencv-python flask flask-socketio python-dotenv ultralytics supervision pandas
```

**Performance lento**
- Reducir resolución de cámara en `vision/manager.py`
- Ajustar FPS de procesamiento
- Verificar que CUDA esté disponible: `torch.cuda.is_available()`

## 🚀 Próximas Mejoras

- [ ] Soporte para múltiples cámaras simultáneas
- [ ] API REST para configuración remota
- [ ] Base de datos SQL en lugar de CSV
- [ ] Autenticación JWT para WebSocket
- [ ] Docker containerization

## 📝 Licencia

[Especificar licencia]

## 👥 Contacto

**AI Cistem Labs**  
GitHub: [AI-Cistem-Labs](https://github.com/AI-Cistem-Labs)

---

**Desarrollado para**: NVIDIA Jetson Nano/NX  
**Versión de Python**: 3.8  
**Framework de detección**: YOLOv8 (Ultralytics)
