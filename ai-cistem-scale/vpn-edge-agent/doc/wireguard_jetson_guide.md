# WireGuard Installation Guide for Jetson Devices
## Requirements
* Ubuntu 22.04.5 (it was tested in this version, but it should work in other versions as well)
* kernel 5.15.148 (can be checked with `uname -r`)

## Installation Steps
Clone the modified WireGuard repository that contains the necessary patches for Jetson devices:
```bash
git clone https://github.com/MrVasquez96/wireguard-linux-compat.git
```
Clone the WireGuard tools repository:
```bash
git clone https://git.zx2c4.com/wireguard-tools
```
Then, run the following comands to build and install the WireGuard kernel module:
```bash
make -C wireguard-linux-compat/src -j$(nproc)
sudo make -C wireguard-linux-compat/src install
sudo depmod -a
make -C wireguard-tools/src -j$(nproc)
sudo make -C wireguard-tools/src install
```
If everything went well, you should now have WireGuard installed on your Jetson device. You can verify the installation by running:
```bash
$ wg --version
wireguard-tools v1.0.20250521 - https://git.zx2c4.com/wireguard-tools/
```
You also can trigger wireguard with:
```bash
sudo wg
sudo wg-quick up wg0
```
and should see something like this:
```bash
[#] ip link add dev wg0 type wireguard
[#] wg addconf wg0 /dev/fd/63
[#] ip -4 address add 10.0.0.2/24 dev wg0
[#] ip link set mtu 1420 up dev wg0
```