# PrestoDeck 2.0

PrestoDeck 2.0 is a Spotify controller for the Pimoroni Presto. It shows current album art, playback controls, playlists, speaker selection, search, liked songs, volume, queue information, and an idle full-screen album-art mode.

For best performance, the Presto talks to a small Raspberry Pi bridge on your local network. The Pi handles the heavier Spotify and album-art requests, leaving the Presto as a fast touch interface.

![PrestoDeck 2.0](docs/PrestoDeck%202.0.jpg)

![Full screen album art](docs/Full%20Screen.jpg)

## Hardware

- Pimoroni Presto
- Micro SD card for UI icons
- Raspberry Pi on the same WiFi network, recommended
- Spotify Premium account

## Setup Overview

1. Clone this repo and open the project folder.
2. Create a Spotify Developer app.
3. Generate your own Spotify credentials.
4. Copy `src/secrets.example.py` to `src/secrets.py`.
5. Fill in your WiFi, Spotify credentials, and Raspberry Pi bridge URL.
6. Copy the app files to the Presto.
7. Copy the icon files to the SD card.
8. Install and start the Raspberry Pi bridge.
9. Boot the Presto and test.

## Clone The Repo

```bash
git clone https://github.com/JJC618/PrestoDeck-2.0.git
cd PrestoDeck-2.0
```

## Spotify Developer App

Create an app at the [Spotify Developer Dashboard](https://developer.spotify.com/dashboard).

Use this redirect URI:

```text
http://127.0.0.1:8080
```

Enable Web API access.

## Generate Spotify Credentials

On your computer, install the helper dependency:

```bash
python3 -m pip install spotipy
```

Then run:

```bash
python3 adhoc/generate_token.py
```

The script asks for your Spotify client ID, client secret, and redirect URI. It prints a `SPOTIFY_CREDENTIALS = {...}` block when complete.

## Configure Secrets

Copy the example file:

```bash
cp src/secrets.example.py src/secrets.py
```

Edit `src/secrets.py` and set:

- `WIFI_SSID`
- `WIFI_PASSWORD`
- `SPOTIFY_BRIDGE_BASE_URL`
- `SPOTIFY_CREDENTIALS`

Example bridge URL:

```python
SPOTIFY_BRIDGE_BASE_URL = "http://192.168.1.100:8787"
```

Do not publish `src/secrets.py`. It contains private credentials.

## SD Card Files

Copy the UI icon files to the SD card. See [sd_card/README.md](sd_card/README.md) for the expected layout.

The simplest layout is:

```text
/sd/icon.png
/sd/icons/*.png
```

## Upload To Presto

Use Thonny or your preferred MicroPython upload tool.

Copy these folders/files to the Presto:

```text
src/main.py
src/base.py
src/secrets.py
src/applications/
```

On the Presto, `main.py` should be at the device root.

## Raspberry Pi Bridge

Copy this repo to the Raspberry Pi, including your completed `src/secrets.py`.

First, open an SSH terminal to the Pi. Replace `admin` and `YOUR_PI_IP` if your Pi uses a different username or IP address:

```bash
ssh admin@YOUR_PI_IP
```

Create a project folder on the Pi:

```bash
mkdir -p ~/PrestoDeck
exit
```

Back on your computer, from inside the `PrestoDeck-2.0` folder, copy the project files to the Pi:

```bash
scp -r adhoc docs pi_bridge sd_card src README.md admin@YOUR_PI_IP:~/PrestoDeck/
```

If you are using a different Pi username, change `admin@YOUR_PI_IP` to match your setup.

Then SSH back into the Pi and open the project folder:

```bash
ssh admin@YOUR_PI_IP
cd ~/PrestoDeck
```

From the project folder on the Pi, run:

```bash
bash pi_bridge/install_service.sh
```

Check it is running:

```bash
systemctl status presto-spotify-bridge
```

Test from another device on the same network:

```bash
curl http://YOUR_PI_IP:8787/health
```

## Updating The Bridge

After copying new files to the Raspberry Pi:

```bash
sudo systemctl restart presto-spotify-bridge
```

## Troubleshooting

See [TROUBLESHOOTING.md](TROUBLESHOOTING.md) for WiFi, bridge, Spotify token, playlist, album-art, SD card, and Raspberry Pi service issues.

## Credits

Built from the original PrestoDeck idea and adapted into a Raspberry Pi assisted Spotify controller for the Pimoroni Presto.
