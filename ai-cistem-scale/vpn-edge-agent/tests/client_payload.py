import socketio

sio = socketio.Client()

@sio.event
def connect():
    print("Conectado")
    sio.emit("data", {"mensaje": "Hola servidor"})

@sio.on("response")
def on_response(msg):
    print("Respuesta:", msg)

@sio.event
def disconnect():
    print("Desconectado")

sio.connect("http://10.0.0.1:9000")
sio.wait()
