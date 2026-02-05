# Tailscale Alternative VPN Solution
This project implements a custom VPN solution inspired by Tailscale, utilizing WireGuard for secure networking. It consists of two main components: the VPN Hub (server) and the VPN Edge Agent (client). The VPN Hub manages connections and routes traffic, while the VPN Edge Agent runs on client devices to connect to the hub.

## Components
- **VPN Hub**: A Flask-based server that handles client registrations, manages WireGuard configurations, and routes traffic between connected clients.
- **VPN Edge Agent**: A Python application that runs on client devices, establishing a WireGuard connection to the VPN Hub and maintaining connectivity.

## Why?
Tailscale costs money for commercial use and has limitations on customizability. This project aims to provide a free and open-source alternative that can be tailored to specific needs.

## How to use?
Read the documentation in each component's folder:
- [VPN Hub Documentation](vpn-hub/readme.md)
- [VPN Edge Agent Documentation](vpn-edge-agent/doc/readme.md)

## Upcoming Features
* [ ] Improved identifier (currently using NODE_NAME, which may not be unique, and also may me mutable)
* [ ] Delete peers from the hub if they have been offline for a long time. This is more than just deleting from the database, also removing from WireGuard config.