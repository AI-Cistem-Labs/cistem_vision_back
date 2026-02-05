import os
import subprocess
import requests

KEY_DIR = "keys"

def generar_claves():
    os.makedirs(KEY_DIR, exist_ok=True)

    private_key = f"{KEY_DIR}/private.key"
    public_key = f"{KEY_DIR}/public.key"

    if not os.path.exists(private_key):
        result = subprocess.run(
            ["wg", "genkey"],
            capture_output=True,
            text=True,
            check=True
        )

        priv = result.stdout.strip()

        with open(private_key, "w") as f:
            f.write(priv)

        result = subprocess.run(
            ["wg", "pubkey"],
            input=priv,
            capture_output=True,
            text=True,
            check=True
        )

        pub = result.stdout.strip()

        with open(public_key, "w") as f:
            f.write(pub)

    return private_key, public_key

def escribir_config(data, private_key_path):
    with open(private_key_path) as f:
        private_key = f.read().strip()

    config = f"""
[Interface]
PrivateKey = {private_key}
Address = {data['ip_virtual']}/24

[Peer]
PublicKey = {data['hub_public_key']}
Endpoint = {data['hub_endpoint']}
AllowedIPs = 10.0.0.0/24
PersistentKeepalive = 25
"""

    os.chmod("/etc/wireguard", 0o600)
    with open("/etc/wireguard/wg0.conf", "w") as f:
        f.write(config)

def levantar_tunel():
    try:
        subprocess.run(["wg", "show", "wg0"], check=True, stdout=subprocess.DEVNULL)
    except subprocess.CalledProcessError:
        subprocess.run(["wg-quick", "up", "wg0"], check=True)

def generar_nuevas_claves():
    subprocess.run(
        "wg genkey | tee keys/private.new | wg pubkey > keys/public.new",
        shell=True,
        check=True
    )

def solicitar_rotacion(hub_url, nombre, token):
    with open("keys/public.new") as f:
        pub = f.read().strip()

    r = requests.post(
        f"{hub_url}/rotate",
        json={
            "nombre": nombre,
            "public_key": pub,
            "token": token
        },
        timeout=10
    )
    r.raise_for_status()

def aplicar_nueva_clave():
    subprocess.run([
        "wg", "set", "wg0",
        "private-key", "keys/private.new"
    ], check=True)

    os.replace("keys/private.new", "keys/private.key")
    os.replace("keys/public.new", "keys/public.key")
