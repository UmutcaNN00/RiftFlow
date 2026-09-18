import time
import logging
import ctypes
from PySide6.QtCore import QThread, Signal
from .lcu_client import LcuClient
from .config import ConfigManager

logger = logging.getLogger(__name__)

class LcuWorker(QThread):
    status_changed = Signal(str)
    gameflow_changed = Signal(str)
    champ_selected = Signal(int)
    notification = Signal(str)
    log_message = Signal(str)
    champ_select_updated = Signal(str, str)

    def __init__(self, config_manager: ConfigManager, lcu_client: LcuClient, ddragon, parent=None):
        super().__init__(parent)
        self.config = config_manager
        self.lcu = lcu_client
        self.ddragon = ddragon
        self._running = True
        self._is_polling = False
        self.last_accept_time = 0
        self.last_phase = None
        self.last_connected = None
        self._chat_sent_for_session = False
        self._aram_rerolled = False
        self._last_selected_champ = ""
        self._last_banned_champ = ""
        self._play_again_done = False
        self._low_spec_minimized = False
        self._end_emote_done = False
        self._last_swap_check = 0
        self._last_ff_check = 0
        self._accepted_swap_ids = set()
        self._last_lock_attempts = {}    # action_id -> timestamp (kilit deneme zamanı)
        self._action_retry_counts = {}   # action_id -> retry count (max retry denetimi)

    def run(self):
        while self._running:
            self.poll_cycle()
            self.msleep(800)

    def stop(self):
        self._running = False
        self.wait()

    def log(self, text):
        t_str = time.strftime('%H:%M:%S')
        self.log_message.emit(f'[{t_str}] {text}')

    def poll_cycle(self):
        if self._is_polling:
            return
            
        self._is_polling = True
        try:
            alive = self.lcu.is_alive()
            if not alive:
                if self.last_connected != False:
                    self.status_changed.emit("Disconnected")
                    self.log("LoL İstemcisi bağlantısı koptu veya bekleniyor...")
                    self.last_connected = False
                    self.last_phase = None  # Yeniden bağlanınca phase değişikliği algılansın
                return

            if self.last_connected != True:
                self.status_changed.emit("Connected")
                self.log("LoL İstemcisine (LCU) başarıyla bağlandı!")
                self.last_connected = True
            
            phase = self.lcu.get_gameflow_phase()
            if phase is not None:
                clean_phase = str(phase).strip().strip('\"')
                if clean_phase != self.last_phase:
                    self.gameflow_changed.emit(clean_phase)
                    self.log(f"Oyun Durumu Değişti: {clean_phase}")
                    self.last_phase = clean_phase
                    if clean_phase != "ChampSelect":
                        self._chat_sent_for_session = False
                        self._aram_rerolled = False
                        self._accepted_swap_ids.clear()
                        self._last_lock_attempts.clear()
                        self._action_retry_counts.clear()
                    if clean_phase in ("Lobby", "None", "Matchmaking"):
                        self._last_selected_champ = ""
                        self._last_banned_champ = ""
                        self._play_again_done = False
                        self._end_emote_done = False
                        self.champ_select_updated.emit("", "")
                    elif clean_phase == "InProgress":
                        self._play_again_done = False
                        self._end_emote_done = False
                        if self._last_selected_champ:
                            self.champ_select_updated.emit(self._last_selected_champ, self._last_banned_champ)

                if clean_phase == "ReadyCheck":
                    self.handle_ready_check()
                elif clean_phase == "ChampSelect":
                    self.handle_champ_select()
                elif clean_phase == "Lobby":
                    if self.config.get("auto_queue", False):
                        self.lcu.start_matchmaking()
                    if self.config.get("auto_party_ready", False):
                        self.handle_party_ready()
                    if self._low_spec_minimized:
                        try:
                            self.lcu.request("POST", "/riotclient/ux-show")
                        except Exception:
                            pass
                        self._low_spec_minimized = False
                elif clean_phase == "InProgress":
                    if self.config.get("auto_low_spec", False) and not self._low_spec_minimized:
                        try:
                            self.lcu.request("POST", "/riotclient/ux-minimize")
                            self._low_spec_minimized = True
                            self.log("Düşük Donanım Modu: İstemci arka plana küçültüldü (FPS Boost aktif).")
                        except Exception:
                            pass
                    if self.config.get("auto_no_ff", False):
                        self.handle_auto_no_ff()
                elif clean_phase == "PreEndOfGame":
                    if self.config.get("auto_end_emote", False) and not self._end_emote_done:
                        self.handle_end_emote()
                    if self.config.get("auto_play_again", False) and not self._play_again_done:
                        self.handle_play_again()
                elif clean_phase in ("EndOfGame", "WaitingForStats"):
                    if self._low_spec_minimized:
                        try:
                            self.lcu.request("POST", "/riotclient/ux-show")
                        except Exception:
                            pass
                        self._low_spec_minimized = False
                    if self.config.get("auto_play_again", False) and not self._play_again_done:
                        self.handle_play_again()

        except Exception as e:
            logger.error(f"Error in poll_cycle: {e}")
        finally:
            self._is_polling = False

    def handle_ready_check(self):
        if not self.config.get("auto_accept", False):
            return
            
        current_time = time.time()
        if current_time - self.last_accept_time > 4.0:
            delay = self.config.get("accept_delay", 0)
            if delay > 0:
                self.log(f"Maç bulundu! {delay} saniye gecikme bekleniyor...")
                for _ in range(int(delay * 10)):
                    if not self._running:
                        return
                    self.msleep(100)
            self.log("Maç otomatik kabul ediliyor...")
            try:
                if self.lcu.accept_matchmaking():
                    self.last_accept_time = time.time()
                    self.notification.emit("Maç Otomatik Kabul Edildi!")
                    self.log("Maç başarıyla kabul edildi!")
            except Exception as e:
                logger.error(f"Failed to auto-accept: {e}")

    def handle_champ_select(self):
        # Handle chat on entrance
        if self.config.get("post_pick_chat", False) and not self._chat_sent_for_session:
            msg = self.config.get("chat_message", "mid")
            repeats = self.config.get("chat_repeat_count", 1)
            if msg:
                self.log(f"Lobi sohbetine otomatik mesaj gönderiliyor: '{msg}' ({repeats}x)")
                if self.lcu.send_champ_select_chat(msg, repeats):
                    self._chat_sent_for_session = True
                    self.log("Sohbet mesajı başarıyla yollandı.")

        session = self.lcu.get_champ_select_session()
        if not session or not isinstance(session, dict):
            return

        # ARAM Auto Reroll
        if self.config.get("auto_reroll_aram", False) and not self._aram_rerolled:
            is_aram = session.get("benchEnabled", False) or session.get("hasInterest", False)
            if is_aram and session.get("rerollsRemaining", 0) > 0:
                try:
                    self.lcu.request("POST", "/lol-champ-select/v1/session/my-selection/reroll")
                    self._aram_rerolled = True
                    self.log("ARAM otomatik zar atıldı!")
                except Exception as e:
                    logger.debug(f"ARAM reroll failed: {e}")

        # Auto Swap Accept (Role / Pick Order / Champion Trade)
        if self.config.get("auto_swap_accept", False):
            self.handle_swap_accept()

        local_player_cell_id = session.get("localPlayerCellId")
        actions = session.get("actions", [])
        
        # Extract live picked champion and banned champion for user
        my_champ_name = ""
        my_ban_name = ""
        
        # 1. Check local player in myTeam (for intent or locked pick)
        for p in session.get("myTeam", []):
            if p.get("cellId") == local_player_cell_id:
                cid = p.get("championId") or p.get("championPickIntent")
                if cid and cid > 0:
                    cname = self.ddragon.get_champion_name(cid)
                    if cname and cname != "Unknown":
                        my_champ_name = cname
                break
                
        # 2. Check actions for pick and ban (hovering and locked)
        for action_group in actions:
            for action in action_group:
                if action.get("actorCellId") == local_player_cell_id:
                    act_type = action.get("type")
                    cid = action.get("championId")
                    if cid and cid > 0:
                        cname = self.ddragon.get_champion_name(cid)
                        if cname and cname != "Unknown":
                            if act_type == "pick":
                                my_champ_name = cname
                            elif act_type == "ban":
                                my_ban_name = cname

        # (Fallback removed: myTeamBans check was triggering when teammates banned user's preferred ban)

        # Cache for when match starts
        if my_champ_name:
            self._last_selected_champ = my_champ_name
        if my_ban_name:
            self._last_banned_champ = my_ban_name

        self.champ_select_updated.emit(my_champ_name, my_ban_name)
        
        # Seçilemez şampiyonlar: tamamlanmış action'lar + her iki takımın banları
        unselectable = set()
        bans = session.get("bans", {})
        for b_id in bans.get("myTeamBans", []) + bans.get("theirTeamBans", []):
            if b_id and b_id > 0:
                unselectable.add(b_id)
        for action_group in actions:
            for action in action_group:
                if action.get("completed") and action.get("championId"):
                    unselectable.add(action.get("championId"))

        phase = session.get("timer", {}).get("phase", "")
        for action_group in actions:
            for action in action_group:
                if action.get("actorCellId") == local_player_cell_id and not action.get("completed"):
                    action_id = action.get("id")
                    action_type = action.get("type")
                    is_in_progress = action.get("isInProgress", False)

                    if action_type == "pick":
                        self.handle_pick_action(action_id, action, unselectable, is_in_progress, phase)
                    elif action_type == "ban":
                        self.handle_ban_action(action_id, action, unselectable, is_in_progress, phase)

    def handle_pick_action(self, action_id, action, unselectable, is_in_progress, phase=""):
        if not self.config.get("auto_pick", True):
            return

        target_champ = None
        target_name = None
        for i in range(1, 4):
            champ_name = self.config.get(f"pick_preference_{i}")
            if not champ_name or champ_name == "None": continue
            champ_id = self.ddragon.get_champion_id(champ_name)
            if champ_id and champ_id not in unselectable:
                target_champ = champ_id
                target_name = champ_name
                break

        if not target_champ:
            return

        # 1. Önseçim / Hover: Sıra henüz bizde değilse niyet göster
        if not is_in_progress:
            is_hovered = action.get("championId") == target_champ
            if not is_hovered:
                self.log(f"Şampiyon gösteriliyor (Önseçim/Hover): {target_name} (ID: {target_champ})")
                self.lcu.hover_champion(action_id, target_champ)
            return

        # 2. Seçim sırası bizde (isInProgress == True)! Kilitleme denetimi
        now = time.time()
        if now - self._last_lock_attempts.get(action_id, 0) < 1.2:
            return

        retries = self._action_retry_counts.get(action_id, 0)
        if retries >= 3:
            return  # Sonsuz döngü ve LCU spam engeli

        self._last_lock_attempts[action_id] = now
        self._action_retry_counts[action_id] = retries + 1

        self.log(f"Sıra bizde! Şampiyon kilitleniyor: {target_name} (ID: {target_champ})")
        if self.lcu.lock_champion(action_id, target_champ, "pick"):
            self.champ_selected.emit(target_champ)
            self.log(f"Şampiyon başarıyla kilitlendi: {target_name}")
        else:
            self.log(f"Şampiyon kilitleme başarısız: {target_name}, 1.2 sn sonra tekrar denenecek.")

    def handle_ban_action(self, action_id, action, unselectable, is_in_progress, phase=""):
        if not self.config.get("auto_ban", self.config.get("auto_lock", True)):
            return

        target_ban = None
        target_name = None
        for i in range(1, 4):
            champ_name = self.config.get(f"ban_preference_{i}")
            if not champ_name or champ_name == "None": continue
            champ_id = self.ddragon.get_champion_id(champ_name)
            if champ_id and champ_id not in unselectable:
                target_ban = champ_id
                target_name = champ_name
                break

        if not target_ban:
            return

        # 1. Ban adayını hover yap (kullanıcı ve takım görsün)
        is_hovered = action.get("championId") == target_ban
        if not is_hovered:
            self.log(f"Ban adayı gösteriliyor: {target_name}")
            self.lcu.hover_champion(action_id, target_ban)

        # 2. Ban sırası aktifken kilitle
        if not is_in_progress:
            return

        now = time.time()
        if now - self._last_lock_attempts.get(action_id, 0) < 1.2:
            return

        retries = self._action_retry_counts.get(action_id, 0)
        if retries >= 3:
            return  # Sonsuz döngü ve LCU spam engeli

        self._last_lock_attempts[action_id] = now
        self._action_retry_counts[action_id] = retries + 1

        self.log(f"Ban sırası aktif! Ban kilitleniyor: {target_name} (ID: {target_ban})")
        if self.lcu.lock_champion(action_id, target_ban, "ban"):
            self.log(f"Ban başarıyla kilitlendi: {target_name}")
        else:
            self.log(f"Ban kilitleme başarısız: {target_name}, 1.2 sn sonra tekrar denenecek.")

    def handle_party_ready(self):
        try:
            self.lcu.request("PUT", "/lol-lobby/v1/parties/ready", json={})
        except Exception:
            pass

    def handle_play_again(self):
        try:
            try:
                self.lcu.request("POST", "/lol-end-of-game/v1/state/dismiss-stats")
            except Exception:
                pass
            self.msleep(400)
            self.lcu.request("POST", "/lol-lobby/v2/play-again")
            self._play_again_done = True
            self.log("Maç bitti: Otomatik lobiye dönüldü (Play Again).")
        except Exception:
            pass

        # Auto Honor Ally
        try:
            ballot = self.lcu.request("GET", "/lol-honor-v2/v1/ballot")
            if ballot and isinstance(ballot, dict):
                allies = ballot.get("eligibleAllies", [])
                game_id = ballot.get("gameId")
                if allies and game_id:
                    target_id = allies[0].get("summonerId") or allies[0].get("puuid")
                    if target_id:
                        self.lcu.request("POST", "/lol-honor-v2/v1/honor-player", json={
                            "gameId": game_id,
                            "honorCategory": "HEART",
                            "summonerId": target_id
                        })
                        self.log("Maç sonu: Takım arkadaşına otomatik 'GG / Harika Takım Oyuncusu' onuru verildi!")
        except Exception:
            pass

    def handle_swap_accept(self):
        now = time.time()
        if now - self._last_swap_check < 1.0:
            return
        self._last_swap_check = now
        
        # Position / Lane / Role swap accept (Only incoming requests where state == 'RECEIVED')
        try:
            p_swaps = self.lcu.request("GET", "/lol-champ-select/v1/session/position-swaps")
            if isinstance(p_swaps, list):
                for s in p_swaps:
                    sid = s.get("id")
                    state = str(s.get("state", "")).upper()
                    if sid and state == "RECEIVED" and sid not in self._accepted_swap_ids:
                        self.lcu.request("POST", f"/lol-champ-select/v1/session/position-swaps/{sid}/accept")
                        self._accepted_swap_ids.add(sid)
                        self.log(f"Gelen rol/koridor takas isteği kabul edildi! (ID: {sid})")
        except Exception:
            pass

        # Pick order swap accept (Only incoming requests where state == 'RECEIVED')
        try:
            po_swaps = self.lcu.request("GET", "/lol-champ-select/v1/session/pick-order-swaps")
            if isinstance(po_swaps, list):
                for s in po_swaps:
                    sid = s.get("id")
                    state = str(s.get("state", "")).upper()
                    if sid and state == "RECEIVED" and sid not in self._accepted_swap_ids:
                        self.lcu.request("POST", f"/lol-champ-select/v1/session/pick-order-swaps/{sid}/accept")
                        self._accepted_swap_ids.add(sid)
                        self.log(f"Gelen seçim sırası takas isteği kabul edildi! (ID: {sid})")
        except Exception:
            pass

        # Champion trade accept (Only incoming trades where state == 'RECEIVED')
        try:
            c_swaps = self.lcu.request("GET", "/lol-champ-select/v1/session/swaps")
            if isinstance(c_swaps, list):
                for s in c_swaps:
                    sid = s.get("id")
                    state = str(s.get("state", "")).upper()
                    if sid and state == "RECEIVED" and sid not in self._accepted_swap_ids:
                        self.lcu.request("POST", f"/lol-champ-select/v1/session/swaps/{sid}/accept")
                        self._accepted_swap_ids.add(sid)
                        self.log(f"Gelen şampiyon takas isteği kabul edildi! (ID: {sid})")
        except Exception:
            pass

    def handle_end_emote(self):
        try:
            hwnd = ctypes.windll.user32.GetForegroundWindow()
            buf = ctypes.create_unicode_buffer(256)
            ctypes.windll.user32.GetWindowTextW(hwnd, buf, 256)
            if "League of Legends" in buf.value:
                # Ctrl + 6 (Mastery Emote)
                ctypes.windll.user32.keybd_event(0x11, 0, 0, 0)
                ctypes.windll.user32.keybd_event(0x36, 0, 0, 0)
                self.msleep(50)
                ctypes.windll.user32.keybd_event(0x36, 0, 2, 0)
                ctypes.windll.user32.keybd_event(0x11, 0, 2, 0)
                self.log("Maç Sonu: Otomatik GG / Ustalık İfadesi patlatıldı!")
        except Exception:
            pass
        self._end_emote_done = True

    def handle_auto_no_ff(self):
        now = time.time()
        if now - self._last_ff_check < 4.0:
            return
        self._last_ff_check = now
        try:
            hwnd = ctypes.windll.user32.GetForegroundWindow()
            buf = ctypes.create_unicode_buffer(256)
            ctypes.windll.user32.GetWindowTextW(hwnd, buf, 256)
            if "League of Legends" in buf.value:
                # F6 is default surrender NO key in LoL
                ctypes.windll.user32.keybd_event(0x75, 0, 0, 0)
                self.msleep(40)
                ctypes.windll.user32.keybd_event(0x75, 0, 2, 0)
        except Exception:
            pass
