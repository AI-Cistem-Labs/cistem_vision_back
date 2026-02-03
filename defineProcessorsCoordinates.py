#!/usr/bin/env python3
"""
Script independiente para definir ROIs y obtener coordenadas
Uso: python define_roi_coordinates.py

Este script te permite:
1. Conectar a una cámara por RTSP
2. Dibujar ROIs con el mouse (polígonos o líneas)
3. Obtener las coordenadas exactas para copiar/pegar en tu procesador

Autor: Sistema Cistem Vision
Fecha: 2025-02-02
"""

import cv2
import numpy as np
from datetime import datetime


class ROIDefiner:
    """
    Herramienta para definir ROIs y obtener coordenadas
    """

    def __init__(self):
        self.drawing_points = []
        self.window_name = "Definir ROI - Cistem Vision"
        self.snapshot = None
        self.roi_type = 'polygon'  # 'polygon' o 'line'

    def mouse_callback(self, event, x, y, flags, param):
        """Callback para eventos del mouse"""
        if event == cv2.EVENT_LBUTTONDOWN:
            # Click izquierdo: agregar punto
            self.drawing_points.append([x, y])
            print(f"  ➕ Punto agregado: ({x}, {y})")

        elif event == cv2.EVENT_RBUTTONDOWN:
            # Click derecho: eliminar último punto
            if self.drawing_points:
                removed = self.drawing_points.pop()
                print(f"  ➖ Punto eliminado: {removed}")

    def capture_snapshot(self, rtsp_url):
        """
        Captura un frame de la cámara RTSP

        Args:
            rtsp_url: URL RTSP de la cámara

        Returns:
            numpy.ndarray: Frame capturado o None si falla
        """
        print("\n" + "=" * 70)
        print("📷 CAPTURANDO SNAPSHOT DE LA CÁMARA")
        print("=" * 70)
        print(f"URL: {rtsp_url}")
        print("Conectando...")

        cap = cv2.VideoCapture(rtsp_url)

        if not cap.isOpened():
            print("❌ ERROR: No se pudo conectar a la cámara")
            print("   Verifica:")
            print("   - La URL RTSP es correcta")
            print("   - La cámara está encendida")
            print("   - Hay conexión de red")
            return None

        # Capturar varios frames (los primeros pueden estar corruptos)
        print("Capturando frames...")
        frame = None
        for i in range(10):
            ret, frame = cap.read()
            if ret:
                print(f"✅ Frame capturado exitosamente ({i + 1}/10)")
                break

        cap.release()

        if frame is None:
            print("❌ ERROR: No se pudo capturar ningún frame")
            return None

        # Mostrar información del frame
        h, w = frame.shape[:2]
        print(f"\n📐 Resolución: {w}x{h}")
        print("✅ Snapshot capturado correctamente")

        return frame

    def draw_roi_interface(self, instruction_text="Dibuja el ROI"):
        """
        Interfaz interactiva para dibujar ROI

        Args:
            instruction_text: Texto de instrucciones

        Returns:
            list: Lista de puntos [(x,y), ...] o None si se cancela
        """
        if self.snapshot is None:
            print("❌ ERROR: No hay snapshot cargado")
            return None

        self.drawing_points = []

        cv2.namedWindow(self.window_name)
        cv2.setMouseCallback(self.window_name, self.mouse_callback)

        print("\n" + "=" * 70)
        print("🎨 MODO DIBUJO")
        print("=" * 70)
        print(f"Tipo: {self.roi_type.upper()}")
        print("\nControles:")
        print("  • Click Izquierdo: Agregar punto")
        print("  • Click Derecho: Borrar último punto")
        print("  • ENTER: Confirmar ROI")
        print("  • ESC: Cancelar")
        print("=" * 70)

        if self.roi_type == 'line':
            print("\n💡 Para LÍNEA: Necesitas exactamente 2 puntos")
        else:
            print("\n💡 Para POLÍGONO: Necesitas mínimo 3 puntos")

        print("\nEmpeza a dibujar...\n")

        while True:
            img_copy = self.snapshot.copy()

            # Panel de instrucciones
            cv2.rectangle(img_copy, (0, 0), (900, 100), (0, 0, 0), -1)

            # Título
            cv2.putText(img_copy, instruction_text, (20, 35),
                        cv2.FONT_HERSHEY_SIMPLEX, 0.8, (0, 255, 0), 2)

            # Instrucciones
            cv2.putText(img_copy, "Click Izq: Punto | Click Der: Borrar | ENTER: OK | ESC: Cancelar",
                        (20, 70), cv2.FONT_HERSHEY_SIMPLEX, 0.6, (255, 255, 255), 1)

            # Contador de puntos
            num_points = len(self.drawing_points)
            color_count = (0, 255, 0) if num_points >= 2 else (0, 165, 255)
            cv2.putText(img_copy, f"Puntos: {num_points}", (20, 95),
                        cv2.FONT_HERSHEY_SIMPLEX, 0.6, color_count, 2)

            # Dibujar puntos y líneas
            if len(self.drawing_points) > 0:
                pts = np.array(self.drawing_points, np.int32).reshape((-1, 1, 2))

                if self.roi_type == 'polygon':
                    # Polígono
                    cv2.polylines(img_copy, [pts], True, (0, 255, 255), 2)

                    # Rellenar con transparencia
                    if len(self.drawing_points) > 2:
                        overlay = img_copy.copy()
                        cv2.fillPoly(overlay, [pts], (0, 255, 255))
                        cv2.addWeighted(overlay, 0.3, img_copy, 0.7, 0, img_copy)

                elif self.roi_type == 'line':
                    # Línea
                    if len(self.drawing_points) >= 2:
                        cv2.line(img_copy,
                                 tuple(self.drawing_points[0]),
                                 tuple(self.drawing_points[1]),
                                 (0, 255, 255), 3)
                    elif len(self.drawing_points) == 1:
                        cv2.circle(img_copy, tuple(self.drawing_points[0]), 5, (0, 255, 255), -1)

                # Dibujar todos los puntos
                for i, pt in enumerate(self.drawing_points):
                    cv2.circle(img_copy, tuple(pt), 6, (0, 255, 255), -1)
                    cv2.circle(img_copy, tuple(pt), 8, (255, 255, 255), 2)
                    # Numerar puntos
                    cv2.putText(img_copy, str(i + 1), (pt[0] + 10, pt[1] - 10),
                                cv2.FONT_HERSHEY_SIMPLEX, 0.5, (255, 255, 255), 2)

            cv2.imshow(self.window_name, img_copy)

            key = cv2.waitKey(1) & 0xFF

            # ENTER: Confirmar
            if key == 13:
                if self.roi_type == 'polygon' and len(self.drawing_points) >= 3:
                    print("\n✅ ROI confirmado")
                    cv2.destroyWindow(self.window_name)
                    return self.drawing_points
                elif self.roi_type == 'line' and len(self.drawing_points) >= 2:
                    print("\n✅ Línea confirmada")
                    cv2.destroyWindow(self.window_name)
                    return self.drawing_points[:2]  # Solo primeros 2 puntos
                else:
                    min_points = 2 if self.roi_type == 'line' else 3
                    print(f"⚠️  Necesitas al menos {min_points} puntos")

            # ESC: Cancelar
            elif key == 27:
                print("\n❌ Operación cancelada")
                cv2.destroyWindow(self.window_name)
                return None

    def print_coordinates(self, points, roi_name, roi_type='polygon'):
        """
        Imprime las coordenadas en formato listo para copiar/pegar

        Args:
            points: Lista de puntos
            roi_name: Nombre del ROI
            roi_type: Tipo de ROI ('polygon' o 'line')
        """
        print("\n" + "=" * 70)
        print("📋 COORDENADAS GENERADAS")
        print("=" * 70)

        # Formato para Python (NumPy array)
        print(f"\n# {roi_name.upper()}")
        print(f"# Tipo: {roi_type}")
        print(f"# Puntos: {len(points)}")
        print(f"\n# Para usar en tu procesador:")
        print("-" * 70)

        print(f"\n{roi_name} = np.array([")
        for point in points:
            print(f"    [{point[0]}, {point[1]}],")
        print("], dtype=np.int32)")

        # Alternativa sin NumPy
        print(f"\n# O sin NumPy (lista simple):")
        print(f"{roi_name} = [")
        for point in points:
            print(f"    [{point[0]}, {point[1]}],")
        print("]")

        # Formato para JSON (si fuera necesario después)
        print(f"\n# Formato JSON (para configuración futura):")
        print(f'"{roi_name}": {{')
        print(f'  "type": "{roi_type}",')
        print(f'  "points": {points},')
        print(f'  "enabled": true,')
        if roi_type == 'polygon':
            print(f'  "color": [0, 0, 255]  # Rojo (B, G, R)')
        else:
            print(f'  "color": [0, 255, 255]  # Amarillo (B, G, R)')
        print('}')

        print("\n" + "=" * 70)
        print("✅ Copia el código de arriba y pégalo en tu procesador")
        print("=" * 70)


def main():
    """Función principal"""

    print("\n" + "=" * 70)
    print("🎯 CISTEM VISION - DEFINIDOR DE ROIs")
    print("   Genera coordenadas para hardcodear en procesadores")
    print("=" * 70)

    definer = ROIDefiner()

    # ========================================
    # PASO 1: Configuración de la cámara
    # ========================================
    print("\n📹 PASO 1: CONFIGURACIÓN DE LA CÁMARA")
    print("-" * 70)

    print("\nEjemplos de URLs RTSP:")
    print("  • rtsp://usuario:password@192.168.1.100:554/stream1")
    print("  • rtsp://admin:admin123@10.0.0.50/h264/ch1/main/av_stream")
    print("  • rtsp://192.168.1.64:554/stream")

    rtsp_url = input("\n🔗 Ingresa la URL RTSP de la cámara: ").strip()

    if not rtsp_url:
        print("❌ URL vacía. Saliendo...")
        return

    # Opción de usar imagen existente
    if rtsp_url.lower() in ['test', 'imagen', 'img']:
        img_path = input("📁 Ruta de la imagen de prueba: ").strip()
        snapshot = cv2.imread(img_path)
        if snapshot is None:
            print("❌ No se pudo cargar la imagen")
            return
    else:
        # Capturar snapshot
        snapshot = definer.capture_snapshot(rtsp_url)

        if snapshot is None:
            print("\n⚠️  No se pudo capturar snapshot en vivo")
            opcion = input("¿Usar imagen guardada en su lugar? (s/n): ").strip().lower()

            if opcion == 's':
                img_path = input("📁 Ruta de la imagen: ").strip()
                snapshot = cv2.imread(img_path)
                if snapshot is None:
                    print("❌ No se pudo cargar la imagen")
                    return
            else:
                print("❌ Saliendo...")
                return

    definer.snapshot = snapshot

    # ========================================
    # PASO 2: Definir ROIs
    # ========================================
    print("\n" + "=" * 70)
    print("📐 PASO 2: DEFINIR ROIs")
    print("=" * 70)

    rois_defined = []

    while True:
        print("\n" + "-" * 70)
        print("MENÚ DE ROIs")
        print("-" * 70)
        print("1. Agregar Zona Restringida (Polígono)")
        print("2. Agregar Línea de Conteo")
        print("3. Agregar Área de Interés (Polígono)")
        print("4. Ver resumen de ROIs definidos")
        print("5. Finalizar y mostrar código completo")
        print("0. Salir sin guardar")
        print("-" * 70)

        opcion = input("Selecciona opción: ").strip()

        if opcion == '1':
            # Zona restringida (polígono)
            print("\n🔴 ZONA RESTRINGIDA")
            nombre = input("Nombre del ROI (ej: zona_restringida): ").strip()
            nombre = nombre if nombre else "zona_restringida"

            definer.roi_type = 'polygon'
            points = definer.draw_roi_interface(f"Dibuja: {nombre.upper()}")

            if points:
                definer.print_coordinates(points, nombre, 'polygon')
                rois_defined.append({
                    'name': nombre,
                    'type': 'polygon',
                    'points': points,
                    'color': [0, 0, 255]  # Rojo
                })
                print(f"\n✅ ROI '{nombre}' agregado")

        elif opcion == '2':
            # Línea de conteo
            print("\n📏 LÍNEA DE CONTEO")
            nombre = input("Nombre de la línea (ej: linea_entrada): ").strip()
            nombre = nombre if nombre else "linea_entrada"

            definer.roi_type = 'line'
            points = definer.draw_roi_interface(f"Dibuja: {nombre.upper()} (2 puntos)")

            if points:
                definer.print_coordinates(points, nombre, 'line')
                rois_defined.append({
                    'name': nombre,
                    'type': 'line',
                    'points': points,
                    'color': [0, 255, 255]  # Amarillo
                })
                print(f"\n✅ Línea '{nombre}' agregada")

        elif opcion == '3':
            # Área de interés genérica
            print("\n🟢 ÁREA DE INTERÉS")
            nombre = input("Nombre del área (ej: area_acceso): ").strip()
            nombre = nombre if nombre else "area_interes"

            definer.roi_type = 'polygon'
            points = definer.draw_roi_interface(f"Dibuja: {nombre.upper()}")

            if points:
                definer.print_coordinates(points, nombre, 'polygon')
                rois_defined.append({
                    'name': nombre,
                    'type': 'polygon',
                    'points': points,
                    'color': [0, 255, 0]  # Verde
                })
                print(f"\n✅ ROI '{nombre}' agregado")

        elif opcion == '4':
            # Ver resumen
            if not rois_defined:
                print("\n⚠️  No hay ROIs definidos aún")
            else:
                print("\n" + "=" * 70)
                print(f"📋 ROIs DEFINIDOS ({len(rois_defined)})")
                print("=" * 70)

                for i, roi in enumerate(rois_defined, 1):
                    print(f"\n{i}. {roi['name']}")
                    print(f"   Tipo: {roi['type']}")
                    print(f"   Puntos: {len(roi['points'])}")
                    print(f"   Color: {roi['color']}")

                # Mostrar preview visual
                preview = snapshot.copy()
                for roi in rois_defined:
                    pts = np.array(roi['points'], np.int32).reshape((-1, 1, 2))
                    color = tuple(roi['color'])

                    if roi['type'] == 'polygon':
                        overlay = preview.copy()
                        cv2.fillPoly(overlay, [pts], color)
                        cv2.addWeighted(overlay, 0.3, preview, 0.7, 0, preview)
                        cv2.polylines(preview, [pts], True, color, 2)
                    else:
                        cv2.line(preview, tuple(roi['points'][0]),
                                 tuple(roi['points'][1]), color, 3)

                    # Etiqueta
                    x, y = roi['points'][0]
                    cv2.putText(preview, roi['name'], (x, y - 10),
                                cv2.FONT_HERSHEY_SIMPLEX, 0.7, color, 2)

                cv2.imshow("Preview - Todos los ROIs", preview)
                print("\nPresiona cualquier tecla para continuar...")
                cv2.waitKey(0)
                cv2.destroyAllWindows()

        elif opcion == '5':
            # Finalizar y mostrar código completo
            if not rois_defined:
                print("\n⚠️  No hay ROIs para generar código")
            else:
                print_final_code(rois_defined)
                break

        elif opcion == '0':
            # Salir
            confirmar = input("\n¿Seguro que quieres salir sin guardar? (s/n): ").strip().lower()
            if confirmar == 's':
                print("👋 Hasta luego")
                return

        else:
            print("❌ Opción inválida")

    print("\n✅ Proceso completado exitosamente")


def print_final_code(rois):
    """Imprime código completo listo para copiar/pegar en procesador"""

    print("\n" + "=" * 70)
    print("🎉 CÓDIGO COMPLETO PARA TU PROCESADOR")
    print("=" * 70)

    print("\n# ========================================")
    print("# ROIs DEFINIDOS - Copiar en __init__")
    print("# ========================================")
    print("\nimport numpy as np")
    print("\n# Dentro de __init__(self, cam_id):")

    for roi in rois:
        print(f"\n# {roi['name'].upper()}")
        print(f"self.{roi['name']} = np.array([")
        for point in roi['points']:
            print(f"    [{point[0]}, {point[1]}],")
        print("], dtype=np.int32)")

    print("\n\n# ========================================")
    print("# EJEMPLO DE USO EN process_frame()")
    print("# ========================================")

    for roi in rois:
        print(f"\n# Usar {roi['name']}:")
        if roi['type'] == 'polygon':
            print(f"""
# Verificar si punto está dentro
centro = (cx, cy)
if cv2.pointPolygonTest(self.{roi['name']}, centro, False) >= 0:
    # Punto está dentro de {roi['name']}
    print("Objeto en {roi['name']}")

# Dibujar el ROI
pts = self.{roi['name']}.reshape((-1, 1, 2))
overlay = frame.copy()
cv2.fillPoly(overlay, [pts], {roi['color']})
cv2.addWeighted(overlay, 0.3, frame, 0.7, 0, frame)
cv2.polylines(frame, [pts], True, {roi['color']}, 2)
""")
        else:  # line
            print(f"""
# Detectar cruce de línea
if prev_point and curr_point:
    # Calcular si cruza la línea
    line_p1 = tuple(self.{roi['name']}[0])
    line_p2 = tuple(self.{roi['name']}[1])
    # ... lógica de cruce ...

# Dibujar línea
cv2.line(frame, 
         tuple(self.{roi['name']}[0]), 
         tuple(self.{roi['name']}[1]), 
         {roi['color']}, 3)
""")

    print("\n" + "=" * 70)
    print("✅ Código generado - Listo para usar")
    print("=" * 70)

    # Guardar en archivo
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    filename = f"roi_coordinates_{timestamp}.py"

    with open(filename, 'w') as f:
        f.write("# ROIs generados automáticamente\n")
        f.write(f"# Fecha: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n\n")
        f.write("import numpy as np\n\n")

        for roi in rois:
            f.write(f"# {roi['name'].upper()}\n")
            f.write(f"{roi['name']} = np.array([\n")
            for point in roi['points']:
                f.write(f"    [{point[0]}, {point[1]}],\n")
            f.write("], dtype=np.int32)\n\n")

    print(f"\n📁 Código también guardado en: {filename}")


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print("\n\n⚠️  Proceso interrumpido por el usuario")
    except Exception as e:
        print(f"\n❌ Error: {str(e)}")
        import traceback

        traceback.print_exc()