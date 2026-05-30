WIFI_SSID = "Your WiFi name"
WIFI_PASSWORD = "Your WiFi password"

# Optional, but recommended. Set this to the Raspberry Pi running the bridge.
USE_SPOTIFY_BRIDGE = True
SPOTIFY_BRIDGE_BASE_URL = "http://192.168.1.100:8787"

# Paste the generated Spotify credentials here after running:
# python3 adhoc/generate_token.py
SPOTIFY_CREDENTIALS = {
    "refresh_token": "your_refresh_token",
    "client_id": "your_client_id",
    "client_secret": "your_client_secret",
    "device_id": None,
}
