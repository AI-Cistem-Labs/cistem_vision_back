# modules/vision/video_stream_optimizer.py
"""
Optimizador de streaming de video para Orin Nano 8GB
Limita streams simultáneos y reduce uso de memoria
"""
import cv2
import numpy as np
from collections import deque
import time
import logging

logger = logging.getLogger(__name__)


class VideoStreamOptimizer:
    """
    Optimiza transmisión de video para reducir uso de memoria

    Límites para Orin Nano 8GB:
    - Máximo 4 streams simultáneos
    - Compresión JPEG adaptativa
    - Reducción automática de resolución
    """

    def __init__(self, max_concurrent_streams=4):
        """
        Args:
            max_concurrent_streams: Máximo de streams simultáneos (4 para Orin Nano 8GB)
        """
        self.max_concurrent_streams = max_concurrent_streams
        self.active_streams = {}  # {cam_id: {'client_id': sid, 'last_access': time}}

        logger.info(f"📹 VideoStreamOptimizer inicializado (max streams: {max_concurrent_streams})")

    def can_start_stream(self, cam_id: int, client_id: str) -> bool:
        """
        Verifica si se puede iniciar un nuevo stream

        Args:
            cam_id: ID de la cámara
            client_id: ID del cliente (SocketIO SID)

        Returns:
            bool: True si se puede iniciar, False si límite alcanzado
        """
        # Si ya está activo para este cliente, actualizar timestamp
        if cam_id in self.active_streams:
            if client_id in self.active_streams[cam_id]:
                self.active_streams[cam_id][client_id] = time.time()
                return True

        # Limpiar streams inactivos (>60s sin actividad)
        self._cleanup_inactive_streams(timeout=60)

        # Contar streams únicos (por cliente)
        total_active_clients = sum(len(clients) for clients in self.active_streams.values())

        # Verificar límite
        if total_active_clients >= self.max_concurrent_streams:
            logger.warning(f"⚠️ Límite de streams alcanzado ({total_active_clients}/{self.max_concurrent_streams})")
            logger.warning(f"   Activos: {list(self.active_streams.keys())}")
            return False

        # Registrar nuevo stream
        if cam_id not in self.active_streams:
            self.active_streams[cam_id] = {}

        self.active_streams[cam_id][client_id] = time.time()

        logger.info(
            f"✅ Stream iniciado: Cam {cam_id}, Cliente {client_id[:8]}... ({total_active_clients + 1}/{self.max_concurrent_streams})")
        return True

    def stop_stream(self, cam_id: int, client_id: str):
        """
        Detiene un stream y libera recursos

        Args:
            cam_id: ID de la cámara
            client_id: ID del cliente
        """
        if cam_id in self.active_streams:
            if client_id in self.active_streams[cam_id]:
                del self.active_streams[cam_id][client_id]

                # Si no hay más clientes para esta cámara, eliminar entrada
                if not self.active_streams[cam_id]:
                    del self.active_streams[cam_id]

                total_active = sum(len(clients) for clients in self.active_streams.values())
                logger.info(
                    f"🛑 Stream detenido: Cam {cam_id}, Cliente {client_id[:8]}... ({total_active}/{self.max_concurrent_streams})")

    def _cleanup_inactive_streams(self, timeout=60):
        """
        Limpia streams inactivos

        Args:
            timeout: Segundos sin actividad para considerar inactivo
        """
        current_time = time.time()
        cams_to_remove = []

        for cam_id, clients in list(self.active_streams.items()):
            clients_to_remove = []

            for client_id, last_access in list(clients.items()):
                if current_time - last_access > timeout:
                    clients_to_remove.append(client_id)

            for client_id in clients_to_remove:
                del clients[client_id]
                logger.info(f"🧹 Stream inactivo limpiado: Cam {cam_id}, Cliente {client_id[:8]}...")

            if not clients:
                cams_to_remove.append(cam_id)

        for cam_id in cams_to_remove:
            del self.active_streams[cam_id]

    def optimize_frame(self, frame: np.ndarray, quality: int = 65) -> bytes:
        """
        Optimiza frame para transmisión

        Optimizaciones:
        - Reduce resolución a 720p máximo
        - Compresión JPEG con calidad ajustable

        Args:
            frame: Frame original
            quality: Calidad JPEG (50-90, default 65 para balance memoria/calidad)

        Returns:
            bytes: JPEG comprimido
        """
        try:
            if frame is None or frame.size == 0:
                logger.warning("⚠️ Frame vacío en optimize_frame")
                return b''

            h, w = frame.shape[:2]

            # ⭐ Reducir a 720p si es muy grande (ahorra ~60% memoria)
            if w > 1280:
                scale = 1280 / w
                new_w = 1280
                new_h = int(h * scale)
                frame = cv2.resize(frame, (new_w, new_h), interpolation=cv2.INTER_LINEAR)
                logger.debug(f"📏 Frame reducido: {w}x{h} -> {new_w}x{new_h}")

            # ⭐ Comprimir a JPEG
            encode_param = [int(cv2.IMWRITE_JPEG_QUALITY), quality]
            success, buffer = cv2.imencode('.jpg', frame, encode_param)

            if not success:
                logger.error("❌ Error en cv2.imencode")
                return b''

            frame_bytes = buffer.tobytes()
            size_kb = len(frame_bytes) / 1024

            if size_kb > 100:  # Log si frame es muy grande
                logger.debug(f"📦 Frame size: {size_kb:.1f} KB (quality={quality})")

            return frame_bytes

        except Exception as e:
            logger.error(f"❌ Error optimizando frame: {e}")
            return b''

    def get_status(self):
        """
        Retorna estado actual del optimizador

        Returns:
            dict: Estado con streams activos y límites
        """
        total_active = sum(len(clients) for clients in self.active_streams.values())

        return {
            'active_streams': total_active,
            'max_streams': self.max_concurrent_streams,
            'cameras_streaming': list(self.active_streams.keys()),
            'utilization_percent': (total_active / self.max_concurrent_streams) * 100
        }


# Singleton global
_stream_optimizer = VideoStreamOptimizer(max_concurrent_streams=4)


def get_stream_optimizer():
    """Retorna instancia del optimizador"""
    return _stream_optimizer