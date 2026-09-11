import os
import json
from pathlib import Path


APP_NAME = "Sound IQ"
APP_VERSION = "2.0.0"
APP_AUTHOR = "naimhossain332332-a11y"

SETTINGS_DIR = Path(os.environ.get("APPDATA", Path.home())) / "SoundIQ"
SETTINGS_FILE = SETTINGS_DIR / "settings.json"
LOG_DIR = SETTINGS_DIR / "logs"
DB_DIR = SETTINGS_DIR / "data"

DEFAULT_SETTINGS = {
    "window": {
        "width": 1280,
        "height": 860,
        "maximized": False,
        "sidebar_width": 260,
    },
    "audio": {
        "volume": 80,
        "speed": 100,
        "loop": False,
        "output_device": None,
    },
    "search": {
        "max_results": 100,
        "search_history": [],
        "max_history": 50,
    },
    "indexing": {
        "folders": [],
        "auto_reindex_on_start": False,
    },
    "ui": {
        "theme": "dark",
        "show_splash": True,
    },
    "update": {
        "check_on_startup": True,
        "last_checked": None,
    },
}


class AppSettings:
    def __init__(self):
        self._data = dict(DEFAULT_SETTINGS)
        self._ensure_dirs()
        self.load()

    def _ensure_dirs(self):
        SETTINGS_DIR.mkdir(parents=True, exist_ok=True)
        LOG_DIR.mkdir(parents=True, exist_ok=True)
        DB_DIR.mkdir(parents=True, exist_ok=True)

    def load(self):
        if SETTINGS_FILE.exists():
            try:
                with open(SETTINGS_FILE, "r", encoding="utf-8") as f:
                    saved = json.load(f)
                self._deep_merge(self._data, saved)
            except (json.JSONDecodeError, OSError):
                pass

    def save(self):
        try:
            with open(SETTINGS_FILE, "w", encoding="utf-8") as f:
                json.dump(self._data, f, indent=2, ensure_ascii=False)
        except OSError:
            pass

    def get(self, *keys, default=None):
        obj = self._data
        for key in keys:
            if isinstance(obj, dict) and key in obj:
                obj = obj[key]
            else:
                return default
        return obj

    def set(self, *keys_and_value):
        if len(keys_and_value) < 2:
            return
        *keys, value = keys_and_value
        obj = self._data
        for key in keys[:-1]:
            if key not in obj or not isinstance(obj[key], dict):
                obj[key] = {}
            obj = obj[key]
        obj[keys[-1]] = value
        self.save()

    def _deep_merge(self, base, override):
        for key, value in override.items():
            if key in base and isinstance(base[key], dict) and isinstance(value, dict):
                self._deep_merge(base[key], value)
            else:
                base[key] = value

    @property
    def db_path(self):
        return str(DB_DIR / "metadata.db")

    def add_search_history(self, query):
        history = self.get("search", "search_history", default=[])
        if query in history:
            history.remove(query)
        history.insert(0, query)
        max_h = self.get("search", "max_history", default=50)
        self.set("search", "search_history", history[:max_h])

    def get_search_history(self):
        return self.get("search", "search_history", default=[])
