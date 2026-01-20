# 🎥 Cistem Vision Backend v1.1

Sistema de vigilancia inteligente con procesamiento de IA en tiempo real mediante WebSockets (SocketIO).

## 🏗️ Arquitectura del Sistema
```
Frontend (React/Vue) 
    ↕️ WebSocket (SocketIO)
Backend (Flask-SocketIO) 
    ↕️ RTSP
Cámaras IP → Jetson Orin/Nano (Procesamiento IA)
```

### Flujo de Datos
1. **Dispositivos embebidos** (Jetson Orin/Nano) capturan video RTSP de cámaras IP
2. **Procesadores de IA** analizan frames en modo headless
3. **Backend** envía al frontend:
   - Video procesado (bajo demanda)
   - Logs de autodiagnóstico (INFO/WARNING/ERROR)
   - Alertas de seguridad (CRITICAL/PRECAUCION)
   - Datos analíticos en tiempo real

---

## 🚀 Instalación Rápida

### 1. Clonar repositorio
```bash
git clone https://github.com/AI-Cistem-Labs/cistem_vision_back.git
cd cistem_vision_back
git checkout feature/v1.1
```

### 2. Crear entorno virtual
```bash
python3 -m venv .venv
source .venv/bin/activate  # Linux/Mac
# .venv\Scripts\activate   # Windows
```

### 3. Instalar dependencias
```bash
pip install -r requirements.txt
```

### 4. Configurar variables de entorno
```bash
cp .env.example .env
```

Editar `.env`:
```env
JWT_SECRET=tu_clave_secreta_segura
PORT=5000
DEBUG=True
```

### 5. Configurar dispositivo
Editar `config/device.json` con tus cámaras:
```json
{
  "device_id": 101,
  "device_label": "Jetson-Orin-Lab-01",
  "device_type": "jetson_orin",
  "location": {
    "location_id": 1,
    "label": "Laboratorio Principal",
    "description": "Centro de vigilancia - Zona A",
    "mapImageUrl": "https://example.com/map.png",
    "isActive": true
  },
  "cameras": [
    {
      "cam_id": 1001,
      "label": "Cámara Entrada",
      "rtsp_url": "rtsp://admin:password@192.168.1.100:554/stream1",
      "position": [10, 20],
      "status": false,
      "available_processors": [1, 2, 3],
      "active_processor": null
    }
  ]
}
```

### 6. Ejecutar servidor
```bash
python app.py
```

El servidor estará disponible en: `ws://localhost:5000`

---

## 📡 API WebSocket (SocketIO)

### Autenticación

#### `login` - Iniciar sesión
**Request:**
```json
{
  "email": "admin@cistemlabs.ai",
  "password": "secure_password"
}
```

**Response:**
```json
{
  "success": true,
  "token": "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9...",
  "datetime": "2026-01-20T10:30:00.000Z"
}
```

#### `get_profile` - Obtener perfil
**Request:**
```json
{
  "token": "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9..."
}
```

**Response:**
```json
{
  "id_profile": 1,
  "name": "Juan Pérez",
  "email": "admin@cistemlabs.ai",
  "role": "Administrador",
  "photo_url": "https://example.com/photo.jpg",
  "datetime": "2026-01-20T10:30:00.000Z"
}
```

---

### Estaciones y Cámaras

#### `get_stations` - Obtener jerarquía completa
**Request:**
```json
{
  "token": "your_jwt_token"
}
```

**Response:**
```json
{
  "data": [
    {
      "location_id": 1,
      "label": "Laboratorio Principal",
      "description": "Centro de vigilancia - Zona A",
      "mapImageUrl": "https://example.com/map.png",
      "isActive": true,
      "devices": [
        {
          "device_id": 101,
          "label": "Jetson-Orin-Lab-01",
          "cameras": [
            {
              "cam_id": 1001,
              "label": "Cámara Entrada",
              "status": true,
              "position": [10, 20],
              "processors": [
                {
                  "processor_id": 1,
                  "label": "Detección de Intrusos",
                  "description": "Monitorea áreas restringidas",
                  "status": true
                }
              ],
              "logs": [
                {
                  "log_id": 1,
                  "datetime": "2026-01-20T10:25:00.000Z",
                  "msg": "Cámara iniciada correctamente",
                  "label": "INFO"
                }
              ]
            }
          ]
        }
      ]
    }
  ],
  "datetime": "2026-01-20T10:30:00.000Z"
}
```

---

### Control de Cámaras

#### `update_camera_status` - Encender/Apagar cámara
```json
{
  "token": "your_jwt_token",
  "location_id": 1,
  "device_id": 101,
  "cam_id": 1001,
  "active": true
}
```

#### `update_camera_position` - Actualizar posición en mapa
```json
{
  "token": "your_jwt_token",
  "location_id": 1,
  "device_id": 101,
  "cam_id": 1001,
  "position": [25, 40]
}
```

#### `select_processor` - Cambiar procesador de IA
```json
{
  "token": "your_jwt_token",
  "location_id": 1,
  "device_id": 101,
  "cam_id": 1001,
  "processor_id": 2
}
```

---

### Logs y Alertas

#### `get_logs` - Obtener logs de autodiagnóstico
```json
{
  "token": "your_jwt_token",
  "location_id": 1,
  "device_id": 101,
  "cam_id": 1001
}
```

#### `get_alerts` - Obtener alertas de seguridad
```json
{
  "token": "your_jwt_token",
  "location_id": 1,
  "device_id": 101,
  "cam_id": 1001
}
```

#### `mark_alert_read` - Marcar alerta como leída
```json
{
  "token": "your_jwt_token",
  "alert_id": 1
}
```

#### `mark_all_alerts_read` - Marcar todas como leídas
```json
{
  "token": "your_jwt_token"
}
```

---

### Streaming de Video

#### `get_camera_feed` - Iniciar streaming
```json
{
  "token": "your_jwt_token",
  "location_id": 1,
  "device_id": 101,
  "cam_id": 1001
}
```

**Eventos recibidos:**
```json
{
  "cam_id": 1001,
  "frame": "base64_encoded_jpeg_frame",
  "time_active": "00:05:32",
  "frame_number": 9876
}
```

#### `stop_camera_feed` - Detener streaming
```json
{
  "token": "your_jwt_token",
  "cam_id": 1001
}
```

---

## 🧩 Estructura del Proyecto
```
cistem_vision_back/
│
├── 📄 app.py                          # Servidor principal SocketIO
├── 📄 extensions.py                   # Instancia compartida de SocketIO
├── 📄 requirements.txt                # Dependencias
├── 📄 .env                            # Variables de entorno (NO subir a Git)
│
├── 📂 config/                         # Configuración local del dispositivo
│   ├── device.json                    # Info del dispositivo y cámaras
│   └── config_manager.py              # Gestor de configuración
│
├── 📂 controllers/                    # Controladores SocketIO
│   ├── auth_controller.py             # Login, perfil, logout
│   ├── station_controller.py          # Jerarquía de estaciones
│   ├── logs_controller.py             # Logs de autodiagnóstico
│   ├── alerts_controller.py           # Alertas de seguridad
│   ├── camera_controller.py           # Control de cámaras
│   └── video_controller.py            # Streaming de video
│
├── 📂 modules/
│   ├── 📂 vision/                     # Sistema de visión artificial
│   │   ├── manager.py                 # VisionManager (gestión de cámaras)
│   │   ├── 📂 processors/             # Procesadores de IA dinámicos
│   │   │   ├── base_processor.py      # Clase base abstracta
│   │   │   ├── person_counter.py      # Ejemplo: Contador de personas
│   │   │   └── intrusion_detector.py  # Ejemplo: Detector de intrusos
│   │   └── 📂 specialists/
│   │       ├── frame_grabber.py       # Captura frames RTSP
│   │       ├── frame_processor.py     # Procesa frames con IA
│   │       └── video_streamer.py      # Envía frames al frontend
│   │
│   └── 📂 analytics/                  # Sistema de análisis
│       ├── manager.py                 # AnalyticsManager
│       └── 📂 specialists/
│           ├── system_logger.py       # Logs automáticos (Singleton)
│           └── alerts_engine.py       # Motor de alertas (Singleton)
│
└── 📂 data/                           # Datos generados (Git ignore)
    └── *.csv                          # CSVs de procesadores
```

---

## 🤖 Crear Procesadores Personalizados

### 1. Crear archivo en `modules/vision/processors/`
```python
# modules/vision/processors/mi_procesador.py
from .base_processor import BaseProcessor
import cv2
import csv
from datetime import datetime

class MiProcesador(BaseProcessor):
    PROCESSOR_ID = 4
    PROCESSOR_LABEL = "Mi Procesador Custom"
    PROCESSOR_DESCRIPTION = "Descripción de lo que hace"
    
    def __init__(self, cam_id):
        super().__init__(cam_id)
        self.csv_file = f"data/mi_procesador_{cam_id}_{datetime.now().strftime('%Y-%m-%d')}.csv"
        self._init_csv()
    
    def _init_csv(self):
        with open(self.csv_file, 'w', newline='') as f:
            writer = csv.writer(f)
            writer.writerow(['timestamp', 'campo1', 'campo2'])
    
    def process_frame(self, frame):
        # Tu lógica de procesamiento aquí
        processed_frame = frame.copy()
        
        # Ejemplo: dibujar texto
        cv2.putText(processed_frame, "Mi Procesador", (10, 30),
                    cv2.FONT_HERSHEY_SIMPLEX, 1, (0, 255, 0), 2)
        
        # Guardar datos en CSV
        self._save_to_csv([datetime.now().isoformat(), "valor1", "valor2"])
        
        # Generar alerta si es necesario
        # self.generate_alert("Evento detectado", "CRITICAL")
        
        return processed_frame
    
    def _save_to_csv(self, row):
        with open(self.csv_file, 'a', newline='') as f:
            writer = csv.writer(f)
            writer.writerow(row)
```

### 2. El procesador se registra automáticamente
No necesitas modificar nada más. El sistema lo detecta automáticamente.

### 3. Agregar a `device.json`
```json
"available_processors": [1, 2, 3, 4]
```

---

## 📊 Sistema de Logs y Alertas

### Logs de Autodiagnóstico
```python
from modules.analytics.specialists.system_logger import system_logger

# Predefinidos
system_logger.camera_started(cam_id)
system_logger.rtsp_connection_failed(cam_id)
system_logger.processor_changed(cam_id, "Nuevo Procesador")

# Custom
system_logger.log(cam_id, "Mensaje personalizado", "WARNING")
```

### Alertas Inteligentes
```python
from modules.analytics.specialists.alerts_engine import alerts_engine

# Predefinidas
alerts_engine.intrusion_detected(cam_id, "Sector A3")
alerts_engine.crowd_detected(cam_id, 50)

# Custom
alerts_engine.create_alert(
    cam_id,
    "Evento personalizado detectado",
    level="CRITICAL",
    context={"extra": "data"}
)
```

---

## 🧪 Testing

### Probar importaciones
```bash
python test_imports.py
```

### Probar con Postman
Importar colección desde: `postman_collection.json`

---

## 🔧 Configuración Avanzada

### Cambiar puerto
```bash
# .env
PORT=8080
```

### Habilitar modo debug
```bash
# .env
DEBUG=True
```

### Múltiples cámaras
Agregar en `config/device.json`:
```json
"cameras": [
  {"cam_id": 1001, "label": "Cámara 1", ...},
  {"cam_id": 1002, "label": "Cámara 2", ...},
  {"cam_id": 1003, "label": "Cámara 3", ...}
]
```

---

## 🐛 Troubleshooting

### Error: "Token inválido o expirado"
- Verificar que el token se está enviando en el campo `token` del JSON
- Los tokens expiran en 24 horas

### Error: Importación de módulos
```bash
# Asegurar que existen todos los __init__.py
touch config/__init__.py
touch modules/__init__.py
touch modules/vision/__init__.py
touch modules/analytics/__init__.py
```

### Error: RTSP no conecta
- Verificar URL RTSP en `device.json`
- Probar con VLC: `vlc rtsp://admin:pass@192.168.1.100:554/stream1`

---

## 📚 Stack Tecnológico

- **Backend**: Flask, Flask-SocketIO
- **WebSocket**: SocketIO
- **Autenticación**: JWT
- **Visión Artificial**: OpenCV, YOLOv8 (opcional)
- **Procesamiento**: NumPy, CSV
- **Hardware**: Jetson Orin/Nano, Raspberry Pi

---

## 👥 Contribuir

1. Fork el repositorio
2. Crear rama feature: `git checkout -b feature/nueva-funcionalidad`
3. Commit cambios: `git commit -m 'Agregar nueva funcionalidad'`
4. Push: `git push origin feature/nueva-funcionalidad`
5. Abrir Pull Request

---

## 📄 Licencia

Proyecto privado - Cistem Labs © 2025

---

## 📞 Contacto

- **Email**: support@cistemlabs.ai
- **GitHub**: https://github.com/AI-Cistem-Labs

---

## 🗺️ Roadmap

- [x] Sistema de autenticación JWT
- [x] Gestión de estaciones y cámaras
- [x] Logs de autodiagnóstico
- [x] Motor de alertas inteligente
- [x] Streaming de video procesado
- [x] Procesadores dinámicos
- [ ] Base de datos persistente (PostgreSQL)
- [ ] Grabación de video
- [ ] Dashboard de analytics
- [ ] Notificaciones push
- [ ] API REST complementaria