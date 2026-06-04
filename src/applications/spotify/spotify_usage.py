try:
    import ujson as json
except ImportError:
    import json

from applications.spotify.spotify_assets import ensure_dir, file_exists
from applications.spotify.spotify_settings import APP_ASSET_ROOT, SD_ASSET_ROOTS


USAGE_FILE_NAME = "spotify_menu_usage.json"


def usage_file_path():
    if file_exists("/sd"):
        cache_root = "/sd/cache"
        ensure_dir(cache_root)
        return cache_root + "/" + USAGE_FILE_NAME

    for root in SD_ASSET_ROOTS:
        if file_exists(root):
            cache_root = root + "/cache"
            ensure_dir(cache_root)
            return cache_root + "/" + USAGE_FILE_NAME

    cache_root = APP_ASSET_ROOT + "/cache"
    ensure_dir(cache_root)
    return cache_root + "/" + USAGE_FILE_NAME


class MenuUsage:
    def __init__(self):
        self.path = usage_file_path()
        self.counts = {
            "devices": {},
            "playlists": {},
        }
        self.load()

    def load(self):
        if not file_exists(self.path):
            return
        try:
            with open(self.path, "r") as f:
                data = json.loads(f.read())
            for category in self.counts:
                values = data.get(category, {})
                if isinstance(values, dict):
                    self.counts[category] = values
        except Exception as e:
            print("Menu usage settings not loaded:", e)

    def save(self):
        try:
            with open(self.path, "w") as f:
                f.write(json.dumps(self.counts))
        except Exception as e:
            print("Menu usage settings not saved:", e)

    def record(self, category, key):
        if category not in self.counts or not key:
            return
        values = self.counts[category]
        values[key] = self.count(category, key) + 1
        self.save()

    def count(self, category, key):
        try:
            return int(self.counts.get(category, {}).get(key, 0))
        except (TypeError, ValueError):
            return 0

    def sort_items(self, category, items, key_index):
        indexed = list(enumerate(items))
        indexed.sort(key=lambda pair: (-self.count(category, pair[1][key_index]), pair[0]))
        return [pair[1] for pair in indexed]
