# Troubleshooting

This guide covers the most common setup and runtime issues with PrestoDeck 2.0.

## Quick Health Checks

From your computer, check the Pi bridge is alive:

```bash
curl http://YOUR_PI_IP:8787/health
```

Expected:

```json
{"ok": true}
```

Check the bridge service on the Pi:

```bash
ssh admin@YOUR_PI_IP
systemctl status presto-spotify-bridge
```

Restart the bridge after copying new files:

```bash
sudo systemctl restart presto-spotify-bridge
```

Watch bridge logs:

```bash
journalctl -u presto-spotify-bridge -f
```

## Red Boot Error Messages

The Presto stops on red boot errors because continuing would usually leave the app half-loaded.

### `(sd card mount failed)`

The Presto could not mount the SD card.

Likely causes:

- The SD card is not inserted fully.
- The SD card is not formatted as FAT32.
- The SD card has a partition/layout the Presto cannot read.
- The SD card reader or card is faulty.

Fix:

Format the SD card as FAT32, copy the contents of the repo `sd_card` folder back onto it, eject it cleanly, then reboot the Presto.

### `(icons missing sd)`

The SD card mounted, but one or more required image files were not found.

Likely causes:

- The `icons` folder was not copied to the SD card.
- Files were copied inside an extra folder instead of the SD card root.
- One of the icon filenames was changed.

Fix:

The SD card root should look like this:

```text
icon.png
icons/
```

The `icons` folder must contain files such as `play.png`, `pause.png`, `speaker.png`, `search.png`, `left_arrow.png`, and `right_arrow.png`.

### `(wrong wifi password)`

The Presto could not connect to WiFi within the startup timeout.

Likely causes:

- `WIFI_SSID` is wrong.
- `WIFI_PASSWORD` is wrong.
- The WiFi network is out of range.
- The router is not accepting the device.

Fix:

Check `secrets.py` on the Presto root and make sure the SSID and password match exactly, including spaces, capitals, and symbols.

### `(secrets missing local)`

The Presto cannot find usable Spotify credentials in its local `secrets.py`.
This only applies if `USE_SPOTIFY_BRIDGE = False`.

Likely causes:

- `secrets.py` is missing from the Presto root.
- `secrets.py` was copied inside `src/` instead of the Presto root.
- `SPOTIFY_CREDENTIALS` is missing or empty.

Fix:

Copy your private `src/secrets.py` to the Presto root so it sits beside `main.py`.

### `(secrets missing bridge)`

The Presto is set to use the Raspberry Pi bridge, but the bridge URL is missing from `secrets.py`.

Likely causes:

- `SPOTIFY_BRIDGE_BASE_URL` is missing or blank in `secrets.py`.
- `USE_SPOTIFY_BRIDGE = True`, but the bridge URL was not copied in.

Fix:

Set the bridge URL in the Presto `secrets.py` file:

```python
SPOTIFY_BRIDGE_BASE_URL = "http://YOUR_PI_IP:8787"
```

### `(bridge unavailable)`

The Presto has a bridge URL, but it cannot contact the Raspberry Pi bridge service.

Likely causes:

- The Pi bridge service is not running.
- The Pi is turned off or disconnected from the network.
- The Pi has a different IP address.
- `SPOTIFY_BRIDGE_BASE_URL` points to the wrong IP address.
- A firewall or network issue is blocking port `8787`.

Fix:

From your computer, test:

```bash
curl http://YOUR_PI_IP:8787/health
```

If that fails, SSH into the Pi and restart/check the service:

```bash
sudo systemctl restart presto-spotify-bridge
systemctl status presto-spotify-bridge
```

### `(spotify uri incorrect)`

The Spotify credentials are missing required values, invalid, expired, or do not have the permissions the app needs.
In the recommended bridge setup, these credentials are used by the Pi bridge.

Likely causes:

- The generated `SPOTIFY_CREDENTIALS` block was copied incorrectly.
- The Spotify app client ID or client secret is wrong.
- The refresh token is invalid.
- The token was generated without the required scopes.

Fix:

Run the token helper again:

```bash
python3 adhoc/generate_token.py
```

Copy the new `SPOTIFY_CREDENTIALS` block into `src/secrets.py`, then copy that file to the Pi and restart the bridge.

### `(version mismatch)`

The Presto app and Raspberry Pi bridge are running different PrestoDeck versions.

Likely causes:

- The Presto files were updated but the Pi bridge files were not.
- The Pi bridge files were copied over but the service was not restarted.
- The Pi is running an older checkout of the GitHub repo.

Fix:

Update both devices from the same GitHub version. Copy the latest files to the Pi:

```bash
scp -r adhoc docs pi_bridge sd_card src README.md TROUBLESHOOTING.md admin@YOUR_PI_IP:~/PrestoDeck/
```

Then restart the bridge:

```bash
sudo systemctl restart presto-spotify-bridge
```

Check the bridge version:

```bash
curl http://YOUR_PI_IP:8787/health
```

The `bridge_version` should match the version shown on the Presto boot screen.

## Presto Stuck On Connecting To WiFi

This usually means `secrets.py` is missing or the WiFi details are wrong.

On the Presto, these files should be at the device root:

```text
main.py
base.py
secrets.py
applications/
```

They should not be inside a `src/` folder on the Presto.

In Thonny, run this on the Presto:

```python
import secrets
print(repr(secrets.WIFI_SSID))
print(len(secrets.WIFI_PASSWORD))
```

Do not print your password. Check the SSID is exact and the password length looks right.

## Bridge Failed

Check `SPOTIFY_BRIDGE_BASE_URL` in `src/secrets.py`:

```python
USE_SPOTIFY_BRIDGE = True
SPOTIFY_BRIDGE_BASE_URL = "http://YOUR_PI_IP:8787"
```

Then test:

```bash
curl http://YOUR_PI_IP:8787/health
```

If `/health` works but the Presto still says `Bridge Failed`, restart the bridge and reboot the Presto app.

## Album Art Does Not Load On Boot

First check the bridge:

```bash
curl http://YOUR_PI_IP:8787/health
```

Then check startup state once:

```bash
curl -i http://YOUR_PI_IP:8787/startup
```

Avoid repeatedly calling `/startup`; it talks to Spotify and can trigger rate limiting.

If the bridge returns `Too many requests`, wait for the `Retry-After` value if shown. The value is in seconds.

## Spotify Says Too Many Requests

Spotify has rate-limited your app or token.

If you see:

```json
{"error": "Too many requests", "retry_after": "120"}
```

wait that many seconds before trying again.

If the Presto shows:

```text
Bridge Blocked 120s
```

the bridge has detected Spotify's cooldown timer and has paused Spotify API calls until the countdown finishes. Leave the Pi bridge running and wait for the timer to reach zero. The Presto checks the bridge status about every 15 seconds, so the number may update in small jumps.

Safe command while waiting:

```bash
curl http://YOUR_PI_IP:8787/health
```

Avoid these until the timer expires:

```bash
curl http://YOUR_PI_IP:8787/startup
curl http://YOUR_PI_IP:8787/state
```

To stop all bridge activity while waiting:

```bash
sudo systemctl stop presto-spotify-bridge
```

Start it again later:

```bash
sudo systemctl start presto-spotify-bridge
```

## Playlists Show None Found

Regenerate Spotify credentials using the helper script:

```bash
python3 adhoc/generate_token.py
```

The token must include playlist read scopes. Copy the new `SPOTIFY_CREDENTIALS` into:

```text
src/secrets.py
```

Then copy it to the Pi and restart the bridge:

```bash
scp src/secrets.py admin@YOUR_PI_IP:~/PrestoDeck/src/secrets.py
sudo systemctl restart presto-spotify-bridge
```

## Liked Songs Or Add To Playlist Does Not Work

Regenerate Spotify credentials. The token needs library and playlist modify permissions.

After updating `src/secrets.py`, upload it to both:

```text
Presto root/secrets.py
Pi ~/PrestoDeck/src/secrets.py
```

Restart the bridge:

```bash
sudo systemctl restart presto-spotify-bridge
```

## Search Finds Tracks But Playback Does Not Start

Spotify playback commands require an active Spotify device.

Open Spotify on your phone, computer, or speaker first, start playback once, then try PrestoDeck again.

## SD Card Or Icons Do Not Show

The simplest SD card layout is:

```text
/icon.png
/icons/*.png
```

The app also checks:

```text
/applications/spotify/icon.png
/applications/spotify/icons/*.png
```

If icons are missing on current versions, the app will stop at boot with `(icons missing sd)` so the problem is visible immediately.

## Raspberry Pi Service Not Installed

SSH into the Pi:

```bash
ssh admin@YOUR_PI_IP
```

Go to the project folder:

```bash
cd ~/PrestoDeck
```

Install the service:

```bash
bash pi_bridge/install_service.sh
```

Check it:

```bash
systemctl status presto-spotify-bridge
```

## Copying Files To The Pi Fails

Run the copy command from inside the `PrestoDeck-2.0` folder on your computer:

```bash
cd /path/to/PrestoDeck-2.0
scp -r adhoc docs pi_bridge sd_card src README.md TROUBLESHOOTING.md admin@YOUR_PI_IP:~/PrestoDeck/
```

If you see `No such file or directory`, you are probably one folder too high.

## Public GitHub Setup Versus Private Device Setup

GitHub should contain:

```text
src/secrets.example.py
```

Your Presto and Pi need your private:

```text
src/secrets.py
```

Never publish `src/secrets.py`; it contains your WiFi and Spotify credentials.
