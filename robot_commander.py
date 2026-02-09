#!/usr/bin/env python3
"""
Servidor SocketIO (PC) que:
✅ RECIBE datos del robot (telemetry)
✅ RECIBE feedback de patrullaje (patrol)
✅ ENVÍA comandos de patrullaje al robot
✅ BROADCAST al frontend para UI en tiempo real
✅ UI HTML integrada en "/"
✅ INTEGRADO con station_controller para mostrar cámaras del robot
"""

import sys
import os
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from flask import Flask, request, jsonify
from flask_socketio import SocketIO, emit
from modules.robot.handlers import RobotDataHandler
import logging
from datetime import datetime, timezone

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

app = Flask(__name__)
app.config["SECRET_KEY"] = "cistem_robot_secret_2026"

socketio = SocketIO(
    app,
    cors_allowed_origins="*",
    async_mode="threading",
    ping_timeout=60,
    ping_interval=25
)

handler = RobotDataHandler()

# ⭐ NUEVO: Conectar handler con station_controller para que obtenga cámaras del robot
try:
    from controllers.station_controller import set_robot_handler
    set_robot_handler(handler)
    logger.info("✅ Handler del robot conectado con station_controller")
except Exception as e:
    logger.warning(f"⚠️ No se pudo conectar handler con station_controller: {e}")

# 🔧 MEJORADO: Diccionario para rastrear SIDs por device_id/location_id
# Formato: {(location_id, device_id): {"telemetry": sid, "patrol": sid, "main": sid}}
robot_connections = {}


def _get_robot_key(location_id: int, device_id: int):
    """Genera clave única para identificar un robot"""
    return (int(location_id), int(device_id))


def _register_connection(location_id: int, device_id: int, client_type: str, sid: str):
    """Registra una conexión de robot"""
    key = _get_robot_key(location_id, device_id)
    if key not in robot_connections:
        robot_connections[key] = {}
    robot_connections[key][client_type] = sid
    logger.info(f"📝 Registrado: Robot {key} - {client_type} -> SID {sid}")


def _unregister_connection(sid: str):
    """Elimina una conexión cuando se desconecta"""
    for key, connections in list(robot_connections.items()):
        for client_type, stored_sid in list(connections.items()):
            if stored_sid == sid:
                del connections[client_type]
                logger.info(f"🗑️ Desregistrado: Robot {key} - {client_type} (SID {sid})")
                if not connections:  # Si no quedan conexiones, eliminar el robot
                    del robot_connections[key]
                return key, client_type
    return None, None


def _get_robot_sid(location_id: int, device_id: int):
    """
    Obtiene el SID del robot para enviar comandos.
    Prioridad: patrol > main > telemetry
    """
    key = _get_robot_key(location_id, device_id)
    connections = robot_connections.get(key, {})
    
    # Intentar en orden de prioridad
    for client_type in ["patrol", "main", "telemetry"]:
        if client_type in connections:
            return connections[client_type], client_type
    
    return None, None


# ============================================================================
# SOCKETIO: CONEXIÓN
# ============================================================================
@socketio.on("connect")
def handle_connect(auth):
    sid = request.sid
    auth = auth or {}

    device_id = auth.get("device_id")
    location_id = auth.get("location_id")
    client_type = auth.get("client_type", "main")  # Default: "main"

    # Frontend/browsers conectan sin auth
    if device_id is None or location_id is None:
        logger.info(f"🌐 Frontend conectado (SID: {sid})")
        return

    # Registrar conexión del robot
    _register_connection(location_id, device_id, client_type, sid)
    
    logger.info("=" * 70)
    logger.info(f"🤖 ✅ ROBOT CONECTADO")
    logger.info(f"   Location ID: {location_id}")
    logger.info(f"   Device ID: {device_id}")
    logger.info(f"   Client Type: {client_type}")
    logger.info(f"   SID: {sid}")
    logger.info(f"   Conexiones activas: {robot_connections.get(_get_robot_key(location_id, device_id), {})}")
    logger.info("=" * 70)


@socketio.on("disconnect")
def handle_disconnect():
    sid = request.sid
    key, client_type = _unregister_connection(sid)
    
    if key:
        logger.warning(f"🤖 ⚠️ Robot desconectado: {key} - {client_type} (SID: {sid})")
    else:
        logger.warning(f"🌐 Cliente desconectado (SID: {sid})")


# ============================================================================
# SOCKETIO: EVENTOS DEL ROBOT (ENTRADA)
# ============================================================================
@socketio.on("camera_info")
def handle_camera_info(data):
    logger.info("📹 Recibido: camera_info")
    handler.handle_camera_info(data)
    # Broadcast al frontend
    emit("camera_info", data, broadcast=True)


@socketio.on("alert")
def handle_alert(data):
    logger.info("🚨 Recibido: alert")
    handler.handle_alert(data)
    # Broadcast al frontend
    emit("alert", data, broadcast=True)


@socketio.on("robot_info")
def handle_robot_info(data):
    logger.info("🔋 Recibido: robot_info")
    handler.handle_robot_info(data)
    # Broadcast al frontend
    emit("robot_info", data, broadcast=True)


@socketio.on("robot_state")
def handle_robot_state(data):
    logger.info("🤖 Recibido: robot_state")
    logger.info(f"   state: {data.get('state')}")
    handler.handle_robot_state(data)
    # Broadcast al frontend
    emit("robot_state", data, broadcast=True)


@socketio.on("patrol_feedback")
def handle_patrol_feedback(data):
    logger.info("📡 Recibido: patrol_feedback")
    logger.info(f"   state: {data.get('state')}")
    handler.handle_robot_state(data)
    # Broadcast al frontend
    emit("patrol_feedback", data, broadcast=True)


# ============================================================================
# 🔧 COMANDOS (SALIDA) -> Envío mejorado al robot
# ============================================================================
def send_command_to_robot(command: str, device_id: int = 1, location_id: int = 1):
    """
    Envía un comando al robot.
    Busca automáticamente la mejor conexión disponible.
    """
    valid_commands = ["go_home", "start_patrol", "pause_patrol", "resume_patrol", "stop_patrol"]
    if command not in valid_commands:
        return {"success": False, "error": f"Comando inválido. Válidos: {valid_commands}"}

    # Obtener SID del robot
    robot_sid, client_type = _get_robot_sid(location_id, device_id)
    
    if robot_sid is None:
        logger.error(f"❌ Robot no conectado: location_id={location_id}, device_id={device_id}")
        logger.error(f"   Conexiones actuales: {robot_connections}")
        return {
            "success": False, 
            "error": f"Robot no conectado (location_id={location_id}, device_id={device_id})"
        }

    command_data = {
        "location_id": int(location_id),
        "device_id": int(device_id),
        "label": "Robot Oficina",
        "command": command,
        "timestamp": datetime.now(timezone.utc).isoformat()
    }

    try:
        # Enviar comando al robot específico
        socketio.emit("patrol_command", command_data, to=robot_sid)
        
        logger.info("=" * 70)
        logger.info(f"✅ COMANDO ENVIADO AL ROBOT")
        logger.info(f"   Comando: {command}")
        logger.info(f"   Robot: location_id={location_id}, device_id={device_id}")
        logger.info(f"   Client Type: {client_type}")
        logger.info(f"   SID: {robot_sid}")
        logger.info("=" * 70)
        
        # También broadcast para que el frontend lo vea
        emit("command_sent", command_data, broadcast=True)
        
        return {
            "success": True, 
            "message": f"Comando enviado via {client_type}",
            "command_data": command_data,
            "sent_to_sid": robot_sid,
            "client_type": client_type
        }
    except Exception as e:
        logger.error(f"❌ Error al enviar comando: {e}")
        return {"success": False, "error": str(e)}


# ============================================================================
# HTTP API
# ============================================================================
@app.route("/robot/command", methods=["POST"])
def http_send_command():
    data = request.get_json()
    if not data or "command" not in data:
        return jsonify({"success": False, "error": 'Falta campo "command"'}), 400

    command = data["command"]
    device_id = data.get("device_id", 1)
    location_id = data.get("location_id", 1)

    result = send_command_to_robot(command, device_id, location_id)
    return jsonify(result), (200 if result.get("success") else 400)


@app.route("/robot/status", methods=["GET"])
def get_robot_status():
    device_id = request.args.get("device_id", 1, type=int)
    location_id = request.args.get("location_id", 1, type=int)

    key = _get_robot_key(location_id, device_id)
    connections = robot_connections.get(key, {})
    
    telemetry_connected = "telemetry" in connections
    patrol_connected = "patrol" in connections
    main_connected = "main" in connections
    any_connected = bool(connections)

    status = handler.get_robot_status(device_id)
    state = handler.get_robot_state(device_id)
    cameras = handler.get_robot_cameras()

    return jsonify({
        "connected": any_connected,
        "telemetry_connected": telemetry_connected,
        "patrol_connected": patrol_connected,
        "main_connected": main_connected,
        "active_connections": list(connections.keys()),
        "device_id": device_id,
        "location_id": location_id,
        "status": status,
        "state": state,
        "cameras": cameras
    })


@app.route("/debug/connections", methods=["GET"])
def debug_connections():
    """Endpoint de debug para ver todas las conexiones activas"""
    debug_info = {}
    for key, connections in robot_connections.items():
        location_id, device_id = key
        debug_info[f"robot_{location_id}_{device_id}"] = connections
    
    return jsonify({
        "total_robots": len(robot_connections),
        "connections": debug_info
    })


@app.route("/debug/sids", methods=["GET"])
def debug_sids():
    """Mantener compatibilidad con endpoint anterior"""
    return debug_connections()


# ============================================================================
# UI HTML (integrada) - ACTUALIZADA
# ============================================================================
@app.route("/")
def index():
    return r'''
<!DOCTYPE html>
<html lang="es-MX">
<head>
  <meta charset="utf-8"/>
  <meta name="viewport" content="width=device-width,initial-scale=1"/>
  <title>Robot Control Center</title>
  <script src="https://cdn.socket.io/4.5.4/socket.io.min.js"></script>
  <style>
    :root{
      --bg1:#0b1020;
      --bg2:#141b36;
      --card:#0f1630;
      --border:rgba(255,255,255,0.12);
      --muted:rgba(255,255,255,0.7);
      --text:#ffffff;
      --good:#22c55e;
      --warn:#f59e0b;
      --bad:#ef4444;
      --info:#38bdf8;
      --accent:#a78bfa;
    }
    *{box-sizing:border-box}
    body{
      margin:0;
      font-family: ui-sans-serif, system-ui, -apple-system, "Segoe UI", Arial;
      color:var(--text);
      background: radial-gradient(1200px 700px at 20% 10%, #1f2a5a 0%, transparent 60%),
                  radial-gradient(1000px 600px at 80% 0%, #3b1a64 0%, transparent 55%),
                  linear-gradient(160deg, var(--bg1), var(--bg2));
      min-height:100vh;
      padding:24px;
    }
    .wrap{max-width:1100px;margin:0 auto}
    .topbar{
      display:flex; gap:16px; align-items:stretch; flex-wrap:wrap;
      margin-bottom:18px;
    }
    .card{
      background: rgba(15,22,48,0.72);
      border:1px solid var(--border);
      border-radius:16px;
      box-shadow: 0 10px 30px rgba(0,0,0,0.35);
      backdrop-filter: blur(10px);
      padding:18px;
    }
    .card h1{margin:0;font-size:22px;letter-spacing:0.2px}
    .sub{margin-top:6px;color:var(--muted);font-size:13px}
    .badge{
      display:inline-flex; align-items:center; gap:8px;
      padding:6px 10px; border-radius:999px;
      font-weight:700; font-size:12px;
      border:1px solid var(--border);
      background: rgba(255,255,255,0.06);
    }
    .dot{width:10px;height:10px;border-radius:99px;background:var(--bad)}
    .grid{
      display:grid;
      grid-template-columns: 1.1fr 0.9fr;
      gap:16px;
    }
    @media (max-width: 900px){
      .grid{grid-template-columns:1fr}
    }
    .kpis{
      display:grid;
      grid-template-columns: repeat(4, 1fr);
      gap:12px;
      margin-top:12px;
    }
    @media (max-width: 900px){
      .kpis{grid-template-columns: repeat(2, 1fr)}
    }
    .kpi{
      padding:14px;
      border-radius:14px;
      border:1px solid var(--border);
      background: rgba(255,255,255,0.06);
      min-height:82px;
    }
    .kpi .label{font-size:12px;color:var(--muted);font-weight:700;letter-spacing:0.6px;text-transform:uppercase}
    .kpi .val{margin-top:8px;font-size:26px;font-weight:800}
    .kpi .hint{margin-top:6px;font-size:12px;color:var(--muted)}
    .status-pill{
      display:flex; justify-content:center; align-items:center;
      padding:14px 16px;
      border-radius:14px;
      font-size:18px;
      font-weight:900;
      border:1px solid var(--border);
      background: rgba(255,255,255,0.06);
      margin-top:10px;
    }
    .pill-in_home{background: rgba(34,197,94,0.18); border-color: rgba(34,197,94,0.35)}
    .pill-to_home{background: rgba(56,189,248,0.18); border-color: rgba(56,189,248,0.35)}
    .pill-is_patrolling{background: rgba(167,139,250,0.18); border-color: rgba(167,139,250,0.35)}
    .pill-paused{background: rgba(245,158,11,0.18); border-color: rgba(245,158,11,0.35)}
    .pill-stopped{background: rgba(239,68,68,0.18); border-color: rgba(239,68,68,0.35)}
    .pill-unknown{background: rgba(255,255,255,0.06)}
    .cmds{
      display:grid;
      grid-template-columns: repeat(3, 1fr);
      gap:10px;
      margin-top:12px;
    }
    @media (max-width: 900px){
      .cmds{grid-template-columns:1fr}
    }
    button{
      border:1px solid var(--border);
      background: rgba(255,255,255,0.08);
      color:var(--text);
      padding:12px 14px;
      border-radius:14px;
      cursor:pointer;
      font-weight:800;
      font-size:14px;
      transition: transform 0.06s ease, background 0.2s ease, opacity 0.2s ease;
    }
    button:hover{background: rgba(255,255,255,0.12)}
    button:active{transform: translateY(1px)}
    button:disabled{opacity:0.5; cursor:not-allowed}
    .btn-good{background: rgba(34,197,94,0.16)}
    .btn-warn{background: rgba(245,158,11,0.16)}
    .btn-bad{background: rgba(239,68,68,0.16)}
    .btn-info{background: rgba(56,189,248,0.16)}
    .log{
      margin-top:12px;
      font-family: ui-monospace, SFMono-Regular, Menlo, monospace;
      font-size:12px;
      color:rgba(255,255,255,0.85);
      border:1px solid var(--border);
      background: rgba(0,0,0,0.25);
      border-radius:14px;
      padding:12px;
      height:160px;
      overflow:auto;
      white-space: pre-wrap;
    }
    .row{display:flex; gap:10px; flex-wrap:wrap; align-items:center}
    .small{font-size:12px;color:var(--muted)}
    a{color:var(--info)}
  </style>
</head>
<body>
  <div class="wrap">
    <div class="topbar">
      <div class="card" style="flex:1">
        <h1>🤖 Robot Control Center</h1>
        <div class="sub">Control bidireccional completo (Socket.IO + HTTP) - CORREGIDO</div>
        <div class="row" style="margin-top:10px">
          <span class="badge" id="wsBadge"><span class="dot" id="wsDot"></span><span id="wsText">Socket: desconectado</span></span>
          <span class="badge" id="teleBadge">telemetry: --</span>
          <span class="badge" id="patrolBadge">patrol: --</span>
          <span class="badge" id="mainBadge">main: --</span>
          <span class="badge">device_id: <span id="deviceId">1</span> · location_id: <span id="locationId">1</span></span>
        </div>
      </div>
    </div>

    <div class="grid">
      <div class="card">
        <h2 style="margin:0;font-size:18px">📊 Telemetría</h2>
        <div class="kpis">
          <div class="kpi">
            <div class="label">Batería</div>
            <div class="val" id="batteryVal">--%</div>
            <div class="hint" id="batteryHint">status: --</div>
          </div>
          <div class="kpi">
            <div class="label">Temp. Máx</div>
            <div class="val" id="tempMaxVal">--°C</div>
            <div class="hint">motores</div>
          </div>
          <div class="kpi">
            <div class="label">Temp. Prom</div>
            <div class="val" id="tempAvgVal">--°C</div>
            <div class="hint">motores</div>
          </div>
          <div class="kpi">
            <div class="label">Warning</div>
            <div class="val" id="motWarnVal">--</div>
            <div class="hint">motores calientes</div>
          </div>
        </div>
        <div class="small" style="margin-top:10px">Última actualización: <span id="lastTelemetry">--</span></div>
      </div>

      <div class="card">
        <h2 style="margin:0;font-size:18px">🚨 Estado de Patrullaje</h2>
        <div class="status-pill pill-unknown" id="statePill">❓ UNKNOWN</div>
        <div class="small" style="margin-top:10px">Última actualización: <span id="lastState">--</span></div>

        <h2 style="margin:14px 0 0;font-size:18px">🎮 Comandos</h2>
        <div class="cmds">
          <button class="btn-good" onclick="sendCommand('start_patrol')">▶️ start_patrol</button>
          <button class="btn-warn" onclick="sendCommand('pause_patrol')">⏸️ pause_patrol</button>
          <button class="btn-info" onclick="sendCommand('resume_patrol')">▶️ resume_patrol</button>
          <button class="btn-bad" onclick="sendCommand('stop_patrol')">⏹️ stop_patrol</button>
          <button class="btn-info" onclick="sendCommand('go_home')">🏠 go_home</button>
          <button onclick="refreshStatus()">🔄 refresh</button>
        </div>

        <div class="log" id="logBox"></div>
      </div>
    </div>

    <div class="small" style="margin-top:14px">
      Debug: <a href="/debug/connections" target="_blank">/debug/connections</a> ·
      API: <a href="/robot/status" target="_blank">/robot/status</a>
    </div>
  </div>

<script>
  const DEFAULT_DEVICE_ID = 1;
  const DEFAULT_LOCATION_ID = 1;

  const wsBadge = document.getElementById('wsBadge');
  const wsDot = document.getElementById('wsDot');
  const wsText = document.getElementById('wsText');

  const teleBadge = document.getElementById('teleBadge');
  const patrolBadge = document.getElementById('patrolBadge');
  const mainBadge = document.getElementById('mainBadge');

  const batteryVal = document.getElementById('batteryVal');
  const batteryHint = document.getElementById('batteryHint');
  const tempMaxVal = document.getElementById('tempMaxVal');
  const tempAvgVal = document.getElementById('tempAvgVal');
  const motWarnVal = document.getElementById('motWarnVal');

  const lastTelemetry = document.getElementById('lastTelemetry');
  const statePill = document.getElementById('statePill');
  const lastState = document.getElementById('lastState');

  const logBox = document.getElementById('logBox');

  function log(msg){
    const t = new Date().toLocaleTimeString('es-MX', {hour:'2-digit', minute:'2-digit', second:'2-digit'});
    logBox.textContent = `[${t}] ${msg}\n` + logBox.textContent;
  }

  function setWS(connected){
    wsDot.style.background = connected ? 'var(--good)' : 'var(--bad)';
    wsText.textContent = connected ? 'Socket: conectado' : 'Socket: desconectado';
  }

  function setState(state){
    const map = {
      in_home: '🏠 IN HOME',
      to_home: '🚶 TO HOME',
      is_patrolling: '🚨 PATROLLING',
      paused: '⏸️ PAUSED',
      stopped: '⏹️ STOPPED'
    };
    const clsMap = {
      in_home: 'pill-in_home',
      to_home: 'pill-to_home',
      is_patrolling: 'pill-is_patrolling',
      paused: 'pill-paused',
      stopped: 'pill-stopped'
    };

    statePill.className = 'status-pill ' + (clsMap[state] || 'pill-unknown');
    statePill.textContent = map[state] || ('❓ ' + (state || 'unknown').toUpperCase());
    lastState.textContent = new Date().toLocaleTimeString('es-MX', {hour:'2-digit', minute:'2-digit', second:'2-digit'});
  }

  function setTelemetry(data){
    const bat = data.battery || {};
    const mot = data.motors || {};
    if (typeof bat.soc !== 'undefined'){
      batteryVal.textContent = `${bat.soc}%`;
      batteryHint.textContent = `status: ${bat.status || '--'}`;

      let col = 'var(--good)';
      if (bat.soc < 20) col = 'var(--bad)';
      else if (bat.soc < 50) col = 'var(--warn)';
      batteryVal.style.color = col;
    }

    if (typeof mot.max_temp !== 'undefined'){
      tempMaxVal.textContent = `${mot.max_temp}°C`;
      let col = 'var(--good)';
      if (mot.max_temp > 60) col = 'var(--bad)';
      else if (mot.max_temp > 50) col = 'var(--warn)';
      tempMaxVal.style.color = col;
    }

    if (typeof mot.avg_temp !== 'undefined'){
      tempAvgVal.textContent = `${mot.avg_temp}°C`;
    }

    if (typeof mot.motors_warning !== 'undefined'){
      motWarnVal.textContent = `${mot.motors_warning}/${mot.total_motors || '--'}`;
      motWarnVal.style.color = (mot.motors_warning > 0) ? 'var(--warn)' : 'var(--good)';
    }

    lastTelemetry.textContent = new Date().toLocaleTimeString('es-MX', {hour:'2-digit', minute:'2-digit', second:'2-digit'});
  }

  async function sendCommand(cmd){
    log(`➡️ Enviando comando: ${cmd} ...`);
    try{
      const r = await fetch('/robot/command', {
        method:'POST',
        headers:{'Content-Type':'application/json'},
        body: JSON.stringify({
          command: cmd,
          device_id: DEFAULT_DEVICE_ID,
          location_id: DEFAULT_LOCATION_ID
        })
      });
      const j = await r.json();
      if (j.success){
        log(`✅ OK: ${cmd} (via ${j.client_type || 'unknown'})`);
      }else{
        log(`❌ Error: ${j.error || 'desconocido'}`);
      }
    }catch(e){
      log(`❌ Error fetch: ${e}`);
    }
  }

  async function refreshStatus(){
    try{
      const r = await fetch(`/robot/status?device_id=${DEFAULT_DEVICE_ID}&location_id=${DEFAULT_LOCATION_ID}`);
      const j = await r.json();

      teleBadge.textContent = `telemetry: ${j.telemetry_connected ? '✅' : '❌'}`;
      patrolBadge.textContent = `patrol: ${j.patrol_connected ? '✅' : '❌'}`;
      mainBadge.textContent = `main: ${j.main_connected ? '✅' : '❌'}`;

      if (j.status) setTelemetry(j.status);
      if (j.state) setState(j.state);

      const conns = j.active_connections ? j.active_connections.join(', ') : 'ninguna';
      log(`🔄 Status: ${conns} | state=${j.state || 'n/a'}`);
    }catch(e){
      log(`❌ Poll error: ${e}`);
    }
  }

  // SocketIO frontend
  const socket = io();

  socket.on('connect', () => { 
    setWS(true); 
    log('✅ Socket frontend conectado'); 
    refreshStatus(); 
  });
  
  socket.on('disconnect', () => { 
    setWS(false); 
    log('⚠️ Socket frontend desconectado'); 
  });

  socket.on('robot_info', (data) => {
    setTelemetry(data);
  });

  socket.on('patrol_feedback', (data) => {
    if (data && data.state) setState(data.state);
  });

  socket.on('robot_state', (data) => {
    if (data && data.state) setState(data.state);
  });

  socket.on('command_sent', (data) => {
    log(`📤 Comando enviado al robot: ${data.command}`);
  });

  // Polling de respaldo
  setInterval(refreshStatus, 10000);
  refreshStatus();
</script>
</body>
</html>
    '''


# ============================================================================
# MAIN
# ============================================================================
if __name__ == "__main__":
    print("\n" + "=" * 70)
    print("🎯 ROBOT COMMANDER - VERSIÓN CORREGIDA")
    print("=" * 70)
    print("🌐 UI: http://0.0.0.0:5000/")
    print("📡 API: POST /robot/command | GET /robot/status | GET /debug/connections")
    print("✅ Comunicación bidireccional completa")
    print("✅ Soporte para múltiples tipos de cliente (telemetry, patrol, main)")
    print("=" * 70)
    print("\n⏳ Esperando conexión del robot...\n")
    socketio.run(app, host="0.0.0.0", port=5000, debug=False, allow_unsafe_werkzeug=True)