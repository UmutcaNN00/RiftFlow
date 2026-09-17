import requests
import logging
import time
import os
import json

logger = logging.getLogger(__name__)

class DataDragon:
    def __init__(self):
        self.versions_url = "https://ddragon.leagueoflegends.com/api/versions.json"
        self.current_version = None
        self.champions_data = {}
        self.champ_id_to_name = {}
        self._last_fetch_attempt = 0
        
        self.cache_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "..", "cache")
        self.cache_file = os.path.join(self.cache_dir, "champion_cache.json")
        os.makedirs(self.cache_dir, exist_ok=True)

    def fetch_latest_version(self):
        try:
            response = requests.get(self.versions_url, timeout=5)
            response.raise_for_status()
            versions = response.json()
            if versions:
                self.current_version = versions[0]
                return self.current_version
        except Exception as e:
            logger.error(f"Failed to fetch DataDragon versions: {e}")
        return "14.18.1"

    def fetch_champions(self):
        if not self.current_version:
            self.fetch_latest_version()
            
        champions_url = f"https://ddragon.leagueoflegends.com/cdn/{self.current_version}/data/tr_TR/champion.json"
        try:
            response = requests.get(champions_url, timeout=6)
            if response.status_code != 200:
                champions_url = f"https://ddragon.leagueoflegends.com/cdn/{self.current_version}/data/en_US/champion.json"
                response = requests.get(champions_url, timeout=6)
            response.raise_for_status()
            data = response.json()
            self.champions_data = data.get("data", {})
            
            # Save to cache
            try:
                with open(self.cache_file, "w", encoding="utf-8") as f:
                    json.dump(self.champions_data, f, ensure_ascii=False)
            except Exception as e:
                logger.error(f"Failed to save champion cache: {e}")
                
        except Exception as e:
            logger.error(f"Failed to fetch champions data, attempting to load from cache: {e}")
            self.load_from_cache()

        if self.champions_data:
            self.champ_id_to_name = {}
            for name, info in self.champions_data.items():
                champ_id = int(info["key"])
                self.champ_id_to_name[champ_id] = info.get("name", name)
                
        return self.champions_data

    def load_from_cache(self):
        if os.path.exists(self.cache_file):
            try:
                with open(self.cache_file, "r", encoding="utf-8") as f:
                    self.champions_data = json.load(f)
                logger.info("Loaded champions data from local cache.")
            except Exception as e:
                logger.error(f"Failed to load champion cache: {e}")
                self.champions_data = {}
        else:
            self.champions_data = {}

    def get_champion_name(self, champ_id):
        if not self.champ_id_to_name:
            if time.time() - self._last_fetch_attempt >= 30:
                self._last_fetch_attempt = time.time()
                self.fetch_champions()
        try:
            return self.champ_id_to_name.get(int(champ_id), "Unknown")
        except (ValueError, TypeError):
            return "Unknown"
        
    def _normalize_name(self, text):
        if not text:
            return ""
        text = text.lower()
        replacements = {
            'ı': 'i', 'i': 'i',
            'ş': 's', 's': 's',
            'ğ': 'g', 'g': 'g',
            'ü': 'u', 'u': 'u',
            'ö': 'o', 'o': 'o',
            'ç': 'c', 'c': 'c'
        }
        for tr, eng in replacements.items():
            text = text.replace(tr, eng)
        return text.replace("'", "").replace(" ", "").replace(".", "")
        
    def get_champion_id(self, champ_name):
        if not champ_name or champ_name == "None":
            return None
            
        target_raw = champ_name.strip()
        
        # Special cases mapping to LCU IDs
        special_cases = {
            "wukong": "monkeyking",
            "nunu & willump": "nunu",
            "renata glasc": "renata"
        }
        
        target_lower = target_raw.lower()
        if target_lower in special_cases:
            target_raw = special_cases[target_lower]
            
        target = self._normalize_name(target_raw)
        
        for internal_id, info in self.champions_data.items():
            disp_name = info.get("name", "")
            
            clean_disp = self._normalize_name(disp_name)
            clean_internal = self._normalize_name(internal_id)
            
            if target == clean_disp or target == clean_internal:
                return int(info["key"])
                
        return None
