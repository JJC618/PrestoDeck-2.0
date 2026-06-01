APP_ASSET_ROOT = "applications/spotify"
SD_ASSET_ROOTS = ("/sd/applications/spotify", "/sd")
APP_VERSION = "0.2.1"

try:
    import secrets as project_secrets
except Exception:
    project_secrets = None

PLAYBACK_FETCH_INTERVAL = 20
TOUCH_FETCH_GRACE = 2
PLAYLIST_CACHE_SECONDS = 300

AMBIENT_LED_COUNT = 7

ALBUM_ART_CACHE_DIR = "cache/album_art"
ALBUM_ART_CACHE_MAX_BYTES = 1024 * 1024 * 1024
PRESTO_ALBUM_ART_CACHE_ENABLED = False

USE_SPOTIFY_BRIDGE = getattr(project_secrets, "USE_SPOTIFY_BRIDGE", True)
SPOTIFY_BRIDGE_BASE_URL = getattr(project_secrets, "SPOTIFY_BRIDGE_BASE_URL", "http://192.168.1.100:8787")
