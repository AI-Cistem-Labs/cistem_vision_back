# How to test if it works?
1. Establish the VPN connection using the VPN Edge Agent. Follow the setup instructions in the [VPN Edge Agent Setup Instructions](./readme.md) to configure.
2. In the `../tests` folder, they are two test scripts, `client_payload.js` and `hub_video_streamer.py`.

## Test 1: Curl Test
1. Open a terminal and navigate to the `./vpn-edge-agent/` directory.
2. Be sure you are running the VPN Edge Agent and the VPN connection is active (in parallel terminal).
3. Ensure the hub server is running and accessible through the VPN connection.
4. In the hub, run the `test_server.py` script to start a simple HTTP server that responds to ping requests:
   ```bash
   sudo -E ./env/bin/python tests/test_server.py
   ```
5. In the terminal, run the following command to send a test request to the hub server:
   ```bash
   curl http://10.0.0.1:8080/ping
   ```
6. If the VPN connection is working correctly, you should receive a response from the hub server indicating that the ping was successful, such as:
   ```json
   {
     "status": "ok",
     "msg": "VPN tunnel working"
   }
   ```

## Test 2: Send Payload Test
1. Open a terminal and navigate to the `./vpn-edge-agent/` directory.
2. Be sure you are running the VPN Edge Agent and the VPN connection is active (in parallel terminal).
3. Ensure the **hub** server is running and accessible through the VPN connection, and run the `hub_json_receiver.py` script, this script has code related to events so it needs to be running to receive the payload.
4. Install the required dependencies in the **agent** for the `client_payload.py` script if you haven't already:
   ```bash
   pip install python-socketio
   ```
5. In the terminal of the **agent**, run the following command to execute the `client_payload.py` script:
   ```bash
   python tests/client_payload.py
   ```
6. The script will attempt to send a test payload to the hub server through the VPN connection. If successful, you should see a confirmation message in the **agent** indicating that the payload was sent successfully.
   ```bash
   Conectado
   Respuesta: {status:'ok'}
   ```
7. And in the **hub** terminal, you should see the received payload:
   ```bash
   10.0.0.2 - - [06/Feb/2026 02:41:39] "GET /socket.io/?transport=polling&EIO=4&sid=dJ7uaaMLPH9maUvlAAAA&t=1770367299.34054
   JSON recibido: {'mensaje': 'Hola servidor'}
   ```

## Test 3: Hub Video Streamer Test
### Dependencies
Before running the test, make sure you have the necessary dependencies installed. You can install them using the following command:
> Disclaimer: The following command is for Arch Linux. If you are using a different distribution, please use the appropriate package manager and package names for your system.
```bash
sudo pacman -S \
    gstreamer \
    gst-plugins-base \
    gst-plugins-good \
    gst-plugins-bad \
    gst-plugins-ugly \
    gst-libav \
    gst-rtsp-server \
    python-gobject \
    gobject-introspection \
    v4l-utils
```
### Execution steps
Open a terminal on the **edge device** and navigate to the `./vpn-edge-agent/` directory. Be sure you are running the VPN Edge Agent and the VPN connection is active (in parallel terminal). **IMPORTANT:** This script must be executed with the **system python**, not the virtual environment python, because it relies on system-wide installed GStreamer libraries. Run the following command to execute the `hub_video_streamer.py` script:
```bash
/usr/bin/python tests/hub_video_streamer.py
```
If the script starts correctly, you should see an output similar to:
```bash
RTSP activo en rtsp://<EDGE_DEVICE_IP>:8554/stream
```
The RTSP server is now running and streaming live video from the edge device camera through the VPN.

### Accessing the stream
From the **hub server** (or any device connected to the VPN), open a media client (it is recommended to use `ffplay` for testing) and connect to the RTSP stream using the following command, replacing `<EDGE_DEVICE_VPN_IP>` with the VPN IP address of the edge device (ej. 10.0.0.2):
```bash
ffplay rtsp://<EDGE_DEVICE_VPN_IP>:8554/stream
``` 
You should see the live video stream from the edge device’s camera, transmitted over RTSP through the VPN tunnel.

### Considerations
* This test **does not use http**.
* It does not expose a `/video_feed` endpoint.
* It does not work in a web browser, you need to use a media client that supports RTSP streaming, such as `ffplay`, `VLC`, or `GStreamer` itself. 