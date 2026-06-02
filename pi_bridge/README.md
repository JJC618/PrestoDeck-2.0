# Presto Spotify Bridge

Run this on a Raspberry Pi so the Presto can use a fast local service instead of making every Spotify request itself.

## Install As A Service

From the `PrestoDeck` folder on the Raspberry Pi:

```bash
bash pi_bridge/install_service.sh
```

The installer creates and starts this systemd service:

```text
presto-spotify-bridge.service
```

## Useful Commands

```bash
sudo systemctl restart presto-spotify-bridge
sudo systemctl status presto-spotify-bridge
journalctl -u presto-spotify-bridge -f
```

## Optional Log Limit

To stop Pi journal logs from growing too large over time, check usage with:

```bash
journalctl --disk-usage
```

Then set a cap in `/etc/systemd/journald.conf`:

```ini
SystemMaxUse=100M
MaxRetentionSec=14day
```

Restart journald after saving:

```bash
sudo systemctl restart systemd-journald
```

## Manual Run

```bash
python3 pi_bridge/spotify_bridge.py --host 0.0.0.0 --port 8787
```

## Test

Replace `YOUR_PI_IP` with the Raspberry Pi IP address:

```bash
curl http://YOUR_PI_IP:8787/health
curl http://YOUR_PI_IP:8787/state
```

The health response includes the bridge version, whether Spotify is rate-limited, and whether the Presto has contacted the bridge recently.

## Endpoints

- `GET /health`
- `GET /state`
- `GET /album-art/current?size=250`
- `GET /album-art/preload-queue`
- `GET /recently-played`
- `GET /playlists`
- `GET /devices`
- `GET /queue`
- `GET /search?q=song`
- `POST /play`
- `POST /pause`
- `POST /next`
- `POST /previous`
- `POST /volume`
- `POST /shuffle`
- `POST /repeat`
- `POST /queue/add`
- `POST /device/select`
- `POST /liked/add`
- `POST /liked/remove`
- `POST /liked/contains`
- `POST /playlist/add`

The bridge reads Spotify credentials from `src/secrets.py`.
