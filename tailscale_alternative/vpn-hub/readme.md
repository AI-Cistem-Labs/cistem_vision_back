# VPN Hub Setup Instructions
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
### On Arch Linux
```bash
sudo pacman -Syu
sudo pacman -S wireguard-tools
sudo pacman -S linux-headers wireguard-dkms
```

## Firewall Configuration (Hub)
Allow only UDP port 51820 through the firewall.
```bash
sudo ufw allow 51820/udp
```
No other ports need to be exposed.

## Generate Hub Keys
```bash
cd /etc/wireguard
sudo wg genkey | sudo tee hub_private.key | sudo wg pubkey | sudo tee hub_public.key
```
This generates: 
* `hub_private.key`: The private key for the hub (keep this secret).
* `hub_public.key`: The public key for the hub (to be shared with clients).

## WireGuard Configuration
Create the WireGuard configuration file for the hub:
```bash
sudo nano /etc/wireguard/wg0.conf
```
Add the following content, replacing `<CONTENIDO DE hub_private.key>` with the actual content of the `hub_private.key` file:
```ini
[Interface]
Address = 10.0.0.1/24
ListenPort = 51820
PrivateKey = <CONTENIDO DE hub_private.key>
SaveConfig = false
```
Explanation: 
* `Address`: The VPN subnet for the hub.
* `ListenPort`: The port WireGuard will listen on.
* `PrivateKey`: The hub's private key.
* `SaveConfig`: Prevents WireGuard from overwriting the config file.

## Set Permissions
Ensure the configuration file has the correct permissions:
```bash
sudo chmod 600 /etc/wireguard/wg0.conf
```

## Bring up the WireGuard Interface
Start the WireGuard interface:
```bash
sudo wg-quick up wg0
```

## Running the Hub Application
1. Navigate to the `vpn-hub` directory.
2. Create a virtual environment and install dependencies:
    ```bash
    python3 -m venv venv
    source venv/bin/activate
    pip install -r doc/requirements.txt
    ```
3. Set up the environment variables in a `.env` file (refer to [.env.example](./doc/.env.example) for guidance).
    Explanation of each variable:
    * `HUB_PUBLIC_KEY`: The public key of the hub (from `hub_public.key`).
    * `HUB_ENDPOINT`: The public IP address or domain name of the hub. You can get it using `ip a` on the hub machine.
    * `HUB_PORT`: The port WireGuard is listening on (default is `51820`).
    * `BOOTSTRAP_TOKEN`: A secure token that clients will use to authenticate with the hub.
4. Run the Flask application with sudo to allow it to manage WireGuard, and using the `-E` flag to preserve environment variables:
    ```bash
    sudo -E ./venv/bin/python main.py
    ```
5. The hub should now be running and ready to accept client connections.