import json
import os
import sys
import shutil
import logging
import threading

logger = logging.getLogger(__name__)

def get_default_config_path():
    if getattr(sys, 'frozen', False):
        base_dir = os.path.dirname(sys.executable)
    else:
        base_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
    return os.path.join(base_dir, "settings.json")

class ConfigManager:
    def __init__(self, config_path=None):
        if not config_path or config_path == "settings.json":
            self.config_path = get_default_config_path()
        else:
            self.config_path = config_path
        self.config = {}
        self._lock = threading.Lock()

    def load(self):
        with self._lock:
            if not os.path.exists(self.config_path):
                self.config = {}
                return

            try:
                with open(self.config_path, 'r', encoding='utf-8') as f:
                    self.config = json.load(f)
            except json.JSONDecodeError:
                logger.error(f"Corrupted config found at {self.config_path}. Backing up to .bak.")
                bak_path = f"{self.config_path}.bak"
                try:
                    shutil.copy2(self.config_path, bak_path)
                except Exception as e:
                    logger.error(f"Failed to create backup: {e}")
                self.config = {}
            except Exception as e:
                logger.error(f"Error loading config: {e}")
                self.config = {}

            # Enforce defaults
            defaults = {
                "auto_pick": True,
                "auto_ban": True,
                "auto_accept": True
            }
            needs_save = False
            for k, v in defaults.items():
                if k not in self.config:
                    self.config[k] = v
                    needs_save = True
                    
            if needs_save:
                # Can't call self.save() directly as it would deadlock on self._lock
                tmp_path = f"{self.config_path}.tmp"
                try:
                    with open(tmp_path, 'w', encoding='utf-8') as f:
                        json.dump(self.config, f, indent=4)
                    os.replace(tmp_path, self.config_path)
                except Exception as e:
                    logger.error(f"Error saving default config values: {e}")

    def save(self):
        with self._lock:
            tmp_path = f"{self.config_path}.tmp"
            try:
                with open(tmp_path, 'w', encoding='utf-8') as f:
                    json.dump(self.config, f, indent=4)
                # Atomic replacement
                os.replace(tmp_path, self.config_path)
            except Exception as e:
                logger.error(f"Error saving config: {e}")
                if os.path.exists(tmp_path):
                    try:
                        os.remove(tmp_path)
                    except Exception as clean_e:
                        logger.error(f"Error removing tmp file: {clean_e}")

    def get(self, key, default=None):
        with self._lock:
            return self.config.get(key, default)

    def set(self, key, value):
        with self._lock:
            self.config[key] = value
