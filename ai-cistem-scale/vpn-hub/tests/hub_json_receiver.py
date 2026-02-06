from flask import Flask
from flask_socketio import SocketIO, emit

app = Flask(__name__)
socketio = SocketIO(app, cors_allowed_origins="*")

@socketio.on("connect")
def handle_connect():
    print("Cliente conectado")

@socketio.on("data")
def handle_data(data):
    print("JSON recibido:", data)
    emit("response", {"status": "ok"})  

@socketio.on("disconnect")
def handle_disconnect():
    print("Cliente desconectado")

if __name__ == "__main__":
    socketio.run(app, host="10.0.0.1", port=9000)
