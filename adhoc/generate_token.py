import sys
import spotipy
from spotipy.oauth2 import SpotifyOAuth
from spotipy.cache_handler import MemoryCacheHandler

DEFAULT_ALBUM_ART_CACHE_GB = 1


def prompt_credentials():
    client_id = input("Enter Spotify Client ID: ").strip()
    client_secret = input("Enter Spotify Client Secret: ").strip()
    redirect_uri = input("Enter Redirect URI: ").strip()
    return client_id, client_secret, redirect_uri


def prompt_album_art_cache_bytes():
    print("\n5. Album-art cache size")
    print("This controls the maximum album-art cache size on the Raspberry Pi bridge.")
    print("Press Enter for the default: {}GB".format(DEFAULT_ALBUM_ART_CACHE_GB))
    while True:
        value = input("Enter maximum cache size, for example 512MB, 1GB, or 2GB: ").strip().lower()
        if not value:
            return DEFAULT_ALBUM_ART_CACHE_GB * 1024 * 1024 * 1024

        try:
            if value.endswith("gb"):
                number = float(value[:-2].strip())
                return int(number * 1024 * 1024 * 1024)
            if value.endswith("g"):
                number = float(value[:-1].strip())
                return int(number * 1024 * 1024 * 1024)
            if value.endswith("mb"):
                number = float(value[:-2].strip())
                return int(number * 1024 * 1024)
            if value.endswith("m"):
                number = float(value[:-1].strip())
                return int(number * 1024 * 1024)
            if value.isdigit():
                return int(value) * 1024 * 1024 * 1024
        except ValueError:
            pass

        print("Invalid size. Try examples like 512MB, 1GB, or 2GB.")


def get_spotify_token(client_id, client_secret, redirect_uri):
    cache_handler = MemoryCacheHandler()
    auth = SpotifyOAuth(
        scope=" ".join((
            "user-read-playback-state",
            "user-modify-playback-state",
            "user-read-recently-played",
            "user-library-read",
            "user-library-modify",
            "playlist-read-private",
            "playlist-read-collaborative",
            "playlist-modify-public",
            "playlist-modify-private",
        )),
        client_id=client_id,
        client_secret=client_secret,
        redirect_uri=redirect_uri,
        open_browser=False,
        cache_handler = cache_handler
    )
    auth.get_access_token(as_dict=False)
    token_info = cache_handler.get_cached_token()
    if not token_info or not token_info.get('refresh_token'):
        sys.exit("Error: Unable to get Spotify refresh token.")
    return auth, token_info['refresh_token']

def choose_device(spotify):
    devices = spotify.devices().get("devices", [])
    if not devices:
        print("No active Spotify devices found.")
        return None
    for idx, device in enumerate(devices):
        print(f"{idx}: {device.get('name')}")
    while True:
        choice = input("Select default device by its number: ").strip()
        if choice.isdigit() and int(choice) in range(len(devices)):
            print(devices[int(choice)].get("name"))
            return devices[int(choice)].get("id")
        print("Invalid device number. Try again.")

def main():
    client_id, client_secret, redirect_uri = prompt_credentials()
    auth, token = get_spotify_token(client_id, client_secret, redirect_uri)
    spotify = spotipy.Spotify(oauth_manager=auth)
    device_id = choose_device(spotify)
    album_art_cache_max_bytes = prompt_album_art_cache_bytes()
    
    credentials = {
        "refresh_token": token,
        "client_id": client_id,
        "client_secret": client_secret,
        "device_id": device_id,
    }
    print("\nCopy the following lines to secrets.py:")
    print(f"SPOTIFY_CREDENTIALS={credentials}")
    print(f"ALBUM_ART_CACHE_MAX_BYTES={album_art_cache_max_bytes}")

if __name__ == "__main__":
    main()
