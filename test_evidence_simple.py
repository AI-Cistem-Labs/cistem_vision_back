#!/usr/bin/env python3
"""
test_evidence_simple.py

Prueba simple de guardado de evidencias
"""
import sys
import os

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from modules.robot.evidence_saver import save_evidence_from_base64

# Imagen pequeña de prueba en base64 (1x1 pixel rojo)
TEST_IMAGE_BASE64 = "data:image/jpeg;base64,/9j/4AAQSkZJRgABAQEAYABgAAD//gA7Q1JFQVRPUjogZ2QtanBlZyB2MS4wICh1c2luZyBJSkcgSlBFRyB2NjIpLCBxdWFsaXR5ID0gOTAK/9sAQwADAgIDAgIDAwMDBAMDBAUIBQUEBAUKBwcGCAwKDAwLCgsLDQ4SEA0OEQ4LCxAWEBETFBUVFQwPFxgWFBgSFBUU/8AAEQgAAQABAwERAAIRAQMRAf/EABYAAQEBAAAAAAAAAAAAAAAAAAACBf/EAB8QAAEDBQEBAAAAAAAAAAAAAAABAgMRBBITI8HxMf/EABYBAQEBAAAAAAAAAAAAAAAAAAIDBP/EABwRAAICAgMAAAAAAAAAAAAAAAECABEhAxIxQf/aAAwDAQACEQMRAD8AuOFeT8D8EvCbqSVCPLh6f//Z"


def main():
    print("\n" + "=" * 70)
    print("🧪 TEST SIMPLE - Guardado de Evidencia")
    print("=" * 70 + "\n")

    result = save_evidence_from_base64(
        base64_data=TEST_IMAGE_BASE64,
        alert_id=999,
        device_id=1
    )

    if result:
        print("✅ ÉXITO!")
        print("=" * 70)
        print(f"📁 URL: {result['url']}")
        print(f"💾 Path local: {result['local_path']}")
        print(f"📦 Tamaño: {result['size_bytes']} bytes")
        print("=" * 70)
        print(f"\n💡 Accede a: http://localhost:5000{result['url']}")
    else:
        print("❌ ERROR: No se pudo guardar")

    print()


if __name__ == '__main__':
    main()