print("📂 Inicializando paquete de controladores...")

# Importar todos los controladores
from . import auth_controller
from . import station_controller
from . import logs_controller
from . import alerts_controller
from . import camera_controller
from . import video_controller

print("✅ Todos los controladores importados correctamente")