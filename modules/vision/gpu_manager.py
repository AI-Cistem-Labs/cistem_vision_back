# modules/vision/gpu_manager.py
"""
GPU Manager para Jetson Orin Nano 8GB
Estrategia: 2 GPU + resto CPU con prioridad inteligente
"""
import torch
import logging
import gc

logger = logging.getLogger(__name__)


class GPUManager:
    """
    Gestor de GPU optimizado para Orin Nano 8GB

    Prioridad de procesadores:
    - ID 2 (Intrusion Detector): Prioridad 100 (crítico)
    - ID 3 (Flow Cars): Prioridad 80
    - ID 1 (Person Counter): Prioridad 60
    """
    _instance = None

    # ⭐ CRÍTICO: Solo 2 slots GPU para Orin Nano 8GB
    _max_gpu_slots = 2
    _gpu_slots_used = 0
    _gpu_assigned_cams = []  # Lista de cam_ids en GPU

    # Prioridad por procesador
    PROCESSOR_GPU_PRIORITY = {
        2: 100,  # Intrusion Detector (más complejo, zona + detección)
        3: 80,  # Flow Cars (4 clases de vehículos)
        1: 60,  # Person Counter (1 clase)
    }

    def __new__(cls):
        if cls._instance is None:
            cls._instance = super(GPUManager, cls).__new__(cls)
        return cls._instance

    def request_gpu_slot(self, cam_id: int, processor_id: int = None) -> bool:
        """
        Solicita GPU basado en prioridad del procesador
        """
        if not torch.cuda.is_available():
            logger.warning(f"[Cam {cam_id}] CUDA no disponible")
            return False

        # Si ya tiene slot, OK
        if cam_id in self._gpu_assigned_cams:
            return True

        # Si hay espacio, asignar
        if self._gpu_slots_used < self._max_gpu_slots:
            self._gpu_slots_used += 1
            self._gpu_assigned_cams.append(cam_id)

            priority = self.PROCESSOR_GPU_PRIORITY.get(processor_id, 0)
            logger.info(
                f"✅ [Cam {cam_id}] GPU slot {self._gpu_slots_used}/{self._max_gpu_slots} (Processor {processor_id}, Priority {priority})")
            return True

        # GPU llena
        logger.warning(f"⚠️ [Cam {cam_id}] GPU saturada ({self._gpu_slots_used}/{self._max_gpu_slots}), usando CPU")
        return False

    def release_gpu_slot(self, cam_id: int):
        """Libera slot de GPU y limpia memoria"""
        if cam_id in self._gpu_assigned_cams:
            self._gpu_assigned_cams.remove(cam_id)
            self._gpu_slots_used = max(0, self._gpu_slots_used - 1)
            logger.info(f"🔓 [Cam {cam_id}] GPU slot liberado ({self._gpu_slots_used}/{self._max_gpu_slots})")

            # Limpieza agresiva
            if torch.cuda.is_available():
                torch.cuda.empty_cache()
                torch.cuda.ipc_collect()
            gc.collect()

    def get_recommended_device(self, cam_id: int, processor_id: int = None) -> tuple:
        """
        Retorna (device, use_half) optimizado

        Returns:
            tuple: (device_string, use_half_precision)
        """
        if self.request_gpu_slot(cam_id, processor_id):
            return ('cuda:0', True)  # GPU + FP16
        else:
            return ('cpu', False)  # CPU + FP32

    def get_gpu_memory_info(self):
        """Retorna info detallada de memoria GPU"""
        if not torch.cuda.is_available():
            return None

        try:
            allocated = torch.cuda.memory_allocated(0) / 1024 ** 2  # MB
            reserved = torch.cuda.memory_reserved(0) / 1024 ** 2
            total = torch.cuda.get_device_properties(0).total_memory / 1024 ** 2

            return {
                'allocated_mb': allocated,
                'reserved_mb': reserved,
                'total_mb': total,
                'free_mb': total - reserved,
                'usage_percent': (reserved / total) * 100,
                'slots_used': self._gpu_slots_used,
                'slots_max': self._max_gpu_slots,
                'assigned_cams': self._gpu_assigned_cams.copy()
            }
        except Exception as e:
            logger.error(f"Error GPU info: {e}")
            return None

    def force_cleanup(self):
        """Limpieza agresiva de memoria"""
        if torch.cuda.is_available():
            torch.cuda.empty_cache()
            torch.cuda.ipc_collect()
        gc.collect()
        logger.info("🧹 Limpieza forzada de memoria ejecutada")


# Singleton global
_gpu_manager_instance = GPUManager()


def get_gpu_manager():
    """Retorna instancia del GPU Manager"""
    return _gpu_manager_instance