#!/bin/bash
# install_optimizations.sh
# Instalación automatizada de optimizaciones para Orin Nano 8GB

echo "🚀 INSTALACIÓN: Optimizaciones Orin Nano 8GB para 7+ cámaras"
echo "================================================================"

# 1. Copiar GPU Manager
echo "📦 Instalando GPU Manager..."
cp gpu_manager.py modules/vision/

# 2. Copiar Video Stream Optimizer
echo "📦 Instalando Video Stream Optimizer..."
cp video_stream_optimizer.py modules/vision/

# 3. Backup de procesadores actuales
echo "💾 Creando backup de procesadores..."
mkdir -p backups
cp modules/vision/processors/person_counter_processor.py backups/
cp modules/vision/processors/intrusion_detector_processor.py backups/
cp modules/vision/processors/flow_cars_processor.py backups/

# 4. Copiar procesadores optimizados
echo "📦 Instalando procesadores optimizados..."
cp person_counter_processor.py modules/vision/processors/
cp intrusion_detector_processor.py modules/vision/processors/
cp flow_cars_processor.py modules/vision/processors/

# 5. Actualizar video_controller.py
echo "📦 Actualizando video_controller.py..."
# Agregar import al inicio
if ! grep -q "from modules.vision.video_stream_optimizer import get_stream_optimizer" controllers/video_controller.py; then
    sed -i '/from modules.vision.manager import VisionManager/a from modules.vision.video_stream_optimizer import get_stream_optimizer' controllers/video_controller.py
fi

echo ""
echo "================================================================"
echo "✅ INSTALACIÓN COMPLETADA"
echo "================================================================"
echo ""
echo "📋 PRÓXIMOS PASOS:"
echo "1. Ejecutar: sudo ./optimize_system.sh"
echo "2. Reiniciar sistema"
echo "3. Ejecutar backend: python3 app.py"
echo ""
echo "🎯 RESULTADO ESPERADO:"
echo "   - 2 cámaras en GPU (1001, 1003 - Intrusion Detector)"
echo "   - 5 cámaras en CPU (resto)"
echo "   - Máximo 4 streams de video simultáneos"
echo "   - Memoria < 7GB con todas las cámaras activas"
echo ""