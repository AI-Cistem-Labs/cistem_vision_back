# modules/vision/manager.py
import threading
import time
import subprocess
import cv2
import multiprocessing as mp
import numpy as np
from multiprocessing import shared_memory
from config.config_manager import device_config
from modules.vision.processors import get_processor_class
from modules.analytics.specialists.system_logger import system_logger
from modules.vision.camera_process import CameraProcess

# CRÍTICO: Usar 'spawn' para evitar conflictos con eventlet/greenlets en los procesos hijos
try:
    if mp.get_start_method(allow_none=True) != 'spawn':
        mp.set_start_method('spawn', force=True)
except Exception:
    pass


class VisionManager:
    """
    Vision Manager INFALIBLE + ZERO LATENCY (Multicprocess)
    
    🛡️ INFALIBLE:
    ✅ Procesos independientes por cámara (aislamiento total)
    ✅ Watchdog monitorizando procesos (PID check)
    ✅ Shared Memory para API preview sin bloquear procesamiento
    ✅ Reinicio automático ante crashes
    """
    _instance = None

    def __new__(cls):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
            cls._instance._initialized = False
        return cls._instance

    def __init__(self):
        if self._initialized:
            return

        self.active_cameras = {}
        self.lock = threading.Lock()
        self._initialized = True
        
        # Watchdog
        self._watchdog_thread = None
        self._watchdog_running = False
        self._start_watchdog()
        
        print("✅ VisionManager (MULTIPROCESS) inicializado")

    def _start_watchdog(self):
        """Inicia thread watchdog para monitorear procesos de cámaras"""
        self._watchdog_running = True
        self._watchdog_thread = threading.Thread(
            target=self._watchdog_loop,
            daemon=True
        )
        self._watchdog_thread.start()
        print("🐕 Watchdog iniciado")

    def _watchdog_loop(self):
        """Loop que monitorea el estado de los procesos cada 5 segundos"""
        while self._watchdog_running:
            try:
                time.sleep(5)
                
                with self.lock:
                    for cam_id, camera_data in list(self.active_cameras.items()):
                        process = camera_data.get('process')
                        
                        # Verificar si el proceso sigue vivo
                        if process is None or not process.is_alive():
                            print(f"⚠️ Watchdog: Cam {cam_id} proceso muerto (PID {process.pid if process else '?'}), reiniciando...")
                            self._restart_camera_internal(cam_id)
            
            except Exception as e:
                print(f"❌ Watchdog error: {e}")
                time.sleep(5)

    def _restart_camera_internal(self, cam_id):
        """Reinicia una cámara (llamado por watchdog)"""
        try:
            if cam_id in self.active_cameras:
                camera_data = self.active_cameras[cam_id]
                processor_id = camera_data['processor_id']
                
                # Cleanup previo
                self.stop_camera(cam_id)
                
                # Wait before restart
                time.sleep(2)
                
                # Restart
                self.start_camera(cam_id, processor_id)
                print(f"✅ Cam {cam_id} reiniciada por watchdog")
                
        except Exception as e:
            print(f"❌ Error reiniciando cam {cam_id}: {e}")

    def start_camera(self, cam_id, processor_id=None):
        """Inicia proceso de cámara"""
        with self.lock:
            if cam_id in self.active_cameras:
                print(f"⚠️ Cámara {cam_id} ya activa")
                return False

            camera = device_config.get_camera(cam_id)
            if not camera:
                print(f"❌ Configuración de cámara {cam_id} no encontrada")
                return False

            if processor_id is None:
                processor_id = camera.get('active_processor', 1)

            rtsp_url = device_config.get_rtsp_url(cam_id)
            if not rtsp_url:
                print(f"❌ URL RTSP para cámara {cam_id} no encontrada")
                return False

            # Iniciar Proceso (CameraProcess)
            try:
                process = CameraProcess(
                    cam_id=cam_id,
                    processor_id=processor_id,
                    rtsp_url=rtsp_url,
                    width=1280, 
                    height=720,
                    fps=15 
                )
                process.start()
                
                # Guardar referencia
                self.active_cameras[cam_id] = {
                    'cam_id': cam_id,
                    'process': process,
                    'processor_id': processor_id,
                    'shm_name': process.shm_name,
                    'frame_shape': (720, 1280, 3) 
                }
                
                system_logger.camera_started(cam_id)
                print(f"✅ Cámara {cam_id} iniciada (PID {process.pid})")
                return True
                
            except Exception as e:
                print(f"❌ Error iniciando cámara {cam_id}: {e}")
                return False

    def stop_camera(self, cam_id):
        """Detiene cámara de forma segura"""
        with self.lock:
            if cam_id not in self.active_cameras:
                return False

            camera_data = self.active_cameras[cam_id]
            process = camera_data.get('process')
            
            if process:
                process.stop() # Set stop event
                process.join(timeout=3)
                if process.is_alive():
                    print(f"⚠️ Cam {cam_id} no respondió, matando proceso...")
                    process.terminate()

            del self.active_cameras[cam_id]
            print(f"✅ Cámara {cam_id} detenida")
            return True

    def is_camera_active(self, cam_id):
        with self.lock:
            return cam_id in self.active_cameras

    def get_processed_frame(self, cam_id):
        """Obtiene el último frame desde Shared Memory (para API)"""
        shm = None
        try:
            with self.lock:
                if cam_id not in self.active_cameras:
                    return None
                camera_data = self.active_cameras[cam_id]
            
            shm_name = camera_data.get('shm_name')
            frame_shape = camera_data.get('frame_shape')
            
            if not shm_name:
                return None
                
            # Conectar a memoria compartida existente
            shm = shared_memory.SharedMemory(name=shm_name)
            
            # Leer buffer
            # IMPORTANTE: Copiar los datos para liberar la SM inmediatamente
            buffer_frame = np.ndarray(frame_shape, dtype=np.uint8, buffer=shm.buf)
            frame_copy = buffer_frame.copy()
            
            shm.close()
            return frame_copy
            
        except FileNotFoundError:
            # El proceso puede haber muerto o reiniciando
            return None
        except Exception as e:
            if shm:
                try:
                    shm.close()
                except:
                    pass
            # print(f"⚠️ Error leyendo frame {cam_id}: {e}")
            return None

# Singleton
vision_manager = VisionManager()