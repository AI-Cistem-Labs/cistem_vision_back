# modules/robot/evidence_saver.py
"""
Módulo SIMPLE para guardar evidencias de alertas del robot
"""
import os
import base64
import logging
from datetime import datetime
from pathlib import Path
from dotenv import load_dotenv

# Cargar variables de entorno
load_dotenv()

logger = logging.getLogger(__name__)


def save_evidence_from_base64(
        base64_data: str,
        alert_id: int,
        device_id: int,
        base_path: str = "static/evidence"
) -> dict:
    """
    Guarda una imagen desde base64 al disco

    Args:
        base64_data: String completo de la data URL (data:image/jpeg;base64,...)
        alert_id: ID de la alerta
        device_id: ID del dispositivo
        base_path: Ruta base donde guardar

    Returns:
        dict con 'url' y 'local_path' o None si falla
    """
    try:
        # 1. Verificar que sea una data URL de imagen
        if not base64_data.startswith('data:image'):
            logger.warning(f"⚠️ No es una data URL de imagen, se ignora")
            return None

        # 2. Extraer la parte base64
        if 'base64,' not in base64_data:
            logger.error("❌ No se encontró 'base64,' en la data URL")
            return None

        base64_str = base64_data.split('base64,')[1]

        # 3. Decodificar base64
        image_bytes = base64.b64decode(base64_str)
        logger.debug(f"📦 Decodificado: {len(image_bytes)} bytes")

        # 4. Generar nombre único de archivo
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S_%f")
        filename = f"alert_{alert_id}_dev_{device_id}_{timestamp}.jpg"

        # 5. Crear ruta completa
        alerts_dir = Path(base_path) / "alerts"
        alerts_dir.mkdir(parents=True, exist_ok=True)

        file_path = alerts_dir / filename

        # 6. Guardar archivo
        with open(file_path, 'wb') as f:
            f.write(image_bytes)

        logger.info(f"✅ Imagen guardada: {filename} ({len(image_bytes)} bytes)")

        # 7. Obtener Base URL para Retornar URLs ABSOLUTAS
        # Prioridad: TAILSCALE_IP > HOSTNAME > localhost
        server_ip = os.getenv("TAILSCALE_IP", "localhost")
        server_port = os.getenv("SERVER_PORT", "5000")
        base_url = f"http://{server_ip}:{server_port}"

        return {
            'type': 'image',
            'url': f"{base_url}/static/evidence/alerts/{filename}",
            'thumbnail_url': None,  # Por ahora sin miniatura
            'local_path': str(file_path),
            'size_bytes': len(image_bytes)
        }

    except Exception as e:
        logger.error(f"❌ Error guardando evidencia: {e}")
        return None


def delete_evidence_file(file_path: str) -> bool:
    """
    Elimina un archivo de evidencia

    Args:
        file_path: Ruta completa del archivo

    Returns:
        True si se eliminó correctamente
    """
    try:
        path = Path(file_path)
        if path.exists():
            path.unlink()
            logger.info(f"🗑️ Archivo eliminado: {path.name}")
            return True
        else:
            logger.warning(f"⚠️ Archivo no existe: {file_path}")
            return False
    except Exception as e:
        logger.error(f"❌ Error eliminando archivo: {e}")
        return False