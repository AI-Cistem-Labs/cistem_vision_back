import multiprocessing as mp
import threading
import time
import subprocess
import cv2
import numpy as np
import traceback
import os
import queue
from datetime import datetime
from multiprocessing import shared_memory
from modules.vision.processors import get_processor_class
from modules.analytics.specialists.alerts_engine import alerts_engine

class VideoWriterThread(threading.Thread):
    """
    Hilo dedicado a escribir video de forma Asíncrona via Comandos.
    """
    def __init__(self, cam_id, width, height, fps=15):
        super().__init__()
        self.cam_id = cam_id
        self.width = width
        self.height = height
        self.fps = fps
        # Cola para comandos (start, stop) y frames
        self.queue = queue.Queue() 
        self.stop_event = threading.Event()
        self.is_recording = False
        self.writer = None
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
        
        # Generar thumbnail SÍNCRONO (rápido) para tener el nombre listo para la alerta
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
        
        # Marcamos como grabando 'lógicamente' para que la UI/Lógica sepa
        # El hilo se encargará de inicializar el writer real
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
                # Type FRAME
                self.queue.put({'type': 'FRAME', 'data': frame.copy()}, block=False)
            except queue.Full:
                pass

    def _init_writer(self, filename):
        filepath = os.path.join(self.output_dir, filename)
        writer = None
        
        # Intento 1: avc1
        try:
            fourcc = cv2.VideoWriter_fourcc(*'avc1')
            writer = cv2.VideoWriter(filepath, fourcc, self.fps, (self.width, self.height))
            if not writer.isOpened():
                 print(f"⚠️ [Cam {self.cam_id}] Fallback avc1 -> mp4v")
                 raise Exception("avc1 failed")
        except:
             # Intento 2: mp4v
             try:
                fourcc = cv2.VideoWriter_fourcc(*'mp4v')
                writer = cv2.VideoWriter(filepath, fourcc, self.fps, (self.width, self.height))
             except Exception as e:
                print(f"❌ [Cam {self.cam_id}] Fatal VideoWriter: {e}")
                
        return writer

    def run(self):
        while not self.stop_event.is_set():
            try:
                item = self.queue.get(timeout=1.0)
            except queue.Empty:
                if not self.is_recording and self.writer:
                     # Timeout y no grabando? Cerrar por seguridad
                     self.writer.release()
                     self.writer = None
                continue

            msg_type = item.get('type')

            if msg_type == 'START':
                if self.writer:
                    self.writer.release()
                
                filename = item['filename']
                print(f"🎥 [Cam {self.cam_id}] Iniciando Writer para: {filename}")
                self.writer = self._init_writer(filename)
                
                if not self.writer or not self.writer.isOpened():
                    print(f"❌ [Cam {self.cam_id}] No se pudo iniciar grabación")
                    self.writer = None

            elif msg_type == 'FRAME':
                if self.writer and self.writer.isOpened():
                    try:
                        self.writer.write(item['data'])
                    except Exception as e:
                         print(f"⚠️ Error escritura frame: {e}")

            elif msg_type == 'STOP':
                print(f"🛑 [Cam {self.cam_id}] Deteniendo grabación")
                if self.writer:
                    self.writer.release()
                    self.writer = None
                    print(f"💾 [Cam {self.cam_id}] Archivo cerrado correctamente")

        # Cleanup final
        if self.writer:
            self.writer.release()


class CameraProcess(mp.Process):
    """
    Proceso independiente para manejo de cámara con CERO LATENCIA + SENTINEL MODE.
    """
    
    def __init__(self, cam_id, processor_id, rtsp_url, width=1280, height=720, fps=15):
        super().__init__()
        self.cam_id = cam_id
        self.processor_id = processor_id
        self.rtsp_url = rtsp_url
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
        self.is_intrusion_active = False
        self.intrusion_start_time = 0
        self.last_intrusion_time = 0
        self.cooldown_seconds = 5.0
        self.last_alert_time = 0
        self.alert_interval = 10.0

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

    def _handle_sentinel_mode(self, result, frame):
        try:
            is_intrusion = result.get('intrusion', False)
            intruders_count = result.get('count', 0)
            current_time = time.time()

            # Estado 1: Intrusión Activa
            if is_intrusion:
                self.last_intrusion_time = current_time
                
                if not self.video_thread.is_recording:
                    print(f"🚨 [Cam {self.cam_id}] INTRUSIÓN DETECTADA - Iniciando grabación")
                    # Pasamos el frame actual para usarlo de thumbnail
                    filename, thumbname = self.video_thread.start_recording(first_frame=frame)
                    
                    if filename:
                        alerts_engine.create_alert(
                            self.cam_id,
                            f"¡INTRUSO DETECTADO! Iniciando grabación...",
                            "CRITICAL",
                            {
                                "count": intruders_count, 
                                "video": f"/static/evidence/{filename}",
                                "thumbnail": f"/static/evidence/{thumbname}" if thumbname else None
                            }
                        )
                else:
                    if current_time - self.last_alert_time > self.alert_interval:
                         alerts_engine.create_alert(
                            self.cam_id,
                            f"Intrusión en curso - {intruders_count} sospechoso(s)",
                            "CRITICAL",
                            {"count": intruders_count, "video_status": "recording"}
                        )
                         self.last_alert_time = current_time

            # Estado 2: Sin intrusión (posible Cooldown)
            else:
                if self.video_thread.is_recording:
                    if current_time - self.last_intrusion_time > self.cooldown_seconds:
                        print(f"✅ [Cam {self.cam_id}] Zona despejada - Deteniendo grabación")
                        
                        # Guardar referencias
                        last_file = self.video_thread.current_filename
                        last_thumb = self.video_thread.current_thumbnail
                        
                        self.video_thread.stop_recording()
                        
                        # Alerta Final
                        context = {}
                        if last_file:
                            context["video"] = f"/static/evidence/{last_file}"
                        if last_thumb:
                            context["thumbnail"] = f"/static/evidence/{last_thumb}"
                            
                        alerts_engine.create_alert(
                            self.cam_id,
                            f"Intrusión finalizada. Evidencia guardada.",
                            "PRECAUCION",
                            context
                        )

            # Enviamos frame INCONDICIONALMENTE si is_recording es True
            # El hilo decidirá si lo escribe (si hay writer activo)
            if self.video_thread.is_recording:
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
