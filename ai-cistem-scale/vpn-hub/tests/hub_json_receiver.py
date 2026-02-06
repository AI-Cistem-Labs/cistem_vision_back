from flask import Flask, request, jsonify

app = Flask(__name__)

@app.route("/data", methods=["POST"])
def receive_data():
    data = request.json
    print("JSON recibido:", data)
    return jsonify({"status": "ok"})

app.run(host="10.0.0.1", port=9000)
