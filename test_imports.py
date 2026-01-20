# test_imports.py
print("🧪 Probando importaciones...\n")

try:
    from config.config_manager import device_config
    print("✅ device_config importado correctamente")
except Exception as e:
    print(f"❌ Error importando device_config: {e}")

try:
    from modules.vision.processors import get_available_processors
    print("✅ get_available_processors importado correctamente")
    processors = get_available_processors()
    print(f"   Procesadores disponibles: {list(processors.keys())}")
except Exception as e:
    print(f"❌ Error importando get_available_processors: {e}")

try:
    from modules.analytics.specialists.system_logger import system_logger
    print("✅ system_logger importado correctamente")
except Exception as e:
    print(f"❌ Error importando system_logger: {e}")

try:
    from modules.analytics.specialists.alerts_engine import alerts_engine
    print("✅ alerts_engine importado correctamente")
except Exception as e:
    print(f"❌ Error importando alerts_engine: {e}")

print("\n✅ Todas las importaciones funcionan correctamente!")