import os
import time
import urequests as requests

from applications.spotify.spotify_client import quote
from applications.spotify.spotify_settings import (
    ALBUM_ART_CACHE_DIR,
    ALBUM_ART_CACHE_MAX_BYTES,
    APP_ASSET_ROOT,
    PRESTO_ALBUM_ART_CACHE_ENABLED,
    SPOTIFY_BRIDGE_BASE_URL,
    SD_ASSET_ROOTS,
    USE_SPOTIFY_BRIDGE,
)

BRIDGE_IMAGE_RETRY_AT = 0
BRIDGE_IMAGE_RETRY_SECONDS = 30


def file_exists(path):
    try:
        os.stat(path)
        return True
    except OSError:
        return False


def mount_sd_card():
    if file_exists("/sd"):
        return True

    try:
        import machine
        import sdcard

        sd_spi = machine.SPI(
            0,
            sck=machine.Pin(34, machine.Pin.OUT),
            mosi=machine.Pin(35, machine.Pin.OUT),
            miso=machine.Pin(36, machine.Pin.OUT)
        )
        sd = sdcard.SDCard(sd_spi, machine.Pin(39))
        os.mount(sd, "/sd")
        return True
    except Exception as e:
        print("SD card not mounted:", e)
        return False


def asset_path(relative_path):
    for root in SD_ASSET_ROOTS:
        path = root + "/" + relative_path
        if file_exists(path):
            return path
    return APP_ASSET_ROOT + "/" + relative_path


def ensure_dir(path):
    parts = path.split("/")
    current = ""
    for part in parts:
        if not part:
            current = "/"
            continue
        current = current.rstrip("/") + "/" + part if current else part
        try:
            os.mkdir(current)
        except OSError:
            pass


def writable_cache_root():
    for root in SD_ASSET_ROOTS:
        if file_exists(root):
            cache_root = root + "/" + ALBUM_ART_CACHE_DIR
            ensure_dir(cache_root)
            return cache_root

    cache_root = APP_ASSET_ROOT + "/" + ALBUM_ART_CACHE_DIR
    ensure_dir(cache_root)
    return cache_root


def cache_total_size(path):
    total = 0
    try:
        names = os.listdir(path)
    except OSError:
        return 0

    for name in names:
        child = path.rstrip("/") + "/" + name
        try:
            total += os.stat(child)[6]
        except OSError:
            pass
    return total


def purge_cache(path):
    try:
        names = os.listdir(path)
    except OSError:
        return

    for name in names:
        child = path.rstrip("/") + "/" + name
        try:
            os.remove(child)
        except OSError:
            pass


def save_album_cover_to_cache(cache_root, cache_path, img, label):
    if not PRESTO_ALBUM_ART_CACHE_ENABLED:
        return

    try:
        if cache_total_size(cache_root) + len(img) >= ALBUM_ART_CACHE_MAX_BYTES:
            print("Album-art cache limit reached, purging cache")
            purge_cache(cache_root)
        with open(cache_path, "wb") as f:
            f.write(img)
    except OSError as e:
        print(label, e)


def album_cache_key(track, size):
    album = track.get("album", {})
    key = album.get("id") or track.get("id") or "unknown"
    return "{}_{}.jpg".format(key, size)


def get_cached_album_cover(track, size=250):
    cache_root = writable_cache_root()
    cache_path = cache_root + "/" + album_cache_key(track, size)
    try:
        with open(cache_path, "rb") as f:
            return f.read()
    except OSError:
        return None


def get_album_cover(track, size=250, allow_direct_fallback=True):
    """Fetches a resized album cover image, preferring cache or bridge."""
    cache_root = writable_cache_root()
    cache_path = cache_root + "/" + album_cache_key(track, size)

    img = get_cached_album_cover(track, size)
    if img:
        return img

    if USE_SPOTIFY_BRIDGE:
        img = get_album_cover_from_bridge(track, size)
        if img:
            save_album_cover_to_cache(cache_root, cache_path, img, "Failed caching bridge image:")
            return img
        if not allow_direct_fallback:
            return None

    images = track["album"]["images"]
    image_index = 0 if size > 250 or len(images) == 1 else 1
    img_url = images[image_index]["url"]
    resize_url = f"https://wsrv.nl/?url={img_url}&w={size}&h={size}"

    img = None
    try:
        response = requests.get(resize_url)
        if response.status_code == 200:
            img = response.content
            save_album_cover_to_cache(cache_root, cache_path, img, "Failed caching image:")
        else:
            print("Failed to fetch image:", response.status_code)
        response.close()
    except Exception as e:
        print("Fetch image error:", e)

    return img


def get_album_cover_from_bridge(track, size):
    global BRIDGE_IMAGE_RETRY_AT

    if time.time() < BRIDGE_IMAGE_RETRY_AT:
        return None

    images = track["album"]["images"]
    image_index = 0 if size > 250 or len(images) == 1 else 1
    image_url = images[image_index]["url"]
    track_id = track.get("id") or track.get("uri", "unknown").split(":")[-1]

    response = None
    try:
        response = requests.get(
            "{}/album-art/current?size={}&track_id={}&image_url={}".format(
                SPOTIFY_BRIDGE_BASE_URL.rstrip("/"),
                size,
                quote(track_id),
                quote(image_url),
            )
        )
        if response.status_code == 200:
            BRIDGE_IMAGE_RETRY_AT = 0
            return response.content
        print("Failed to fetch bridge image:", response.status_code)
        BRIDGE_IMAGE_RETRY_AT = time.time() + BRIDGE_IMAGE_RETRY_SECONDS
    except Exception as e:
        print("Bridge image fetch error:", e)
        BRIDGE_IMAGE_RETRY_AT = time.time() + BRIDGE_IMAGE_RETRY_SECONDS
    finally:
        if response:
            response.close()
    return None
