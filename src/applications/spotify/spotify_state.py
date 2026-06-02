import time


class State:
    def __init__(self):
        self.toggle_leds = True
        self.is_playing = False
        self.repeat = "off"
        self.shuffle = False
        self.track = None
        self.menu_mode = 0  # 0=Playback, 1=Playlists, 2=Speaker Select, 3=Queue, 4=Search, 5=Search Results, 6=Search Action, 7=Like Action, 8=Add To Playlist, 9=Message
        self.exit = False
        self.latest_fetch = None
        self.force_redraw = False
        self.progress_ms = 0
        self.duration_ms = 0
        self.volume_percent = 50
        self.volume_overlay_until = 0
        self.volume_buttons_hidden = False
        self.toast_message = None
        self.toast_until = 0
        self.track_liked = False
        self.last_progress_update = 0
        self.playback_fetch_at = None
        self.playback_fetch_until = None
        self.playback_fetch_track_id = None
        self.playback_fetch_allow_recently = True
        self.track_end_fetch_at = None
        self.track_end_fetch_track_id = None
        self.recently_played_attempts = 0
        self.recently_played_next_at = 0
        self.devices_data = []
        self.queue_data = []
        self.playlist_page = 0
        self.device_page = 0
        self.search_query = ""
        self.search_results = []
        self.selected_search_index = None
        self.t9_key = None
        self.t9_index = 0
        self.t9_time = 0
        self.t9_picker = None
        self.last_touch_time = time.time()
        self.fullscreen_art = False
        self.api_busy = False
        self.fullscreen_progress_bucket = -1

    @property
    def show_playlists(self):
        return self.menu_mode == 1

    @show_playlists.setter
    def show_playlists(self, value):
        self.menu_mode = 1 if value else 0

    def copy(self):
        state = State()
        state.toggle_leds = self.toggle_leds
        state.is_playing = self.is_playing
        state.repeat = self.repeat
        state.shuffle = self.shuffle
        state.menu_mode = self.menu_mode
        state.track = {'id': self.track['id']} if self.track else None
        state.devices_data = list(self.devices_data)
        state.queue_data = list(self.queue_data)
        state.playlist_page = self.playlist_page
        state.device_page = self.device_page
        state.search_query = self.search_query
        state.search_results = list(self.search_results)
        state.selected_search_index = self.selected_search_index
        state.t9_picker = self.t9_picker
        state.volume_percent = self.volume_percent
        state.volume_overlay_until = self.volume_overlay_until
        state.volume_buttons_hidden = self.volume_buttons_hidden
        state.toast_message = self.toast_message
        state.toast_until = self.toast_until
        state.track_liked = self.track_liked
        state.playback_fetch_at = self.playback_fetch_at
        state.playback_fetch_until = self.playback_fetch_until
        state.playback_fetch_track_id = self.playback_fetch_track_id
        state.playback_fetch_allow_recently = self.playback_fetch_allow_recently
        state.track_end_fetch_at = self.track_end_fetch_at
        state.track_end_fetch_track_id = self.track_end_fetch_track_id
        state.recently_played_attempts = self.recently_played_attempts
        state.recently_played_next_at = self.recently_played_next_at
        state.fullscreen_art = self.fullscreen_art
        state.api_busy = self.api_busy
        state.fullscreen_progress_bucket = self.fullscreen_progress_bucket
        return state

    def __eq__(self, other):
        if not isinstance(other, State) or other is None:
            return False
        return (
            self.toggle_leds == other.toggle_leds and
            self.is_playing == other.is_playing and
            self.repeat == other.repeat and
            self.shuffle == other.shuffle and
            self.menu_mode == other.menu_mode and
            self.devices_data == other.devices_data and
            self.queue_data == other.queue_data and
            self.playlist_page == other.playlist_page and
            self.device_page == other.device_page and
            self.search_query == other.search_query and
            self.search_results == other.search_results and
            self.selected_search_index == other.selected_search_index and
            self.t9_picker == other.t9_picker and
            self.volume_percent == other.volume_percent and
            self.volume_overlay_until == other.volume_overlay_until and
            self.volume_buttons_hidden == other.volume_buttons_hidden and
            self.toast_message == other.toast_message and
            self.toast_until == other.toast_until and
            self.track_liked == other.track_liked and
            self.playback_fetch_at == other.playback_fetch_at and
            self.playback_fetch_until == other.playback_fetch_until and
            self.playback_fetch_track_id == other.playback_fetch_track_id and
            self.playback_fetch_allow_recently == other.playback_fetch_allow_recently and
            self.track_end_fetch_at == other.track_end_fetch_at and
            self.track_end_fetch_track_id == other.track_end_fetch_track_id and
            self.recently_played_attempts == other.recently_played_attempts and
            self.recently_played_next_at == other.recently_played_next_at and
            self.fullscreen_art == other.fullscreen_art and
            self.api_busy == other.api_busy and
            self.fullscreen_progress_bucket == other.fullscreen_progress_bucket and
            (self.track or {}).get('id') == (other.track or {}).get('id')
        )

    def get_current_progress(self):
        if not self.is_playing:
            return min(self.progress_ms, self.duration_ms)
        elapsed_ms = int((time.time() - self.last_progress_update) * 1000)
        return min(self.progress_ms + elapsed_ms, self.duration_ms)
