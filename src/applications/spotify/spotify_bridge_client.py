import ujson as json
import urequests as requests
import time

from applications.spotify.spotify_client import quote, quote_plus


class BridgeHttpError(Exception):
    def __init__(self, status_code, message, retry_after=None):
        super().__init__(message)
        self.status_code = status_code
        self.retry_after = retry_after


class BridgeSession:
    def __init__(self):
        self.device_id = None


class SpotifyBridgeClient:
    def __init__(self, base_url):
        self.base_url = base_url.rstrip("/")
        self.session = BridgeSession()

    def devices(self):
        return self.get("/devices")

    def health(self):
        return self.get("/health")

    def startup_state(self):
        return self.get("/startup")

    def transfer_playback(self, device_id):
        self.session.device_id = device_id
        return self.post("/device/select", {"device_id": device_id})

    def play(self, context_uri=None, uris=None, offset=None, position_ms=None):
        body = {}
        if context_uri is not None:
            body["context_uri"] = context_uri
        if uris is not None:
            body["uris"] = list(uris)
        if offset is not None:
            body["offset"] = offset
        if position_ms is not None:
            body["position_ms"] = position_ms
        return self.post("/play", body)

    def pause(self):
        return self.post("/pause")

    def toggle_shuffle(self, state):
        value = "true" if state else "false"
        return self.post("/shuffle", {"state": value})

    def toggle_repeat(self, state):
        return self.post("/repeat", {"state": state})

    def set_volume(self, volume_percent):
        return self.post("/volume", {"volume_percent": int(volume_percent)})

    def next(self):
        return self.post("/next")

    def previous(self):
        return self.post("/previous")

    def current_playing(self):
        return self.get("/state")

    def recently_played(self):
        return self.get("/recently-played")

    def current_user_playlists(self, limit=20, offset=0):
        return self.get("/playlists?limit={}&offset={}".format(limit, offset))

    def queue(self):
        return self.get("/queue")

    def add_to_queue(self, uri):
        return self.post("/queue/add", {"uri": uri})

    def search_tracks(self, query, limit=5):
        return self.get("/search?type=track&limit={}&q={}".format(limit, quote_plus(query)))

    def liked_tracks_contains(self, track_id):
        resp = self.get("/liked/contains?track_id={}".format(quote(track_id)))
        return bool(resp and resp.get("liked"))

    def save_track(self, track_id):
        return self.post("/liked/add", {"track_id": track_id})

    def remove_saved_track(self, track_id):
        return self.post("/liked/remove", {"track_id": track_id})

    def add_track_to_playlist(self, playlist_uri, track_uri):
        return self.post("/playlist/add", {"playlist_uri": playlist_uri, "track_uri": track_uri})

    def get(self, path):
        response = requests.get(self.base_url + path)
        return self.read_response(response)

    def post(self, path, body=None):
        response = requests.post(
            self.base_url + path,
            headers={"Content-Type": "application/json"},
            data=json.dumps(body or {}),
        )
        return self.read_response(response)

    def read_response(self, response):
        try:
            if response.status_code >= 400:
                retry_after = None
                message = "Bridge HTTP {}".format(response.status_code)
                try:
                    payload = response.json()
                    message = payload.get("error", message)
                    retry_after = payload.get("retry_after")
                except Exception:
                    pass
                raise BridgeHttpError(response.status_code, message, retry_after)
            if response.content:
                return response.json()
            return {}
        finally:
            response.close()


class SpotifyBridgeFallbackClient:
    def __init__(self, bridge_client, local_client):
        self.bridge_client = bridge_client
        self.local_client = local_client
        self.session = bridge_client.session
        self.bridge_retry_at = 0
        self.bridge_status_checked_at = 0
        self.spotify_blocked_until = 0
        self.bridge_available = None

    def devices(self):
        return self.call("devices")

    def startup_state(self):
        if self.spotify_block_remaining():
            self.bridge_available = False
            raise Exception("Spotify API blocked for {}s".format(self.spotify_block_remaining()))
        try:
            result = self.bridge_client.startup_state()
            self.session = self.bridge_client.session
            self.bridge_retry_at = 0
            self.spotify_blocked_until = 0
            self.bridge_available = True
            return result
        except BridgeHttpError as e:
            if e.status_code == 429:
                self.note_spotify_block(e.retry_after)
                raise
            print("Bridge startup unavailable, using local Spotify API:", e)
            self.bridge_retry_at = time.time() + 30
            self.bridge_available = False
            result = self.local_client.current_playing()
            self.session = self.local_client.session
            return result
        except Exception as e:
            print("Bridge startup unavailable, using local Spotify API:", e)
            self.bridge_retry_at = time.time() + 30
            self.bridge_available = False
            result = self.local_client.current_playing()
            self.session = self.local_client.session
            return result

    def transfer_playback(self, device_id):
        result = self.call("transfer_playback", device_id)
        self.session.device_id = self.active_client().session.device_id
        return result

    def play(self, context_uri=None, uris=None, offset=None, position_ms=None):
        return self.call("play", context_uri=context_uri, uris=uris, offset=offset, position_ms=position_ms)

    def pause(self):
        return self.call("pause")

    def toggle_shuffle(self, state):
        return self.call("toggle_shuffle", state)

    def toggle_repeat(self, state):
        return self.call("toggle_repeat", state)

    def set_volume(self, volume_percent):
        return self.call("set_volume", volume_percent)

    def next(self):
        return self.call("next")

    def previous(self):
        return self.call("previous")

    def current_playing(self):
        return self.call("current_playing")

    def recently_played(self):
        return self.call("recently_played")

    def current_user_playlists(self, limit=20, offset=0):
        return self.call("current_user_playlists", limit=limit, offset=offset)

    def queue(self):
        return self.call("queue")

    def add_to_queue(self, uri):
        return self.call("add_to_queue", uri)

    def search_tracks(self, query, limit=5):
        return self.call("search_tracks", query, limit=limit)

    def liked_tracks_contains(self, track_id):
        return self.call("liked_tracks_contains", track_id)

    def save_track(self, track_id):
        return self.call("save_track", track_id)

    def remove_saved_track(self, track_id):
        return self.call("remove_saved_track", track_id)

    def add_track_to_playlist(self, playlist_uri, track_uri):
        return self.call("add_track_to_playlist", playlist_uri, track_uri)

    def call(self, method_name, *args, **kwargs):
        if self.spotify_block_remaining():
            self.bridge_available = False
            raise Exception("Spotify API blocked for {}s".format(self.spotify_block_remaining()))

        if time.time() < self.bridge_retry_at:
            self.bridge_available = False
            result = getattr(self.local_client, method_name)(*args, **kwargs)
            self.session = self.local_client.session
            return result

        try:
            result = getattr(self.bridge_client, method_name)(*args, **kwargs)
            self.session = self.bridge_client.session
            self.bridge_retry_at = 0
            self.spotify_blocked_until = 0
            self.bridge_available = True
            return result
        except BridgeHttpError as e:
            if e.status_code == 429:
                self.note_spotify_block(e.retry_after)
                raise
            print("Bridge unavailable, using local Spotify API:", e)
            self.bridge_retry_at = time.time() + 30
            self.bridge_available = False
            result = getattr(self.local_client, method_name)(*args, **kwargs)
            self.session = self.local_client.session
            return result
        except Exception as e:
            print("Bridge unavailable, using local Spotify API:", e)
            self.bridge_retry_at = time.time() + 30
            self.bridge_available = False
            result = getattr(self.local_client, method_name)(*args, **kwargs)
            self.session = self.local_client.session
            return result

    def active_client(self):
        return self.local_client if self.session is self.local_client.session else self.bridge_client

    def note_spotify_block(self, retry_after):
        try:
            seconds = int(float(retry_after))
        except (TypeError, ValueError):
            seconds = 60
        self.spotify_blocked_until = max(self.spotify_blocked_until, time.time() + seconds)
        self.bridge_retry_at = self.spotify_blocked_until
        self.bridge_available = False

    def spotify_block_remaining(self):
        return max(0, int(self.spotify_blocked_until - time.time()))

    def refresh_bridge_status(self):
        try:
            resp = self.bridge_client.health()
            self.bridge_status_checked_at = time.time()
            if resp and resp.get("spotify_blocked"):
                self.note_spotify_block(resp.get("retry_after"))
            elif self.spotify_block_remaining() == 0:
                self.spotify_blocked_until = 0
                self.bridge_retry_at = 0
                self.bridge_available = True
            return resp
        except Exception as e:
            print("Bridge status unavailable:", e)
            self.bridge_status_checked_at = time.time()
            self.bridge_available = False
            return None
