APP_ASSET_ROOT = "applications/spotify"
SD_ASSET_ROOTS = ("/sd/applications/spotify", "/sd")
APP_VERSION = "1.2.3"

try:
    import secrets as project_secrets
except Exception:
    project_secrets = None

PLAYBACK_FETCH_INTERVAL = 60
TOUCH_FETCH_GRACE = 2
PLAYLIST_CACHE_SECONDS = 300
BRIDGE_HEALTH_INTERVAL = 120
BRIDGE_HEALTH_ALERT_INTERVAL = 30

AMBIENT_LED_COUNT = 7

ALBUM_ART_CACHE_DIR = "cache/album_art"
ALBUM_ART_CACHE_MAX_BYTES = 1024 * 1024 * 1024
PRESTO_ALBUM_ART_CACHE_ENABLED = False

SPOTIFY_BRIDGE_BASE_URL = getattr(project_secrets, "SPOTIFY_BRIDGE_BASE_URL", "http://192.168.1.100:8787")
