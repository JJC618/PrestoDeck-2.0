import gc
import time
import jpegdec
import pngdec
import uasyncio as asyncio
from applications.spotify.spotify_assets import asset_path, file_exists, get_album_cover, get_cached_album_cover, mount_sd_card
from applications.spotify.spotify_bridge_client import BridgeHttpError, SpotifyBridgeClient, SpotifyBridgeOnlyClient
from applications.spotify.spotify_controls import ControlButton
from applications.spotify.spotify_settings import (
    APP_VERSION,
    PLAYBACK_FETCH_INTERVAL,
    PLAYLIST_CACHE_SECONDS,
    SD_ASSET_ROOTS,
    SPOTIFY_BRIDGE_BASE_URL,
    TOUCH_FETCH_GRACE,
)
from applications.spotify.spotify_state import State
from base import BaseApp


class StartupError(Exception):
    pass


RECENTLY_PLAYED_BURST_LIMIT = 2
RECENTLY_PLAYED_SLOW_INTERVAL = 600


REQUIRED_SD_ASSETS = (
    "icon.png",
    "icons/close.png",
    "icons/left_arrow.png",
    "icons/light_off.png",
    "icons/light_on.png",
    "icons/like.png",
    "icons/liked.png",
    "icons/next.png",
    "icons/pause.png",
    "icons/play.png",
    "icons/playlists.png",
    "icons/previous.png",
    "icons/repeat_off.png",
    "icons/repeat_on.png",
    "icons/repeat_on_1.png",
    "icons/right_arrow.png",
    "icons/search.png",
    "icons/shuffle_off.png",
    "icons/shuffle_on.png",
    "icons/speaker.png",
    "icons/volume_down.png",
    "icons/volume_up.png",
)


class Spotify(BaseApp):
    def __init__(self):
        super().__init__(ambient_light=True, full_res=True, layers=2)

        self.display.set_font("sans")
        self.display.set_layer(1)
        self.startup_gray_pen = self.display.create_pen(179, 179, 179)
        self.startup_error_pen = self.display.create_pen(255, 0, 0)
        if not mount_sd_card():
            self.halt_startup_error("Loading Spotify...", "(sd card mount failed)")
        if not self.required_sd_assets_available():
            self.halt_startup_error("Loading Spotify...", "(icons missing sd)")

        self.display.set_layer(0)
        try:
            icon = pngdec.PNG(self.display)
            icon.open_file(asset_path("icon.png"))
            icon_x, icon_y = self.centered_visual_position(icon.get_width(), icon.get_height(), y_offset=-20)
            icon.decode(icon_x, icon_y)
            self.presto.update()
        except Exception as e:
            print("Startup icon not loaded:", e)

        self.display.set_layer(1)
        startup_message_at = time.time()
        self.display_startup_message("Connecting to WIFI")

        self.presto.connect()
        wifi_started_at = time.time()
        while not self.presto.wifi.isconnected():
            if time.time() - wifi_started_at > 20:
                self.halt_startup_error("Connecting to WIFI", "(wrong wifi password)")
            self.display_startup_message("Connecting to WIFI")
            time.sleep(0.5)

        self.wait_for_message_minimum(startup_message_at, 2)
        self.clear(1)
        startup_message_at = time.time()
        self.display_startup_message("Loading Spotify...")
        try:
            self.state = State()
            self.spotify_client = self.get_spotify_client()
        except StartupError as e:
            self.halt_startup_error("Loading Spotify...", str(e))
        self.wait_for_message_minimum(startup_message_at, 2)
        self.clear(1)
        self.presto.update()

        self.j = jpegdec.JPEG(self.display)
        self.device_zones = []
        self.playlist_zones = []
        self.playlist_nav_zones = []
        self.queue_zones = []
        self.keyboard_zones = []
        self.keyboard_last_action = None
        self.keyboard_last_press_at = 0
        self.search_result_zones = []
        self.search_action_zones = []
        self.like_action_zones = []
        self.add_playlist_zones = []
        self.device_nav_zones = []
        self.playlists_data = []
        self.playlists_fetched_at = 0
        self.bridge_status_next_at = 0
        self.bridge_status_label = None
        self.album_art_retry_after = {}
        self.album_art_fetched_tracks = {}
        self.album_art_requested_tracks = {}
        self.album_art_bounds = None
        self.pending_art_track_id = None
        self.pending_art_fullscreen = False
        self.art_fetch_after = 0
        self.pending_art_attempts = 0
        self.active_speaker_pen = self.display.create_pen(89, 188, 97)
        self.ui_gray_pen = self.display.create_pen(179, 179, 179)
        self.keyboard_key_pen = self.ui_gray_pen
        self.keyboard_key_shadow_pen = self.ui_gray_pen
        self.keyboard_label_pen = self.display.create_pen(8, 8, 8)
        self.bridge_ok_pen = self.display.create_pen(89, 188, 97)
        self.bridge_bad_pen = self.display.create_pen(255, 0, 0)
        self.bridge_unknown_pen = self.ui_gray_pen
        self.setup_buttons()
        try:
            self.prepare_startup_playback()
        except StartupError as e:
            self.halt_startup_error("Loading Spotify...", str(e))

    def wait_for_message_minimum(self, started_at, seconds):
        remaining = seconds - (time.time() - started_at)
        if remaining > 0:
            time.sleep(remaining)

    def startup_text_x(self, text, scale):
        return self.centered_text_x(text, scale)

    def centered_text_x(self, text, scale, container_width=None, container_x=0):
        width = self.width if container_width is None else container_width
        return container_x + max(0, (width - self.measure_text_width(text, scale)) // 2)

    def centered_visual_x(self, visual_width, container_width=None, container_x=0):
        width = self.width if container_width is None else container_width
        return container_x + max(0, (width - visual_width) // 2)

    def centered_visual_position(self, visual_width, visual_height, y_offset=0):
        return (
            self.centered_visual_x(visual_width),
            max(0, (self.height - visual_height) // 2 + y_offset),
        )

    def centered_button_bounds(self, width, height, y):
        return (self.centered_visual_x(width), y, width, height)

    def sd_asset_exists(self, relative_path):
        for root in SD_ASSET_ROOTS:
            if root.startswith("/sd") and file_exists(root + "/" + relative_path):
                return True
        return False

    def required_sd_assets_available(self):
        for relative_path in REQUIRED_SD_ASSETS:
            if not self.sd_asset_exists(relative_path):
                print("Missing SD asset:", relative_path)
                return False
        return True

    def display_startup_message(self, text, error=None):
        self.clear(1)
        self.display.set_pen(self.ui_gray_pen if hasattr(self, "ui_gray_pen") else self.startup_gray_pen)
        version = "PrestoDeck {}".format(APP_VERSION)
        self.display.text(version, self.startup_text_x(version, 0.6), 12, scale=0.6)
        self.display.set_pen(self.colors.WHITE)
        self.display.set_thickness(2)
        self.display.text(text, self.startup_text_x(text, 1.0), self.height - 80, scale=1.0)
        if error:
            self.display.set_pen(self.bridge_bad_pen if hasattr(self, "bridge_bad_pen") else self.startup_error_pen)
            self.display.text(error, self.startup_text_x(error, 0.8), self.height - 50, scale=0.8)
        self.presto.update()

    def halt_startup_error(self, text, error):
        while True:
            self.display_startup_message(text, error)
            time.sleep(2)

    def display_text(self, text, position, color=65535, scale=1, thickness=None):
        if thickness:
            self.display.set_thickness(2)
        x,y = position
        self.display.set_pen(color)
        self.display.text(text, x, y, scale=scale)
        self.presto.update()

    def schedule_track_change_fetch(self):
        now = time.time()
        self.state.playback_fetch_at = now + 1
        self.state.playback_fetch_until = now + 6
        self.state.playback_fetch_track_id = (self.state.track or {}).get("id")

    def run_api_action(self, action, label="Working..."):
        if self.state.api_busy:
            return None

        self.state.api_busy = True
        try:
            return action()
        except Exception as e:
            print(label, e)
            return None
        finally:
            self.state.api_busy = False

    def apply_playback_result(self, result, previous_requested_track_id=None):
        if not result:
            return

        device_id, track, is_playing, shuffle, repeat, prog, dur, volume, liked = result[:9]
        source = result[9] if len(result) > 9 else "current"
        self.note_playback_source(source)
        previous_track_id = (self.state.track or {}).get("id")
        if device_id:
            self.spotify_client.session.device_id = device_id

        self.state.track = track
        self.state.is_playing = is_playing
        self.state.shuffle = shuffle
        self.state.repeat = repeat
        self.state.progress_ms = prog
        self.state.duration_ms = dur
        if volume is not None:
            self.state.volume_percent = volume
        self.state.track_liked = liked
        self.state.last_progress_update = time.time()
        self.state.force_redraw = True

        current_track_id = (track or {}).get("id")
        if current_track_id and current_track_id != previous_track_id:
            self.queue_album_art_refresh(current_track_id)
        if (
            previous_requested_track_id and
            current_track_id == previous_requested_track_id and
            self.state.playback_fetch_until and
            time.time() < self.state.playback_fetch_until
        ):
            self.state.playback_fetch_at = time.time() + 1
        else:
            self.state.playback_fetch_until = None
            self.state.playback_fetch_track_id = None

    def should_fetch_recently_played(self):
        if self.state.recently_played_attempts < RECENTLY_PLAYED_BURST_LIMIT:
            return True
        return time.time() >= self.state.recently_played_next_at

    def note_playback_source(self, source):
        if source == "recently_played":
            self.state.recently_played_attempts += 1
            if self.state.recently_played_attempts >= RECENTLY_PLAYED_BURST_LIMIT:
                self.state.recently_played_next_at = time.time() + RECENTLY_PLAYED_SLOW_INTERVAL
        elif source == "current":
            self.state.recently_played_attempts = 0
            self.state.recently_played_next_at = 0

    def prepare_startup_playback(self):
        if self.state.api_busy:
            return
        self.state.api_busy = True
        try:
            result = fetch_state(self.spotify_client, startup=True, raise_errors=True)
        except BridgeHttpError as e:
            message = str(e).lower()
            if e.status_code in (401, 403) or self.spotify_credentials_error(message):
                raise StartupError("(spotify uri incorrect)")
            if e.status_code == 502:
                raise StartupError("(bridge unavailable)")
            print("Failed preparing startup playback:", e)
            result = None
        except Exception as e:
            message = str(e).lower()
            if self.spotify_credentials_error(message):
                raise StartupError("(spotify uri incorrect)")
            print("Failed preparing startup playback:", e)
            result = None
        finally:
            self.state.api_busy = False
        if result:
            self.apply_playback_result(result)
            self.state.latest_fetch = time.time()
            if self.state.track:
                self.queue_album_art_refresh(self.state.track.get("id"))
                self.art_fetch_after = time.time() + 0.5
        else:
            self.state.playback_fetch_at = time.time() + 2
            self.state.force_redraw = True

    def draw_menu_nav(self, page, total_pages, zones, align_right=False):
        zones.clear()
        if total_pages <= 1:
            return

        nav_y = self.height - 48
        if align_right:
            left_bounds = (245, nav_y, 70, 45)
            right_bounds = (self.width - 80, nav_y, 70, 45)
        else:
            left_bounds = (145, nav_y, 70, 45)
            right_bounds = (self.width - 215, nav_y, 70, 45)
        page_text = "{}/{}".format(page + 1, total_pages)
        page_scale = 0.6
        left_center = left_bounds[0] + (left_bounds[2] // 2)
        right_center = right_bounds[0] + (right_bounds[2] // 2)
        page_center = (left_center + right_center) // 2
        page_x = page_center - (self.measure_text_width(page_text, page_scale) // 2)

        try:
            left = pngdec.PNG(self.display)
            left.open_file(asset_path("icons/left_arrow.png"))
            right = pngdec.PNG(self.display)
            right.open_file(asset_path("icons/right_arrow.png"))

            if page > 0:
                left.decode(left_bounds[0] + (left_bounds[2] - left.get_width()) // 2, left_bounds[1] + 7)
                zones.append(("prev", left_bounds))
            if page < total_pages - 1:
                right.decode(right_bounds[0] + (right_bounds[2] - right.get_width()) // 2, right_bounds[1] + 7)
                zones.append(("next", right_bounds))
        except Exception as e:
            print("Menu nav icons not loaded:", e)

        self.display.set_pen(self.ui_gray_pen)
        self.display.text(page_text, page_x, nav_y + 18, scale=page_scale)

    def render_speaker_screen(self):
        self.clear(1)
        self.display.set_pen(self.colors._BLACK)
        self.display.rectangle(0, 0, self.width, self.height)
        self.display.set_pen(self.colors.WHITE)
        self.display.set_thickness(3)
        self.display.text("Select Speaker", 15, 15, scale=1.0)

        for button in self.buttons:
            if button.name == "Close Queue":
                button.update(self.state, button)
                button.draw(self.state)

        self.device_zones = []
        self.device_nav_zones = []
        y = 70
        row_height = 50
        items_per_page = 5
        total_pages = max(1, (len(self.state.devices_data) + items_per_page - 1) // items_per_page)
        self.state.device_page = min(self.state.device_page, total_pages - 1)
        page_start = self.state.device_page * items_per_page
        page_devices = self.state.devices_data[page_start:page_start + items_per_page]

        for name, dev_id, is_active in page_devices:
            display_name = name if len(name) <= 26 else name[:24] + ".."
            self.display.set_pen(self.ui_gray_pen)
            self.display.line(15, y + row_height - 5, self.width - 15, y + row_height - 5)
            self.display.set_pen(self.active_speaker_pen if is_active else self.colors.WHITE)
            self.display.text(display_name, 25, y + 10, scale=0.8)
            self.device_zones.append((dev_id, (0, y, self.width, row_height)))
            y += row_height
        if not self.state.devices_data:
            if self.spotify_api_blocked():
                self.draw_api_blocked_results_message()
            else:
                self.display.text("No Speakers Found", 25, y, scale=0.8)
        self.draw_menu_nav(self.state.device_page, total_pages, self.device_nav_zones)
        self.presto.update()

    def spotify_credentials_error(self, message):
        terms = (
            "401",
            "403",
            "invalid",
            "scope",
            "permission",
            "refresh_token",
            "client_id",
            "client_secret",
            "credentials",
            "access token",
            "token",
        )
        return any(term in message for term in terms)

    def get_spotify_client(self):
        if not SPOTIFY_BRIDGE_BASE_URL:
            raise StartupError("(bridge url missing)")
        bridge_client = SpotifyBridgeClient(SPOTIFY_BRIDGE_BASE_URL)
        try:
            health = bridge_client.health()
        except Exception:
            raise StartupError("(bridge unavailable)")
        bridge_version = health.get("bridge_version") if health else None
        if bridge_version and bridge_version != APP_VERSION:
            raise StartupError("(version mismatch)")
        return SpotifyBridgeOnlyClient(bridge_client)
        
    def setup_buttons(self):
        """Initializes control buttons and their behavior."""
        def update_show_controls(state, button):
            if button.name == "Playlist" and state.menu_mode in (1, 2, 3, 4, 5, 6, 7, 8, 9):
                button.enabled = True
            else:
                button.enabled = state.menu_mode == 0

        def update_play_pause(state, button):
            button.enabled = state.menu_mode == 0
            button.icon = "pause.png" if state.is_playing else "play.png"

        def update_shuffle(state, button):
            button.enabled = state.menu_mode == 0
            button.icon = "shuffle_on.png" if state.shuffle else "shuffle_off.png"

        def update_repeat(state, button):
            button.enabled = state.menu_mode == 0
            if state.repeat == "track":
                button.icon = "repeat_on_1.png"
            elif state.repeat == "context":
                button.icon = "repeat_on.png"
            else:
                button.icon = "repeat_off.png"

        def update_volume_button(state, button):
            button.enabled = (
                state.menu_mode == 0 and
                not state.volume_buttons_hidden and
                not self.spotify_api_blocked()
            )

        def update_like_button(state, button):
            button.enabled = state.menu_mode == 0 and state.track is not None
            button.icon = "liked.png" if state.track_liked else "like.png"

        def update_light_or_speaker(state, button):
            """Transforms the top-right multi-action button contextually."""
            button.enabled = state.menu_mode in (0, 1)
            if state.menu_mode == 1:
                button.icon = "speaker.png"
            else:
                button.icon = "light_on.png" if state.toggle_leds else "light_off.png"

        def update_close_queue(state, button):
            button.enabled = state.menu_mode in (2, 3, 4, 5, 6, 7, 8)

        def update_search_button(state, button):
            button.enabled = state.menu_mode == 1

        def play_pause(self):
            if self.state.is_playing:
                self.spotify_client.pause()
            else:
                self.spotify_client.play()
            self.state.is_playing = not self.state.is_playing
            self.state.last_progress_update = time.time()
            self.state.force_redraw = True

        def next_track(self):
            self.spotify_client.next()
            self.schedule_track_change_fetch()
            self.state.force_redraw = True

        def previous_track(self):
            self.spotify_client.previous()
            self.schedule_track_change_fetch()
            self.state.force_redraw = True

        def toggle_shuffle(self):
            self.spotify_client.toggle_shuffle(not self.state.shuffle)
            self.state.shuffle = not self.state.shuffle
            self.state.force_redraw = True

        def toggle_repeat(self):
            next_repeat = {
                "off": "context",
                "context": "track",
                "track": "off",
            }.get(self.state.repeat, "context")
            self.spotify_client.toggle_repeat(next_repeat)
            self.state.repeat = next_repeat
            self.state.force_redraw = True

        def volume_down(self):
            self.adjust_volume(-5)

        def volume_up(self):
            self.adjust_volume(5)

        def open_like_menu(self):
            if not self.state.track:
                return
            self.state.menu_mode = 7
            self.state.fullscreen_art = False
            self.state.force_redraw = True

        def handle_top_right_press(self):
            if self.state.menu_mode == 1:
                self.state.menu_mode = 2
                self.fetch_devices()
            else:
                self.toggle_leds(not self.state.toggle_leds)
                self.state.toggle_leds = not self.state.toggle_leds
            self.state.fullscreen_art = False
            self.state.force_redraw = True

        def handle_playlist_button(self):
            if self.state.menu_mode in (1, 2, 3, 4, 5, 6, 7, 8, 9):
                self.state.menu_mode = 0
                self.clear(1)
                self.state.latest_fetch = None
                self.state.devices_data = []
                self.state.queue_data = []
                self.state.search_results = []
                self.state.selected_search_index = None
            else:
                self.state.menu_mode = 1
                self.state.force_redraw = True
                self.fetch_and_render_playlists()
            self.state.fullscreen_art = False
            self.state.force_redraw = True

        def close_overlay(self):
            if self.state.menu_mode == 2:
                self.state.menu_mode = 1
            elif self.state.menu_mode == 5:
                self.state.menu_mode = 4
            elif self.state.menu_mode == 6:
                self.state.menu_mode = 5
            elif self.state.menu_mode == 8:
                self.state.menu_mode = 7
            else:
                self.state.menu_mode = 0
            self.clear(1)
            self.state.queue_data = []
            if self.state.menu_mode not in (4, 5):
                self.state.search_results = []
            self.state.selected_search_index = None
            self.state.fullscreen_art = False
            self.state.force_redraw = True

        def open_search(self):
            self.state.menu_mode = 4
            self.state.search_query = ""
            self.state.search_results = []
            self.state.selected_search_index = None
            self.state.t9_key = None
            self.state.t9_index = 0
            self.state.t9_picker = None
            self.state.fullscreen_art = False
            self.state.force_redraw = True

        buttons_config = [
            ("Playlist", ["playlists.png"], (0, 0, 80, 80), handle_playlist_button, update_show_controls),
            ("Next", ["next.png"], (self.center_x + 60, self.height - 100, 80, 100), next_track, update_show_controls),
            ("Previous", ["previous.png"], (self.center_x - 140, self.height - 100, 80, 100), previous_track, update_show_controls),
            ("Play", ["play.png", "pause.png"], self.centered_button_bounds(80, 100, self.height - 100), play_pause, update_play_pause),
            ("Toggle Shuffle", ["shuffle_on.png", "shuffle_off.png"], (self.center_x - 230, self.height - 100, 80, 100), toggle_shuffle, update_shuffle),
            ("Toggle Repeat", ["repeat_on.png", "repeat_on_1.png", "repeat_off.png"], (self.center_x + 150, self.height - 100, 80, 100), toggle_repeat, update_repeat),
            ("Volume Down", ["volume_down.png"], (20, 155, 60, 80), volume_down, update_volume_button),
            ("Volume Up", ["volume_up.png"], (400, 155, 60, 80), volume_up, update_volume_button),
            ("Like", ["like.png", "liked.png"], (390, self.height - 180, 80, 80), open_like_menu, update_like_button),
            ("Top Right Multi Button", ["light_on.png", "light_off.png", "speaker.png"], (self.width - 100, 0, 100, 80), handle_top_right_press, update_light_or_speaker),
            ("Search", ["search.png"], (self.width - 200, 0, 100, 80), open_search, update_search_button),
            ("Close Queue", ["close.png"], (self.width - 100, 0, 100, 80), close_overlay, update_close_queue),
        ]

        self.buttons = [
            ControlButton(self.display, name, icons, bounds, on_press, update)
            for name, icons, bounds, on_press, update in buttons_config
        ]

    def fetch_devices(self):
        """Downloads active hardware device routes available to target."""
        try:
            resp = self.spotify_client.devices()
            if resp and "devices" in resp:
                self.state.devices_data = [
                    (d["name"], d["id"], d.get("is_active", False))
                    for d in resp["devices"] if d
                ]
                self.state.device_page = 0
        except Exception as e:
            print("Error retrieving network speakers:", e)
            self.state.devices_data = []

    def fetch_and_render_search_results(self):
        """Downloads track search results and opens the results screen."""
        query = self.state.search_query.strip()
        if not query:
            return

        self.clear(1)
        self.display.set_pen(self.colors._BLACK)
        self.display.rectangle(0, 0, self.width, self.height)
        self.display.set_pen(self.colors.WHITE)
        self.display.text("Searching...", 40, self.height // 2, scale=1.0)
        self.presto.update()

        try:
            resp = self.spotify_client.search_tracks(query)
            items = resp.get("tracks", {}).get("items", []) if resp else []
            self.state.search_results = [
                item for item in items
                if item and item.get("uri")
            ][:5]
        except Exception as e:
            print("Error searching tracks:", e)
            self.state.search_results = []

        self.state.menu_mode = 5
        self.state.force_redraw = True

    def render_search_keyboard(self):
        """Draws the search keyboard and query field."""
        self.clear(1)
        self.keyboard_zones = []

        self.display.set_pen(self.colors._BLACK)
        self.display.rectangle(0, 0, self.width, self.height)
        keyboard_y = 80

        self.display.set_pen(self.colors._BLACK)
        self.display.rectangle(8, 6, self.width - 110, 42)
        self.display.set_pen(self.colors.WHITE)
        query = self.state.search_query[-24:] if self.state.search_query else "Search tracks"
        self.display.text(query, 18, 18, scale=0.8)

        for button in self.buttons:
            if button.name == "Close Queue":
                button.update(self.state, button)
                button.draw(self.state)

        self.draw_qwerty_keyboard(keyboard_y)
        self.presto.update()

    def draw_qwerty_keyboard(self, keyboard_y):
        """Draws a compact on-screen QWERTY keyboard."""
        key_h = 70
        gap = 6
        small_gap = 4
        key_w = 43
        rows = [
            "1234567890",
            "qwertyuiop",
            "asdfghjkl",
            "zxcvbnm",
        ]

        for row_index, row_keys in enumerate(rows):
            row_width = (len(row_keys) * key_w) + ((len(row_keys) - 1) * small_gap)
            x = (self.width - row_width) // 2
            y = keyboard_y + (row_index * (key_h + gap))
            for char in row_keys:
                self.draw_keyboard_key(char, char, x, y, key_w, key_h)
                x += key_w + small_gap

        controls_y = keyboard_y + (4 * (key_h + gap))
        x = 7
        self.draw_keyboard_key("back", "DEL", x, controls_y, 94, key_h, label_scale=0.65)
        x += 94 + gap
        self.draw_keyboard_key("space", "SPACE", x, controls_y, 230, key_h, label_scale=0.7)
        x += 230 + gap
        self.draw_keyboard_key("search", "SEARCH", x, controls_y, self.width - x - 7, key_h, label_scale=0.6)

    def draw_keyboard_key(self, action, label, x, y, width, height, label_scale=0.9):
        self.display.set_pen(self.keyboard_key_shadow_pen)
        self.display.rectangle(x, y + height - 10, width, 10)
        self.display.set_pen(self.keyboard_key_pen)
        self.display.rectangle(x, y, width, height - 4)
        self.draw_centered_keyboard_text(label.upper(), x, y, width, height - 4, label_scale)
        self.keyboard_zones.append((action, (x, y, width, height)))

    def draw_centered_keyboard_text(self, text, x, y, width, height, scale):
        text_width = int(len(text) * 8 * scale)
        text_height = int(14 * scale)
        text_x = x + max(2, (width - text_width) // 2)
        text_y = y + max(2, ((height - text_height) // 2) + 1)
        self.display.set_pen(self.keyboard_label_pen)
        self.display.set_thickness(2)
        self.display.text(text, text_x, text_y, scale=scale)

    def adjust_volume(self, delta):
        """Changes the active Spotify device volume by the requested percentage."""
        if self.spotify_api_blocked():
            self.state.force_redraw = True
            return
        volume = max(0, min(100, self.state.volume_percent + delta))
        try:
            self.spotify_client.set_volume(volume)
            self.state.volume_percent = volume
            self.state.volume_overlay_until = time.time() + 5
        except Exception as e:
            print("Failed changing volume:", e)
        self.state.force_redraw = True

    def draw_volume_overlay(self):
        if self.spotify_api_blocked():
            x = 115
            y = 18
            width = 250
            height = 30
            label = "Spotify API Blocked"
            self.display.set_pen(self.colors._BLACK)
            self.display.rectangle(x, y, width, height)
            self.display.set_pen(self.bridge_bad_pen)
            text_x = self.centered_text_x(label, 0.7, container_width=width, container_x=x)
            self.display.text(label, text_x, y + 8, scale=0.7)
            return
        if time.time() > self.state.volume_overlay_until:
            return
        x = 115
        y = 18
        width = 250
        height = 30
        bar_width = width - 20
        fill = int(bar_width * max(0, min(100, self.state.volume_percent)) / 100)
        self.display.set_pen(self.colors._BLACK)
        self.display.rectangle(x, y, width, height)
        self.display.set_pen(self.ui_gray_pen)
        self.display.rectangle(x + 10, y + 10, bar_width, 10)
        self.display.set_pen(self.active_speaker_pen)
        self.display.rectangle(x + 10, y + 10, fill, 10)

    def draw_toast(self):
        if not self.state.toast_message or time.time() > self.state.toast_until:
            return
        self.display.set_pen(self.colors._BLACK)
        self.display.rectangle(25, 200, self.width - 50, 70)
        self.display.set_pen(self.colors.WHITE)
        line = self.state.toast_message
        self.display.text(line[:32], 45, 225, scale=0.8)

    def render_message_screen(self):
        self.clear(1)
        self.display.set_pen(self.colors._BLACK)
        self.display.rectangle(0, 0, self.width, self.height)
        self.display.set_pen(self.colors.WHITE)
        line = self.state.toast_message or ""
        self.display.text(line[:30], 35, self.height // 2, scale=0.8)
        self.presto.update()

    def draw_bridge_status(self):
        bridge_available = getattr(self.spotify_client, "bridge_available", None)
        block_remaining = 0
        if hasattr(self.spotify_client, "spotify_block_remaining"):
            block_remaining = self.spotify_client.spotify_block_remaining()
        if block_remaining:
            self.display.set_pen(self.bridge_bad_pen)
            label = "Bridge Blocked {}s".format(block_remaining)
            self.display.text(label, 10, self.height - 24, scale=0.6)
            return

        if bridge_available is True:
            self.display.set_pen(self.bridge_ok_pen)
            label = "Bridge Active"
        elif bridge_available is False:
            self.display.set_pen(self.bridge_bad_pen)
            label = "Bridge Failed"
        else:
            self.display.set_pen(self.bridge_unknown_pen)
            label = "Bridge Unknown"
        self.display.text(label, 10, self.height - 24, scale=0.6)

    def draw_api_blocked_results_message(self):
        try:
            self.display.set_font("bitmap8")
        except Exception:
            pass
        self.display.set_pen(self.bridge_bad_pen)
        scale = 1
        lines = (
            "(Spotify API blocked therefore results not loading.)",
            "(Please see settings menu for timer.)",
        )
        y = self.height - 44
        for line in lines:
            self.display.text(line, self.centered_text_x(line, scale), y, scale=scale)
            y += 20
        self.display.set_font("sans")

    def spotify_api_blocked(self):
        if hasattr(self.spotify_client, "spotify_block_remaining"):
            return self.spotify_client.spotify_block_remaining() > 0
        return False

    def bridge_status_text(self):
        bridge_available = getattr(self.spotify_client, "bridge_available", None)
        block_remaining = 0
        if hasattr(self.spotify_client, "spotify_block_remaining"):
            block_remaining = self.spotify_client.spotify_block_remaining()
        if block_remaining:
            return "Bridge Blocked {}s".format(block_remaining)
        if bridge_available is True:
            return "Bridge Active"
        if bridge_available is False:
            return "Bridge Failed"
        return "Bridge Unknown"

    def refresh_bridge_status_if_due(self):
        if not hasattr(self.spotify_client, "refresh_bridge_status"):
            return
        now = time.time()
        if now < self.bridge_status_next_at:
            return
        previous_label = self.bridge_status_text()
        self.bridge_status_next_at = now + 15
        self.spotify_client.refresh_bridge_status()
        current_label = self.bridge_status_text()
        if current_label != previous_label or current_label != self.bridge_status_label:
            self.bridge_status_label = current_label
            if self.state.menu_mode in (0, 1, 2, 5):
                self.state.force_redraw = True

    def render_search_results(self):
        """Draws track search results."""
        self.clear(1)
        self.search_result_zones = []
        self.search_action_zones = []

        self.display.set_pen(self.colors._BLACK)
        self.display.rectangle(0, 0, self.width, self.height)
        self.display.set_pen(self.colors.WHITE)
        self.display.set_thickness(3)
        self.display.text("Search Results", 25, 35, scale=0.9)

        for button in self.buttons:
            if button.name == "Close Queue":
                button.update(self.state, button)
                button.draw(self.state)

        y_offset = 95
        row_height = 50
        if not self.state.search_results:
            if self.spotify_api_blocked():
                self.draw_api_blocked_results_message()
            else:
                self.display.text("No Results", 25, y_offset, scale=0.8)
        else:
            for index, track in enumerate(self.state.search_results):
                name = track.get("name", "")
                artist_items = track.get("artists", [])
                artists = ", ".join([artist.get("name", "") for artist in artist_items])
                label = name
                if artists:
                    label = name + " - " + artists
                label = ''.join(i if ord(i) < 128 else ' ' for i in label)
                display_name = label if len(label) <= 31 else label[:29] + ".."
                self.display.set_pen(self.ui_gray_pen)
                self.display.line(15, y_offset + row_height - 5, self.width - 15, y_offset + row_height - 5)
                self.display.set_pen(self.colors.WHITE)
                self.display.text(display_name, 25, y_offset + 10, scale=0.7)
                self.search_result_zones.append((index, (0, y_offset, self.width, row_height)))
                y_offset += row_height

        self.presto.update()

    def render_search_action_screen(self):
        """Draws play/queue choices for the selected search result."""
        self.clear(1)
        self.search_action_zones = []

        self.display.set_pen(self.colors._BLACK)
        self.display.rectangle(0, 0, self.width, self.height)
        self.display.set_pen(self.colors.WHITE)
        self.display.set_thickness(3)
        self.display.text("Track Action", 25, 35, scale=0.9)

        self.draw_close_button()

        track = self.selected_search_track()
        y_offset = 105
        if track:
            name = track.get("name", "")
            artists = ", ".join([artist.get("name", "") for artist in track.get("artists", [])])
            label = name + (" - " + artists if artists else "")
            label = ''.join(i if ord(i) < 128 else ' ' for i in label)
            display_name = label if len(label) <= 31 else label[:29] + ".."
            self.display.set_pen(self.colors.WHITE)
            self.display.text(display_name, 25, y_offset, scale=0.7)
        else:
            self.display.text("No Track Selected", 25, y_offset, scale=0.8)

        actions = [
            ("play", "Play Now", 165),
            ("queue", "Add to Queue", 240),
        ]
        for action, label, y in actions:
            self.display.set_pen(self.ui_gray_pen)
            self.display.rectangle(25, y, self.width - 50, 58)
            self.display.set_pen(self.colors.WHITE)
            self.display.text(label, 55, y + 18, scale=0.9)
            self.search_action_zones.append((action, (25, y, self.width - 50, 58)))

        self.presto.update()

    def draw_close_button(self):
        for button in self.buttons:
            if button.name == "Close Queue":
                button.update(self.state, button)
                button.draw(self.state)
                break

    def selected_search_track(self):
        index = self.state.selected_search_index
        if index is None or index < 0 or index >= len(self.state.search_results):
            return None
        return self.state.search_results[index]

    def close_search_action(self):
        self.state.menu_mode = 0
        self.clear(1)
        self.state.latest_fetch = None
        self.state.search_results = []
        self.state.selected_search_index = None
        self.state.fullscreen_art = False
        self.state.force_redraw = True

    def render_like_action_screen(self):
        self.clear(1)
        self.like_action_zones = []

        self.display.set_pen(self.colors._BLACK)
        self.display.rectangle(0, 0, self.width, self.height)
        self.display.set_pen(self.colors.WHITE)
        self.display.set_thickness(3)
        self.display.text("Track Options", 25, 35, scale=0.9)
        self.draw_close_button()

        track_name = (self.state.track or {}).get("name", "")
        track_name = ''.join(i if ord(i) < 128 else ' ' for i in track_name)
        self.display.set_pen(self.colors.WHITE)
        self.display.text(track_name[:31], 25, 105, scale=0.7)

        liked_action = "remove_liked" if self.state.track_liked else "liked"
        liked_label = "Remove from Liked" if self.state.track_liked else "Add to Liked Tracks"
        actions = [
            (liked_action, liked_label, 165),
            ("playlist", "Add to Playlist", 240),
        ]
        for action, label, y in actions:
            self.display.set_pen(self.ui_gray_pen)
            self.display.rectangle(25, y, self.width - 50, 58)
            self.display.set_pen(self.colors.WHITE)
            self.display.text(label, 55, y + 18, scale=0.85)
            self.like_action_zones.append((action, (25, y, self.width - 50, 58)))

        self.presto.update()

    def render_add_to_playlist_screen(self):
        self.clear(1)
        self.add_playlist_zones = []

        self.display.set_pen(self.colors._BLACK)
        self.display.rectangle(0, 0, self.width, self.height)
        self.display.set_pen(self.colors.WHITE)
        self.display.set_thickness(3)
        self.display.text("Add to Playlist", 25, 35, scale=0.9)
        self.draw_close_button()

        y_offset = 95
        row_height = 50
        if not self.playlists_data:
            self.display.text("None Found", 25, y_offset, scale=0.8)
        else:
            for name, uri in self.playlists_data:
                display_name = name if len(name) <= 26 else name[:24] + ".."
                self.display.set_pen(self.ui_gray_pen)
                self.display.line(15, y_offset + row_height - 5, self.width - 15, y_offset + row_height - 5)
                self.display.set_pen(self.colors.WHITE)
                self.display.text(display_name, 25, y_offset + 10, scale=0.8)
                self.add_playlist_zones.append((name, uri, (0, y_offset, self.width, row_height)))
                y_offset += row_height

        self.presto.update()

    def add_current_track_to_liked(self):
        track_id = (self.state.track or {}).get("id")
        if not track_id:
            return
        try:
            self.spotify_client.save_track(track_id)
            self.state.track_liked = self.spotify_client.liked_tracks_contains(track_id)
        except Exception as e:
            print("Failed adding liked track:", e)
        self.state.menu_mode = 0
        self.clear(1)
        self.state.force_redraw = True

    def remove_current_track_from_liked(self):
        track_id = (self.state.track or {}).get("id")
        if not track_id:
            return
        try:
            self.spotify_client.remove_saved_track(track_id)
            self.state.track_liked = False
        except Exception as e:
            print("Failed removing liked track:", e)
        self.state.menu_mode = 0
        self.clear(1)
        self.state.force_redraw = True

    def add_current_track_to_playlist(self, playlist_name, playlist_uri):
        track_uri = (self.state.track or {}).get("uri")
        if not track_uri:
            return
        try:
            self.spotify_client.add_track_to_playlist(playlist_uri, track_uri)
            self.state.toast_message = "Added to playlist " + playlist_name[:12]
            self.state.toast_until = time.time() + 3
        except Exception as e:
            print("Failed adding track to playlist:", e)
            self.state.toast_message = "Playlist add failed"
            self.state.toast_until = time.time() + 3
        self.state.menu_mode = 9
        self.clear(1)
        self.state.force_redraw = True

    def fetch_and_render_queue(self):
        """Downloads upcoming queue tracks and opens the queue screen."""
        self.clear(1)
        self.display.set_pen(self.colors._BLACK)
        self.display.rectangle(0, 0, self.width, self.height)
        self.display.set_pen(self.colors.WHITE)
        self.display.text("Loading Queue...", 40, self.height // 2, scale=1.0)
        self.presto.update()

        try:
            resp = self.spotify_client.queue()
            queue = resp.get("queue", []) if resp else []
            self.state.queue_data = [
                item for item in queue
                if item and item.get("type") == "track" and item.get("uri")
            ][:5]
        except Exception as e:
            print("Error retrieving queue:", e)
            self.state.queue_data = []

        self.state.force_redraw = True

    def render_queue_screen(self):
        """Draws upcoming queue tracks."""
        self.clear(1)
        self.queue_zones = []

        self.display.set_pen(self.colors._BLACK)
        self.display.rectangle(0, 0, self.width, self.height)
        self.display.set_pen(self.colors.WHITE)
        self.display.set_thickness(3)
        self.display.text("Up Next", 25, 35, scale=1.0)

        for button in self.buttons:
            if button.name == "Close Queue":
                button.update(self.state, button)
                button.draw(self.state)

        y_offset = 95
        row_height = 50
        if not self.state.queue_data:
            self.display.text("Queue Empty", 25, y_offset, scale=0.8)
        else:
            for track in self.state.queue_data:
                name = track.get("name", "")
                display_name = name if len(name) <= 26 else name[:24] + ".."
                self.display.set_pen(self.ui_gray_pen)
                self.display.line(15, y_offset + row_height - 5, self.width - 15, y_offset + row_height - 5)
                self.display.set_pen(self.colors.WHITE)
                self.display.text(display_name, 25, y_offset + 10, scale=0.8)
                y_offset += row_height

        self.presto.update()

    def play_queue_from_index(self, index):
        """Starts playback from a selected queue entry and keeps following queued tracks."""
        tracks = self.state.queue_data[index:]
        uris = [track.get("uri") for track in tracks if track.get("uri")]
        if uris:
            self.spotify_client.play(uris=uris)
            self.state.is_playing = True
            self.state.latest_fetch = None
            self.state.force_redraw = True

    def fetch_and_render_playlists(self):
        """Downloads playlist metadata using the backend endpoint module."""
        if self.playlists_data and time.time() - self.playlists_fetched_at < PLAYLIST_CACHE_SECONDS:
            self.state.force_redraw = True
            return

        self.clear(1)
        self.display.set_pen(self.colors._BLACK)
        self.display.rectangle(0, 0, self.width, self.height)
        
        self.display.set_pen(self.colors.WHITE)
        self.display.text("Loading Settings...", 40, self.height // 2, scale=1.0)
        self.presto.update()

        try:
            resp = self.spotify_client.current_user_playlists()
            if resp and "items" in resp:
                items = resp["items"]
                raw_list = [(p["name"], p["uri"]) for p in items if p]
                self.playlists_data = raw_list
                self.state.playlist_page = 0
                self.playlists_fetched_at = time.time()
        except Exception as e:
            print("Error retrieving playlists:", e)
            self.playlists_data = []
            self.state.playlist_page = 0

        self.state.force_redraw = True

    def render_playlist_screen(self):
        """Draws playlist navigation with a speaker-menu shortcut."""
        self.clear(1)
        self.playlist_zones = []
        self.playlist_nav_zones = []
        self.device_zones = []

        self.display.set_pen(self.colors._BLACK)
        self.display.rectangle(0, 0, self.width, self.height)
        
        self.display.set_pen(self.colors.WHITE)
        self.display.set_thickness(3)
        self.display.text("Playlists", 70, 45, scale=1.0)
        self.draw_bridge_status()

        for button in self.buttons:
            if button.name in ["Playlist", "Search", "Top Right Multi Button"]:
                button.update(self.state, button)
                button.draw(self.state)

        y_offset_start = 110
        row_height = 50
        
        y_offset = y_offset_start
        if not self.playlists_data:
            self.display.text("None Found", 30, y_offset, scale=0.7)
        else:
            items_per_page = 6
            total_pages = max(1, (len(self.playlists_data) + items_per_page - 1) // items_per_page)
            self.state.playlist_page = min(self.state.playlist_page, total_pages - 1)
            page_start = self.state.playlist_page * items_per_page
            page_playlists = self.playlists_data[page_start:page_start + items_per_page]

            for name, uri in page_playlists:
                display_name = name if len(name) <= 26 else name[:24] + ".."
                self.display.set_pen(self.ui_gray_pen)
                self.display.line(15, y_offset + row_height - 5, self.width - 15, y_offset + row_height - 5)
                
                self.display.set_pen(self.colors.WHITE)
                self.display.text(display_name, 25, y_offset + 10, scale=0.8)
                
                self.playlist_zones.append((uri, (0, y_offset, self.width, row_height)))
                y_offset += row_height
            self.draw_menu_nav(self.state.playlist_page, total_pages, self.playlist_nav_zones, align_right=True)

        self.presto.update()

    def run(self):
        """Starts the app's event loops."""
        loop = asyncio.get_event_loop()
        loop.create_task(self.touch_handler_loop())
        loop.create_task(self.display_loop())
        loop.run_forever()

    async def touch_handler_loop(self):
        """Handles touch input events and button presses."""
        while not self.state.exit:
            self.touch.poll()

            if self.touch.state:
                self.state.last_touch_time = time.time()
                if self.state.menu_mode == 0 and self.state.volume_buttons_hidden:
                    self.state.volume_buttons_hidden = False
                    self.state.force_redraw = True

            if self.state.menu_mode == 1:
                if self.touch.state:
                    tx, ty = self.touch.x, self.touch.y
                    hit_action = False

                    for direction, bounds in self.playlist_nav_zones:
                        bx, by, bw, bh = bounds
                        if bx <= tx <= (bx + bw) and by <= ty <= (by + bh):
                            hit_action = True
                            if direction == "prev":
                                self.state.playlist_page = max(0, self.state.playlist_page - 1)
                            else:
                                self.state.playlist_page += 1
                            self.state.force_redraw = True
                            break

                    if not hit_action:
                        for target, bounds in self.playlist_zones:
                            bx, by, bw, bh = bounds
                            if bx <= tx <= (bx + bw) and by <= ty <= (by + bh):
                                hit_action = True
                                print(f"Selected Playlist URI: {target}")
                                try:
                                    self.spotify_client.play(context_uri=target)
                                    self.state.is_playing = True
                                except Exception as e:
                                    print("Failed starting context play:", e)
                                self.state.menu_mode = 0
                                self.clear(1)
                                self.state.latest_fetch = None
                                self.state.force_redraw = True
                                self.state.fullscreen_art = False
                                self.state.devices_data = []
                                self.state.queue_data = []
                                break

                    if not hit_action:
                        for button in self.buttons:
                            if button.name in ["Playlist", "Search", "Top Right Multi Button"]:
                                button.update(self.state, button)
                                if button.is_pressed(self.state):
                                    hit_action = True
                                    button.on_press(self)
                                    break

                    while self.touch.state:
                        self.touch.poll()
                        await asyncio.sleep_ms(5)
            elif self.state.menu_mode == 2:
                if self.touch.state:
                    tx, ty = self.touch.x, self.touch.y
                    hit_action = False

                    for direction, bounds in self.device_nav_zones:
                        bx, by, bw, bh = bounds
                        if bx <= tx <= (bx + bw) and by <= ty <= (by + bh):
                            hit_action = True
                            if direction == "prev":
                                self.state.device_page = max(0, self.state.device_page - 1)
                            else:
                                self.state.device_page += 1
                            self.state.force_redraw = True
                            break

                    if not hit_action:
                        for dev_id, bounds in self.device_zones:
                            bx, by, bw, bh = bounds
                            if bx <= tx <= (bx + bw) and by <= ty <= (by + bh):
                                hit_action = True
                                print(f"Transferring playback to device: {dev_id}")
                                try:
                                    self.spotify_client.transfer_playback(dev_id)
                                    self.spotify_client.session.device_id = dev_id
                                    self.state.devices_data = [
                                        (name, item_dev_id, item_dev_id == dev_id)
                                        for name, item_dev_id, is_active in self.state.devices_data
                                    ]
                                except Exception as e:
                                    print("Failed device transfer:", e)
                                self.state.menu_mode = 1
                                self.state.fullscreen_art = False
                                self.state.force_redraw = True
                                break

                    if not hit_action:
                        for button in self.buttons:
                            if button.name in ["Playlist", "Close Queue"]:
                                button.update(self.state, button)
                                if button.is_pressed(self.state):
                                    hit_action = True
                                    button.on_press(self)
                                    break

                    while self.touch.state:
                        self.touch.poll()
                        await asyncio.sleep_ms(5)
            elif self.state.menu_mode == 3:
                if self.touch.state:
                    for button in self.buttons:
                        if button.name in ["Playlist", "Close Queue"]:
                            button.update(self.state, button)
                            if button.is_pressed(self.state):
                                button.on_press(self)
                                break

                    while self.touch.state:
                        self.touch.poll()
                        await asyncio.sleep_ms(5)
            elif self.state.menu_mode == 4:
                if self.touch.state:
                    tx, ty = self.touch.x, self.touch.y
                    hit_action = False

                    for action, bounds in self.keyboard_zones:
                        bx, by, bw, bh = bounds
                        if bx <= tx <= (bx + bw) and by <= ty <= (by + bh):
                            now = time.time()
                            if action == self.keyboard_last_action and now - self.keyboard_last_press_at < 0.12:
                                hit_action = True
                                break
                            self.keyboard_last_action = action
                            self.keyboard_last_press_at = now
                            hit_action = True
                            if action == "space":
                                if self.state.search_query:
                                    self.state.search_query += " "
                                self.state.t9_key = None
                                self.state.t9_picker = None
                            elif action == "back":
                                self.state.search_query = self.state.search_query[:-1]
                                self.state.t9_key = None
                                self.state.t9_picker = None
                            elif action == "search":
                                self.state.t9_key = None
                                self.state.t9_picker = None
                                self.fetch_and_render_search_results()
                            else:
                                if len(self.state.search_query) < 32:
                                    self.state.search_query += action
                                self.state.t9_key = None
                                self.state.t9_picker = None
                            self.state.force_redraw = True
                            break

                    if not hit_action:
                        for button in self.buttons:
                            if button.name in ["Playlist", "Close Queue"]:
                                button.update(self.state, button)
                                if button.is_pressed(self.state):
                                    button.on_press(self)
                                    break

                    if not self.touch.state:
                        self.keyboard_last_action = None
            elif self.state.menu_mode == 5:
                if self.touch.state:
                    tx, ty = self.touch.x, self.touch.y
                    hit_action = False

                    for index, bounds in self.search_result_zones:
                        bx, by, bw, bh = bounds
                        if bx <= tx <= (bx + bw) and by <= ty <= (by + bh):
                            hit_action = True
                            self.state.selected_search_index = index
                            self.state.menu_mode = 6
                            self.state.fullscreen_art = False
                            self.state.force_redraw = True
                            break

                    if not hit_action:
                        for button in self.buttons:
                            if button.name in ["Playlist", "Close Queue"]:
                                button.update(self.state, button)
                                if button.is_pressed(self.state):
                                    button.on_press(self)
                                    break

                    while self.touch.state:
                        self.touch.poll()
                        await asyncio.sleep_ms(5)
            elif self.state.menu_mode == 6:
                if self.touch.state:
                    tx, ty = self.touch.x, self.touch.y
                    hit_action = False

                    for action, bounds in self.search_action_zones:
                        bx, by, bw, bh = bounds
                        if bx <= tx <= (bx + bw) and by <= ty <= (by + bh):
                            hit_action = True
                            track = self.selected_search_track()
                            if track:
                                try:
                                    if action == "play":
                                        self.spotify_client.play(uris=[track.get("uri")])
                                        self.state.is_playing = True
                                    else:
                                        self.spotify_client.add_to_queue(track.get("uri"))
                                except Exception as e:
                                    print("Failed handling search result:", e)
                            self.close_search_action()
                            break

                    if not hit_action:
                        for button in self.buttons:
                            if button.name in ["Playlist", "Close Queue"]:
                                button.update(self.state, button)
                                if button.is_pressed(self.state):
                                    button.on_press(self)
                                    break

                    while self.touch.state:
                        self.touch.poll()
                        await asyncio.sleep_ms(5)
            elif self.state.menu_mode == 7:
                if self.touch.state:
                    tx, ty = self.touch.x, self.touch.y
                    hit_action = False

                    for action, bounds in self.like_action_zones:
                        bx, by, bw, bh = bounds
                        if bx <= tx <= (bx + bw) and by <= ty <= (by + bh):
                            hit_action = True
                            if action == "liked":
                                self.add_current_track_to_liked()
                            elif action == "remove_liked":
                                self.remove_current_track_from_liked()
                            else:
                                self.fetch_and_render_playlists()
                                self.state.menu_mode = 8
                                self.state.force_redraw = True
                            break

                    if not hit_action:
                        for button in self.buttons:
                            if button.name in ["Playlist", "Close Queue"]:
                                button.update(self.state, button)
                                if button.is_pressed(self.state):
                                    button.on_press(self)
                                    break

                    while self.touch.state:
                        self.touch.poll()
                        await asyncio.sleep_ms(5)
            elif self.state.menu_mode == 8:
                if self.touch.state:
                    tx, ty = self.touch.x, self.touch.y
                    hit_action = False

                    for playlist_name, playlist_uri, bounds in self.add_playlist_zones:
                        bx, by, bw, bh = bounds
                        if bx <= tx <= (bx + bw) and by <= ty <= (by + bh):
                            hit_action = True
                            self.add_current_track_to_playlist(playlist_name, playlist_uri)
                            break

                    if not hit_action:
                        for button in self.buttons:
                            if button.name in ["Playlist", "Close Queue"]:
                                button.update(self.state, button)
                                if button.is_pressed(self.state):
                                    button.on_press(self)
                                    break

                    while self.touch.state:
                        self.touch.poll()
                        await asyncio.sleep_ms(5)
            else:
                if self.touch.state:
                    if self.state.fullscreen_art:
                        self.state.fullscreen_art = False
                        self.state.force_redraw = True
                        if self.state.track:
                            self.queue_album_art_refresh(self.state.track.get("id"))
                        self.clear(1)
                        self.presto.update()
                        while self.touch.state:
                            self.touch.poll()
                            await asyncio.sleep_ms(5)
                        await asyncio.sleep_ms(10)
                        continue

                    tx, ty = self.touch.x, self.touch.y
                    hit_action = False

                    if self.album_art_bounds:
                        bx, by, bw, bh = self.album_art_bounds
                        if bx <= tx <= (bx + bw) and by <= ty <= (by + bh):
                            hit_action = True
                            self.state.menu_mode = 3
                            self.state.force_redraw = True
                            self.fetch_and_render_queue()
                            self.state.force_redraw = True

                    if not hit_action:
                        for button in self.buttons:
                            button.update(self.state, button)
                            if button.is_pressed(self.state):
                                print(f"{button.name} pressed")
                                try:
                                    button.on_press(self)
                                except Exception as e:
                                    print(f"Failed to execute on_press: {e}")
                                break
                
                    while self.touch.state:
                        self.touch.poll()
                        await asyncio.sleep_ms(5)

            await asyncio.sleep_ms(10)

    def show_image(self, img, minimized=False):
        """Displays an album cover image offset 50 pixels upward on the screen."""
        try:
            self.j.open_RAM(memoryview(img))

            img_width, img_height = self.j.get_width(), self.j.get_height()
            img_x, img_y = self.centered_visual_position(img_width, img_height, y_offset=-60)
            self.album_art_bounds = (img_x, img_y, img_width, img_height)

            self.clear(0)
            self.j.decode(img_x, img_y, jpegdec.JPEG_SCALE_FULL, dither=True)

        except (OSError, TypeError):
            self.album_art_bounds = None
            print("Failed to load image.")
            self.show_icon_placeholder()

    def show_icon_placeholder(self, fullscreen=False):
        """Displays the app icon when album art is unavailable."""
        try:
            icon = pngdec.PNG(self.display)
            icon.open_file(asset_path("icon.png"))
            icon_width = icon.get_width()
            icon_height = icon.get_height()
            icon_x, icon_y = self.centered_visual_position(icon_width, icon_height)
            if not fullscreen:
                icon_y -= 60
                self.album_art_bounds = (icon_x, icon_y, icon_width, icon_height)
            else:
                self.album_art_bounds = None
                self.clear(1)

            self.clear(0)
            icon.decode(icon_x, icon_y)
        except Exception as e:
            self.album_art_bounds = None
            print("Failed to load icon placeholder:", e)

    def queue_album_art_refresh(self, track_id, fullscreen=False):
        size = 250
        retry_key = "{}_{}".format(track_id, size)
        if self.album_art_requested_tracks.get(retry_key):
            self.pending_art_track_id = None
            return
        if time.time() < self.album_art_retry_after.get(retry_key, 0):
            self.pending_art_track_id = None
            self.show_icon_placeholder(fullscreen=fullscreen)
            return
        self.pending_art_track_id = track_id
        self.pending_art_fullscreen = False
        self.pending_art_attempts = 0
        self.art_fetch_after = time.time() + 1.5
        self.show_icon_placeholder(fullscreen=fullscreen)

    def refresh_pending_album_art(self):
        if not self.pending_art_track_id or not self.state.track:
            return
        if time.time() < self.art_fetch_after:
            return
        if time.time() - self.state.last_touch_time < 1:
            self.art_fetch_after = time.time() + 1
            return

        track_id = self.state.track.get("id")
        if track_id != self.pending_art_track_id:
            self.pending_art_track_id = None
            return

        size = 250
        retry_key = "{}_{}".format(track_id, size)
        self.album_art_requested_tracks[retry_key] = True
        img = get_album_cover(self.state.track, size)
        if img:
            self.show_image(img)
            self.album_art_fetched_tracks[retry_key] = True
            self.pending_art_track_id = None
            return
        else:
            self.show_icon_placeholder(fullscreen=self.pending_art_fullscreen)
        self.pending_art_track_id = None

    def show_fullscreen_image(self, img):
        """Displays album art full screen for idle playback mode."""
        try:
            self.j.open_RAM(memoryview(img))

            img_width, img_height = self.j.get_width(), self.j.get_height()
            img_x = (self.width - img_width) // 2
            img_y = (self.height - img_height) // 2
            self.album_art_bounds = None

            self.clear(0)
            self.clear(1)
            self.j.decode(img_x, img_y, jpegdec.JPEG_SCALE_FULL, dither=True)
            self.draw_fullscreen_progress()
            self.presto.update()

        except (OSError, TypeError):
            print("Failed to load fullscreen image.")
            self.show_icon_placeholder(fullscreen=True)

    def format_progress_time(self, milliseconds):
        seconds = max(0, int(milliseconds // 1000))
        return "{}:{:02d}".format(seconds // 60, seconds % 60)

    def measure_text_width(self, text, scale):
        try:
            return int(self.display.measure_text(text, scale=scale))
        except Exception:
            return int(len(text) * 8 * scale)

    def draw_fullscreen_progress(self):
        if not self.state.duration_ms:
            return

        progress_ms = self.state.get_current_progress()
        duration_ms = self.state.duration_ms
        bar_width = 200
        bar_height = 10
        bar_x = (self.width - bar_width) // 2
        bar_y = 20
        fill = int(bar_width * min(progress_ms, duration_ms) / duration_ms)
        elapsed = self.format_progress_time(progress_ms)
        total = self.format_progress_time(duration_ms)
        text_scale = 0.6
        track_scale = text_scale
        text_width = int(len(elapsed) * 8 * text_scale)
        text_height = int(14 * text_scale)
        text_y = bar_y + (bar_height - text_height) // 2 + 5
        track_name = (self.state.track or {}).get("name", "")
        track_name = ''.join(i if ord(i) < 128 else ' ' for i in track_name)
        track_y = bar_y + bar_height + 14

        self.display.set_layer(1)
        self.display.set_pen(self.colors.BLACK)
        self.display.rectangle(bar_x - 1, bar_y - 1, bar_width + 2, bar_height + 2)
        self.display.set_pen(self.ui_gray_pen)
        self.display.rectangle(bar_x, bar_y, bar_width, bar_height)
        self.display.set_pen(self.active_speaker_pen)
        self.display.rectangle(bar_x, bar_y, fill, bar_height)
        elapsed_x = bar_x - text_width - 25
        total_x = bar_x + bar_width + 5
        self.display.set_pen(self.colors.BLACK)
        for x_offset, y_offset in ((-1, 0), (1, 0), (0, -1), (0, 1)):
            self.display.text(elapsed, elapsed_x + x_offset, text_y + y_offset, scale=text_scale)
            self.display.text(total, total_x + x_offset, text_y + y_offset, scale=text_scale)
        self.display.set_pen(self.ui_gray_pen)
        self.display.text(elapsed, elapsed_x, text_y, scale=text_scale)
        self.display.text(total, total_x, text_y, scale=text_scale)
        if track_name:
            while self.measure_text_width(track_name, track_scale) > self.width - 20 and len(track_name) > 4:
                track_name = track_name[:-5] + " ..."
            track_width = self.measure_text_width(track_name, track_scale)
            track_x = (self.width - track_width) // 2
            self.display.set_pen(self.colors.BLACK)
            for x_offset, y_offset in ((-1, 0), (1, 0), (0, -1), (0, 1)):
                self.display.text(track_name, track_x + x_offset, track_y + y_offset, scale=track_scale)
            self.display.set_pen(self.ui_gray_pen)
            self.display.text(track_name, track_x, track_y, scale=track_scale)
        self.state.fullscreen_progress_bucket = int(progress_ms // 5000)

    def write_track(self):
        """Writes the track name and artists on the screen."""
        if self.state.menu_mode != 0:
            return

        if not self.state.track:
            bridge_available = getattr(self.spotify_client, "bridge_available", None)
            if self.spotify_api_blocked() or bridge_available is False:
                return
            self.display.set_thickness(2)
            self.display.set_pen(self.ui_gray_pen)
            label = "Loading Spotify..."
            self.display.text(label, self.centered_text_x(label, 0.8), self.height - 125, scale=0.8)
            return

        self.display.set_thickness(3)

        track_name = self.state.track.get("name")
        track_name = ''.join(i if ord(i) < 128 else ' ' for i in track_name)
        if len(track_name) > 14:
            track_name = track_name[:14] + " ..."
        self.display.set_pen(self.colors._BLACK)
        self.display.text(track_name, 20, self.height - 137, scale=1.1)
        
        self.display.set_pen(self.colors.WHITE)
        self.display.text(track_name, 18, self.height - 140, scale=1.1)
        
        artists = ", ".join([artist.get("name") for artist in self.state.track.get("artists")])
        artists = ''.join(i if ord(i) < 128 else ' ' for i in artists)
        if len(artists) > 25:
            artists = artists[:25] + " ..."
        self.display.set_thickness(2)
        self.display.set_pen(self.colors._BLACK)
        self.display.text(artists, 20, self.height - 108, scale=0.7)
        
        self.display.set_pen(self.colors.WHITE)
        self.display.text(artists, 18, self.height - 111, scale=0.7)

    async def display_loop(self):
        """Periodically updates the display with the latest track info and controls."""
        prev_state = self.state.copy()
        
        if self.state.track:
            self.queue_album_art_refresh(self.state.track.get("id"))
            
        self.clear(1)
        for button in self.buttons:
            button.update(self.state, button)
            button.draw(self.state)
        self.write_track()
        self.draw_volume_overlay()
        self.presto.update()

        while not self.state.exit:
            self.refresh_bridge_status_if_due()
            self.touch.poll()
            if self.touch.state:
                self.state.last_touch_time = time.time()
                if self.state.menu_mode == 0 and self.state.volume_buttons_hidden:
                    self.state.volume_buttons_hidden = False
                    self.state.force_redraw = True
            if (
                self.state.menu_mode == 0 and
                not self.state.fullscreen_art and
                not self.state.volume_buttons_hidden and
                time.time() - self.state.last_touch_time > 6
            ):
                self.state.volume_buttons_hidden = True
                self.state.force_redraw = True
            if self.state.volume_overlay_until and time.time() > self.state.volume_overlay_until:
                self.state.volume_overlay_until = 0
                self.state.force_redraw = True
            if self.state.toast_until and time.time() > self.state.toast_until:
                self.state.toast_until = 0
                self.state.toast_message = None
                if self.state.menu_mode == 9:
                    self.state.menu_mode = 0
                    self.clear(1)
                self.state.force_redraw = True

            if self.state.menu_mode == 0:
                scheduled_fetch_due = (
                    self.state.playback_fetch_at is not None and
                    time.time() >= self.state.playback_fetch_at
                )
                ready_to_fetch = (
                    not self.state.latest_fetch or
                    time.time() - self.state.latest_fetch > PLAYBACK_FETCH_INTERVAL
                )
                missing_track_fetch_due = (
                    self.state.track is None and
                    (
                        not self.state.latest_fetch or
                        time.time() - self.state.latest_fetch > 5
                    )
                )
                recently_touched = time.time() - self.state.last_touch_time < TOUCH_FETCH_GRACE
                if missing_track_fetch_due or scheduled_fetch_due or (ready_to_fetch and not recently_touched):
                    self.state.latest_fetch = time.time()
                    self.state.playback_fetch_at = None
                    previous_requested_track_id = self.state.playback_fetch_track_id
                    result = self.run_api_action(
                        lambda: fetch_state(
                            self.spotify_client,
                            allow_recently_played=self.should_fetch_recently_played(),
                        ),
                        "Failed fetching playback state:",
                    )
                    if result:
                        self.apply_playback_result(result, previous_requested_track_id)

                await asyncio.sleep(0)

                previous_track_id = (prev_state.track or {}).get('id') if prev_state else None
                if self.state.track and previous_track_id != self.state.track.get("id"):
                    self.queue_album_art_refresh(
                        self.state.track.get("id"),
                        fullscreen=self.state.fullscreen_art,
                    )

                await asyncio.sleep(0)
                self.refresh_pending_album_art()

                if self.state.track and not self.state.fullscreen_art and time.time() - self.state.last_touch_time > 30:
                    self.state.fullscreen_art = True
                    self.state.force_redraw = False
                    img = get_cached_album_cover(self.state.track, 480) or get_cached_album_cover(self.state.track, 250)
                    if img:
                        self.show_fullscreen_image(img)
                    else:
                        self.show_icon_placeholder(fullscreen=True)
                    prev_state = self.state.copy()
                    await asyncio.sleep_ms(200)
                    continue

                if self.state.fullscreen_art:
                    progress_bucket = int(self.state.get_current_progress() // 5000) if self.state.duration_ms else -1
                    if progress_bucket != self.state.fullscreen_progress_bucket:
                        img = (
                            get_cached_album_cover(self.state.track, 480) or
                            get_cached_album_cover(self.state.track, 250)
                        ) if self.state.track else None
                        if img:
                            self.show_fullscreen_image(img)
                        else:
                            self.show_icon_placeholder(fullscreen=True)
                        prev_state = self.state.copy()
                    if prev_state != self.state or self.state.force_redraw:
                        self.state.force_redraw = False
                        if self.state.track:
                            img = get_cached_album_cover(self.state.track, 480) or get_cached_album_cover(self.state.track, 250)
                            if img:
                                self.show_fullscreen_image(img)
                            else:
                                self.show_icon_placeholder(fullscreen=True)
                        prev_state = self.state.copy()
                    await asyncio.sleep_ms(200)
                    continue

                if prev_state != self.state or self.state.force_redraw:
                    self.state.force_redraw = False
                    
                    self.clear(1)
                    for button in self.buttons:
                        button.update(self.state, button)
                        button.draw(self.state)
                    self.write_track()
                    self.draw_volume_overlay()

                    self.presto.update()
                    prev_state = self.state.copy()
            else:
                if prev_state != self.state or self.state.force_redraw:
                    self.state.force_redraw = False
                    if self.state.menu_mode == 1:
                        self.render_playlist_screen()
                    elif self.state.menu_mode == 2:
                        self.render_speaker_screen()
                    elif self.state.menu_mode == 3:
                        self.render_queue_screen()
                    elif self.state.menu_mode == 4:
                        self.render_search_keyboard()
                    elif self.state.menu_mode == 5:
                        self.render_search_results()
                    elif self.state.menu_mode == 7:
                        self.render_like_action_screen()
                    elif self.state.menu_mode == 8:
                        self.render_add_to_playlist_screen()
                    elif self.state.menu_mode == 9:
                        self.render_message_screen()
                    else:
                        self.render_search_action_screen()
                    prev_state = self.state.copy()

            gc.collect()
            await asyncio.sleep_ms(200)

def fetch_state(spotify_client, startup=False, raise_errors=False, allow_recently_played=True):
    """Fetches the current playback state from Spotify."""
    current_track = None
    is_playing = False
    shuffle = False
    repeat = "off"
    device_id = None
    progress_ms = 0
    duration_ms = 0
    volume_percent = None
    track_liked = False
    source = "current"
    try:
        if startup and hasattr(spotify_client, "startup_state"):
            resp = spotify_client.startup_state()
        else:
            resp = spotify_client.current_playing()
        if resp and resp.get("item"):
            current_track = resp["item"]
            is_playing = resp.get("is_playing")
            shuffle = resp.get("shuffle_state")
            repeat = resp.get("repeat_state", "off")
            device_id = resp["device"]["id"]
            volume_percent = resp["device"].get("volume_percent")
            track_liked = bool(resp.get("track_liked", False))
            progress_ms = resp.get("progress_ms", 0)
            duration_ms = current_track.get("duration_ms", 0)
            print("Got current playing track: " + current_track.get("name"))
    except Exception as e:
        print("Failed to get current playing track:", e)
        if raise_errors:
            raise

    if not current_track and allow_recently_played:
        try:
            resp = spotify_client.recently_played()
            if resp and resp.get("items"):
                current_track = resp["items"][0]["track"]
                duration_ms = current_track.get("duration_ms", 0)
                source = "recently_played"
                print("Got recently playing track: " + current_track.get("name"))
        except Exception as e:
            print("Failed to get recently played track:", e)
            if raise_errors:
                raise

    if not current_track:
        return None

    return device_id, current_track, is_playing, shuffle, repeat, progress_ms, duration_ms, volume_percent, track_liked, source

def launch():
    """Launches the Spotify app and starts the event loop."""
    app = Spotify()
    app.run()

    app.clear()
    del app
    gc.collect()
