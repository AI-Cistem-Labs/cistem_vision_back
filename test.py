#!/usr/bin/env python3
"""
Diagnóstico de delay en sistema de vigilancia
Identifica exactamente dónde está el cuello de botella
"""

import subprocess
import time
import sys
import cv2


class DelayDiagnostic:
    """Diagnóstico completo del sistema"""

    def __init__(self):
        self.issues = []
        self.warnings = []

    def log_issue(self, message):
        """Registra problema crítico"""
        print(f"❌ CRÍTICO: {message}")
        self.issues.append(message)

    def log_warning(self, message):
        """Registra advertencia"""
        print(f"⚠️ ADVERTENCIA: {message}")
        self.warnings.append(message)

    def log_ok(self, message):
        """Registra OK"""
        print(f"✅ OK: {message}")

    def check_ffmpeg_processes(self):
        """Verifica procesos FFmpeg activos"""
        print("\n" + "=" * 60)
        print("1. PROCESOS FFMPEG")
        print("=" * 60)

        try:
            result = subprocess.run(
                ['ps', 'aux'],
                capture_output=True,
                text=True
            )

            ffmpeg_processes = [
                line for line in result.stdout.split('\n')
                if 'ffmpeg' in line.lower() and 'grep' not in line.lower()
            ]

            count = len(ffmpeg_processes)

            if count == 0:
                self.log_ok("No hay procesos FFmpeg ejecutándose")
            elif count <= 7:  # Asumiendo 7 cámaras
                self.log_ok(f"{count} procesos FFmpeg (normal)")
                for proc in ffmpeg_processes:
                    parts = proc.split()
                    cpu_usage = parts[2] if len(parts) > 2 else "?"
                    print(f"   CPU: {cpu_usage}% - {' '.join(parts[10:15])}")
            else:
                self.log_issue(f"{count} procesos FFmpeg (demasiados, hay acumulación)")
                self.log_issue("SOLUCIÓN: pkill -9 ffmpeg")

        except Exception as e:
            self.log_warning(f"No se pudo verificar procesos: {e}")

    def check_cpu_usage(self):
        """Verifica uso de CPU"""
        print("\n" + "=" * 60)
        print("2. USO DE CPU")
        print("=" * 60)

        try:
            result = subprocess.run(
                ['top', '-bn1'],
                capture_output=True,
                text=True,
                timeout=3
            )

            lines = result.stdout.split('\n')
            cpu_line = [l for l in lines if 'Cpu(s)' in l or '%Cpu' in l]

            if cpu_line:
                print(f"   {cpu_line[0]}")

                # Extraer porcentaje idle
                if 'id' in cpu_line[0]:
                    idle_str = cpu_line[0].split('id')[0].split()[-1]
                    try:
                        idle = float(idle_str.replace(',', '.'))
                        used = 100 - idle

                        if used > 80:
                            self.log_issue(f"CPU al {used:.1f}% (sobrecargado)")
                            self.log_issue("CAUSA: Encoding en CPU es muy lento")
                            self.log_issue("SOLUCIÓN: Usar hardware encoding (GStreamer)")
                        elif used > 60:
                            self.log_warning(f"CPU al {used:.1f}% (alto)")
                        else:
                            self.log_ok(f"CPU al {used:.1f}% (normal)")
                    except:
                        pass

        except Exception as e:
            self.log_warning(f"No se pudo verificar CPU: {e}")

    def check_gstreamer(self):
        """Verifica si GStreamer está disponible"""
        print("\n" + "=" * 60)
        print("3. GSTREAMER (Hardware Encoding)")
        print("=" * 60)

        try:
            result = subprocess.run(
                ['gst-launch-1.0', '--version'],
                capture_output=True,
                text=True,
                timeout=3
            )

            if result.returncode == 0:
                version = result.stdout.split('\n')[0]
                self.log_ok(f"GStreamer instalado: {version}")
                print("   ✅ Puedes usar OPCIÓN 1 (manager_realtime.py)")
            else:
                self.log_warning("GStreamer NO instalado")
                print("   ⚠️ Usa OPCIÓN 2 (manager_ffmpeg_realtime.py)")
                print("   O instala: sudo apt install gstreamer1.0-tools")

        except FileNotFoundError:
            self.log_warning("GStreamer NO instalado")
            print("   ⚠️ Usa OPCIÓN 2 (manager_ffmpeg_realtime.py)")
            print("   O instala: sudo apt install gstreamer1.0-tools")
        except Exception as e:
            self.log_warning(f"Error verificando GStreamer: {e}")

    def check_camera_stream(self, rtsp_url):
        """Verifica latencia de cámara origen"""
        print("\n" + "=" * 60)
        print("4. LATENCIA DE STREAM")
        print("=" * 60)
        print(f"   Probando: {rtsp_url}")

        try:
            print("   Conectando...")
            cap = cv2.VideoCapture(rtsp_url)

            if not cap.isOpened():
                self.log_issue("No se pudo conectar a la cámara")
                return

            # Obtener props
            width = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH))
            height = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
            fps = int(cap.get(cv2.CAP_PROP_FPS))

            print(f"   Resolución: {width}x{height}")
            print(f"   FPS configurado: {fps}")

            # Medir FPS real
            print("   Midiendo FPS real (3 segundos)...")
            start = time.time()
            frames = 0

            while time.time() - start < 3:
                ret, frame = cap.read()
                if ret:
                    frames += 1

            actual_fps = frames / 3.0
            print(f"   FPS real: {actual_fps:.1f}")

            if actual_fps < fps * 0.8:
                self.log_warning(f"FPS real ({actual_fps:.1f}) < FPS configurado ({fps})")
                self.log_warning("La cámara ya tiene delay en origen")
            else:
                self.log_ok(f"FPS real ({actual_fps:.1f}) normal")

            # Tamaño de frame
            pixels = width * height
            mbps = (pixels * actual_fps * 3 * 8) / 1_000_000  # RGB, bits/sec

            print(f"   Throughput: {mbps:.1f} Mbps")

            if mbps > 100:
                self.log_warning(f"Throughput muy alto ({mbps:.1f} Mbps)")
                self.log_warning("SOLUCIÓN: Usar substream de menor resolución")

            cap.release()

        except Exception as e:
            self.log_issue(f"Error probando stream: {e}")

    def check_mediamtx(self):
        """Verifica MediaMTX"""
        print("\n" + "=" * 60)
        print("5. MEDIAMTX")
        print("=" * 60)

        try:
            result = subprocess.run(
                ['curl', '-s', 'http://localhost:9997/v3/config/global/get'],
                capture_output=True,
                text=True,
                timeout=3
            )

            if result.returncode == 0:
                self.log_ok("MediaMTX respondiendo en puerto 9997")
            else:
                self.log_issue("MediaMTX no responde")
                self.log_issue("SOLUCIÓN: sudo systemctl restart mediamtx")

        except Exception as e:
            self.log_warning(f"Error verificando MediaMTX: {e}")

    def print_summary(self):
        """Imprime resumen y recomendaciones"""
        print("\n" + "=" * 60)
        print("RESUMEN DE DIAGNÓSTICO")
        print("=" * 60)

        if not self.issues and not self.warnings:
            print("\n✅ TODO OK - Sistema configurado correctamente")
            print("\nSi aún hay delay, verifica:")
            print("  1. Que estés usando manager_realtime.py o manager_ffmpeg_realtime.py")
            print("  2. Que hayas reiniciado la aplicación")
            print("  3. Que no haya procesos FFmpeg viejos (pkill -9 ffmpeg)")
            return

        if self.issues:
            print(f"\n❌ PROBLEMAS CRÍTICOS ({len(self.issues)}):")
            for i, issue in enumerate(self.issues, 1):
                print(f"\n{i}. {issue}")

        if self.warnings:
            print(f"\n⚠️ ADVERTENCIAS ({len(self.warnings)}):")
            for i, warning in enumerate(self.warnings, 1):
                print(f"\n{i}. {warning}")

        print("\n" + "=" * 60)
        print("RECOMENDACIONES")
        print("=" * 60)

        # Determinar mejor opción
        has_gstreamer = any('GStreamer instalado' in str(self.log_ok.__self__) for _ in [0])
        high_cpu = any('CPU al' in issue and 'sobrecargado' in issue for issue in self.issues)

        print("\n🎯 SIGUIENTE PASO:")

        if high_cpu:
            print("\n1. MATAR PROCESOS FFMPEG:")
            print("   pkill -9 ffmpeg")
            print("   sudo systemctl restart mediamtx")

        print("\n2. USAR EL ARCHIVO CORRECTO:")
        try:
            result = subprocess.run(
                ['gst-launch-1.0', '--version'],
                capture_output=True,
                timeout=1
            )
            if result.returncode == 0:
                print("   ✅ USAR: manager_realtime.py (GStreamer disponible)")
            else:
                print("   ✅ USAR: manager_ffmpeg_realtime.py")
        except:
            print("   ✅ USAR: manager_ffmpeg_realtime.py")

        print("\n3. COPIAR ARCHIVOS:")
        print("   cp manager_realtime.py modules/vision/manager.py")
        print("   cp intrusion_detector_realtime.py modules/vision/processors/intrusion_detector_processor.py")

        print("\n4. REINICIAR APLICACIÓN")
        print("   python main.py")

        print("\n" + "=" * 60)


def main():
    """Función principal"""
    print("=" * 60)
    print("DIAGNÓSTICO DE DELAY EN SISTEMA DE VIGILANCIA")
    print("=" * 60)

    diag = DelayDiagnostic()

    # Ejecutar diagnósticos
    diag.check_ffmpeg_processes()
    diag.check_cpu_usage()
    diag.check_gstreamer()
    diag.check_mediamtx()

    # Test opcional de cámara
    print("\n" + "=" * 60)
    test_cam = input("\n¿Probar latencia de cámara específica? (s/N): ").lower()

    if test_cam == 's':
        rtsp_url = input("URL RTSP (ej: rtsp://admin:pass@192.168.1.214:554/stream1): ")
        if rtsp_url:
            diag.check_camera_stream(rtsp_url)

    # Resumen
    diag.print_summary()


if __name__ == "__main__":
    main()