WIFI_SSID = "Your WiFi name"
WIFI_PASSWORD = "Your WiFi password"

# Required. Set this to the Raspberry Pi running the bridge.
SPOTIFY_BRIDGE_BASE_URL = "http://192.168.1.100:8787"

# Required by the Raspberry Pi bridge. Paste the generated Spotify credentials here after running:
# python3 adhoc/generate_token.py
SPOTIFY_CREDENTIALS = {
    "refresh_token": "your_refresh_token",
    "client_id": "your_client_id",
    "client_secret": "your_client_secret",
    "device_id": None,
}

# Optional. The token helper can generate this line. Default is 1GB.
ALBUM_ART_CACHE_MAX_BYTES = 1024 * 1024 * 1024
