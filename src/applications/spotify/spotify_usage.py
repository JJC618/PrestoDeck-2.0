try:
    import ujson as json
except ImportError:
    import json

from applications.spotify.spotify_assets import ensure_dir, file_exists
from applications.spotify.spotify_settings import APP_ASSET_ROOT, SD_ASSET_ROOTS


USAGE_FILE_NAME = "spotify_menu_usage.json"
MAX_SEARCH_HISTORY = 500


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
        self.searches = []
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
            searches = data.get("searches", [])
            if isinstance(searches, list):
                self.searches = [item for item in searches if isinstance(item, str)][:MAX_SEARCH_HISTORY]
        except Exception as e:
            print("Menu usage settings not loaded:", e)

    def save(self):
        try:
            with open(self.path, "w") as f:
                data = dict(self.counts)
                data["searches"] = self.searches
                f.write(json.dumps(data))
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

    def record_search(self, query):
        query = query.strip()
        if not query:
            return
        query_lower = query.lower()
        self.searches = [item for item in self.searches if item.lower() != query_lower]
        self.searches.insert(0, query)
        self.searches = self.searches[:MAX_SEARCH_HISTORY]
        self.save()

    def search_suggestion(self, query):
        if not query.strip():
            return None
        query_lower = query.lower()
        matches = []
        for index, item in enumerate(self.searches):
            item_lower = item.lower()
            if item_lower.startswith(query_lower) and item_lower != query_lower:
                matches.append((len(item_lower), index, item))
        if matches:
            matches.sort()
            return matches[0][2]
        return None
