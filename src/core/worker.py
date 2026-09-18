import time
import logging
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
    profile_updated = Signal(dict)

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
        self._runes_applied_for_session = False
        self._spells_applied_for_session = False
        self._last_selected_champ = ""
        self._last_banned_champ = ""
        self._low_spec_minimized = False
        self._last_invite_check = 0
        self._last_presence_check = 0
        self._last_profile_fetch = 0
        self._offline_applied = False
        self._accepted_invite_ids = set()
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
                self._update_profile_and_rank()
            elif time.time() - self._last_profile_fetch > 15.0:
                self._last_profile_fetch = time.time()
                self._update_profile_and_rank()
            
            phase = self.lcu.get_gameflow_phase()
            if phase is not None:
                clean_phase = str(phase).strip().strip('\"')
                if clean_phase != self.last_phase:
                    self.gameflow_changed.emit(clean_phase)
                    self.log(f"Oyun Durumu Değişti: {clean_phase}")
                    self.last_phase = clean_phase
                    if clean_phase != "ChampSelect":
                        self._chat_sent_for_session = False
                        self._runes_applied_for_session = False
                        self._spells_applied_for_session = False
                        self._last_lock_attempts.clear()
                        self._action_retry_counts.clear()
                    else:
                        self._last_lock_attempts.clear()
                        self._action_retry_counts.clear()
                    if clean_phase in ("Lobby", "None", "Matchmaking"):
                        self._last_selected_champ = ""
                        self._last_banned_champ = ""
                        self.champ_select_updated.emit("", "")
                    elif clean_phase == "InProgress":
                        if self._last_selected_champ:
                            self.champ_select_updated.emit(self._last_selected_champ, self._last_banned_champ)

                if clean_phase == "ReadyCheck":
                    self.handle_ready_check()
                elif clean_phase == "ChampSelect":
                    self.handle_champ_select()
                elif clean_phase in ("Lobby", "None"):
                    if self.config.get("auto_accept_invites", False):
                        self.handle_incoming_invites()
                    if self.config.get("auto_appear_offline", False):
                        self.handle_appear_offline()
                    if clean_phase == "Lobby":
                        if self.config.get("auto_queue", False):
                            self.lcu.start_matchmaking()
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
                elif clean_phase in ("PreEndOfGame", "EndOfGame", "WaitingForStats"):
                    if self._low_spec_minimized:
                        try:
                            self.lcu.request("POST", "/riotclient/ux-show")
                        except Exception:
                            pass
                        self._low_spec_minimized = False

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

        local_player_cell_id = session.get("localPlayerCellId")

        # Auto Smart Spells (Auto Smite for Jungle, Flash + TP/Ignite)
        if self.config.get("auto_smart_spells", True) and not self._spells_applied_for_session:
            self.handle_smart_spells(session, local_player_cell_id)

        # Auto Recommended Runes
        if self.config.get("auto_recommended_runes", False) and not self._runes_applied_for_session:
            self.handle_auto_runes(session, local_player_cell_id)

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

        retries = self._action_retry_counts.get(action_id, 0)
        # Dynamic fallback: if priority 1 fails repeatedly (e.g. taken/disabled), try priority 2, then 3
        pref_start = 1
        if retries >= 4:
            pref_start = 2
        if retries >= 8:
            pref_start = 3

        target_champ = None
        target_name = None
        for i in range(pref_start, 4):
            champ_name = self.config.get(f"pick_preference_{i}")
            if not champ_name or champ_name == "None": continue
            champ_id = self.ddragon.get_champion_id(champ_name)
            if champ_id and champ_id not in unselectable:
                target_champ = champ_id
                target_name = champ_name
                break

        if not target_champ:
            return

        # 1. Önseçim / Hover: Sıra henüz bizde değilken (PLANNING veya bekleme) niyet göster
        if not is_in_progress:
            is_hovered = (action.get("championId") == target_champ)
            if not is_hovered:
                self.log(f"Şampiyon gösteriliyor (Önseçim/Hover): {target_name} (ID: {target_champ})")
                self.lcu.hover_champion(action_id, target_champ)
            return

        # 2. Seçim sırası bizde (isInProgress == True)! Sürekli ve kararlı kilitleme denetimi
        now = time.time()
        if now - self._last_lock_attempts.get(action_id, 0) < 0.9:
            return

        self._last_lock_attempts[action_id] = now
        self._action_retry_counts[action_id] = retries + 1

        self.log(f"Sıra bizde! Şampiyon kilitleniyor: {target_name} (ID: {target_champ}) [Deneme #{retries + 1}]")
        if self.lcu.lock_champion(action_id, target_champ, "pick"):
            self.champ_selected.emit(target_champ)
            self.log(f"Şampiyon başarıyla kilitlendi: {target_name}")
            self._last_selected_champ = target_name
        else:
            self.log(f"Şampiyon kilitleme henüz tamamlanamadı: {target_name}, tekrar deneniyor...")

    def handle_ban_action(self, action_id, action, unselectable, is_in_progress, phase=""):
        if not self.config.get("auto_ban", self.config.get("auto_lock", True)):
            return

        # Ban işlemi SADECE ban sırası aktifken (is_in_progress == True) çalışmalıdır.
        if not is_in_progress:
            return

        retries = self._action_retry_counts.get(action_id, 0)
        # Dynamic fallback: if priority 1 fails repeatedly, try priority 2, then 3
        pref_start = 1
        if retries >= 4:
            pref_start = 2
        if retries >= 8:
            pref_start = 3

        target_ban = None
        target_name = None
        for i in range(pref_start, 4):
            champ_name = self.config.get(f"ban_preference_{i}")
            if not champ_name or champ_name == "None": continue
            champ_id = self.ddragon.get_champion_id(champ_name)
            if champ_id and champ_id not in unselectable:
                target_ban = champ_id
                target_name = champ_name
                break

        if not target_ban:
            return

        now = time.time()
        if now - self._last_lock_attempts.get(action_id, 0) < 0.9:
            return

        self._last_lock_attempts[action_id] = now
        self._action_retry_counts[action_id] = retries + 1

        self.log(f"Ban sırası aktif! Ban kilitleniyor: {target_name} (ID: {target_ban}) [Deneme #{retries + 1}]")
        if self.lcu.lock_champion(action_id, target_ban, "ban"):
            self.log(f"Ban başarıyla kilitlendi: {target_name}")
            self._last_banned_champ = target_name
        else:
            self.log(f"Ban kilitleme henüz tamamlanamadı: {target_name}, tekrar deneniyor...")

    def handle_smart_spells(self, session, local_player_cell_id):
        # 4: Flash, 11: Smite, 14: Ignite, 12: Teleport, 7: Heal, 3: Exhaust, 6: Ghost
        pos = ""
        for p in session.get("myTeam", []):
            if p.get("cellId") == local_player_cell_id:
                pos = str(p.get("assignedPosition") or "").lower()
                break

        if not pos:
            return

        spell1, spell2 = 4, 14
        if pos == "jungle":
            spell1, spell2 = 4, 11 # Flash + Smite
            pos_label = "Orman (Çarp + Sıçra)"
        elif pos == "top":
            spell1, spell2 = 4, 12 # Flash + Teleport
            pos_label = "Üst Koridor (Işınlan + Sıçra)"
        elif pos == "middle":
            spell1, spell2 = 4, 14 # Flash + Tutuştur
            pos_label = "Orta Koridor (Tutuştur + Sıçra)"
        elif pos == "bottom":
            spell1, spell2 = 4, 7  # Flash + Şifa
            pos_label = "Alt Koridor (Şifa + Sıçra)"
        elif pos == "utility":
            spell1, spell2 = 4, 14 # Flash + Tutuştur
            pos_label = "Destek (Tutuştur + Sıçra)"
        else:
            return

        if self.lcu.set_summoner_spells(spell1, spell2):
            self._spells_applied_for_session = True
            self.log(f"Akıllı Büyü: {pos_label} büyüleri otomatik atandı!")

    def handle_appear_offline(self):
        now = time.time()
        if now - self._last_presence_check < 15.0:
            return
        self._last_presence_check = now
        try:
            if self.lcu.set_chat_availability("offline"):
                if not self._offline_applied:
                    self.log("Gizli Mod: Sohbet durumu başarıyla 'Çevrimdışı (offline)' yapıldı.")
                self._offline_applied = True
        except Exception:
            pass

    def handle_auto_runes(self, session, local_player_cell_id):
        locked_cid = 0
        for p in session.get("myTeam", []):
            if p.get("cellId") == local_player_cell_id:
                cid = p.get("championId")
                if cid and cid > 0:
                    locked_cid = cid
                break
        if locked_cid > 0:
            if self.lcu.apply_recommended_runes(locked_cid):
                self._runes_applied_for_session = True
                champ_display = self.ddragon.get_champion_name(locked_cid)
                self.log(f"Otomatik Rün: {champ_display} için en yüksek kazanma oranlı meta rünler içe aktarıldı!")

    def handle_incoming_invites(self):
        now = time.time()
        if now - self._last_invite_check < 2.0:
            return
        self._last_invite_check = now
        try:
            invites = self.lcu.get_received_invitations()
            if isinstance(invites, list):
                for inv in invites:
                    inv_id = inv.get("invitationId") or inv.get("id")
                    from_name = inv.get("fromSummonerName") or "Lobi Arkadaşı"
                    state = str(inv.get("state", "")).upper()
                    if inv_id and state in ("PENDING", "RECEIVED", "") and inv_id not in self._accepted_invite_ids:
                        if self.lcu.accept_invitation(inv_id):
                            self._accepted_invite_ids.add(inv_id)
                            self.log(f"Gelen lobi daveti otomatik kabul edildi! ({from_name})")
        except Exception:
            pass

    def _update_profile_and_rank(self):
        try:
            s_info = self.lcu.get_summoner_info()
            r_info = self.lcu.get_ranked_stats()
            combined = {}
            if isinstance(s_info, dict):
                combined.update(s_info)
            if isinstance(r_info, dict):
                queues = r_info.get("queues", [])
                solo_queue = next((q for q in queues if q.get("queueType") == "RANKED_SOLO_5x5"), None)
                if solo_queue:
                    combined["tier"] = solo_queue.get("tier", "UNRANKED")
                    combined["division"] = solo_queue.get("division", "")
                    combined["leaguePoints"] = solo_queue.get("leaguePoints", 0)
                    combined["wins"] = solo_queue.get("wins", 0)
                    combined["losses"] = solo_queue.get("losses", 0)
            if combined:
                self.profile_updated.emit(combined)
        except Exception:
            pass
