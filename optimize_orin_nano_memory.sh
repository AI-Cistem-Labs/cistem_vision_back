#!/bin/bash
# optimize_orin_nano_memory.sh
# Optimización AGRESIVA de memoria para Jetson Orin Nano 8GB con 8 cámaras

echo "🔧 OPTIMIZACIÓN AGRESIVA: Orin Nano 8GB para 8 cámaras RTSP"
echo "================================================================"

# 1. ⭐ SWAP de 16GB (crítico para 8 cámaras)
echo ""
echo "📦 Paso 1: Configurando SWAP de 16GB..."
if [ -f /swapfile ]; then
    echo "   Removiendo swap anterior..."
    sudo swapoff /swapfile
    sudo rm /swapfile
fi

echo "   Creando swap de 16GB (esto puede tardar 2-3 minutos)..."
sudo fallocate -l 16G /swapfile
sudo chmod 600 /swapfile
sudo mkswap /swapfile
sudo swapon /swapfile

# Hacer permanente
if ! grep -q '/swapfile' /etc/fstab; then
    echo '/swapfile none swap sw 0 0' | sudo tee -a /etc/fstab
fi

# ⭐ Ajustar swappiness (cuándo usar swap)
sudo sysctl vm.swappiness=10  # Usar swap solo cuando sea necesario
echo "vm.swappiness=10" | sudo tee -a /etc/sysctl.conf

echo "   ✅ Swap de 16GB configurado"

# 2. ⭐ Modo MAX Performance
echo ""
echo "⚡ Paso 2: Activando MAX Performance..."
sudo nvpmodel -m 0  # Modo 0 = MAXN (máximo rendimiento)
sudo jetson_clocks   # Clocks al máximo

echo "   ✅ Modo MAXN activado"

# 3. ⭐ Limpiar cache del sistema
echo ""
echo "🧹 Paso 3: Limpiando cache..."
sync
sudo sh -c 'echo 3 > /proc/sys/vm/drop_caches'

echo "   ✅ Cache limpiado"

# 4. ⭐ Deshabilitar servicios innecesarios
echo ""
echo "🛑 Paso 4: Deshabilitando servicios innecesarios..."

# Detener GUI si está corriendo (libera ~400MB)
read -p "   ¿Deshabilitar interfaz gráfica para liberar ~400MB RAM? (y/n): " disable_gui
if [ "$disable_gui" = "y" ]; then
    sudo systemctl set-default multi-user.target
    echo "   ✅ GUI deshabilitada (reiniciar para aplicar)"
    echo "      Para volver a habilitar: sudo systemctl set-default graphical.target"
fi

# 5. ⭐ Optimizar parámetros del kernel
echo ""
echo "🔧 Paso 5: Optimizando kernel para video..."

# Aumentar límites de memoria compartida
sudo sysctl -w kernel.shmmax=4294967296  # 4GB
sudo sysctl -w kernel.shmall=1073741824  # 4GB / 4KB

# Optimizar red para RTSP
sudo sysctl -w net.core.rmem_max=134217728  # 128MB buffer de recepción
sudo sysctl -w net.core.wmem_max=134217728  # 128MB buffer de envío

# Hacer permanente
cat << EOF | sudo tee -a /etc/sysctl.conf
# Optimizaciones para video RTSP
kernel.shmmax=4294967296
kernel.shmall=1073741824
net.core.rmem_max=134217728
net.core.wmem_max=134217728
EOF

echo "   ✅ Kernel optimizado"

# 6. ⭐ Verificar estado
echo ""
echo "================================================================"
echo "📊 ESTADO FINAL:"
echo "================================================================"

echo ""
echo "💾 Memoria RAM:"
free -h

echo ""
echo "💿 Swap:"
swapon --show

echo ""
echo "⚡ Modo de rendimiento:"
sudo nvpmodel -q

echo ""
if command -v tegrastats &> /dev/null; then
    echo "🔥 GPU/CPU (primeros 3 segundos):"
    timeout 3 tegrastats
else
    echo "⚠️ tegrastats no disponible"
fi

echo ""
echo "================================================================"
echo "✅ OPTIMIZACIÓN COMPLETADA"
echo "================================================================"
echo ""
echo "📋 RECOMENDACIONES:"
echo "   1. Reiniciar sistema para aplicar todos los cambios"
echo "   2. Ejecutar backend con: ./run_optimized.sh"
echo "   3. Monitorear con: watch -n 1 'free -h && echo && sudo tegrastats'"
echo "   4. Configurar 2 cámaras en GPU, 6 en CPU"
echo ""
echo "⚠️ LÍMITES PARA 8 CÁMARAS:"
echo "   - Máximo 2 cámaras con GPU simultáneas"
echo "   - Resto en CPU (frame_skip=7 para CPU)"
echo "   - No abrir más de 4 streams de video simultáneos en frontend"
echo ""