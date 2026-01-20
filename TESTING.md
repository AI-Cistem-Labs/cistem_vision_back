# 🧪 Guía de Pruebas - Cistem Vision Backend v1.1

## Pre-requisitos

1. **Instalar dependencias:**
```bash
pip install -r requirements.txt
```

2. **Configurar `.env`:**
```bash
cp .env.example .env
# Editar .env con tus valores
```

3. **Configurar `config/device.json`:**
```json
{
  "cameras": [
    {
      "cam_id": 1001,
      "rtsp_url": "rtsp://tu_camara_ip/stream"
      // ... resto de configuración
    }
  ]
}
```

---

## Nivel 1: Pruebas Unitarias

### Test de Importaciones
```bash
python test_imports.py
```

**Resultado esperado:**
```
✅ device_config importado correctamente
✅ get_available_processors importado correctamente
   Procesadores disponibles: [1, 2]
✅ system_logger importado correctamente
✅ alerts_engine importado correctamente
✅ Todas las importaciones funcionan correctamente!
```

### Test de Vision Manager
```bash
python test_vision.py
```

**Resultado esperado:**
```
✅ Procesador registrado: Contador de Personas (ID: 1)
✅ Procesador registrado: Detector de Intrusos (ID: 2)
✅ VisionManager creado
```

---

## Nivel 2: Prueba de Integración
```bash
python test_full_integration.py
```

**Resultado esperado:**
```
✅ Configuración: OK
✅ Procesadores: 2 registrados
✅ Sistema de logs: 5 registros
✅ Motor de alertas: 3 alertas
✅ Vision Manager: Inicializado
✅ Actualización de config: OK
🎉 TODAS LAS PRUEBAS PASARON EXITOSAMENTE
```

---

## Nivel 3: Servidor SocketIO

### Iniciar servidor
```bash
python app.py
```

**Consola debe mostrar:**
```
🎥 CISTEM VISION BACKEND v1.1
🚀 Servidor iniciando en puerto 5000
📱 Dispositivo: Jetson-Orin-Lab-01 (ID: 101)
📹 Cámaras configuradas: 1
🤖 Procesadores disponibles: 2
   - [1] Contador de Personas
   - [2] Detector de Intrusos
✅ Servidor listo en http://localhost:5000
```

### Health Check
```bash
curl http://localhost:5000/health
```

**Respuesta esperada:**
```json
{
  "status": "healthy",
  "device": {
    "device_id": 101,
    "label": "Jetson-Orin-Lab-01"
  },
  "processors_count": 2,
  "processors": [1, 2]
}
```

---

## Nivel 4: Cliente SocketIO

**Terminal 1** (Servidor):
```bash
python app.py
```

**Terminal 2** (Cliente):
```bash
python test_socketio_client.py
```

**Resultado esperado en Terminal 2:**
```
✅ Conectado al servidor
✅ Token obtenido: eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9...
📨 Respuesta de get_stations:
   {
     "data": [...]
   }
✅ PRUEBAS COMPLETADAS
📡 Escuchando eventos en tiempo real...
```

---

## Nivel 5: Postman Collection

1. **Importar colección:**
   - Abrir Postman
   - Import → Raw text
   - Pegar el JSON de la colección (del documento inicial)

2. **Configurar variables:**
   - `base_url`: `localhost:5000`
   - `token`: (se auto-completa después del login)

3. **Ejecutar flujo:**
   1. Authentication → Login
   2. Authentication → Get Profile
   3. Stations & Cameras → Get Stations
   4. Logs & Alerts → Get Camera Logs
   5. Camera Control → Update Camera Status
   6. Camera Control → Select Processor

---

## Nivel 6: Prueba con Cámara Real

### Con cámara IP
```json
// config/device.json
{
  "cameras": [
    {
      "rtsp_url": "rtsp://admin:password@192.168.1.100:554/stream1"
    }
  ]
}
```

### Con archivo de video (prueba sin cámara)
```json
{
  "cameras": [
    {
      "rtsp_url": "test_video.mp4"  // OpenCV acepta archivos locales
    }
  ]
}
```

### Con webcam
```json
{
  "cameras": [
    {
      "rtsp_url": "0"  // 0 = primera webcam
    }
  ]
}
```

**Ejecutar:**
```bash
# Terminal 1
python app.py

# Terminal 2
python test_socketio_client.py
```

**Verificar:**
- Logs en tiempo real (cámara iniciada, frames procesados)
- Alertas si el procesador detecta algo
- CSVs generados en `data/`

---

## Troubleshooting

### Error: "No module named 'cv2'"
```bash
pip install opencv-python
```

### Error: "RTSP connection failed"
- Verificar URL con VLC: `vlc rtsp://...`
- Verificar red (firewall, permisos)
- Probar con archivo de video local

### Error: "Token inválido"
- Copiar token completo del response de login
- Verificar que JWT_SECRET sea el mismo en .env

### Error: Procesadores no detectados
```bash
# Verificar que existen los archivos
ls modules/vision/processors/*_processor.py

# Probar carga manual
python -c "from modules.vision.processors import get_available_processors; print(get_available_processors())"
```

---

## Checklist de Piloto

- [ ] Todas las pruebas unitarias pasan
- [ ] Servidor arranca sin errores
- [ ] Health check responde OK
- [ ] Cliente SocketIO se conecta
- [ ] Login funciona y genera token
- [ ] get_stations retorna jerarquía completa
- [ ] Logs se generan automáticamente
- [ ] Alertas se envían en tiempo real
- [ ] Cámara se puede encender/apagar
- [ ] Procesador se puede cambiar
- [ ] Video se procesa (si hay cámara conectada)
- [ ] CSVs se generan en `data/`

---

## Próximos Pasos Post-Piloto

1. Conectar base de datos PostgreSQL
2. Implementar grabación de video
3. Dashboard de analytics
4. Notificaciones push
5. API REST complementaria