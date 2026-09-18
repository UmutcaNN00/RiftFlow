import os
import re
import requests
import urllib3
import logging
import time

try:
    import psutil
except ImportError:
    psutil = None

urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)
logger = logging.getLogger(__name__)

class LcuClient:
    def __init__(self, lockfile_path=None):
        self.lockfile_path = lockfile_path
        self.port = None
        self.password = None
        self.protocol = "https"
        self.session = requests.Session()
        self.session.verify = False

    def find_credentials(self):
        # 1. Try reading from running LeagueClientUx process command line
        if psutil:
            try:
                for proc in psutil.process_iter(['name', 'cmdline', 'exe']):
                    name = proc.info.get('name') or ''
                    if 'LeagueClientUx' in name:
                        cmdline = ' '.join(proc.info.get('cmdline') or [])
                        p_match = re.search(r'--app-port=(\d+)', cmdline)
                        t_match = re.search(r'--remoting-auth-token=([\w-]+)', cmdline)
                        if p_match and t_match:
                            self.port = p_match.group(1)
                            self.password = t_match.group(1)
                            self.protocol = "https"
                            self.session.auth = ('riot', self.password)
                            return True
                        
                        exe_path = proc.info.get('exe')
                        if exe_path:
                            candidate = os.path.join(os.path.dirname(exe_path), 'lockfile')
                            if os.path.exists(candidate) and self._parse_file(candidate):
                                return True
            except Exception as e:
                logger.debug(f"Error scanning processes: {e}")

        # 2. Check candidate paths across drives
        candidates = [
            self.lockfile_path,
            r"E:\Riot Games\League of Legends\lockfile",
            r"D:\Riot Games\League of Legends\lockfile",
            r"C:\Riot Games\League of Legends\lockfile",
            r"E:\League of Legends\lockfile",
            r"D:\League of Legends\lockfile",
            r"C:\League of Legends\lockfile",
        ]
        for path in candidates:
            if path and os.path.exists(path):
                if self._parse_file(path):
                    return True

        return False

    def _parse_file(self, path):
        try:
            with open(path, 'r', encoding='utf-8') as f:
                data = f.read().strip().split(':')
                if len(data) >= 5:
                    self.port = data[2]
                    self.password = data[3]
                    self.protocol = data[4]
                    self.session.auth = ('riot', self.password)
                    return True
        except Exception as e:
            logger.error(f"Error reading lockfile {path}: {e}")
        return False

    def parse_lockfile(self):
        return self.find_credentials()

    def get_base_url(self):
        if not self.port or not self.protocol:
            return None
        return f"{self.protocol}://127.0.0.1:{self.port}"

    def request(self, method, endpoint, **kwargs):
        if not self.port:
            if not self.find_credentials():
                raise requests.exceptions.ConnectionError("Could not connect to League Client (LCU).")
            
        url = f"{self.get_base_url()}{endpoint}"
        try:
            response = self.session.request(method, url, timeout=5, **kwargs)
            if response.status_code == 401:
                self.port = None
                self.password = None
                self.session.auth = None
            response.raise_for_status()
            if response.text:
                try:
                    return response.json()
                except ValueError:
                    return response.text
            return {}
        except requests.exceptions.RequestException:
            raise

    def is_alive(self):
        try:
            self.request("GET", "/lol-gameflow/v1/gameflow-phase")
            return True
        except Exception:
            self.port = None
            return False

    def get_gameflow_phase(self):
        try:
            data = self.request("GET", "/lol-gameflow/v1/gameflow-phase")
            if isinstance(data, str):
                return data
            return str(data)
        except Exception:
            return None

    def get_summoner_info(self):
        try:
            return self.request("GET", "/lol-summoner/v1/current-summoner")
        except Exception:
            return None

    def get_lobby_info(self):
        try:
            return self.request("GET", "/lol-lobby/v2/lobby")
        except Exception:
            return None

    def hover_champion(self, action_id, champ_id):
        champ_id = int(champ_id)
        for prefix in ("/lol-champ-select/v1/session/actions", "/lol-champ-select-legacy/v1/session/actions"):
            try:
                self.request("PATCH", f"{prefix}/{action_id}", json={
                    "championId": champ_id,
                    "completed": False
                })
                return True
            except Exception:
                try:
                    self.request("PATCH", f"{prefix}/{action_id}", json={
                        "championId": champ_id
                    })
                    return True
                except Exception as e:
                    logger.debug(f"Hover error on {prefix}/{action_id}: {e}")
        return False

    def lock_champion(self, action_id, champ_id, action_type=None):
        champ_id = int(champ_id)
        logger.info(f"lock_champion called: action {action_id}, champ {champ_id}, type {action_type}")

        # Step 1: PATCH action with championId & completed: True (Primary & Universal LCU lock mechanism)
        for prefix in ("/lol-champ-select/v1/session/actions", "/lol-champ-select-legacy/v1/session/actions"):
            try:
                res = self.request("PATCH", f"{prefix}/{action_id}", json={
                    "championId": champ_id,
                    "completed": True
                })
                if isinstance(res, dict) and res.get("completed") is True:
                    logger.info(f"Action {action_id} verified completed via PATCH {prefix}.")
                    return True
            except Exception as e:
                logger.debug(f"PATCH {prefix}/{action_id} completed:True error: {e}")

        # Step 2: Ensure championId is set, then invoke POST /complete (trigger without body)
        for prefix in ("/lol-champ-select/v1/session/actions", "/lol-champ-select-legacy/v1/session/actions"):
            try:
                self.request("PATCH", f"{prefix}/{action_id}", json={"championId": champ_id})
                time.sleep(0.05)
                url = f"{self.get_base_url()}{prefix}/{action_id}/complete"
                resp = self.session.post(url, timeout=3)
                if resp.status_code in (200, 204):
                    logger.info(f"POST {prefix}/{action_id}/complete status {resp.status_code}")
            except Exception as e:
                logger.debug(f"POST {prefix}/{action_id}/complete error: {e}")

        # Step 3: Definitive ground-truth verification from live session state
        time.sleep(0.08)
        try:
            sess = self.get_champ_select_session()
            if sess and isinstance(sess, dict):
                for group in sess.get("actions", []):
                    for act in group:
                        if act.get("id") == action_id:
                            is_done = bool(act.get("completed"))
                            logger.info(f"Action {action_id} live completed check: {is_done}")
                            return is_done
        except Exception as e:
            logger.debug(f"Session verify error on action {action_id}: {e}")

        return False
            
    def get_champ_select_session(self):
        try:
            return self.request("GET", "/lol-champ-select/v1/session")
        except Exception:
            return None
            
    def accept_matchmaking(self):
        try:
            self.request("POST", "/lol-matchmaking/v1/ready-check/accept")
            return True
        except Exception:
            return False

    def start_matchmaking(self):
        try:
            self.request("POST", "/lol-lobby/v2/lobby/matchmaking/search")
            return True
        except Exception:
            return False

    def stop_matchmaking(self):
        try:
            self.request("DELETE", "/lol-lobby/v2/lobby/matchmaking/search")
            return True
        except Exception:
            return False

    def create_lobby(self, queue_id):
        payload = {"queueId": queue_id}
        try:
            self.request("POST", "/lol-lobby/v2/lobby", json=payload)
            return True
        except Exception:
            return False

    def set_roles(self, first_pref, second_pref):
        """Sets position preferences on the local lobby member with canonical enum validation."""
        role_map = {
            "TOP": "TOP", "JUNGLE": "JUNGLE", "JGL": "JUNGLE",
            "MIDDLE": "MIDDLE", "MID": "MIDDLE", "BOTTOM": "BOTTOM",
            "ADC": "BOTTOM", "BOT": "BOTTOM", "UTILITY": "UTILITY",
            "SUP": "UTILITY", "SUPPORT": "UTILITY", "FILL": "FILL",
            "UNSELECTED": "UNSELECTED"
        }
        c_first = role_map.get(str(first_pref).upper(), "BOTTOM")
        c_second = role_map.get(str(second_pref).upper(), "UTILITY")

        # Duplicate check to prevent LCU 400 error
        if c_first == c_second:
            c_second = "UNSELECTED" if c_first == "FILL" else "FILL"

        if c_first == "FILL":
            c_second = "UNSELECTED"

        payload = {
            "firstPreference": c_first,
            "secondPreference": c_second
        }

        try:
            self.request("PUT", "/lol-lobby/v2/lobby/members/localMember/position-preferences", json=payload)
            logger.info(f"Position preferences set: {c_first} / {c_second}")
            return True
        except Exception as e:
            logger.error(f"Set roles error (payload: {payload}): {e}")
            return False

    def set_summoner_spells(self, spell1_id, spell2_id):
        try:
            self.request("PATCH", "/lol-champ-select/v1/session/my-selection", json={
                "spell1Id": int(spell1_id),
                "spell2Id": int(spell2_id)
            })
            return True
        except Exception as e:
            logger.debug(f"Failed to set summoner spells: {e}")
            return False

    def force_dodge(self):
        """Safely dodges champion select without exiting the League client."""
        try:
            self.request("POST", "/lol-gameflow/v1/session/dodge")
            return True
        except Exception:
            try:
                self.request("POST", "/lol-login/v1/session/invoke", json={
                    "destination": "lcdsServiceProxy",
                    "method": "call",
                    "args": "[\"\", \"teambuilder-draft\", \"quitV2\", \"\"]"
                })
                return True
            except Exception as e:
                logger.error(f"Force dodge error: {e}")
                return False

    def set_chat_availability(self, status="offline"):
        """Changes player availability status in LoL chat (e.g. offline, chat, dnd)."""
        try:
            self.request("PUT", "/lol-chat/v1/me", json={"availability": str(status)})
            return True
        except Exception as e:
            logger.debug(f"Set chat availability error: {e}")
            return False

    def send_champ_select_chat(self, message, repeat_count=1):
        if not message:
            return False
        try:
            convs = self.request('GET', '/lol-chat/v1/conversations')
            if not isinstance(convs, list):
                return False  # LCU hata dict döndürdü, crash önlenir
            champ_conv_id = None
            for c in convs:
                c_type = c.get('type') or ''
                c_id = c.get('id') or ''
                if 'championSelect' in c_type or 'champ-select' in c_id or 'championSelect' in c_id:
                    champ_conv_id = c_id
                    break
            
            if not champ_conv_id and convs:
                for c in convs:
                    if c.get('type') in ('public', 'customGame', 'championSelect'):
                        champ_conv_id = c.get('id')
                        break
                        
            if champ_conv_id:
                count = max(1, min(int(repeat_count), 5))
                for _ in range(count):
                    self.request('POST', f'/lol-chat/v1/conversations/{champ_conv_id}/messages', json={'body': str(message), 'type': 'chat'})
                    time.sleep(0.12)
                return True
        except Exception as e:
            logger.error(f"Failed to send chat message: {e}")
        return False

    def get_bench_champions(self):
        try:
            session = self.get_champ_select_session()
            if session and isinstance(session, dict):
                return session.get("benchChampions", [])
        except Exception:
            pass
        return []

    def swap_bench_champion(self, champ_id):
        try:
            self.request("POST", f"/lol-champ-select/v1/session/bench/swap/{int(champ_id)}")
            return True
        except Exception as e:
            logger.debug(f"Bench swap failed for champ {champ_id}: {e}")
            return False

    def get_received_invitations(self):
        try:
            res = self.request("GET", "/lol-lobby/v2/received-invitations")
            if isinstance(res, list):
                return res
        except Exception:
            pass
        return []

    def accept_invitation(self, invitation_id):
        try:
            self.request("POST", f"/lol-lobby/v2/received-invitations/{invitation_id}/accept")
            return True
        except Exception as e:
            logger.debug(f"Failed to accept invitation {invitation_id}: {e}")
            return False

    def reroll_aram(self):
        try:
            self.request("POST", "/lol-champ-select/v1/session/my-selection/reroll")
            return True
        except Exception as e:
            logger.debug(f"ARAM reroll failed: {e}")
            return False

    def get_ranked_stats(self):
        try:
            return self.request("GET", "/lol-ranked/v1/current-ranked-stats")
        except Exception:
            return None

    def apply_recommended_runes(self, champion_id):
        """
        Fetches official Riot recommended runes for the given champion and sets
        or replaces the active perk page.
        """
        try:
            rec_pages = self.request("GET", "/lol-perks/v1/recommended-pages")
            if not isinstance(rec_pages, list) or not rec_pages:
                return False

            target_page = None
            for p in rec_pages:
                if p.get("championId") == int(champion_id):
                    target_page = p
                    break
            if not target_page:
                target_page = rec_pages[0]

            name = f"RiftFlow: {target_page.get('name', 'Meta')[:18]}"
            primary_style = target_page.get("primaryPerkStyleId")
            sub_style = target_page.get("subStyleId")
            selected_perks = target_page.get("selectedPerkIds", [])

            page_payload = {
                "name": name,
                "primaryStyleId": primary_style,
                "subStyleId": sub_style,
                "selectedPerkIds": selected_perks,
                "current": True
            }

            cur_page = self.request("GET", "/lol-perks/v1/currentpage")
            if cur_page and isinstance(cur_page, dict) and cur_page.get("isEditable", True):
                page_id = cur_page.get("id")
                if page_id:
                    self.request("PUT", f"/lol-perks/v1/pages/{page_id}", json=page_payload)
                    logger.info(f"Recommended runes updated on page {page_id}")
                    return True

            self.request("POST", "/lol-perks/v1/pages", json=page_payload)
            logger.info("Recommended runes applied via POST /lol-perks/v1/pages")
            return True
        except Exception as e:
            logger.debug(f"Failed to apply recommended runes: {e}")
            return False

    def close(self):
        try:
            self.session.close()
        except Exception:
            pass
