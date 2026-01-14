import os
import pandas as pd
import datetime


class CSVStorageSpecialist:
    def __init__(self, data_dir="data/"):
        self.data_dir = data_dir
        if not os.path.exists(self.data_dir):
            os.makedirs(self.data_dir)

    def _get_next_id(self, file_path, id_field):
        """Calcula el siguiente ID incremental basándose en el archivo actual."""
        if not os.path.exists(file_path):
            return 1
        try:
            df = pd.read_csv(file_path)
            if df.empty: return 1
            return int(df[id_field].max()) + 1
        except:
            return 1

    def save_event(self, cam_id, data_dict):
        """Guarda un log o alerta y le asigna un ID y estado inicial."""
        type_data = data_dict.get("type", "log")
        file_path = os.path.join(self.data_dir, f"cam_{cam_id}_{type_data}.csv")

        id_field = "alert_id" if type_data == "alert" else "log_id"
        data_dict[id_field] = self._get_next_id(file_path, id_field)

        if type_data == "alert":
            data_dict["read"] = False  # Estado inicial para alertas nuevas

        df = pd.DataFrame([data_dict])
        df.to_csv(file_path, mode='a', index=False, header=not os.path.exists(file_path))
        return data_dict

    def load_data(self, cam_id, type_data, limit=20):
        """Carga el historial desde el CSV."""
        file_path = os.path.join(self.data_dir, f"cam_{cam_id}_{type_data}.csv")
        if not os.path.exists(file_path): return []
        try:
            df = pd.read_csv(file_path)
            return df.tail(limit).to_dict('records')
        except:
            return []

    def mark_as_read(self, cam_id, alert_id):
        """Modifica el campo 'read' de una alerta específica."""
        file_path = os.path.join(self.data_dir, f"cam_{cam_id}_alert.csv")
        if not os.path.exists(file_path): return False
        try:
            df = pd.read_csv(file_path)
            if alert_id in df['alert_id'].values:
                df.loc[df['alert_id'] == alert_id, 'read'] = True
                df.to_csv(file_path, index=False)
                return True
            return False
        except:
            return False

    def mark_all_as_read(self, cam_id):
        """Marca todas las alertas de la cámara como leídas."""
        file_path = os.path.join(self.data_dir, f"cam_{cam_id}_alert.csv")
        if not os.path.exists(file_path): return 0
        try:
            df = pd.read_csv(file_path)
            count = len(df[df['read'] == False])
            df['read'] = True
            df.to_csv(file_path, index=False)
            return count
        except:
            return 0

    def delete_alert(self, cam_id, alert_id):
        """Elimina físicamente una fila del CSV por su ID."""
        file_path = os.path.join(self.data_dir, f"cam_{cam_id}_alert.csv")
        if not os.path.exists(file_path): return False
        try:
            df = pd.read_csv(file_path)
            if alert_id in df['alert_id'].values:
                df = df[df['alert_id'] != alert_id]  # Filtramos para excluir el ID
                df.to_csv(file_path, index=False)
                return True
            return False
        except:
            return False