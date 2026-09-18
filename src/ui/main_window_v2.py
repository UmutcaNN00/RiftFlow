import os
import sys
import time
import requests
import webbrowser
import logging
from PySide6.QtWidgets import (
    QMainWindow, QWidget, QVBoxLayout, QHBoxLayout, QGridLayout,
    QGroupBox, QSlider, QLabel, QComboBox, QPushButton, QSpacerItem, QSizePolicy,
    QStackedWidget, QButtonGroup, QSpinBox, QLineEdit, QTextEdit, QScrollArea, QFrame,
    QApplication
)
from PySide6.QtCore import Qt, QSize, Signal, QRectF, QPropertyAnimation, Property, QEasingCurve
from PySide6.QtGui import QPixmap, QIcon, QPainter, QColor, QFont, QPainterPath

from src.core.config import ConfigManager
from src.core.worker import LcuWorker
from src.core.lcu_client import LcuClient
from src.core.data_dragon import DataDragon
from src.ui.modern_theme import MODERN_THEME

logger = logging.getLogger(__name__)

# Canonical LCU Position Map
ROLE_CANONICAL_MAP = {
    "TOP": "TOP",
    "JUNGLE": "JUNGLE", "JGL": "JUNGLE",
    "MIDDLE": "MIDDLE", "MID": "MIDDLE",
    "BOTTOM": "BOTTOM", "ADC": "BOTTOM", "BOT": "BOTTOM",
    "UTILITY": "UTILITY", "SUP": "UTILITY", "SUPPORT": "UTILITY",
    "FILL": "FILL",
    "UNSELECTED": "UNSELECTED"
}

ROLE_DEFINITIONS = [
    ("TOP", "ÜST"),
    ("JUNGLE", "ORMAN"),
    ("MIDDLE", "ORTA"),
    ("BOTTOM", "ALT"),
    ("UTILITY", "DESTEK"),
    ("FILL", "DOLDUR")
]

class ModernSwitch(QWidget):
    toggled = Signal(bool)
    
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setFixedSize(48, 24)
        self.setCursor(Qt.PointingHandCursor)
        self._checked = False
        self._pos = 0.0
        
        self.anim = QPropertyAnimation(self, b"pos_val")
        self.anim.setDuration(180)
        self.anim.setEasingCurve(QEasingCurve.OutCubic)
        
    def get_pos(self):
        return self._pos
        
    def set_pos(self, val):
        self._pos = val
        self.update()
        
    pos_val = Property(float, get_pos, set_pos)
    
    def isChecked(self):
        return self._checked
        
    def setChecked(self, checked):
        checked = bool(checked)
        if self._checked != checked:
            self._checked = checked
            self._pos = 1.0 if self._checked else 0.0
            self.update()
        
    def mouseReleaseEvent(self, event):
        if event.button() == Qt.LeftButton:
            self._checked = not self._checked
            self.anim.stop()
            self.anim.setStartValue(self._pos)
            self.anim.setEndValue(1.0 if self._checked else 0.0)
            self.anim.start()
            self.toggled.emit(self._checked)
            
    def paintEvent(self, event):
        p = QPainter(self)
        p.setRenderHint(QPainter.Antialiasing)
        
        w = self.width()
        h = self.height()
        radius = h / 2.0
        
        # Color interpolation: Off: #1A1D26, On: #0AC8B9
        r = int(26 + (10 - 26) * self._pos)
        g = int(29 + (200 - 29) * self._pos)
        b = int(38 + (185 - 38) * self._pos)
        bg_color = QColor(r, g, b)
        
        # Border color: #2E3445 -> #12E6D5
        br = int(46 + (18 - 46) * self._pos)
        bg = int(52 + (230 - 52) * self._pos)
        bb = int(69 + (213 - 69) * self._pos)
        border_color = QColor(br, bg, bb)
        
        # Draw track
        path = QPainterPath()
        path.addRoundedRect(0.5, 0.5, w - 1.0, h - 1.0, radius, radius)
        p.fillPath(path, bg_color)
        p.setPen(border_color)
        p.drawPath(path)
        
        # Draw thumb
        thumb_diam = h - 6.0
        thumb_x = 3.0 + self._pos * (w - thumb_diam - 6.0)
        thumb_y = 3.0
        
        # Soft drop shadow
        shadow_rect = QRectF(thumb_x, thumb_y + 1.0, thumb_diam, thumb_diam)
        p.setPen(Qt.NoPen)
        p.setBrush(QColor(0, 0, 0, 60))
        p.drawEllipse(shadow_rect)
        
        # Thumb circle
        thumb_rect = QRectF(thumb_x, thumb_y, thumb_diam, thumb_diam)
        p.setBrush(QColor("#FFFFFF"))
        p.drawEllipse(thumb_rect)


class DualRowRoleSelector(QWidget):
    roles_changed = Signal(str, str)  # (primary, secondary)

    def __init__(self, parent=None):
        super().__init__(parent)
        self.primary_role = "BOTTOM"
        self.secondary_role = "UTILITY"
        self.primary_buttons = {}
        self.secondary_buttons = {}
        self.init_ui()

    def init_ui(self):
        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(0, 0, 0, 0)
        main_layout.setSpacing(6)

        # 1. Satır: Birincil Rol
        lbl_pri = QLabel("Birincil Rol (1. Tercih):")
        lbl_pri.setStyleSheet("color: #0AC8B9; font-weight: bold; font-size: 11px;")
        main_layout.addWidget(lbl_pri)

        row1_layout = QHBoxLayout()
        row1_layout.setSpacing(4)
        for role_code, label in ROLE_DEFINITIONS:
            btn = QPushButton(label)
            btn.setObjectName("laneBtn")
            btn.setCursor(Qt.PointingHandCursor)
            btn.clicked.connect(lambda _, r=role_code: self.on_primary_clicked(r))
            self.primary_buttons[role_code] = btn
            row1_layout.addWidget(btn)
        main_layout.addLayout(row1_layout)

        # 2. Satır: İkincil Rol
        self.lbl_sec = QLabel("İkincil Rol (2. Tercih):")
        self.lbl_sec.setStyleSheet("color: #9A6EE2; font-weight: bold; font-size: 11px;")
        main_layout.addWidget(self.lbl_sec)

        row2_layout = QHBoxLayout()
        row2_layout.setSpacing(4)
        for role_code, label in ROLE_DEFINITIONS:
            btn = QPushButton(label)
            btn.setObjectName("laneBtn")
            btn.setCursor(Qt.PointingHandCursor)
            btn.clicked.connect(lambda _, r=role_code: self.on_secondary_clicked(r))
            self.secondary_buttons[role_code] = btn
            row2_layout.addWidget(btn)
        main_layout.addLayout(row2_layout)

        self.update_ui_state()

    def on_primary_clicked(self, role_code):
        if self.primary_role == role_code:
            return

        old_primary = self.primary_role
        self.primary_role = role_code

        if role_code == "FILL":
            self.secondary_role = "UNSELECTED"
        else:
            # Smart swap: if new primary was secondary, swap them
            if self.secondary_role == role_code:
                self.secondary_role = old_primary if old_primary != "FILL" else "FILL"
            elif self.secondary_role == "UNSELECTED":
                self.secondary_role = "FILL" if role_code != "FILL" else "UTILITY"

        self.update_ui_state()
        self.emit_roles()

    def on_secondary_clicked(self, role_code):
        if self.primary_role == "FILL":
            self.primary_role = "MIDDLE"

        if self.secondary_role == role_code:
            return

        old_secondary = self.secondary_role
        self.secondary_role = role_code

        # Smart swap: if new secondary was primary, swap them
        if self.primary_role == role_code:
            self.primary_role = old_secondary if old_secondary not in ("UNSELECTED", "FILL") else "TOP"

        self.update_ui_state()
        self.emit_roles()

    def update_ui_state(self):
        # Update Primary Buttons
        for code, btn in self.primary_buttons.items():
            is_active = (code == self.primary_role)
            btn.setProperty("roleState", "primary" if is_active else "")
            btn.style().unpolish(btn)
            btn.style().polish(btn)

        # Update Secondary Buttons (Disabled if primary is FILL)
        is_fill_primary = (self.primary_role == "FILL")
        for code, btn in self.secondary_buttons.items():
            btn.setEnabled(not is_fill_primary)
            is_active = (code == self.secondary_role and not is_fill_primary)
            btn.setProperty("roleState", "secondary" if is_active else "")
            btn.style().unpolish(btn)
            btn.style().polish(btn)

        if is_fill_primary:
            self.lbl_sec.setText("İkincil Rol (Devre Dışı - Birincil 'DOLDUR')")
            self.lbl_sec.setStyleSheet("color: #6A7282; font-size: 11px;")
        else:
            self.lbl_sec.setText("İkincil Rol (2. Tercih):")
            self.lbl_sec.setStyleSheet("color: #9A6EE2; font-weight: bold; font-size: 11px;")

    def set_roles(self, primary, secondary):
        pr = ROLE_CANONICAL_MAP.get(str(primary).upper(), "BOTTOM")
        sr = ROLE_CANONICAL_MAP.get(str(secondary).upper(), "UTILITY")

        if pr == sr and pr != "UNSELECTED":
            sr = "FILL" if pr != "FILL" else "UNSELECTED"
        if pr == "FILL":
            sr = "UNSELECTED"

        self.primary_role = pr
        self.secondary_role = sr
        self.update_ui_state()

    def get_roles(self):
        pr = self.primary_role or "BOTTOM"
        sr = self.secondary_role or ("UNSELECTED" if pr == "FILL" else "UTILITY")
        return pr, sr

    def emit_roles(self):
        pr, sr = self.get_roles()
        self.roles_changed.emit(pr, sr)


class MainWindowV2(QMainWindow):
    ROLE_SUPPORTED_QUEUES = {400, 420, 440, 700}

    def __init__(self):
        super().__init__()
        self.setWindowTitle("RiftFlow - Pro Paneli")
        self.resize(1180, 720)
        self.setMinimumSize(1140, 700)
        self.setStyleSheet(MODERN_THEME)

        self.config = ConfigManager()
        self.config.load()
        
        self.ddragon = DataDragon()
        self.ddragon.fetch_champions()
        self.champ_list = ["None"] + sorted([info.get("name", k) for k, info in self.ddragon.champions_data.items()])
        self.icon_cache = {}

        self.lcu_client = LcuClient()
        self.lcu_worker = LcuWorker(self.config, self.lcu_client, self.ddragon)
        
        self._is_loading = True
        try:
            self.init_ui()
            self.load_config()
        finally:
            self._is_loading = False
        
        # Connect worker signals
        self.lcu_worker.gameflow_changed.connect(self.update_gameflow)
        self.lcu_worker.status_changed.connect(self.update_status)
        self.lcu_worker.log_message.connect(self.append_log)
        self.lcu_worker.champ_select_updated.connect(self.update_champ_select_labels)
        self.lcu_worker.notification.connect(self.append_log)
        self.lcu_worker.profile_updated.connect(self.update_profile_info)
        self.lcu_worker.start()

    def append_log(self, text):
        if hasattr(self, 'log_text'):
            self.log_text.append(text)
            scrollbar = self.log_text.verticalScrollBar()
            scrollbar.setValue(scrollbar.maximum())

    def get_champion_internal_name(self, display_name):
        for internal_name, info in self.ddragon.champions_data.items():
            if info.get("name") == display_name:
                return internal_name
        return display_name

    def get_champion_pixmap(self, champ_display_name, size=48):
        if not champ_display_name or champ_display_name == "None": 
            pm = QPixmap(size, size)
            pm.fill(Qt.transparent)
            return pm
        if f"{champ_display_name}_{size}" in self.icon_cache: 
            return self.icon_cache[f"{champ_display_name}_{size}"]
        
        version = self.ddragon.current_version or "14.18.1"
        internal_name = self.get_champion_internal_name(champ_display_name)
        url = f"https://ddragon.leagueoflegends.com/cdn/{version}/img/champion/{internal_name}.png"
        try:
            response = requests.get(url, timeout=3)
            if response.status_code == 200:
                raw_pm = QPixmap()
                raw_pm.loadFromData(response.content)
                
                target = QPixmap(size, size)
                target.fill(Qt.transparent)
                p = QPainter(target)
                p.setRenderHint(QPainter.Antialiasing)
                p.setRenderHint(QPainter.SmoothPixmapTransform)
                path = QPainterPath()
                path.addEllipse(0, 0, size, size)
                p.setClipPath(path)
                p.drawPixmap(0, 0, size, size, raw_pm)
                p.end()
                
                self.icon_cache[f"{champ_display_name}_{size}"] = target
                return target
        except Exception:
            pass
        return QPixmap(size, size)

    def init_ui(self):
        central_widget = QWidget()
        self.setCentralWidget(central_widget)
        main_layout = QHBoxLayout(central_widget)
        main_layout.setContentsMargins(0, 0, 0, 0)
        main_layout.setSpacing(0)
        
        # Sidebar (3 tabs: Ana Sayfa, Scriptler, Loglar - Ayarlar removed as requested)
        sidebar = QWidget()
        sidebar.setObjectName("sidebar")
        sidebar.setFixedWidth(180)
        sidebar_layout = QVBoxLayout(sidebar)
        sidebar_layout.setContentsMargins(0, 20, 0, 20)
        sidebar_layout.setSpacing(6)
        
        self.nav_btns = []
        nav_items = ["Ana Sayfa", "Scriptler", "Loglar"]
        for i, item in enumerate(nav_items):
            btn = QPushButton(item)
            btn.setCheckable(True)
            if i == 0:
                btn.setChecked(True)
            btn.clicked.connect(lambda checked, idx=i: self.switch_page(idx))
            self.nav_btns.append(btn)
            sidebar_layout.addWidget(btn)
            
        sidebar_layout.addStretch()
        main_layout.addWidget(sidebar)
        
        # Right Area
        right_widget = QWidget()
        right_layout = QVBoxLayout(right_widget)
        right_layout.setContentsMargins(0, 0, 0, 0)
        right_layout.setSpacing(0)
        
        # Header
        header = QWidget()
        header.setObjectName("header")
        header.setFixedHeight(52)
        header_layout = QHBoxLayout(header)
        header_layout.setContentsMargins(20, 0, 20, 0)
        
        title_label = QLabel("RiftFlow :: LoL Otomasyonu")
        title_label.setObjectName("headerTitle")
        
        self.profile_label = QLabel("Profil: Oyuncu (Bağlanıyor...)")
        self.profile_label.setStyleSheet("color: #E2B25A; font-weight: bold;")
        self.status_label = QLabel("Durum: Bağlanıyor...")
        self.status_label.setObjectName("readyText")
        
        header_layout.addWidget(title_label)
        header_layout.addStretch()
        header_layout.addWidget(self.profile_label)
        header_layout.addSpacing(15)
        header_layout.addWidget(self.status_label)
        
        right_layout.addWidget(header)
        
        # Content - QStackedWidget (3 pages)
        self.stacked_widget = QStackedWidget()
        right_layout.addWidget(self.stacked_widget)
        
        # Page 0: Ana Sayfa
        page_home = QWidget()
        page_home_layout = QHBoxLayout(page_home)
        page_home_layout.setContentsMargins(25, 20, 25, 20)
        page_home_layout.setSpacing(20)
        self.setup_matchmaking_card(page_home_layout)
        self.setup_pickban_card(page_home_layout)
        page_home_layout.addStretch()
        self.stacked_widget.addWidget(page_home)
        
        # Page 1: Scriptler
        self.setup_scripts_page()
        
        # Page 2: Loglar
        self.setup_logs_page()
            
        self.stacked_widget.setCurrentIndex(0)
        main_layout.addWidget(right_widget)

    def switch_page(self, idx):
        for i, btn in enumerate(self.nav_btns):
            btn.setChecked(i == idx)
        self.stacked_widget.setCurrentIndex(idx)

    def setup_matchmaking_card(self, parent_layout):
        group = QGroupBox("EŞLEŞTİRME & LOBİ")
        group.setFixedWidth(450)
        layout = QVBoxLayout(group)
        layout.setContentsMargins(14, 10, 14, 10)
        layout.setSpacing(10)
        
        # Game Mode selection & Create Lobby
        mode_header = QLabel("Oyun Modu:")
        layout.addWidget(mode_header)
        
        mode_box = QHBoxLayout()
        self.game_mode_combo = QComboBox()
        self.game_mode_combo.setObjectName("modeSelectCombo")
        self.mode_queue_map = {
            "Dereceli Tek/Çift (Solo/Duo)": 420,
            "Dereceli Esnek (Flex 5v5)": 440,
            "Sıralı Seçim (Normal Draft)": 400,
            "Kapalı Seçim (Blind Pick)": 430,
            "ARAM (Sonsuz Uçurum)": 450,
            "Arena (2v2v2v2)": 1700
        }
        for m_name in self.mode_queue_map.keys():
            self.game_mode_combo.addItem(m_name)
        mode_box.addWidget(self.game_mode_combo, 1)

        self.btn_create_lobby = QPushButton("Lobi Oluştur", objectName="createLobbyBtn")
        self.btn_create_lobby.setCursor(Qt.PointingHandCursor)
        self.btn_create_lobby.clicked.connect(self.on_create_lobby_clicked)
        mode_box.addWidget(self.btn_create_lobby)
        layout.addLayout(mode_box)
        
        self.queue_status = QLabel("Sıra Durumu: [Boşta]")
        self.queue_status.setObjectName("highlightText")
        layout.addWidget(self.queue_status)
        
        # Auto Accept + Sleek Slider
        aa_layout = QVBoxLayout()
        aa_header = QHBoxLayout()
        aa_lbl = QLabel("Oto Kabul")
        aa_lbl.setStyleSheet("font-weight: bold; color: #FFFFFF;")
        aa_header.addWidget(aa_lbl)
        self.auto_accept_sw = ModernSwitch()
        aa_header.addWidget(self.auto_accept_sw)
        
        self.accept_delay_badge = QLabel("[ Anında ]")
        self.accept_delay_badge.setStyleSheet("color: #0AC8B9; font-weight: bold; background-color: #1A1C23; padding: 2px 8px; border-radius: 4px;")
        aa_header.addWidget(self.accept_delay_badge)
        aa_header.addStretch()
        aa_layout.addLayout(aa_header)
        
        slider_box = QHBoxLayout()
        slider_box.addWidget(QLabel("Kabul Gecikmesi:"))
        self.accept_delay_slider = QSlider(Qt.Horizontal)
        self.accept_delay_slider.setRange(0, 10)
        self.accept_delay_slider.setValue(0)
        self.accept_delay_slider.valueChanged.connect(self.on_delay_slider_changed)
        slider_box.addWidget(self.accept_delay_slider)
        aa_layout.addLayout(slider_box)
        layout.addLayout(aa_layout)
        
        # Dual Row Role Selector (Primary & Secondary separated)
        layout.addSpacing(2)
        self.role_selector = DualRowRoleSelector()
        self.role_selector.roles_changed.connect(self.on_roles_changed)
        layout.addWidget(self.role_selector)
        
        layout.addSpacing(4)
        self.live_status = QLabel("Canlı Durum: Bekleniyor...", objectName="highlightText")
        layout.addWidget(self.live_status)
        self.lobby_count = QLabel("Lobideki Oyuncular: 1", objectName="highlightText")
        layout.addWidget(self.lobby_count)
        
        # Summoner Rank Badge
        rank_card = QFrame()
        rank_card.setStyleSheet("""
            QFrame {
                background-color: #14161D;
                border: 1px solid #232733;
                border-radius: 8px;
                padding: 4px;
            }
        """)
        rc_layout = QVBoxLayout(rank_card)
        rc_layout.setContentsMargins(10, 6, 10, 6)
        rc_layout.setSpacing(3)
        self.rank_label = QLabel("Sihirdar: Bağlanıyor...")
        self.rank_label.setStyleSheet("color: #E2B25A; font-weight: bold; font-size: 12px;")
        rc_layout.addWidget(self.rank_label)
        layout.addWidget(rank_card)
        
        layout.addSpacing(6)
        btn_layout = QHBoxLayout()
        self.start_btn = QPushButton("Sıraya Gir", objectName="startQueueBtn")
        self.stop_btn = QPushButton("Sıradan Çık", objectName="stopQueueBtn")
        self.start_btn.clicked.connect(self.start_queue)
        self.stop_btn.clicked.connect(self.stop_queue)
        btn_layout.addWidget(self.start_btn)
        btn_layout.addWidget(self.stop_btn)
        layout.addLayout(btn_layout)
        
        parent_layout.addWidget(group)

    def on_roles_changed(self, primary, secondary):
        self.config.set('role_primary', primary)
        self.config.set('role_secondary', secondary)
        if not getattr(self, '_is_loading', False):
            self.config.save()
            self.apply_roles_if_in_lobby()

    def on_create_lobby_clicked(self):
        mode_text = self.game_mode_combo.currentText()
        queue_id = self.mode_queue_map.get(mode_text, 420)
        self.on_mode_button_clicked(mode_text, queue_id)

    def on_delay_slider_changed(self, val):
        if val == 0:
            self.accept_delay_badge.setText("[ Anında ]")
        else:
            self.accept_delay_badge.setText(f"[ {val} sn ]")
        if not getattr(self, '_is_loading', False):
            self.save_config()

    def setup_pickban_card(self, parent_layout):
        group = QGroupBox("ŞAMPİYON SEÇİM & BAN")
        group.setFixedWidth(490)
        layout = QVBoxLayout(group)
        layout.setContentsMargins(14, 10, 14, 10)
        layout.setSpacing(6)
        
        layout.addWidget(QLabel("Seçim Tercihi"))
        
        pick_grid = QGridLayout()
        pick_grid.setSpacing(6)
        self.pick_icons = []
        self.pick_combos = []
        for i, text in enumerate(["1.", "2.", "3."]):
            lbl = QLabel(text)
            lbl.setAlignment(Qt.AlignCenter)
            pick_grid.addWidget(lbl, 0, i)
            
            icon = QLabel()
            icon.setFixedSize(48, 48)
            icon.setStyleSheet("background-color: #1A1C23; border-radius: 24px;")
            icon.setAlignment(Qt.AlignCenter)
            self.pick_icons.append(icon)
            pick_grid.addWidget(icon, 1, i, alignment=Qt.AlignCenter)
            
            combo = QComboBox()
            combo.setFixedWidth(118)
            combo.addItems(self.champ_list)
            combo.currentIndexChanged.connect(lambda idx, c=i: self.update_pick(c))
            self.pick_combos.append(combo)
            pick_grid.addWidget(combo, 2, i)
            
        ready = QLabel("Hazır", objectName="readyText")
        pick_grid.addWidget(ready, 2, 3)
        layout.addLayout(pick_grid)
        
        sw_layout1 = QHBoxLayout()
        sw_layout1.addWidget(QLabel("Oto Şampiyon Seçimi"))
        self.auto_sel_sw = ModernSwitch()
        sw_layout1.addWidget(self.auto_sel_sw)
        sw_layout1.addStretch()
        layout.addLayout(sw_layout1)
        
        sw_layout2 = QHBoxLayout()
        sw_layout2.addWidget(QLabel("Oto Banlama"))
        self.auto_lock_sw = ModernSwitch()
        sw_layout2.addWidget(self.auto_lock_sw)
        sw_layout2.addStretch()
        layout.addLayout(sw_layout2)
        
        # Chat box
        sw_layout3 = QVBoxLayout()
        sw_top = QHBoxLayout()
        sw_top.addWidget(QLabel("Şampiyon Seçimi Sohbet Mesajı"))
        self.post_pick_chat_sw = ModernSwitch()
        sw_top.addWidget(self.post_pick_chat_sw)
        sw_top.addStretch()
        sw_layout3.addLayout(sw_top)
        
        chat_inputs = QHBoxLayout()
        self.chat_msg_input = QLineEdit()
        self.chat_msg_input.setPlaceholderText("Lobi sohbet mesajı (örn: mid lütfen)...")
        chat_inputs.addWidget(self.chat_msg_input, 3)
        
        chat_inputs.addWidget(QLabel("Tekrar:"))
        self.chat_repeat_spin = QSpinBox()
        self.chat_repeat_spin.setRange(1, 5)
        self.chat_repeat_spin.setValue(1)
        self.chat_repeat_spin.setSuffix(" Kez")
        self.chat_repeat_spin.setFixedWidth(75)
        self.chat_repeat_spin.valueChanged.connect(lambda val: (self.config.set('chat_repeat_count', val), self.config.save()))
        chat_inputs.addWidget(self.chat_repeat_spin)
        sw_layout3.addLayout(chat_inputs)
        
        # Presets row
        presets_box = QHBoxLayout()
        presets_box.setSpacing(5)
        for preset_text in ["mid", "top pls", "adc", "jungle salın pls", "selamlar takım"]:
            p_btn = QPushButton(preset_text, objectName="presetBtn")
            p_btn.setCursor(Qt.PointingHandCursor)
            p_btn.clicked.connect(lambda _, txt=preset_text: (self.chat_msg_input.setText(txt), self.save_config()))
            presets_box.addWidget(p_btn)
        presets_box.addStretch()
        sw_layout3.addLayout(presets_box)
        
        layout.addLayout(sw_layout3)
        layout.addWidget(QLabel("Ban Tercihi:"))
        
        ban_grid = QGridLayout()
        ban_grid.setSpacing(6)
        self.ban_icons = []
        self.ban_combos = []
        for i in range(3):
            icon = QLabel()
            icon.setFixedSize(48, 48)
            icon.setStyleSheet("background-color: #1A1C23; border-radius: 24px;")
            icon.setAlignment(Qt.AlignCenter)
            self.ban_icons.append(icon)
            ban_grid.addWidget(icon, 0, i, alignment=Qt.AlignCenter)
            
            combo = QComboBox()
            combo.setFixedWidth(118)
            combo.addItems(self.champ_list)
            combo.currentIndexChanged.connect(lambda idx, c=i: self.update_ban(c))
            self.ban_combos.append(combo)
            ban_grid.addWidget(combo, 1, i)
            
        ready_ban = QLabel("Hazır", objectName="readyText")
        ban_grid.addWidget(ready_ban, 1, 3)
        layout.addLayout(ban_grid)
        
        layout.addStretch()
        
        # Status box with Safe Dodge & OP.GG Multi-Search buttons
        status_box = QFrame()
        status_box.setStyleSheet("""
            QFrame {
                background-color: #14161D;
                border: 1px solid #232733;
                border-radius: 8px;
            }
        """)
        s_layout = QVBoxLayout(status_box)
        s_layout.setContentsMargins(10, 6, 10, 6)
        s_layout.setSpacing(4)
        
        top_status_row = QHBoxLayout()
        self.pb_dot = QLabel("●")
        self.pb_dot.setStyleSheet("color: #717B8A; font-size: 13px;")
        top_status_row.addWidget(self.pb_dot)
        
        self.pb_status = QLabel("Durum: [Lobi Bekleniyor]")
        self.pb_status.setStyleSheet("color: #E2B25A; font-weight: bold; font-size: 12px;")
        top_status_row.addWidget(self.pb_status)
        top_status_row.addStretch()
        s_layout.addLayout(top_status_row)
        
        detail_row = QHBoxLayout()
        detail_row.setSpacing(10)
        self.pb_selected = QLabel("Seçim: -")
        self.pb_selected.setStyleSheet("color: #0AC8B9; font-weight: bold; font-size: 11px;")
        detail_row.addWidget(self.pb_selected, 1)
        self.pb_banned = QLabel("Ban: -")
        self.pb_banned.setStyleSheet("color: #E05656; font-weight: bold; font-size: 11px;")
        detail_row.addWidget(self.pb_banned, 1)
        s_layout.addLayout(detail_row)

        # Action row: Safe Dodge & OP.GG Multi-search
        action_row = QHBoxLayout()
        self.btn_dodge = QPushButton("Lobiyi Güvenle Boz (Dodge)", objectName="dodgeBtn")
        self.btn_dodge.setCursor(Qt.PointingHandCursor)
        self.btn_dodge.clicked.connect(self.on_safe_dodge_clicked)
        action_row.addWidget(self.btn_dodge)

        self.btn_opgg = QPushButton("Takımı OP.GG'de Gör", objectName="opggBtn")
        self.btn_opgg.setCursor(Qt.PointingHandCursor)
        self.btn_opgg.clicked.connect(self.open_opgg_multi_search)
        action_row.addWidget(self.btn_opgg)
        s_layout.addLayout(action_row)
        
        layout.addWidget(status_box)
        parent_layout.addWidget(group)

    def on_safe_dodge_clicked(self):
        if self.lcu_client.force_dodge():
            self.append_log("Lobiden güvenle çıkıldı / şampiyon seçimi bozuldu (Dodge).")
        else:
            self.append_log("Dodge isteği başarısız oldu (Şu an şampiyon seçiminde olmayabilirsiniz).")

    def open_opgg_multi_search(self):
        try:
            names = []
            session = self.lcu_client.get_champ_select_session()
            if session and isinstance(session, dict):
                for p in session.get("myTeam", []):
                    puuid = p.get("puuid")
                    if puuid:
                        try:
                            s = self.lcu_client.request("GET", f"/lol-summoner/v2/summoners/puuid/{puuid}")
                            if isinstance(s, dict):
                                gname = s.get("gameName")
                                tag = s.get("tagLine", "TR1")
                                if gname:
                                    names.append(f"{gname}%23{tag}")
                        except Exception:
                            pass
            
            if not names:
                lobby = self.lcu_client.get_lobby_info()
                if lobby and isinstance(lobby, dict):
                    for m in lobby.get("members", []):
                        m_name = m.get("summonerName")
                        if m_name:
                            names.append(m_name)

            if names:
                url = f"https://www.op.gg/multisearch/tr?summoners={','.join(names)}"
                webbrowser.open(url)
                self.append_log(f"OP.GG Çoklu Arama açıldı: {len(names)} oyuncu bulundu.")
            else:
                self.append_log("OP.GG için takım oyuncuları henüz tespit edilemedi (Lobi veya Şampiyon Seçimi bekleniyor).")
        except Exception as e:
            self.append_log(f"OP.GG arama hatası: {e}")

    def setup_scripts_page(self):
        page = QWidget()
        scroll = QScrollArea(page)
        scroll.setWidgetResizable(True)
        scroll.setStyleSheet("QScrollArea { border: none; background: transparent; }")
        
        content = QWidget()
        layout = QVBoxLayout(content)
        layout.setContentsMargins(25, 20, 25, 20)
        layout.setSpacing(15)
        
        group1 = QGroupBox("YENİLİKÇİ VE GEREKLİ OTOMASYONLAR")
        g1_layout = QVBoxLayout(group1)
        g1_layout.setSpacing(12)
        
        modules = [
            ("Otomatik Meta Rün İçe Aktarma (Auto Runes)", "Şampiyon kilitlendiği an resmi Riot API'sinden en yüksek kazanma oranlı meta rün sayfasını uygular.", "auto_recommended_runes"),
            ("Akıllı Çarp & Büyü Koruyucusu (Smart Spells / Auto Smite)", "Ormancı geldiğinde otomatik Çarp+Sıçra, diğer rollere uygun meta sihirdar büyülerini atar.", "auto_smart_spells"),
            ("Otomatik Arkadaş Daveti Kabulü (Auto Invite Accept)", "Arkadaşların seni bir lobiye davet ettiğinde beklemeden otomatik katılır.", "auto_accept_invites"),
            ("Gizli Mod / Çevrimdışı Görünme (Appear Offline)", "LoL istemcisinde maç atarken arkadaş listesinde görünmez (offline) kalmanı sağlar.", "auto_appear_offline"),
            ("İstemci Düşük Donanım Modu (FPS Boost)", "Oyun içindeyken LoL istemcisini uyutarak maksimum FPS ve sıfır RAM kullanımı sağlar.", "auto_low_spec")
        ]
        
        self.script_switches = {}
        for title, desc, key in modules:
            row = QHBoxLayout()
            lbl_box = QVBoxLayout()
            lbl_box.addWidget(QLabel(title))
            sub = QLabel(desc)
            sub.setStyleSheet("color: #6C7A89; font-size: 11px;")
            lbl_box.addWidget(sub)
            row.addLayout(lbl_box)
            
            sw = ModernSwitch()
            sw.setChecked(self.config.get(key, True if key in ("auto_recommended_runes", "auto_smart_spells") else False))
            sw.toggled.connect(lambda val, k=key: self.on_script_toggled(k, val))
            self.script_switches[key] = sw
            row.addWidget(sw)
            g1_layout.addLayout(row)
            
        layout.addWidget(group1)
        
        group2 = QGroupBox("HIZLI LOBİ EYLEMLERİ")
        g2_layout = QHBoxLayout(group2)
        btn_fix_lobby = QPushButton("Lobiyi Yenile / Sıfırla")
        btn_fix_lobby.clicked.connect(lambda: self.on_mode_button_clicked('Dereceli Tek/Çift (Solo/Duo)', 420))
        
        btn_leave_lobby = QPushButton("Lobiden Tamamen Ayrıl")
        btn_leave_lobby.clicked.connect(self.leave_lobby_action)
        
        g2_layout.addWidget(btn_fix_lobby)
        g2_layout.addWidget(btn_leave_lobby)
        layout.addWidget(group2)
        
        layout.addStretch()
        
        page_layout = QVBoxLayout(page)
        page_layout.setContentsMargins(0, 0, 0, 0)
        scroll.setWidget(content)
        page_layout.addWidget(scroll)
        
        self.stacked_widget.addWidget(page)

    def leave_lobby_action(self):
        try:
            self.lcu_client.request("DELETE", "/lol-lobby/v2/lobby")
            self.append_log("Lobiden tamamen ayrılındı.")
            self.queue_status.setText("Sıra Durumu: [Boşta]")
        except Exception:
            pass

    def on_script_toggled(self, key, val):
        if getattr(self, '_is_loading', False):
            return
        self.config.set(key, val)
        self.config.save()
        status_txt = "Açık" if val else "Kapalı"
        self.append_log(f"Otomasyon Ayarı Güncellendi: {key} -> {status_txt}")

    def setup_logs_page(self):
        page = QWidget()
        layout = QVBoxLayout(page)
        layout.setContentsMargins(30, 20, 30, 20)
        layout.setSpacing(15)
        
        top_layout = QHBoxLayout()
        top_layout.addWidget(QLabel("CANLI SİSTEM KONSOLU & EVENT LOGLARI"))
        top_layout.addStretch()
        btn_clear = QPushButton("Logları Temizle")
        btn_clear.clicked.connect(lambda: self.log_text.clear())
        top_layout.addWidget(btn_clear)
        layout.addLayout(top_layout)
        
        self.log_text = QTextEdit()
        self.log_text.setReadOnly(True)
        self.log_text.append(f"[{time.strftime('%H:%M:%S')}] RiftFlow Pro Paneli Başlatıldı.")
        layout.addWidget(self.log_text)
        
        self.stacked_widget.addWidget(page)

    def update_pick(self, idx):
        champ = self.pick_combos[idx].currentText()
        pm = self.get_champion_pixmap(champ)
        if not pm.isNull():
            self.pick_icons[idx].setPixmap(pm)
        else:
            self.pick_icons[idx].clear()
        if not getattr(self, '_is_loading', False):
            self.save_config()

    def update_ban(self, idx):
        champ = self.ban_combos[idx].currentText()
        pm = self.get_champion_pixmap(champ)
        if not pm.isNull():
            self.ban_icons[idx].setPixmap(pm)
        else:
            self.ban_icons[idx].clear()
        if not getattr(self, '_is_loading', False):
            self.save_config()

    def load_config(self):
        self.auto_accept_sw.setChecked(self.config.get('auto_accept', True))
        
        delay = self.config.get('accept_delay', 0)
        self.accept_delay_slider.setValue(delay)
        if delay == 0:
            self.accept_delay_badge.setText("[ Anında ]")
        else:
            self.accept_delay_badge.setText(f"[ {delay} sn ]")
        
        saved_mode = self.config.get('game_mode', 'Dereceli Tek/Çift (Solo/Duo)')
        idx = self.game_mode_combo.findText(saved_mode)
        if idx >= 0:
            self.game_mode_combo.setCurrentIndex(idx)
        
        self.auto_lock_sw.setChecked(self.config.get('auto_ban', True))
        self.auto_sel_sw.setChecked(self.config.get('auto_pick', True))
        
        self.post_pick_chat_sw.setChecked(self.config.get('post_pick_chat', False))
        self.chat_msg_input.setText(self.config.get('chat_message', 'mid'))
        self.chat_repeat_spin.setValue(self.config.get('chat_repeat_count', 1))
        
        # Load roles canonically
        pr = self.config.get('role_primary', 'BOTTOM')
        sr = self.config.get('role_secondary', 'UTILITY')
        self.role_selector.set_roles(pr, sr)
        
        for i in range(1, 4):
            pick = self.config.get(f'pick_preference_{i}', 'None')
            if self.pick_combos[i-1].findText(pick) >= 0: 
                self.pick_combos[i-1].setCurrentText(pick)
            self.update_pick(i-1)
            
            ban = self.config.get(f'ban_preference_{i}', 'None')
            if self.ban_combos[i-1].findText(ban) >= 0: 
                self.ban_combos[i-1].setCurrentText(ban)
            self.update_ban(i-1)
            
        for k, sw in getattr(self, 'script_switches', {}).items():
            sw.setChecked(self.config.get(k, True if k in ("auto_recommended_runes", "auto_smart_spells") else False))

        # Connect signals for auto saving
        self.auto_accept_sw.toggled.connect(lambda _: self.save_config())
        self.auto_lock_sw.toggled.connect(lambda _: self.save_config())
        self.auto_sel_sw.toggled.connect(lambda _: self.save_config())
        self.post_pick_chat_sw.toggled.connect(lambda _: self.save_config())
        self.chat_msg_input.textChanged.connect(lambda _: self.save_config())
        self.game_mode_combo.currentTextChanged.connect(lambda _: self.save_config())

    def on_mode_button_clicked(self, mode_name, queue_id):
        self.config.set('game_mode', mode_name)
        self.config.save()
        try:
            cur_lobby = self.lcu_client.get_lobby_info()
            if cur_lobby:
                self.lcu_client.request("DELETE", "/lol-lobby/v2/lobby")
                time.sleep(0.2)
            self.lcu_client.create_lobby(queue_id)
            time.sleep(0.25)
            self.apply_roles_if_in_lobby()
            self.queue_status.setText(f"Sıra Durumu: [Lobi Kuruldu - {mode_name}]")
            self.append_log(f"Oyun Modu değiştirildi: {mode_name} (Lobi Kuruldu)")
        except Exception:
            pass

    def apply_roles_if_in_lobby(self):
        """Only apply position preferences if currently in a draft/ranked queue."""
        try:
            lobby_info = self.lcu_client.get_lobby_info()
            if not lobby_info or not isinstance(lobby_info, dict):
                return False

            queue_id = lobby_info.get("gameConfig", {}).get("queueId")
            if queue_id not in self.ROLE_SUPPORTED_QUEUES:
                return False

            primary, secondary = self.role_selector.get_roles()
            if self.lcu_client.set_roles(primary, secondary):
                self.append_log(f"Lobi Rolleri Güncellendi: 1. -> {primary}, 2. -> {secondary}")
                return True
        except Exception as e:
            logger.debug(f"apply_roles_if_in_lobby error: {e}")
        return False

    def save_config(self):
        if getattr(self, '_is_loading', False):
            return
        self.config.set('auto_accept', self.auto_accept_sw.isChecked())
        self.config.set('accept_delay', self.accept_delay_slider.value())
        self.config.set('game_mode', self.game_mode_combo.currentText())
        
        self.config.set('auto_ban', self.auto_lock_sw.isChecked())
        self.config.set('auto_lock', self.auto_lock_sw.isChecked())
        self.config.set('auto_pick', self.auto_sel_sw.isChecked())
        self.config.set('auto_sel', self.auto_sel_sw.isChecked())
        
        self.config.set('post_pick_chat', self.post_pick_chat_sw.isChecked())
        self.config.set('chat_message', self.chat_msg_input.text())
        self.config.set('chat_repeat_count', self.chat_repeat_spin.value())
        
        pr, sr = self.role_selector.get_roles()
        self.config.set('role_primary', pr)
        self.config.set('role_secondary', sr)
        
        for i in range(1, 4):
            self.config.set(f'pick_preference_{i}', self.pick_combos[i-1].currentText())
            self.config.set(f'ban_preference_{i}', self.ban_combos[i-1].currentText())
            
        for k, sw in getattr(self, 'script_switches', {}).items():
            self.config.set(k, sw.isChecked())
            
        self.config.save()
        
    def start_queue(self):
        mode_text = self.game_mode_combo.currentText()
        queue_id = self.mode_queue_map.get(mode_text, 420)
        
        try:
            cur_lobby = self.lcu_client.get_lobby_info()
            if not cur_lobby:
                self.lcu_client.create_lobby(queue_id)
                time.sleep(0.3)
            self.apply_roles_if_in_lobby()
            time.sleep(0.2)
            if self.lcu_client.start_matchmaking():
                self.queue_status.setText("Sıra Durumu: [Sıra Aranıyor...]")
                self.live_status.setText("Canlı Durum: Sıra Aranıyor...")
                self.append_log(f"Eşleştirme araması başlatıldı! ({mode_text})")
        except Exception:
            pass
        
    def stop_queue(self):
        try:
            if self.lcu_client.stop_matchmaking():
                self.queue_status.setText("Sıra Durumu: [Durduruldu]")
                self.live_status.setText("Canlı Durum: Sıra Durduruldu")
                self.append_log("Eşleştirme araması durduruldu.")
        except Exception:
            pass
        
    def update_status(self, status):
        if status == "Connected":
            self.status_label.setText("Durum: Aktif (Bağlandı)")
            self.status_label.setStyleSheet("color: #26B47C; font-weight: bold;")
        else:
            self.status_label.setText("Durum: LoL Bekleniyor...")
            self.status_label.setStyleSheet("color: #E2B25A; font-weight: bold;")
            self.profile_label.setText("Profil: Çevrimdışı (LoL Bekleniyor)")
            self.rank_label.setText("Sihirdar: LoL Kapalı")

    def update_profile_info(self, data):
        name = data.get('gameName') or data.get('displayName') or 'Oyuncu'
        tag = data.get('tagLine', 'TR')
        level = data.get('summonerLevel', '')
        tier = data.get('tier', '')
        division = data.get('division', '')
        lp = data.get('leaguePoints', 0)
        
        rank_str = f"{tier} {division} ({lp} LP)" if tier and tier != "UNRANKED" else "Derecesiz (Unranked)"
        self.profile_label.setText(f"Profil: {name}#{tag} (Lv.{level})")
        self.rank_label.setText(f"Sihirdar: {name}#{tag} | {rank_str}")

    def update_champ_select_labels(self, picked, banned):
        if hasattr(self, 'pb_selected'):
            if picked and picked.strip() and picked not in ("Yok", "-", "None", ""):
                self.pb_selected.setText(f"Seçim: {picked}")
                self.pb_selected.setStyleSheet("color: #26B47C; font-weight: bold; font-size: 11px;")
            else:
                self.pb_selected.setText("Seçim: Bekleniyor")
                self.pb_selected.setStyleSheet("color: #0AC8B9; font-weight: bold; font-size: 11px;")

        if hasattr(self, 'pb_banned'):
            if banned and banned.strip() and banned not in ("Yok", "-", "None", ""):
                self.pb_banned.setText(f"Ban: {banned}")
                self.pb_banned.setStyleSheet("color: #E05656; font-weight: bold; font-size: 11px;")
            else:
                self.pb_banned.setText("Ban: Bekleniyor")
                self.pb_banned.setStyleSheet("color: #A0B0C0; font-weight: bold; font-size: 11px;")

    def update_gameflow(self, phase):
        phase_map = {
            "None": "Bekleniyor...",
            "Lobby": "Lobi Kuruldu",
            "Matchmaking": "Sıra Aranıyor...",
            "ReadyCheck": "Maç Bulundu! Kabul Ediliyor...",
            "ChampSelect": "Şampiyon Seçimi Aktif",
            "InProgress": "Oyun İçi (Maç Başladı)",
            "PreEndOfGame": "Maç Bitiyor",
            "EndOfGame": "Maç Bitti"
        }
        text = phase_map.get(phase, phase)
        
        if hasattr(self, 'queue_status'): self.queue_status.setText(f"Sıra Durumu: [{text}]")
        if hasattr(self, 'live_status'): self.live_status.setText(f"Canlı Durum: {text}")
        if hasattr(self, 'pb_status'): self.pb_status.setText(f"Durum: [{text}]")

        if hasattr(self, 'pb_dot'):
            if phase == "ChampSelect":
                self.pb_dot.setStyleSheet("color: #0AC8B9; font-size: 13px;")
                self.pb_status.setStyleSheet("color: #0AC8B9; font-weight: bold; font-size: 12px;")
            elif phase == "InProgress":
                self.pb_dot.setStyleSheet("color: #26B47C; font-size: 13px;")
                self.pb_status.setStyleSheet("color: #26B47C; font-weight: bold; font-size: 12px;")
            elif phase in ("Lobby", "Matchmaking"):
                self.pb_dot.setStyleSheet("color: #E2B25A; font-size: 13px;")
                self.pb_status.setStyleSheet("color: #E2B25A; font-weight: bold; font-size: 12px;")
            else:
                self.pb_dot.setStyleSheet("color: #717B8A; font-size: 13px;")
                self.pb_status.setStyleSheet("color: #A0B0C0; font-weight: bold; font-size: 12px;")

        if phase == "ChampSelect":
            if hasattr(self, 'pb_selected') and self.pb_selected.text().endswith("-"):
                self.pb_selected.setText("Seçim: Bekleniyor")
            if hasattr(self, 'pb_banned') and self.pb_banned.text().endswith("-"):
                self.pb_banned.setText("Ban: Bekleniyor")
        elif phase == "InProgress":
            pass
        elif phase in ("Lobby", "None", "Matchmaking"):
            if hasattr(self, 'pb_selected'): 
                self.pb_selected.setText("Seçim: -")
                self.pb_selected.setStyleSheet("color: #A0B0C0; font-weight: bold; font-size: 11px;")
            if hasattr(self, 'pb_banned'): 
                self.pb_banned.setText("Ban: -")
                self.pb_banned.setStyleSheet("color: #A0B0C0; font-weight: bold; font-size: 11px;")

        if phase in ("Lobby", "Matchmaking"):
            try:
                lobby_info = self.lcu_client.get_lobby_info()
                if lobby_info and isinstance(lobby_info, dict):
                    members = len(lobby_info.get('members', []))
                    if hasattr(self, 'lobby_count'):
                        self.lobby_count.setText(f"Lobideki Oyuncular: {members}")
            except Exception:
                pass
        else:
            if hasattr(self, 'lobby_count'):
                self.lobby_count.setText("Lobideki Oyuncular: 0")

    def closeEvent(self, event):
        """Standard window close exits cleanly without tray persistence."""
        self.lcu_worker.stop()
        self.lcu_worker.wait()
        try:
            self.lcu_client.close()
        except Exception:
            pass
        event.accept()
