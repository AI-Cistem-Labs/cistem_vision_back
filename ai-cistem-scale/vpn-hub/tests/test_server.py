from flask import Flask, jsonify

app = Flask(__name__)

@app.route("/ping")
def ping():
    return jsonify({"status": "ok", "msg": "VPN tunnel working"})

if __name__ == "__main__":
    app.run(host="10.0.0.1", port=8080)
