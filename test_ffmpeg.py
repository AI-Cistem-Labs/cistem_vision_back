#!/usr/bin/env python3
"""
Script de diagnostico para verificar la configuracion de FFmpeg y MediaMTX.
Ejecutar en el Jetson: python3 test_ffmpeg_mediamtx.py
"""

import subprocess
import sys
import os
import time

MEDIAMTX_HOST = os.getenv('TAILSCALE_IP', '100.73.141.61')
MEDIAMTX_RTSP_PORT = os.getenv('MEDIAMTX_RTSP_PORT', '8554')


def print_header(text):
    print("\n" + "=" * 60)
    print(f" {text}")
    print("=" * 60)


def check_ffmpeg():
    """Verifica que FFmpeg este instalado y lista encoders."""
    print_header("VERIFICANDO FFMPEG")

    try:
        result = subprocess.run(['ffmpeg', '-version'], capture_output=True, text=True, timeout=10)
        print("FFmpeg instalado:")
        print(result.stdout.split('\n')[0])
    except FileNotFoundError:
        print("ERROR: FFmpeg no esta instalado!")
        print("Instalar con: sudo apt install ffmpeg")
        return False
    except Exception as e:
        print(f"ERROR: {e}")
        return False

    print("\nEncoders H264 disponibles:")
    try:
        result = subprocess.run(['ffmpeg', '-encoders'], capture_output=True, text=True, timeout=10)
        for line in result.stdout.split('\n'):
            if 'h264' in line.lower() or '264' in line:
                print(f"  {line.strip()}")
    except Exception as e:
        print(f"ERROR listando encoders: {e}")

    return True


def check_mediamtx_connection():
    """Verifica conectividad a MediaMTX."""
    print_header("VERIFICANDO CONEXION A MEDIAMTX")

    print(f"Host: {MEDIAMTX_HOST}")
    print(f"Puerto RTSP: {MEDIAMTX_RTSP_PORT}")

    # Verificar con netcat o ping
    import socket
    try:
        sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        sock.settimeout(5)
        result = sock.connect_ex((MEDIAMTX_HOST, int(MEDIAMTX_RTSP_PORT)))
        sock.close()

        if result == 0:
            print(f"OK: Puerto {MEDIAMTX_RTSP_PORT} accesible")
            return True
        else:
            print(f"ERROR: No se puede conectar al puerto {MEDIAMTX_RTSP_PORT}")
            return False
    except Exception as e:
        print(f"ERROR: {e}")
        return False


def test_ffmpeg_rtsp_publish():
    """Prueba publicar un stream de prueba a MediaMTX."""
    print_header("PROBANDO PUBLICACION RTSP")

    output_url = f"rtsp://{MEDIAMTX_HOST}:{MEDIAMTX_RTSP_PORT}/test_stream"
    print(f"URL de prueba: {output_url}")

    # Generar video de prueba (patron de colores) y publicar
    cmd = [
        'ffmpeg',
        '-y',
        '-f', 'lavfi',
        '-i', 'testsrc=duration=5:size=640x480:rate=15',
        '-c:v', 'libx264',
        '-preset', 'ultrafast',
        '-tune', 'zerolatency',
        '-pix_fmt', 'yuv420p',
        '-f', 'rtsp',
        '-rtsp_transport', 'tcp',
        output_url
    ]

    print(f"\nComando: {' '.join(cmd)}")
    print("\nEjecutando (5 segundos)...")

    try:
        result = subprocess.run(cmd, capture_output=True, text=True, timeout=15)

        if result.returncode == 0:
            print("OK: Publicacion exitosa!")
            return True
        else:
            print(f"ERROR: FFmpeg retorno codigo {result.returncode}")
            print("\nSTDERR (ultimas lineas):")
            stderr_lines = result.stderr.split('\n')
            for line in stderr_lines[-20:]:
                if line.strip():
                    print(f"  {line}")
            return False

    except subprocess.TimeoutExpired:
        print("TIMEOUT: FFmpeg no termino en tiempo esperado")
        return False
    except Exception as e:
        print(f"ERROR: {e}")
        return False


def test_ffmpeg_pipe_rtsp():
    """Prueba publicar via pipe (como lo hace el VisionManager)."""
    print_header("PROBANDO PUBLICACION VIA PIPE")

    import numpy as np

    output_url = f"rtsp://{MEDIAMTX_HOST}:{MEDIAMTX_RTSP_PORT}/test_pipe"
    width, height, fps = 640, 480, 15

    cmd = [
        'ffmpeg',
        '-y',
        '-f', 'rawvideo',
        '-vcodec', 'rawvideo',
        '-pix_fmt', 'bgr24',
        '-s', f'{width}x{height}',
        '-r', str(fps),
        '-i', '-',
        '-c:v', 'libx264',
        '-preset', 'ultrafast',
        '-tune', 'zerolatency',
        '-pix_fmt', 'yuv420p',
        '-f', 'rtsp',
        '-rtsp_transport', 'tcp',
        output_url
    ]

    print(f"URL: {output_url}")
    print(f"Resolucion: {width}x{height} @ {fps}fps")
    print(f"\nComando: {' '.join(cmd)}")
    print("\nEnviando 30 frames de prueba...")

    try:
        process = subprocess.Popen(
            cmd,
            stdin=subprocess.PIPE,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            bufsize=10 ** 8
        )

        # Esperar un momento para que FFmpeg inicie
        time.sleep(1)

        if process.poll() is not None:
            stderr = process.stderr.read().decode('utf-8', errors='ignore')
            print(f"ERROR: FFmpeg termino inmediatamente")
            print(f"\nSTDERR:\n{stderr[-1000:]}")
            return False

        # Enviar frames de prueba
        for i in range(30):
            # Crear frame con gradiente
            frame = np.zeros((height, width, 3), dtype=np.uint8)
            frame[:, :, 0] = (i * 8) % 256  # Blue
            frame[:, :, 1] = 128  # Green
            frame[:, :, 2] = 255 - (i * 8) % 256  # Red

            try:
                process.stdin.write(frame.tobytes())
                process.stdin.flush()
            except BrokenPipeError:
                print(f"ERROR: Pipe roto en frame {i}")
                stderr = process.stderr.read().decode('utf-8', errors='ignore')
                print(f"\nSTDERR:\n{stderr[-1000:]}")
                return False

            time.sleep(1.0 / fps)

        # Cerrar
        process.stdin.close()
        process.terminate()
        process.wait(timeout=5)

        print("OK: Publicacion via pipe exitosa!")
        return True

    except Exception as e:
        print(f"ERROR: {e}")
        return False


def print_mediamtx_config():
    """Muestra configuracion recomendada de MediaMTX."""
    print_header("CONFIGURACION RECOMENDADA DE MEDIAMTX")

    print("""
Para que MediaMTX acepte streams RTSP de entrada, asegurate de que 
mediamtx.yml tenga esta configuracion:

-------------------------------------------
# mediamtx.yml

# Permitir publicacion sin autenticacion
paths:
  all:
    # Permitir que cualquiera publique
    publishUser:
    publishPass:

    # O bien, comentar estas lineas si no existen

  # Stream procesado por IA (se crea automaticamente)
  cam_1001_ai:

  cam_1002_ai:

# Asegurar que RTSP esta habilitado
rtspDisable: no
rtspAddress: :8554
-------------------------------------------

Reinicia MediaMTX despues de cambiar la configuracion:
  sudo systemctl restart mediamtx
  # o
  ./mediamtx
""")


def main():
    print("\n" + "=" * 60)
    print(" DIAGNOSTICO CISTEM VISION - FFMPEG/MEDIAMTX")
    print("=" * 60)

    results = []

    # Verificar FFmpeg
    results.append(("FFmpeg instalado", check_ffmpeg()))

    # Verificar conexion
    results.append(("Conexion MediaMTX", check_mediamtx_connection()))

    # Probar publicacion directa
    results.append(("Publicacion directa", test_ffmpeg_rtsp_publish()))

    # Probar publicacion via pipe
    results.append(("Publicacion via pipe", test_ffmpeg_pipe_rtsp()))

    # Mostrar configuracion
    print_mediamtx_config()

    # Resumen
    print_header("RESUMEN")
    all_ok = True
    for name, ok in results:
        status = "OK" if ok else "FALLO"
        print(f"  {name}: {status}")
        if not ok:
            all_ok = False

    if all_ok:
        print("\n✅ Todo funciona correctamente!")
    else:
        print("\n❌ Hay problemas que resolver.")
        print("   Revisa los errores arriba y la configuracion de MediaMTX.")

    return 0 if all_ok else 1


if __name__ == "__main__":
    sys.exit(main())