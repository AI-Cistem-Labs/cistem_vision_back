# How to test if it works?
1. Establish the VPN connection using the VPN Edge Agent. Follow the setup instructions in the [VPN Edge Agent Setup Instructions](./readme.md) to configure.
2. In the `../tests` folder, they are two test scripts, `send_payload.py` and `hub_video_streamer.py`.

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
3. Ensure the hub server is running and accessible through the VPN connection, and run the `hub_json_receiver.py` script.
4. In the terminal, run the following command to execute the `send_payload.py` script:
   ```bash
   sudo -E ./env/bin/python tests/send_payload.py
   ```
5. The script will attempt to send a test payload to the hub server through the VPN connection. If successful, you should see a confirmation message in the hub indicating that the payload was sent successfully.

## Test 3: Hub Video Streamer Test
1. Open a terminal and navigate to the `./vpn-edge-agent/` directory.
2. Be sure you are running the VPN Edge Agent and the VPN connection is active (in parallel terminal).
3. In the terminal, run the following command to execute the `hub_video_streamer.py` script:
   ```bash
   sudo -E ./env/bin/python tests/hub_video_streamer.py
   ```
4. The script will expose an endpoint on the hub server that streams video frames captured from the edge device's camera through the VPN connection.
5. Open a web browser and navigate to `http://<HUB_SERVER_IP>:9100/video_feed` (replace `<HUB_SERVER_IP>` with the actual IP address of the hub server).
6. You should see the live video stream from the edge device's camera displayed in the browser.