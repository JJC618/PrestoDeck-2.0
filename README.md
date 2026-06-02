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

The Raspberry Pi bridge is required. Spotify credentials are used by the Pi
bridge, and the Presto only contacts the bridge; it does not make local Spotify
API calls.

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

## Upload Checklist

When updating or installing from scratch, make sure all three targets are updated from the same repo version.

Presto device root:

```text
main.py
base.py
secrets.py
applications/
```

SD card root:

```text
icon.png
icons/
```

Raspberry Pi project folder:

```text
~/PrestoDeck/adhoc
~/PrestoDeck/docs
~/PrestoDeck/pi_bridge
~/PrestoDeck/sd_card
~/PrestoDeck/src
~/PrestoDeck/README.md
~/PrestoDeck/TROUBLESHOOTING.md
```

After updating the Pi files, restart the bridge:

```bash
sudo systemctl restart presto-spotify-bridge
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

## Optional: Limit Pi Logs

The bridge writes service logs to the Raspberry Pi system journal. Raspberry Pi OS usually manages this automatically, but you can cap journal storage so logs cannot slowly grow forever.

The album-art cache is already capped by the app at 1GB. This optional step is only for the Pi service logs.

Check current journal usage:

```bash
journalctl --disk-usage
```

Edit the journal settings:

```bash
sudo nano /etc/systemd/journald.conf
```

Add or update these lines:

```ini
SystemMaxUse=100M
MaxRetentionSec=14day
```

Then restart the journal service:

```bash
sudo systemctl restart systemd-journald
```

## Updating The Bridge

After copying new files to the Raspberry Pi:

```bash
sudo systemctl restart presto-spotify-bridge
```

## Troubleshooting

See [TROUBLESHOOTING.md](TROUBLESHOOTING.md) for WiFi, bridge, Spotify token, playlist, album-art, SD card, and Raspberry Pi service issues.

## Changelog

### 0.3.0

- Made the Raspberry Pi bridge compulsory for all Spotify API communication.
- Removed the Presto-side local Spotify API client and the old optional bridge setting.
- Added `spotify_url.py` for the small URL-encoding helpers still needed by bridge requests.
- Renamed the missing bridge URL boot error to `(bridge url missing)`.
- Kept stopped or unreachable bridge services under `(bridge unavailable)`.
- Improved startup handling for rejected Pi-side Spotify credentials.
- Hardened album-art requests so old clients cannot trigger playback-state lookups.
- Updated the release test script to match the new bridge-only file layout.

### 0.2.12

- Show a clearer bridge unavailable boot error when the Raspberry Pi service cannot be reached.

### 0.2.11

- Show bridge failure instead of a stale API-block countdown when the bridge health check fails.

### 0.2.10

- Removed Presto-side Spotify fallback calls.
- Kept album-art fetching bridge-only so Spotify traffic is logged from one place.

### 0.2.9

- Reduced idle Spotify API usage by polling playback every 60 seconds.
- Stopped automatic queue preloading from normal playback state refreshes.

### 0.2.8

- Limited album-art network fetching to one request per track and reused local cached art for fullscreen redraws.

### 0.2.7

- Reduced Spotify API calls by letting album-art requests use the already-known track image instead of refreshing playback state.

### 0.2.6

- Fixed speaker paging so all detected devices are available across pages.
- Centred page counters between the navigation arrows.

### 0.2.5

- Made the search keyboard respond on press-down for faster typing.

### 0.2.4

- Added Spotify API blocked messages to search results and speaker selection screens.
- Improved blocked-message readability on the Presto.

### 0.2.3

- Added boot checks for SD card mount failures and missing SD card icons.
- Added troubleshooting guidance for red boot error messages.

### 0.2.2

- Centred player visuals, including album art, placeholder icon, and play/pause control positioning.

### 0.2.1

- Improved startup and blocked-message text centring.
- Hid the loading message on the player screen when Spotify is API-blocked.

### 0.2.0

- Added startup diagnostics, bridge health details, and visible Spotify API blocked states.
- Added version reporting for the Presto app and Raspberry Pi bridge.

### 0.1.0

- Added playlist and speaker paging controls.

## Credits

Built from the original PrestoDeck app by Fatih Ak and adapted into a Raspberry Pi assisted Spotify controller for the Pimoroni Presto.
