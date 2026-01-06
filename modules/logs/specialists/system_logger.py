from ..base import BaseLogSpecialist
import datetime

class SystemLogger(BaseLogSpecialist):
    def __init__(self, device_name, comms_module):
        super().__init__(device_name)
        self.comms = comms_module

    def update(self, message):
        # Nuevo formato de JSON solicitado
        log_payload = {
            "type": "log",
            "device": self.device_name,
            "date": datetime.datetime.now().strftime("%Y-%m-%d"),
            "msg": message
        }
        self.comms.send_data("log_event", log_payload)