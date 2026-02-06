# VPN Edge Agent Setup Instructions
The VPN Edge Agent is the client component of the custom VPN solution. It connects to the VPN Hub and establishes a secure WireGuard connection.

## Requirements
* Linux (Arch or Ubuntu recommended)
* Root privileges
* WireGuard installed
* Python 3.10+

## Install WireGuard
### On Ubuntu / Debian
> DISCLAIMER: I have only tested this on Arch Linux, but these instructions should work on Ubuntu/Debian as well.
```bash
sudo apt update
sudo apt install wireguard wireguard-tools
```

## Project Setup
From the `vpn-edge-agent` directory, create and activate a virtual environment:
```bash
python3 -m venv venv
source venv/bin/activate
```
Install the required Python packages:
```bash
pip install -r requirements.txt
```

## Environment Variables
Create a `.env` file in the `vpn-edge-agent`, following the structure of the provided [.env.example](./.env.example) file.
Explanation of each variable:
* `NODE_NAME`: A unique identifier for the client device, e.g., `jetson1`.
* `HUB_URL`: The URL of the VPN Hub, e.g., `http://<real_hub_ip>:5000`.
* `BOOTSTRAP_TOKEN`: A secure token that matches the one in the VPN Hub.
* `HEARTBEAT_INTERVAL`: Interval in seconds for sending heartbeat messages to the hub (e.g., `30`).
* `ROTATE_INTERVAL`: Interval in seconds for rotating the WireGuard keys (e.g., `86400` for 24 hours).
* `CONNECT_RETRY_INTERVAL`: Interval in seconds to wait before retrying connection to the hub if it fails (e.g., `15`).


## Running the VPN Edge Agent
Run the VPN Edge Agent with root privileges, preserving the environment variables with `sudo -E`:
```bash
sudo -E venv/bin/python main.py
```