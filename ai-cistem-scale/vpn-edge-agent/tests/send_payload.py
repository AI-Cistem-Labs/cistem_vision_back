import requests

payload = {
    "device": "edge-agent-01",
    "fps": 30,
    "resolution": "1920x1080"
}

r = requests.post("http://10.0.0.1:9000/data", json=payload, timeout=5)

print(r.json())