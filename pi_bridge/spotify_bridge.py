#!/usr/bin/env python3
"""Small local Spotify bridge for Presto.

Run this on the Raspberry Pi. Presto can call this local HTTP service instead
of calling Spotify directly.
"""

import argparse
import importlib.util
import json
import hashlib
import sys
import threading
import time
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.error import HTTPError, URLError
from urllib.parse import parse_qs, quote, urlencode, urlparse
from urllib.request import Request, urlopen


ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"


def load_project_secrets():
    secrets_path = SRC / "secrets.py"
    if not secrets_path.exists():
        raise RuntimeError(
            "Missing {}. Copy PrestoDeck/src/secrets.py to the Raspberry Pi.".format(secrets_path)
        )

    spec = importlib.util.spec_from_file_location("presto_secrets", secrets_path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)

    if not hasattr(module, "SPOTIFY_CREDENTIALS"):
        raise RuntimeError("{} does not define SPOTIFY_CREDENTIALS".format(secrets_path))
    return module


project_secrets = load_project_secrets()


SPOTIFY_API = "https://api.spotify.com/v1"
TOKEN_URL = "https://accounts.spotify.com/api/token"
ALBUM_ART_CACHE = ROOT / "cache" / "album_art"
ALBUM_ART_CACHE_MAX_BYTES = 1024 * 1024 * 1024
QUEUE_PRELOAD_LIMIT = 5
QUEUE_PRELOAD_SECONDS = 60
ALBUM_ART_PRELOAD_SIZES = (250, 480)


class SpotifyBridgeError(Exception):
    def __init__(self, status, message, retry_after=None):
        super().__init__(message)
        self.status = status
        self.message = message
        self.retry_after = retry_after


class SpotifySession:
    def __init__(self, credentials):
        self.credentials = credentials
        self.access_token = credentials.get("access_token")
        self.expires_at = 0
        self.device_id = credentials.get("device_id")

    def ensure_token(self):
        if self.access_token and time.time() < self.expires_at - 30:
            return

        body = urlencode({
            "grant_type": "refresh_token",
            "refresh_token": self.credentials["refresh_token"],
            "client_id": self.credentials["client_id"],
            "client_secret": self.credentials["client_secret"],
        }).encode("utf-8")
        req = Request(
            TOKEN_URL,
            data=body,
            headers={"Content-Type": "application/x-www-form-urlencoded"},
            method="POST",
        )
        data = self._open_json(req)
        self.access_token = data["access_token"]
        self.credentials["access_token"] = self.access_token
        self.expires_at = time.time() + int(data.get("expires_in", 3600))
        if data.get("refresh_token"):
            self.credentials["refresh_token"] = data["refresh_token"]

    def request(self, method, path, body=None, add_device_id=True):
        self.ensure_token()

        url = SPOTIFY_API + path
        if add_device_id and self.device_id:
            join = "&" if "?" in url else "?"
            url += "{}device_id={}".format(join, quote(self.device_id))

        headers = {"Authorization": "Bearer {}".format(self.access_token)}
        data = None
        if body is not None:
            data = json.dumps(body).encode("utf-8")
            headers["Content-Type"] = "application/json"

        req = Request(url, data=data, headers=headers, method=method)
        try:
            return self._open_json(req)
        except SpotifyBridgeError as e:
            if e.status != 401:
                raise
            self.access_token = None
            self.ensure_token()
            headers["Authorization"] = "Bearer {}".format(self.access_token)
            req = Request(url, data=data, headers=headers, method=method)
            return self._open_json(req)

    def _open_json(self, req):
        try:
            with urlopen(req, timeout=10) as response:
                content = response.read()
                if not content:
                    return {}
                return json.loads(content.decode("utf-8"))
        except HTTPError as e:
            message = e.read().decode("utf-8", "ignore")
            raise SpotifyBridgeError(e.code, message or e.reason, e.headers.get("Retry-After"))
        except URLError as e:
            raise SpotifyBridgeError(502, str(e.reason))


class BridgeHandler(BaseHTTPRequestHandler):
    session = SpotifySession(project_secrets.SPOTIFY_CREDENTIALS)
    preload_lock = threading.Lock()
    last_queue_preload = 0
    state_lock = threading.Lock()
    state_cache = None
    state_cache_at = 0

    def log_message(self, fmt, *args):
        print("{} - {}".format(self.address_string(), fmt % args))

    def do_GET(self):
        self.handle_request("GET")

    def do_POST(self):
        self.handle_request("POST")

    def handle_request(self, method):
        parsed = urlparse(self.path)
        query = parse_qs(parsed.query)

        try:
            if method == "GET":
                data = self.handle_get(parsed.path, query)
            else:
                data = self.handle_post(parsed.path, query, self.read_json_body())
            self.send_json(data)
        except SpotifyBridgeError as e:
            payload = {"error": e.message}
            if e.retry_after:
                payload["retry_after"] = e.retry_after
            self.send_json(payload, status=e.status, retry_after=e.retry_after)
        except Exception as e:
            self.send_json({"error": str(e)}, status=500)

    def handle_get(self, path, query):
        if path == "/health":
            return {"ok": True}
        if path == "/startup":
            state = self.get_playback_state(max_age=10)
            track = state.get("item") if state else None
            if track:
                self.preload_current_album_art_soon(track)
            return state
        if path == "/state":
            state = self.get_playback_state(max_age=3)
            self.preload_queue_album_art_soon()
            return state
        if path == "/album-art/current":
            return self.send_current_album_art(query)
        if path == "/album-art/preload-queue":
            self.preload_queue_album_art(force=True)
            return {"ok": True}
        if path == "/recently-played":
            return self.session.request("GET", "/me/player/recently-played?limit=1")
        if path == "/playlists":
            limit = query.get("limit", ["20"])[0]
            offset = query.get("offset", ["0"])[0]
            return self.session.request("GET", "/me/playlists?limit={}&offset={}".format(limit, offset))
        if path == "/devices":
            return self.session.request("GET", "/me/player/devices", add_device_id=False)
        if path == "/queue":
            queue = self.session.request("GET", "/me/player/queue")
            self.preload_queue_album_art_soon(queue)
            return queue
        if path == "/search":
            term = query.get("q", [""])[0].strip()
            limit = query.get("limit", ["5"])[0]
            if not term:
                return {"tracks": {"items": []}}
            return self.session.request(
                "GET",
                "/search?type=track&limit={}&q={}".format(limit, quote(term)),
                add_device_id=False,
            )
        if path == "/liked/contains":
            track_id = query.get("track_id", [""])[0]
            if not track_id:
                raise SpotifyBridgeError(400, "Missing track_id")
            return {"liked": self.track_is_liked(self.track_uri(track_id))}
        raise SpotifyBridgeError(404, "Unknown endpoint")

    def get_playback_state(self, max_age=3):
        cls = self.__class__
        now = time.time()
        if cls.state_cache and now - cls.state_cache_at < max_age:
            return cls.state_cache

        with cls.state_lock:
            now = time.time()
            if cls.state_cache and now - cls.state_cache_at < max_age:
                return cls.state_cache
            try:
                state = self.session.request("GET", "/me/player")
                self.attach_liked_state(state)
                cls.state_cache = state
                cls.state_cache_at = time.time()
                return state
            except SpotifyBridgeError as e:
                if e.status == 429 and cls.state_cache:
                    print("Spotify rate limited playback state, using cached state")
                    return cls.state_cache
                raise

    def attach_liked_state(self, state):
        track = state.get("item") if state else None
        track_uri = track.get("uri") if track else None
        if track_uri:
            state["track_liked"] = self.track_is_liked(track_uri)

    def track_is_liked(self, track_uri):
        resp = self.session.request(
            "GET",
            "/me/library/contains?uris={}".format(quote(track_uri)),
            add_device_id=False,
        )
        return bool(resp and resp[0])

    def track_uri(self, track_id_or_uri):
        if track_id_or_uri.startswith("spotify:track:"):
            return track_id_or_uri
        return "spotify:track:" + track_id_or_uri

    def send_current_album_art(self, query):
        size = int(query.get("size", ["250"])[0])
        size = max(64, min(640, size))
        state = self.get_playback_state(max_age=10)
        track = state.get("item") if state else None
        if not track:
            raise SpotifyBridgeError(404, "No current track")

        image_url = self.album_image_url(track, size)
        cache_path = self.album_art_cache_path(track, image_url, size)
        if not cache_path.exists():
            self.fetch_album_art(image_url, size, cache_path)

        with cache_path.open("rb") as f:
            payload = f.read()
        self.send_bytes(payload, "image/jpeg")
        return None

    def preload_current_album_art_soon(self, track):
        thread = threading.Thread(
            target=self.preload_current_album_art,
            args=(track,),
            daemon=True,
        )
        thread.start()

    def preload_current_album_art(self, track):
        try:
            for size in ALBUM_ART_PRELOAD_SIZES:
                self.preload_track_album_art(track, size)
        except Exception as e:
            print("Current album-art preload failed:", e)

    def preload_queue_album_art_soon(self, queue_response=None):
        if time.time() - self.__class__.last_queue_preload < QUEUE_PRELOAD_SECONDS:
            return
        thread = threading.Thread(
            target=self.preload_queue_album_art,
            args=(False, queue_response),
            daemon=True,
        )
        thread.start()

    def preload_queue_album_art(self, force=False, queue_response=None):
        if not self.__class__.preload_lock.acquire(blocking=False):
            return
        try:
            if not force and time.time() - self.__class__.last_queue_preload < QUEUE_PRELOAD_SECONDS:
                return

            queue_response = queue_response or self.session.request("GET", "/me/player/queue")
            queue_items = queue_response.get("queue", []) if queue_response else []
            tracks = [
                item for item in queue_items
                if item and item.get("type") == "track" and item.get("album")
            ][:QUEUE_PRELOAD_LIMIT]

            for track in tracks:
                for size in ALBUM_ART_PRELOAD_SIZES:
                    self.preload_track_album_art(track, size)
            self.__class__.last_queue_preload = time.time()
        except Exception as e:
            print("Queue album-art preload failed:", e)
        finally:
            self.__class__.preload_lock.release()

    def preload_track_album_art(self, track, size):
        image_url = self.album_image_url(track, size)
        cache_path = self.album_art_cache_path(track, image_url, size)
        if cache_path.exists():
            return
        self.fetch_album_art(image_url, size, cache_path)

    def album_image_url(self, track, size):
        images = track["album"]["images"]
        image = images[0] if size > 250 or len(images) == 1 else images[1]
        return image["url"]

    def album_art_cache_path(self, track, image_url, size):
        ALBUM_ART_CACHE.mkdir(parents=True, exist_ok=True)
        album = track.get("album", {})
        key = album.get("id") or track.get("id") or hashlib.sha1(image_url.encode()).hexdigest()
        return ALBUM_ART_CACHE / "{}_{}.jpg".format(key, size)

    def fetch_album_art(self, image_url, size, cache_path):
        resize_url = "https://wsrv.nl/?url={}&w={}&h={}".format(image_url, size, size)
        req = Request(resize_url)
        try:
            with urlopen(req, timeout=10) as response:
                payload = response.read()
                self.save_album_art_cache_file(cache_path, payload)
        except HTTPError as e:
            raise SpotifyBridgeError(e.code, e.reason)
        except URLError as e:
            raise SpotifyBridgeError(502, str(e.reason))

    def save_album_art_cache_file(self, cache_path, payload):
        ALBUM_ART_CACHE.mkdir(parents=True, exist_ok=True)
        if self.album_art_cache_size() + len(payload) >= ALBUM_ART_CACHE_MAX_BYTES:
            print("Album-art cache limit reached, purging cache")
            self.purge_album_art_cache()
        cache_path.write_bytes(payload)

    def album_art_cache_size(self):
        if not ALBUM_ART_CACHE.exists():
            return 0
        return sum(path.stat().st_size for path in ALBUM_ART_CACHE.glob("*") if path.is_file())

    def purge_album_art_cache(self):
        if not ALBUM_ART_CACHE.exists():
            return
        for path in ALBUM_ART_CACHE.glob("*"):
            if path.is_file():
                path.unlink()

    def handle_post(self, path, query, body):
        if path == "/play":
            payload = {}
            if body.get("context_uri"):
                payload["context_uri"] = body["context_uri"]
            if body.get("uris"):
                payload["uris"] = body["uris"]
            return self.session.request("PUT", "/me/player/play", payload or None)
        if path == "/pause":
            return self.session.request("PUT", "/me/player/pause")
        if path == "/next":
            return self.session.request("POST", "/me/player/next")
        if path == "/previous":
            return self.session.request("POST", "/me/player/previous")
        if path == "/volume":
            volume = int(body.get("volume_percent", query.get("volume_percent", [50])[0]))
            volume = max(0, min(100, volume))
            return self.session.request("PUT", "/me/player/volume?volume_percent={}".format(volume))
        if path == "/shuffle":
            state = str(body.get("state", query.get("state", ["false"])[0])).lower()
            state = "true" if state in ("1", "true", "on", "yes") else "false"
            return self.session.request("PUT", "/me/player/shuffle?state={}".format(state))
        if path == "/repeat":
            state = body.get("state", query.get("state", ["off"])[0])
            state = state if state in ("track", "context", "off") else "off"
            return self.session.request("PUT", "/me/player/repeat?state={}".format(state))
        if path == "/queue/add":
            uri = body.get("uri") or query.get("uri", [""])[0]
            if not uri:
                raise SpotifyBridgeError(400, "Missing uri")
            return self.session.request("POST", "/me/player/queue?uri={}".format(quote(uri)))
        if path == "/liked/add":
            track_id = body.get("track_id") or query.get("track_id", [""])[0]
            if not track_id:
                raise SpotifyBridgeError(400, "Missing track_id")
            return self.session.request(
                "PUT",
                "/me/library?uris={}".format(quote(self.track_uri(track_id))),
                None,
                add_device_id=False,
            )
        if path == "/liked/remove":
            track_id = body.get("track_id") or query.get("track_id", [""])[0]
            if not track_id:
                raise SpotifyBridgeError(400, "Missing track_id")
            return self.session.request(
                "DELETE",
                "/me/library?uris={}".format(quote(self.track_uri(track_id))),
                None,
                add_device_id=False,
            )
        if path == "/playlist/add":
            playlist_uri = body.get("playlist_uri") or query.get("playlist_uri", [""])[0]
            track_uri = body.get("track_uri") or query.get("track_uri", [""])[0]
            if not playlist_uri or not track_uri:
                raise SpotifyBridgeError(400, "Missing playlist_uri or track_uri")
            playlist_id = playlist_uri.split(":")[-1]
            return self.session.request(
                "POST",
                "/playlists/{}/tracks".format(quote(playlist_id)),
                {"uris": [track_uri]},
                add_device_id=False,
            )
        if path == "/device/select":
            device_id = body.get("device_id") or query.get("device_id", [""])[0]
            if not device_id:
                raise SpotifyBridgeError(400, "Missing device_id")
            self.session.device_id = device_id
            return self.session.request(
                "PUT",
                "/me/player",
                {"device_ids": [device_id], "play": True},
                add_device_id=False,
            )
        raise SpotifyBridgeError(404, "Unknown endpoint")

    def read_json_body(self):
        length = int(self.headers.get("Content-Length", "0"))
        if length <= 0:
            return {}
        raw = self.rfile.read(length).decode("utf-8")
        return json.loads(raw) if raw else {}

    def send_json(self, data, status=200, retry_after=None):
        if data is None:
            return
        payload = json.dumps(data).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(payload)))
        if retry_after:
            self.send_header("Retry-After", str(retry_after))
        self.send_header("Connection", "close")
        self.end_headers()
        self.wfile.write(payload)

    def send_bytes(self, payload, content_type, status=200):
        self.send_response(status)
        self.send_header("Content-Type", content_type)
        self.send_header("Content-Length", str(len(payload)))
        self.send_header("Connection", "close")
        self.end_headers()
        self.wfile.write(payload)


def main():
    parser = argparse.ArgumentParser(description="Run the Presto Spotify bridge")
    parser.add_argument("--host", default="0.0.0.0")
    parser.add_argument("--port", default=8787, type=int)
    args = parser.parse_args()

    server = ThreadingHTTPServer((args.host, args.port), BridgeHandler)
    print("Spotify bridge listening on http://{}:{}".format(args.host, args.port))
    server.serve_forever()


if __name__ == "__main__":
    main()
