# modules/vision/processors/__init__.py

from .base import BaseVisionProcessor
from .yolo_counter import YoloCounterProcessor

__all__ = ['BaseVisionProcessor', 'YoloCounterProcessor']