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

1. Create a Spotify Developer app.
2. Generate your own Spotify credentials.
3. Copy `src/secrets.example.py` to `src/secrets.py`.
4. Fill in your WiFi, Spotify credentials, and Raspberry Pi bridge URL.
5. Copy the app files to the Presto.
6. Copy the icon files to the SD card.
7. Install and start the Raspberry Pi bridge.
8. Boot the Presto and test.

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

- If the Presto says `Bridge Failed`, check the Pi IP address and restart the bridge service.
- If liked songs or playlist adding does not work, regenerate Spotify credentials with the included helper script.
- If the SD card fails to mount, check the card format and icon file layout.
- If album art is slow, make sure the Raspberry Pi bridge is active.
- If search works but playback does not, make sure Spotify is already open on at least one device.

## Credits

Built from the original PrestoDeck idea and adapted into a Raspberry Pi assisted Spotify controller for the Pimoroni Presto.
