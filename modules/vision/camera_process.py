import multiprocessing as mp
import threading
import time
import subprocess
import cv2
import numpy as np
import traceback
import os
from multiprocessing import shared_memory
from modules.vision.processors import get_processor_class

class CameraProcess(mp.Process):
    """
    Proceso independiente para manejo de cámara con CERO LATENCIA.
    
    Arquitectura:
    1. Hilo de Captura: Lee frames constantemente y guarda SOLO el último.
    2. Loop de Proceso (Main): Toma el último frame, procesa y envía a FFmpeg.
    3. Shared Memory: Expone el último frame procesado para la API (VisionManager).
    """
    
    def __init__(self, cam_id, processor_id, rtsp_url, width=1280, height=720, fps=15):
        super().__init__()
        self.cam_id = cam_id
        self.processor_id = processor_id
        self.rtsp_url = rtsp_url
        self.target_width = width
        self.target_height = height
        self.target_fps = fps
        
        # Comunicación
        self.stop_event = mp.Event()
        
        # Shared Memory para Preview (API)
        # 1280x720x3 bytes
        self.shm_name = f"cam_{cam_id}_shm"
        self.frame_size = self.target_width * self.target_height * 3
        self.shm = None
        
        # Variables internas
        self.latest_frame = None
        self.latest_frame_lock = None
        self.capture_thread = None
        self.frame_shape = (self.target_height, self.target_width, 3)

    def _setup_shared_memory(self):
        """Inicializa memoria compartida para compartir frames con proceso principal"""
        try:
            # Intentar limpiar si existe
            try:
                existing_shm = shared_memory.SharedMemory(name=self.shm_name)
                existing_shm.close()
                existing_shm.unlink()
            except:
                pass
                
            self.shm = shared_memory.SharedMemory(create=True, size=self.frame_size, name=self.shm_name)
            
            # Inicializar con negros
            black_frame = np.zeros(self.frame_shape, dtype=np.uint8)
            buffer = np.ndarray(self.frame_shape, dtype=np.uint8, buffer=self.shm.buf)
            buffer[:] = black_frame[:]
            
            print(f"💾 [Cam {self.cam_id}] Shared Memory creada: {self.shm_name}")
        except Exception as e:
            print(f"❌ [Cam {self.cam_id}] Error Shared Memory: {e}")
            self.shm = None

    def run(self):
        """Punto de entrada del proceso"""
        try:
            print(f"🚀 [Cam {self.cam_id}] Iniciando proceso PID {os.getpid()}")
            
            self.latest_frame_lock = threading.Lock()
            self._setup_shared_memory()
            
            # 1. Iniciar Hilo de Captura
            self.capture_thread = threading.Thread(target=self._capture_loop, daemon=True)
            self.capture_thread.start()
            
            # 2. Iniciar Loop de Procesamiento
            self._process_loop()
            
        except Exception as e:
            print(f"❌ [Cam {self.cam_id}] Error fatal en proceso: {e}")
            traceback.print_exc()
        finally:
            if self.shm:
                try:
                    self.shm.close()
                    self.shm.unlink()
                except:
                    pass
            print(f"🛑 [Cam {self.cam_id}] Proceso finalizado")

    def _capture_loop(self):
        """Lee frames de la cámara lo más rápido posible"""
        reconnect_delay = 5
        
        while not self.stop_event.is_set():
            cap = None
            try:
                print(f"🔌 [Cam {self.cam_id}] Conectando captura ({self.rtsp_url})...")
                cap = cv2.VideoCapture(self.rtsp_url)
                
                # Optimización de buffer
                cap.set(cv2.CAP_PROP_BUFFERSIZE, 1)
                cap.set(cv2.CAP_PROP_FOURCC, cv2.VideoWriter_fourcc(*'H264'))
                
                if not cap.isOpened():
                    print(f"⚠️ [Cam {self.cam_id}] Fallo al abrir RTSP")
                    time.sleep(reconnect_delay)
                    continue
                
                print(f"✅ [Cam {self.cam_id}] Captura iniciada")
                
                while not self.stop_event.is_set():
                    ret, frame = cap.read()
                    if not ret:
                        print(f"⚠️ [Cam {self.cam_id}] Frame captura falló")
                        break
                        
                    with self.latest_frame_lock:
                        self.latest_frame = frame
                        
                    # Pequeño sleep para ceder CPU si FPS es altísimo
                    time.sleep(0.001)
                    
            except Exception as e:
                print(f"❌ [Cam {self.cam_id}] Error en captura: {e}")
            finally:
                if cap:
                    cap.release()
                time.sleep(reconnect_delay)

    def _update_shared_memory(self, frame):
        """Actualiza el frame en memoria compartida"""
        if self.shm is None:
            return
            
        try:
            # Escribir directamente al buffer
            # frame debe ser resizeado a target_width/height antes de llamar a esto
            shared_frame = np.ndarray(self.frame_shape, dtype=np.uint8, buffer=self.shm.buf)
            shared_frame[:] = frame[:]
        except Exception as e:
            # Puede fallar si el shape cambia o se cerró la memoria
            pass

    def _process_loop(self):
        """Loop principal: IA + FFmpeg"""
        ProcessorClass = get_processor_class(self.processor_id)
        if not ProcessorClass:
            print(f"❌ [Cam {self.cam_id}] Procesador {self.processor_id} no encontrado")
            return
            
        processor = ProcessorClass(self.cam_id)
        ffmpeg_process = self._start_ffmpeg()
        
        frame_interval = 1.0 / self.target_fps
        last_process_time = 0
        
        print(f"🎬 [Cam {self.cam_id}] Loop de procesamiento iniciado")
        
        while not self.stop_event.is_set():
            loop_start = time.time()
            
            # 1. Obtener frame más reciente
            frame = None
            with self.latest_frame_lock:
                if self.latest_frame is not None:
                    frame = self.latest_frame.copy()
            
            if frame is None:
                time.sleep(0.01)
                if ffmpeg_process and ffmpeg_process.poll() is not None:
                     # Reiniciar FFmpeg si murió incluso sin frames
                     ffmpeg_process = self._start_ffmpeg()
                continue
                
            # 2. Resize siempre a target
            if frame.shape[1] != self.target_width or frame.shape[0] != self.target_height:
                frame = cv2.resize(frame, (self.target_width, self.target_height))

            # 3. Procesamiento (IA) - Control frames
            if loop_start - last_process_time >= frame_interval:
                try:
                    processor.process_frame(frame)
                    processor.draw_detections(frame)
                    last_process_time = loop_start
                    
                    # Actualizar Shared Memory para API
                    self._update_shared_memory(frame)
                    
                except Exception as e:
                    print(f"⚠️ [Cam {self.cam_id}] Error procesando: {e}")

            # 4. FFmpeg Streaming
            if ffmpeg_process:
                try:
                    if ffmpeg_process.poll() is not None:
                         print(f"⚠️ [Cam {self.cam_id}] FFmpeg murió, reiniciando...")
                         ffmpeg_process = self._start_ffmpeg()
                         
                    if ffmpeg_process:
                        ffmpeg_process.stdin.write(frame.tobytes())
                except Exception as e:
                    print(f"⚠️ [Cam {self.cam_id}] Error escribiendo a FFmpeg: {e}")

            # Sleep control
            elapsed = time.time() - loop_start
            sleep_time = max(0.001, frame_interval - elapsed)
            # Acortamos sleep para revisar stop_event más seguido y capturar frames frescos
            if sleep_time > 0.005:
                time.sleep(0.005) 
            else:
                time.sleep(sleep_time)
            
        # Cleanup
        if ffmpeg_process:
            try:
                ffmpeg_process.stdin.close()
                ffmpeg_process.terminate()
            except:
                pass

    def _start_ffmpeg(self):
        """FFmpeg optimizado para ultra-baja latencia"""
        try:
            mediamtx_url = f"rtsp://localhost:8554/camera_{self.cam_id}_ai"
            
            # Parametros copiados y validados de manager.py
            ffmpeg_cmd = [
                'ffmpeg',
                '-y',
                '-f', 'rawvideo',
                '-vcodec', 'rawvideo',
                '-pix_fmt', 'bgr24',
                '-s', f'{self.target_width}x{self.target_height}',
                '-r', str(self.target_fps),
                '-thread_queue_size', '4',
                '-probesize', '32',
                '-analyzeduration', '0',
                '-i', '-',
                '-c:v', 'libx264',
                '-preset', 'ultrafast',
                '-tune', 'zerolatency',
                '-profile:v', 'baseline',
                '-pix_fmt', 'yuv420p',
                '-b:v', '1500k', # Calidad mejorada
                '-maxrate', '1800k',
                '-bufsize', '400k',
                '-g', '30', # ~2 se de GOP
                '-keyint_min', '30',
                '-sc_threshold', '0',
                '-bf', '0',
                '-threads', '1',
                '-fflags', 'nobuffer+flush_packets',
                '-flags', 'low_delay',
                '-strict', 'experimental',
                '-flush_packets', '1',
                '-f', 'rtsp',
                '-rtsp_transport', 'tcp',
                mediamtx_url
            ]
            
            return subprocess.Popen(
                ffmpeg_cmd,
                stdin=subprocess.PIPE,
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
                bufsize=0
            ) 
        except Exception as e:
            print(f"❌ [Cam {self.cam_id}] Error iniciando FFmpeg: {e}")
            return None

    def stop(self):
        """Señal para detener el proceso"""
        self.stop_event.set()
