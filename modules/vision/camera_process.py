import multiprocessing as mp
import threading
import time
import subprocess
import cv2
import numpy as np
import traceback
import os
import queue
import socket
from datetime import datetime
from multiprocessing import shared_memory
from modules.vision.processors import get_processor_class

# Helper para obtener IP
def get_ip_address():
    try:
        # Intento de obtener IP de red local (prioridad 10.x, 192.x, 100.x)
        s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        # No necesita ser alcanzable, solo para que el OS decida la interfaz de salida
        s.connect(("8.8.8.8", 80))
        ip = s.getsockname()[0]
        s.close()
        return ip
    except:
        return "localhost"

class VideoWriterThread(threading.Thread):
    """
    Hilo dedicado a escribir video usando FFmpeg (subprocess) para garantizar H.264.
    """
    def __init__(self, cam_id, width, height, fps=15):
        super().__init__()
        self.cam_id = cam_id
        self.width = width
        self.height = height
        self.fps = int(fps)
        self.queue = queue.Queue() 
        self.stop_event = threading.Event()
        self.is_recording = False
        self.ffmpeg_process = None
        self.current_filename = None
        self.current_thumbnail = None
        self.output_dir = "static/evidence"
        os.makedirs(self.output_dir, exist_ok=True)

    def start_recording(self, first_frame=None):
        """Envía comando de inicio de grabación (No bloqueante)"""
        if self.is_recording:
            return None, None

        timestamp = datetime.utcnow().strftime("%Y%m%d_%H%M%S")
        filename = f"cam_{self.cam_id}_{timestamp}.mp4"
        thumbnail_name = f"cam_{self.cam_id}_{timestamp}_thumb.jpg"
        
        # Generar thumbnail SÍNCRONO (rápido)
        if first_frame is not None:
            try:
                thumbpath = os.path.join(self.output_dir, thumbnail_name)
                cv2.imwrite(thumbpath, first_frame)
            except Exception as e:
                print(f"⚠️ [Cam {self.cam_id}] Error thumbnail: {e}")
                thumbnail_name = None

        # Enviar comando START
        cmd = {
            'type': 'START',
            'filename': filename,
            'timestamp': timestamp
        }
        self.queue.put(cmd)
        
        self.is_recording = True
        self.current_filename = filename
        self.current_thumbnail = thumbnail_name
        
        return filename, thumbnail_name

    def stop_recording(self):
        """Envía comando de parada"""
        if not self.is_recording:
            return
        
        self.is_recording = False
        self.queue.put({'type': 'STOP'})

    def add_frame(self, frame):
        """Encola frame si estamos grabando"""
        if self.is_recording:
            try:
                self.queue.put({'type': 'FRAME', 'data': frame.copy()}, block=False)
            except queue.Full:
                pass

    def _start_ffmpeg_writer(self, filename):
        filepath = os.path.join(self.output_dir, filename)
        
        # Comando para grabar H.264 compatible con navegadores
        # -y: sobrescribir
        # -f rawvideo: entrada cruda
        # -pix_fmt bgr24: formato de OpenCV
        # -c:v libx264: encoder H.264 por software (seguro)
        # -pix_fmt yuv420p: requerido para compatibilidad browser
        # -movflags +faststart: mueve metadata al inicio para streaming
        command = [
            'ffmpeg', '-y',
            '-f', 'rawvideo',
            '-vcodec', 'rawvideo',
            '-s', f'{self.width}x{self.height}',
            '-pix_fmt', 'bgr24',
            '-r', str(self.fps),
            '-i', '-',
            '-c:v', 'libx264',
            '-preset', 'ultrafast', # encode rapidísimo
            '-pix_fmt', 'yuv420p',
            '-movflags', '+faststart',
            filepath
        ]
        
        try:
            # Stderr a DEVNULL para no ensuciar logs, o PIPE para debug
            process = subprocess.Popen(
                command, 
                stdin=subprocess.PIPE, 
                stdout=subprocess.DEVNULL, 
                stderr=subprocess.DEVNULL
            )
            return process
        except Exception as e:
            print(f"❌ [Cam {self.cam_id}] Error iniciando FFmpeg writer: {e}")
            return None

    def run(self):
        while not self.stop_event.is_set():
            try:
                # Timeout corto para revisar stop_event
                item = self.queue.get(timeout=0.5)
            except queue.Empty:
                if not self.is_recording and self.ffmpeg_process:
                     # Si dejamos de grabar y se vació la cola -> cerrar
                     self._close_writer()
                continue

            msg_type = item.get('type')

            if msg_type == 'START':
                self._close_writer() # Asegurar limpieza anterior
                
                filename = item['filename']
                print(f"🎥 [Cam {self.cam_id}] FFMPEG WRITER START: {filename}")
                self.ffmpeg_process = self._start_ffmpeg_writer(filename)

            elif msg_type == 'FRAME':
                if self.ffmpeg_process:
                    try:
                        self.ffmpeg_process.stdin.write(item['data'].tobytes())
                    except Exception as e:
                         # Broken pipe?
                         print(f"⚠️ Error escritura frame ffmpeg: {e}")
                         self._close_writer()

            elif msg_type == 'STOP':
                print(f"🛑 [Cam {self.cam_id}] Finalizando grabación...")
                self._close_writer()
                print(f"💾 [Cam {self.cam_id}] Evidencia guardada.")

        self._close_writer()
        
    def _close_writer(self):
        if self.ffmpeg_process:
            try:
                if self.ffmpeg_process.stdin:
                    self.ffmpeg_process.stdin.close()
                self.ffmpeg_process.wait(timeout=2)
            except Exception as e:
                print(f"⚠️ Error cerrando ffmpeg: {e}")
                self.ffmpeg_process.kill()
            self.ffmpeg_process = None


class CameraProcess(mp.Process):
    """
    Proceso independiente para manejo de cámara con CERO LATENCIA + SENTINEL MODE.
    """
    
    def __init__(self, cam_id, processor_id, rtsp_url, alert_queue, width=1280, height=720, fps=15):
        super().__init__()
        self.cam_id = cam_id
        self.processor_id = processor_id
        self.rtsp_url = rtsp_url
        self.alert_queue = alert_queue  # Cola para enviar alertas al Main Process
        self.target_width = width
        self.target_height = height
        self.target_fps = fps
        
        self.stop_event = mp.Event()
        
        self.shm_name = f"cam_{cam_id}_shm"
        self.frame_size = self.target_width * self.target_height * 3
        self.shm = None
        
        self.latest_frame = None
        self.latest_frame_lock = None
        self.capture_thread = None
        self.frame_shape = (self.target_height, self.target_width, 3)

        # Sentinel Mode
        self.video_thread = None
        self.is_intrusion_active = False # Flag local para estado
        self.cooldown_seconds = 5.0
        self.last_intrusion_time = 0
        
        # Determinar Host URL (para evidence links absolutos)
        self.server_ip = get_ip_address()
        self.server_port = 5000 
        self.base_url = f"http://{self.server_ip}:{self.server_port}"
        print(f"🌍 [Cam {self.cam_id}] Base URL para evidencia: {self.base_url}")

    def _setup_shared_memory(self):
        try:
            try:
                existing_shm = shared_memory.SharedMemory(name=self.shm_name)
                existing_shm.close()
                existing_shm.unlink()
            except:
                pass
                
            self.shm = shared_memory.SharedMemory(create=True, size=self.frame_size, name=self.shm_name)
            
            black_frame = np.zeros(self.frame_shape, dtype=np.uint8)
            buffer = np.ndarray(self.frame_shape, dtype=np.uint8, buffer=self.shm.buf)
            buffer[:] = black_frame[:]
            print(f"💾 [Cam {self.cam_id}] Shared Memory creada: {self.shm_name}")
        except Exception as e:
            print(f"❌ [Cam {self.cam_id}] Error Shared Memory: {e}")
            self.shm = None

    def run(self):
        try:
            print(f"🚀 [Cam {self.cam_id}] Iniciando proceso PID {os.getpid()}")
            
            self.latest_frame_lock = threading.Lock()
            self._setup_shared_memory()
            
            self.video_thread = VideoWriterThread(
                self.cam_id, 
                self.target_width, 
                self.target_height, 
                self.target_fps
            )
            self.video_thread.start()

            self.capture_thread = threading.Thread(target=self._capture_loop, daemon=True)
            self.capture_thread.start()
            
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
            
            if self.video_thread:
                self.video_thread.stop_event.set()
                self.video_thread.join()

            print(f"🛑 [Cam {self.cam_id}] Proceso finalizado")

    def _capture_loop(self):
        reconnect_delay = 5
        while not self.stop_event.is_set():
            cap = None
            try:
                print(f"🔌 [Cam {self.cam_id}] Conectando captura ({self.rtsp_url})...")
                cap = cv2.VideoCapture(self.rtsp_url)
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
                    time.sleep(0.001)
            except Exception as e:
                print(f"❌ [Cam {self.cam_id}] Error en captura: {e}")
            finally:
                if cap:
                    cap.release()
                time.sleep(reconnect_delay)

    def _update_shared_memory(self, frame):
        if self.shm is None:
            return
        try:
            shared_frame = np.ndarray(self.frame_shape, dtype=np.uint8, buffer=self.shm.buf)
            shared_frame[:] = frame[:]
        except Exception as e:
            pass

    def _send_create_alert(self, msg, level="PRECAUCION", context=None, status="detected", button="Ver evento en curso"):
        """Envia alerta CREATE a la cola del Main Process"""
        try:
            alert_payload = {
                "action": "create",
                "cam_id": self.cam_id,
                "msg": msg,
                "level": level,
                "context": context or {},
                "status": status,
                "button": button
            }
            self.alert_queue.put(alert_payload)
        except Exception as e:
            print(f"❌ [Cam {self.cam_id}] Error enviando creacion alerta: {e}")

    def _send_update_alert(self, status="finished", button="Ver evidencia"):
        """Envia alerta UPDATE a la cola del Main Process"""
        try:
            alert_payload = {
                "action": "update",
                "cam_id": self.cam_id,
                "status": status,
                "button": button
            }
            self.alert_queue.put(alert_payload)
        except Exception as e:
            print(f"❌ [Cam {self.cam_id}] Error enviando update alerta: {e}")

    def _handle_sentinel_mode(self, result, frame):
        try:
            is_intrusion = result.get('intrusion', False)
            intruders_count = result.get('count', 0)
            current_time = time.time()

            # Lógica: 1 Alerta ÚNICA al detectar (DETECTED) -> Update al finalizar (FINISHED)
            
            # Estado 1: Intrusión Activa
            if is_intrusion:
                self.last_intrusion_time = current_time
                
                if not self.is_intrusion_active:
                    # NUEVA INTRUSIÓN
                    self.is_intrusion_active = True
                    print(f"🚨 [Cam {self.cam_id}] INTRUSIÓN DETECTADA - Iniciando grabación")
                    
                    # Iniciar grabación
                    filename, thumbname = self.video_thread.start_recording(first_frame=frame)
                    
                    if filename:
                        # URLs ABSOLUTAS
                        video_url = f"{self.base_url}/static/evidence/{filename}"
                        thumb_url = f"{self.base_url}/static/evidence/{thumbname}" if thumbname else None
                        
                        # ALERTA 'DETECTED'
                        self._send_create_alert(
                            f"¡INTRUSO DETECTADO! - {intruders_count} Personas",
                            "CRITICAL",
                            {
                                "count": intruders_count, 
                                "video": video_url,
                                "thumbnail": thumb_url
                            },
                            status="detected",
                            button="Ver evento en curso"
                        )
                
            # Estado 2: Sin intrusión (posible Cooldown)
            else:
                if self.is_intrusion_active:
                    if current_time - self.last_intrusion_time > self.cooldown_seconds:
                        print(f"✅ [Cam {self.cam_id}] Zona despejada - Deteniendo grabación")
                        
                        self.is_intrusion_active = False
                        self.video_thread.stop_recording()
                        
                        # ALERTA UPDATE 'FINISHED'
                        self._send_update_alert(
                            status="finished",
                            button="Ver evidencia"
                        )

            # Enviamos frame SIEMPRE si estamos en "modo intrusión activa" (grabando)
            if self.is_intrusion_active:
                self.video_thread.add_frame(frame)

        except Exception as e:
            print(f"❌ [Cam {self.cam_id}] Error en Sentinel Logic: {e}")
            traceback.print_exc()

    def _process_loop(self):
        ProcessorClass = get_processor_class(self.processor_id)
        if not ProcessorClass:
            return
            
        processor = ProcessorClass(self.cam_id)
        ffmpeg_process = self._start_ffmpeg()
        
        frame_interval = 1.0 / self.target_fps
        last_process_time = 0
        
        print(f"🎬 [Cam {self.cam_id}] Loop de procesamiento iniciado")
        
        while not self.stop_event.is_set():
            loop_start = time.time()
            
            frame = None
            with self.latest_frame_lock:
                if self.latest_frame is not None:
                    frame = self.latest_frame.copy()
            
            if frame is None:
                time.sleep(0.01)
                if ffmpeg_process and ffmpeg_process.poll() is not None:
                     ffmpeg_process = self._start_ffmpeg()
                continue
                
            if frame.shape[1] != self.target_width or frame.shape[0] != self.target_height:
                frame = cv2.resize(frame, (self.target_width, self.target_height))

            if loop_start - last_process_time >= frame_interval:
                try:
                    result = processor.process_frame(frame)
                    processor.draw_detections(frame)
                    
                    if isinstance(result, dict):
                         self._handle_sentinel_mode(result, frame)
                    
                    last_process_time = loop_start
                    self._update_shared_memory(frame)
                    
                except Exception as e:
                    print(f"⚠️ [Cam {self.cam_id}] Error procesando: {e}")
                    traceback.print_exc()

            if ffmpeg_process:
                try:
                    if ffmpeg_process.poll() is not None:
                         ffmpeg_process = self._start_ffmpeg()
                    if ffmpeg_process:
                        ffmpeg_process.stdin.write(frame.tobytes())
                except Exception as e:
                    print(f"⚠️ [Cam {self.cam_id}] Error escribiendo a FFmpeg: {e}")

            elapsed = time.time() - loop_start
            sleep_time = max(0.001, frame_interval - elapsed)
            time.sleep(sleep_time)
            
        if ffmpeg_process:
            try:
                ffmpeg_process.stdin.close()
                ffmpeg_process.terminate()
            except:
                pass

    def _start_ffmpeg(self):
        try:
            mediamtx_url = f"rtsp://localhost:8554/camera_{self.cam_id}_ai"
            ffmpeg_cmd = [
                'ffmpeg', '-y', '-f', 'rawvideo', '-vcodec', 'rawvideo',
                '-pix_fmt', 'bgr24', '-s', f'{self.target_width}x{self.target_height}',
                '-r', str(self.target_fps), '-thread_queue_size', '4',
                '-probesize', '32', '-analyzeduration', '0', '-i', '-',
                '-c:v', 'libx264', '-preset', 'ultrafast', '-tune', 'zerolatency',
                '-profile:v', 'baseline', '-pix_fmt', 'yuv420p',
                '-b:v', '1500k', '-maxrate', '1800k', '-bufsize', '400k',
                '-g', '30', '-keyint_min', '30', '-sc_threshold', '0',
                '-bf', '0', '-threads', '1', '-fflags', 'nobuffer+flush_packets',
                '-flags', 'low_delay', '-strict', 'experimental',
                '-flush_packets', '1', '-f', 'rtsp', '-rtsp_transport', 'tcp',
                mediamtx_url
            ]
            return subprocess.Popen(ffmpeg_cmd, stdin=subprocess.PIPE, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, bufsize=0)
        except Exception as e:
            return None

    def stop(self):
        self.stop_event.set()
