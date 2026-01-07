import pandas as pd
from ..base import BaseAnalyticsSpecialist


class AlertsEngine(BaseAnalyticsSpecialist):
    def analyze(self, current_processor):
        if not current_processor or not current_processor.csv_path:
            return

        try:
            df = pd.read_csv(current_processor.csv_path)
            if df.empty: return

            last_row = df.iloc[-1]
            # Ejemplo: Alerta si hay más de 10 personas
            if last_row['Count'] > 10:
                self.comms.send_data("alert_event", {
                    "type": "alert",
                    "level": "WARNING",
                    "msg": "Aforo alto detectado"
                })
        except Exception:
            pass