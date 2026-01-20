# Data Directory

Esta carpeta almacena los archivos CSV generados por los procesadores de IA.

## Estructura de Archivos

Cada procesador genera su propio archivo CSV con el formato:
```
{processor_name}_{cam_id}_{date}.csv
```

### Ejemplos:
- `person_count_1001_2026-01-20.csv`
- `intrusion_1001_2026-01-20.csv`

## Formato por Procesador

### Person Counter
```csv
timestamp,person_count,alert_level
2026-01-20T10:30:00.000Z,5,NORMAL
2026-01-20T10:30:01.000Z,12,WARNING
```

### Intrusion Detector
```csv
timestamp,intrusion_detected,confidence,zone
2026-01-20T10:30:00.000Z,True,75.5,Sector A3
2026-01-20T10:30:05.000Z,False,0,Sector A3
```

## Nota
Los archivos en esta carpeta son ignorados por Git (`.gitignore`).
Solo se suben a producción cuando sea necesario para análisis.