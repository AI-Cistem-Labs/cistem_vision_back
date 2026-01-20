# test_vision.py
print("🧪 Probando VisionManager...\n")

from modules.vision.manager import VisionManager
from modules.vision.processors import get_available_processors

# Ver procesadores disponibles
processors = get_available_processors()
print(f"✅ Procesadores disponibles: {processors}\n")

# Crear VisionManager
vision_manager = VisionManager()
print("✅ VisionManager creado\n")

print("✅ Prueba exitosa!")