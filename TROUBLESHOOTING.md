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

Then upload that file to the Presto root and copy it to the Pi:

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

If icons are missing, the app should still run, but buttons may appear blank.

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
