import sqlite3

def iniciar_db():
    conn = sqlite3.connect(
        'vpn_hub.db',
        check_same_thread=False
    )
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()

    cursor.execute('''
        CREATE TABLE IF NOT EXISTS jetsons (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            nombre TEXT UNIQUE,
            public_key TEXT,
            ip_virtual TEXT,
            last_seen DATETIME,
            latency_ms REAL,
            status TEXT
        )
    ''')

    conn.commit()
    return conn

def asignar_ip_dinamica(conn, nombre, public_key):
    cursor = conn.cursor()
    cursor.execute(
        "SELECT public_key, ip_virtual FROM jetsons WHERE nombre=?",
        (nombre,)
    )
    resultado = cursor.fetchone()

    if resultado:
        if resultado["public_key"] != public_key:
            cursor.execute(
                "UPDATE jetsons SET public_key=? WHERE nombre=?",
                (public_key, nombre)
            )
            conn.commit()
        return resultado["ip_virtual"]

    cursor.execute(
        "SELECT ip_virtual FROM jetsons ORDER BY id DESC LIMIT 1"
    )
    last = cursor.fetchone()

    if last:
        last_octet = int(last["ip_virtual"].split(".")[-1])
        nueva_ip = f"10.0.0.{last_octet + 1}"
    else:
        nueva_ip = "10.0.0.2"

    cursor.execute(
        "INSERT INTO jetsons (nombre, public_key, ip_virtual) VALUES (?, ?, ?)",
        (nombre, public_key, nueva_ip)
    )
    conn.commit()

    return nueva_ip
