import requests

def registrar_en_hub(hub_url, nombre, public_key, token):
    with open(public_key) as f:
        pub = f.read().strip()

    payload = {
        "nombre": nombre,
        "public_key": pub,
        "token": token
    }

    r = requests.post(f"{hub_url}/registrar", json=payload, timeout=10)
    # r.raise_for_status()
    if not r.ok: 
        print("STATUS: ", r.status_code)
        print("RESPONSE: ", r.text)
        r.raise_for_status()
    return r.json()
