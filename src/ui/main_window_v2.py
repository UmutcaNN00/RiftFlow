import requests
import time
from PySide6.QtWidgets import (
    QMainWindow, QWidget, QVBoxLayout, QHBoxLayout, QGridLayout,
    QGroupBox, QCheckBox, QSlider, QLabel, QComboBox, QPushButton, QSpacerItem, QSizePolicy,
    QStackedWidget, QButtonGroup, QSpinBox, QLineEdit, QTextEdit, QScrollArea, QFrame
)
from PySide6.QtCore import Qt, QSize, Signal, QRectF, QPropertyAnimation, Property
from PySide6.QtGui import QPixmap, QIcon, QPainter, QColor, QFont, QPainterPath

from src.core.config import ConfigManager
from src.core.worker import LcuWorker
from src.core.lcu_client import LcuClient
from src.core.data_dragon import DataDragon
from src.ui.modern_theme import MODERN_THEME

class SwitchWidget(QWidget):
    toggled = Signal(bool)
    
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setFixedSize(50, 24)
        self._checked = False
        self._pos = 0.0
        
        self.anim = QPropertyAnimation(self, b"pos_val")
        self.anim.setDuration(150)
        
    def get_pos(self):
        return self._pos
        
    def set_pos(self, val):
        self._pos = val
        self.update()
        
    pos_val = Property(float, get_pos, set_pos)
    
    def isChecked(self):
        return self._checked
        
    def setChecked(self, checked):
        self._checked = bool(checked)
        self._pos = 1.0 if self._checked else 0.0
        self.update()
        
    def mouseReleaseEvent(self, event):
        if event.button() == Qt.LeftButton:
            self._checked = not self._checked
            self.anim.setStartValue(self._pos)
            self.anim.setEndValue(1.0 if self._checked else 0.0)
            self.anim.start()
            self.toggled.emit(self._checked)
            
    def paintEvent(self, event):
        p = QPainter(self)
        p.setRenderHint(QPainter.Antialiasing)
        
        bg_color = QColor("#0AC8B9") if self._checked else QColor("#2A2D36")
        thumb_color = QColor("#FFFFFF") if self._checked else QColor("#8A9AAB")
        
        path = QPainterPath()
        path.addRoundedRect(0, 0, self.width(), self.height(), self.height()/2, self.height()/2)
        p.fillPath(path, bg_color)
        
        thumb_x = self._pos * (self.width() - self.height())
        thumb_rect = QRectF(thumb_x + 2, 2, self.height() - 4, self.height() - 4)
        p.setBrush(thumb_color)
        p.setPen(Qt.NoPen)
        p.drawEllipse(thumb_rect)
        
        if self._checked:
            p.setPen(QColor("#FFFFFF"))
            font = p.font()
            font.setPointSize(8)
            p.setFont(font)
            p.drawText(QRectF(8, 0, self.width()/2, self.height()), Qt.AlignVCenter, "Açık")

class MainWindowV2(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("RiftFlow - Pro Paneli")
        self.resize(1140, 640)
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
        self.lcu_worker.notification.connect(self.append_log)  # Bildirimler loga yazılsın
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
        
        # Sidebar
        sidebar = QWidget()
        sidebar.setObjectName("sidebar")
        sidebar.setFixedWidth(180)
        sidebar_layout = QVBoxLayout(sidebar)
        sidebar_layout.setContentsMargins(0, 20, 0, 20)
        sidebar_layout.setSpacing(6)
        
        self.nav_btns = []
        nav_items = ["Ana Sayfa", "Scriptler", "Loglar", "Ayarlar"]
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
        header.setFixedHeight(50)
        header_layout = QHBoxLayout(header)
        header_layout.setContentsMargins(20, 0, 20, 0)
        
        title_label = QLabel("RiftFlow :: LoL Otomasyonu")
        title_label.setObjectName("headerTitle")
        
        self.profile_label = QLabel("Profil: Oyuncu (TR)")
        self.status_label = QLabel("Durum: Bağlanıyor...")
        self.status_label.setObjectName("readyText")
        
        header_layout.addWidget(title_label)
        header_layout.addStretch()
        header_layout.addWidget(self.profile_label)
        header_layout.addSpacing(15)
        header_layout.addWidget(self.status_label)
        
        right_layout.addWidget(header)
        
        # Content - QStackedWidget
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
        
        # Page 3: Ayarlar
        self.setup_settings_page()
            
        self.stacked_widget.setCurrentIndex(0)
        main_layout.addWidget(right_widget)

    def switch_page(self, idx):
        for i, btn in enumerate(self.nav_btns):
            btn.setChecked(i == idx)
        self.stacked_widget.setCurrentIndex(idx)

    def setup_matchmaking_card(self, parent_layout):
        group = QGroupBox("EŞLEŞTİRME")
        group.setFixedWidth(430)
        layout = QVBoxLayout(group)
        layout.setSpacing(12)
        
        layout.addWidget(QLabel("Oyun Modu:"))
        mode_layout = QHBoxLayout()
        self.mode_group = QButtonGroup(self)
        self.mode_group.setExclusive(True)
        
        self.btn_ranked = QPushButton("Dereceli Tek/Çift")
        self.btn_ranked.setCheckable(True)
        self.btn_draft = QPushButton("Sıralı Seçim")
        self.btn_draft.setCheckable(True)
        self.btn_aram = QPushButton("ARAM")
        self.btn_aram.setCheckable(True)
        
        self.mode_group.addButton(self.btn_ranked, 1)
        self.mode_group.addButton(self.btn_draft, 2)
        self.mode_group.addButton(self.btn_aram, 3)
        
        mode_layout.addWidget(self.btn_ranked)
        mode_layout.addWidget(self.btn_draft)
        mode_layout.addWidget(self.btn_aram)
        layout.addLayout(mode_layout)
        
        self.queue_status = QLabel("Sıra Durumu: [Boşta]")
        self.queue_status.setObjectName("highlightText")
        layout.addWidget(self.queue_status)
        
        # Auto Queue
        aq_layout = QHBoxLayout()
        aq_layout.addWidget(QLabel("Oto Sıra"))
        self.auto_queue_sw = SwitchWidget()
        aq_layout.addWidget(self.auto_queue_sw)
        aq_layout.addStretch()
        layout.addLayout(aq_layout)
        
        # Auto Accept + Sleek Slider
        aa_layout = QVBoxLayout()
        aa_header = QHBoxLayout()
        aa_header.addWidget(QLabel("Oto Kabul"))
        self.auto_accept_sw = SwitchWidget()
        aa_header.addWidget(self.auto_accept_sw)
        
        self.accept_delay_badge = QLabel("[ Anında ]")
        self.accept_delay_badge.setStyleSheet("color: #0AC8B9; font-weight: bold; background-color: #1A1C23; padding: 2px 8px; border-radius: 4px;")
        aa_header.addWidget(self.accept_delay_badge)
        aa_header.addStretch()
        aa_layout.addLayout(aa_header)
        
        slider_box = QHBoxLayout()
        slider_box.addWidget(QLabel("Gecikme:"))
        self.accept_delay_slider = QSlider(Qt.Horizontal)
        self.accept_delay_slider.setRange(0, 10)
        self.accept_delay_slider.setValue(0)
        self.accept_delay_slider.valueChanged.connect(self.on_delay_slider_changed)
        slider_box.addWidget(self.accept_delay_slider)
        aa_layout.addLayout(slider_box)
        layout.addLayout(aa_layout)
        
        self.role_pref = QCheckBox("Rol Tercihi")
        layout.addWidget(self.role_pref)
        
        role_layout = QHBoxLayout()
        role_layout.addWidget(QLabel("Birincil:"))
        self.primary_role_combo = QComboBox()
        self.primary_role_combo.addItems(["ADC", "Support", "Mid", "Top", "Jungle"])
        role_layout.addWidget(self.primary_role_combo)
        role_layout.addWidget(QLabel("İkincil:"))
        self.secondary_role_combo = QComboBox()
        self.secondary_role_combo.addItems(["Support", "ADC", "Mid", "Top", "Jungle"])
        role_layout.addWidget(self.secondary_role_combo)
        layout.addLayout(role_layout)
        
        layout.addSpacing(5)
        self.live_status = QLabel("Canlı Durum: Bekleniyor...", objectName="highlightText")
        layout.addWidget(self.live_status)
        self.lobby_count = QLabel("Lobideki Oyuncular: 1", objectName="highlightText")
        layout.addWidget(self.lobby_count)
        
        rank_layout = QVBoxLayout()
        rank_layout.setSpacing(4)
        rank_label = QLabel("Sihirdar: Yükleniyor...")
        rank_label.setStyleSheet("color: #E2B25A; font-weight: bold;")
        self.rank_label = rank_label
        rank_layout.addWidget(rank_label)
        
        bar_bg = QWidget()
        bar_bg.setFixedHeight(4)
        bar_bg.setStyleSheet("background-color: #2A2D36; border-radius: 2px;")
        bar_layout = QHBoxLayout(bar_bg)
        bar_layout.setContentsMargins(0,0,0,0)
        bar_fill = QWidget()
        bar_fill.setFixedWidth(120)
        bar_fill.setStyleSheet("background-color: #0AC8B9; border-radius: 2px;")
        bar_layout.addWidget(bar_fill, alignment=Qt.AlignLeft)
        rank_layout.addWidget(bar_bg)
        layout.addLayout(rank_layout)
        
        layout.addSpacing(10)
        btn_layout = QHBoxLayout()
        self.start_btn = QPushButton("Sıraya Gir", objectName="startQueueBtn")
        self.stop_btn = QPushButton("Sıradan Çık", objectName="stopQueueBtn")
        self.start_btn.clicked.connect(self.start_queue)
        self.stop_btn.clicked.connect(self.stop_queue)
        btn_layout.addWidget(self.start_btn)
        btn_layout.addWidget(self.stop_btn)
        layout.addLayout(btn_layout)
        
        parent_layout.addWidget(group)

    def on_delay_slider_changed(self, val):
        if val == 0:
            self.accept_delay_badge.setText("[ Anında ]")
        else:
            self.accept_delay_badge.setText(f"[ {val} sn ]")
        if not getattr(self, '_is_loading', False):
            self.save_config()

    def setup_pickban_card(self, parent_layout):
        group = QGroupBox("ŞAMPİYON SEÇİM/BAN")
        group.setFixedWidth(470)
        layout = QVBoxLayout(group)
        layout.setSpacing(12)
        
        layout.addWidget(QLabel("Seçim Tercihi"))
        
        pick_grid = QGridLayout()
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
            combo.setFixedWidth(115)
            combo.addItems(self.champ_list)
            combo.currentIndexChanged.connect(lambda idx, c=i: self.update_pick(c))
            self.pick_combos.append(combo)
            pick_grid.addWidget(combo, 2, i)
            
        ready = QLabel("Hazır", objectName="readyText")
        pick_grid.addWidget(ready, 2, 3)
        layout.addLayout(pick_grid)
        layout.addSpacing(4)
        
        sw_layout1 = QHBoxLayout()
        sw_layout1.addWidget(QLabel("Oto Şampiyon Seçimi"))
        self.auto_sel_sw = SwitchWidget()
        sw_layout1.addWidget(self.auto_sel_sw)
        sw_layout1.addStretch()
        layout.addLayout(sw_layout1)
        
        sw_layout2 = QHBoxLayout()
        sw_layout2.addWidget(QLabel("Oto Banlama"))
        self.auto_lock_sw = SwitchWidget()
        sw_layout2.addWidget(self.auto_lock_sw)
        sw_layout2.addStretch()
        layout.addLayout(sw_layout2)
        
        # Chat box
        sw_layout3 = QVBoxLayout()
        sw_top = QHBoxLayout()
        sw_top.addWidget(QLabel("Seçim Sonrası Rol Sohbeti"))
        self.post_pick_chat_sw = SwitchWidget()
        sw_top.addWidget(self.post_pick_chat_sw)
        sw_top.addStretch()
        sw_layout3.addLayout(sw_top)
        
        chat_inputs = QHBoxLayout()
        self.chat_msg_input = QLineEdit()
        self.chat_msg_input.setPlaceholderText("Gönderilecek mesaj (örn: mid lütfen)...")
        chat_inputs.addWidget(self.chat_msg_input, 3)
        
        chat_inputs.addWidget(QLabel("Tekrar:"))
        self.repeat_group = QButtonGroup(self)
        self.repeat_group.setExclusive(True)
        self.repeat_btns = []
        for r_num in [1, 2, 3]:
            r_btn = QPushButton(f"{r_num} Kez")
            r_btn.setCheckable(True)
            r_btn.setFixedWidth(56)
            if r_num == 1:
                r_btn.setChecked(True)
            r_btn.clicked.connect(lambda checked, num=r_num: self.on_repeat_btn_clicked(num))
            self.repeat_group.addButton(r_btn)
            self.repeat_btns.append(r_btn)
            chat_inputs.addWidget(r_btn)
        sw_layout3.addLayout(chat_inputs)
        layout.addLayout(sw_layout3)
        
        layout.addSpacing(4)
        layout.addWidget(QLabel("Ban Tercihi:"))
        
        ban_grid = QGridLayout()
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
            combo.setFixedWidth(115)
            combo.addItems(self.champ_list)
            combo.currentIndexChanged.connect(lambda idx, c=i: self.update_ban(c))
            self.ban_combos.append(combo)
            ban_grid.addWidget(combo, 1, i)
            
        ready_ban = QLabel("Hazır", objectName="readyText")
        ban_grid.addWidget(ready_ban, 1, 3)
        layout.addLayout(ban_grid)
        
        layout.addStretch()
        status_box = QFrame()
        status_box.setStyleSheet("""
            QFrame {
                background-color: #14161D;
                border: 1px solid #232733;
                border-radius: 8px;
            }
        """)
        s_layout = QVBoxLayout(status_box)
        s_layout.setContentsMargins(12, 8, 12, 8)
        s_layout.setSpacing(6)
        
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
        self.pb_selected = QLabel("Seçilen: -")
        self.pb_selected.setStyleSheet("color: #0AC8B9; font-weight: bold; font-size: 12px;")
        detail_row.addWidget(self.pb_selected)
        
        detail_row.addSpacing(20)
        
        self.pb_banned = QLabel("Ban: -")
        self.pb_banned.setStyleSheet("color: #E05656; font-weight: bold; font-size: 12px;")
        detail_row.addWidget(self.pb_banned)
        detail_row.addStretch()
        s_layout.addLayout(detail_row)
        
        layout.addWidget(status_box)
        
        parent_layout.addWidget(group)

    def on_repeat_btn_clicked(self, count):
        self.config.set('chat_repeat_count', count)
        if not getattr(self, '_is_loading', False):
            self.save_config()

    def setup_scripts_page(self):
        page = QWidget()
        scroll = QScrollArea(page)
        scroll.setWidgetResizable(True)
        scroll.setStyleSheet("QScrollArea { border: none; background: transparent; }")
        
        content = QWidget()
        layout = QVBoxLayout(content)
        layout.setContentsMargins(25, 20, 25, 20)
        layout.setSpacing(15)
        
        group1 = QGroupBox("MAÇ ÖNCESİ & LOBİ OTOMASYONLARI")
        g1_layout = QVBoxLayout(group1)
        g1_layout.setSpacing(12)
        
        modules = [
            ("ARAM Otomatik Zar Atma (Auto-Reroll)", "ARAM lobisine girildiğinde varsa otomatik 1 adet yeniden zar atar.", "auto_reroll_aram"),
            ("Otomatik Tekrar Oyna (Auto Play Again)", "Maç bittiğinde ve istatistik ekranı geldiğinde otomatik lobiyi yeniden kurar.", "auto_play_again"),
            ("Otomatik 'Hazırım' Onayı (Auto Party Ready)", "Lobi başkanı oyunu başlattığında takımdaki yerini otomatik hazıra çeker.", "auto_party_ready"),
            ("İstemci Düşük Donanım Modu (FPS Boost)", "Oyun içindeyken LoL istemcisini uyutarak maksimum FPS ve sıfır RAM kullanımı sağlar.", "auto_low_spec"),
            ("Oyun Sonu Otomatik İfade/Emote (GGWP)", "Maç bittiği an ekranda otomatik 'Ustalık' veya 'GG' ifadesi patlatır.", "auto_end_emote"),
            ("Erken Teslim Olma Oylamasına Otomatik 'Hayır' Oyu", "15. veya 20. dakikadaki gereksiz teslim olma oylarını anında 'Hayır'lar.", "auto_no_ff"),
            ("Otomatik Rol Takas Kabulü (Auto Swap Accept)", "Şampiyon seçiminde biri seninle rol takas etmek isterse otomatik onaylar.", "auto_swap_accept")
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
            
            sw = SwitchWidget()
            sw.setChecked(self.config.get(key, False))
            sw.toggled.connect(lambda val, k=key: self.on_script_toggled(k, val))
            self.script_switches[key] = sw
            row.addWidget(sw)
            g1_layout.addLayout(row)
            
        layout.addWidget(group1)
        
        group2 = QGroupBox("HIZLI LOBİ EYLEMLERİ")
        g2_layout = QHBoxLayout(group2)
        btn_fix_lobby = QPushButton("Lobiyi Yenile / Sıfırla")
        btn_fix_lobby.clicked.connect(lambda: self.on_mode_button_clicked('Ranked Solo/Duo', 420))
        
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

    def setup_settings_page(self):
        page = QWidget()
        layout = QVBoxLayout(page)
        layout.setContentsMargins(30, 20, 30, 20)
        layout.setSpacing(20)
        
        group = QGroupBox("İSTEMCİ & BAĞLANTI AYARLARI")
        g_layout = QVBoxLayout(group)
        g_layout.setSpacing(15)
        
        lbl_dir = QLabel(f"Tespit Edilen LoL Dizini: E:\\Riot Games\\League of Legends")
        lbl_dir.setStyleSheet("color: #0AC8B9; font-weight: bold;")
        g_layout.addWidget(lbl_dir)
        
        r1 = QHBoxLayout()
        r1.addWidget(QLabel("Maç Bulunduğunda Ses Çal:"))
        self.sw_sound = SwitchWidget()
        self.sw_sound.setChecked(True)
        r1.addWidget(self.sw_sound)
        r1.addStretch()
        g_layout.addLayout(r1)

        r2 = QHBoxLayout()
        r2.addWidget(QLabel("Kapatıldığında Sistem Tepsisine Küçült:"))
        self.sw_tray = SwitchWidget()
        self.sw_tray.setChecked(True)
        r2.addWidget(self.sw_tray)
        r2.addStretch()
        g_layout.addLayout(r2)

        layout.addWidget(group)
        layout.addStretch()
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
        self.auto_queue_sw.setChecked(self.config.get('auto_queue', False))
        self.auto_accept_sw.setChecked(self.config.get('auto_accept', True))
        
        delay = self.config.get('accept_delay', 0)
        self.accept_delay_slider.setValue(delay)
        if delay == 0:
            self.accept_delay_badge.setText("[ Anında ]")
        else:
            self.accept_delay_badge.setText(f"[ {delay} sn ]")
        
        mode = self.config.get('game_mode', 'Ranked Solo/Duo')
        if mode == 'Normal Draft': self.btn_draft.setChecked(True)
        elif mode == 'ARAM': self.btn_aram.setChecked(True)
        else: self.btn_ranked.setChecked(True)
        
        self.auto_lock_sw.setChecked(self.config.get('auto_ban', True))
        self.auto_sel_sw.setChecked(self.config.get('auto_pick', True))
        
        self.post_pick_chat_sw.setChecked(self.config.get('post_pick_chat', False))
        self.chat_msg_input.setText(self.config.get('chat_message', 'mid'))
        
        rpt = self.config.get('chat_repeat_count', 1)
        for i, btn in enumerate(self.repeat_btns):
            btn.setChecked((i + 1) == rpt)
        
        self.role_pref.setChecked(self.config.get('role_pref_enabled', True))
        
        pr = self.config.get('role_primary', 'ADC')
        if self.primary_role_combo.findText(pr) >= 0: self.primary_role_combo.setCurrentText(pr)
        
        sr = self.config.get('role_secondary', 'Support')
        if self.secondary_role_combo.findText(sr) >= 0: self.secondary_role_combo.setCurrentText(sr)
        
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
            sw.setChecked(self.config.get(k, False))

        # Connect signals for auto saving
        self.auto_queue_sw.toggled.connect(lambda _: self.save_config())
        self.auto_accept_sw.toggled.connect(lambda _: self.save_config())
        
        self.btn_ranked.clicked.connect(lambda _: self.on_mode_button_clicked('Ranked Solo/Duo', 420))
        self.btn_draft.clicked.connect(lambda _: self.on_mode_button_clicked('Normal Draft', 400))
        self.btn_aram.clicked.connect(lambda _: self.on_mode_button_clicked('ARAM', 450))
        
        self.auto_lock_sw.toggled.connect(lambda _: self.save_config())
        self.auto_sel_sw.toggled.connect(lambda _: self.save_config())
        self.post_pick_chat_sw.toggled.connect(lambda _: self.save_config())
        self.chat_msg_input.textChanged.connect(lambda _: self.save_config())
        
        self.role_pref.toggled.connect(lambda _: (self.save_config(), self.apply_roles_if_in_lobby()))
        self.primary_role_combo.currentTextChanged.connect(lambda _: (self.save_config(), self.apply_roles_if_in_lobby()))
        self.secondary_role_combo.currentTextChanged.connect(lambda _: (self.save_config(), self.apply_roles_if_in_lobby()))

    def on_mode_button_clicked(self, mode_name, queue_id):
        self.config.set('game_mode', mode_name)
        self.config.save()
        try:
            cur_lobby = self.lcu_client.get_lobby_info()
            if cur_lobby:
                self.lcu_client.request("DELETE", "/lol-lobby/v2/lobby")
                time.sleep(0.2)
            self.lcu_client.create_lobby(queue_id)
            time.sleep(0.2)
            self.apply_roles_if_in_lobby()
            self.queue_status.setText(f"Sıra Durumu: [Lobi Kuruldu - {mode_name}]")
            self.append_log(f"Oyun Modu değiştirildi: {mode_name} (Lobi Kuruldu)")
        except Exception as e:
            pass

    def apply_roles_if_in_lobby(self):
        if not self.config.get('role_pref_enabled', True):
            return
        role_map = {
            "Top": "TOP",
            "Jungle": "JUNGLE",
            "Mid": "MIDDLE",
            "ADC": "BOTTOM",
            "Support": "UTILITY"
        }
        primary = role_map.get(self.primary_role_combo.currentText(), "BOTTOM")
        secondary = role_map.get(self.secondary_role_combo.currentText(), "UTILITY")
        try:
            if self.lcu_client.set_roles(primary, secondary):
                self.append_log(f"Lobi Rolleri Ayarlandı: Birincil -> {primary}, İkincil -> {secondary}")
        except Exception:
            pass

    def save_config(self):
        if getattr(self, '_is_loading', False):
            return
        self.config.set('auto_queue', self.auto_queue_sw.isChecked())
        self.config.set('auto_accept', self.auto_accept_sw.isChecked())
        self.config.set('accept_delay', self.accept_delay_slider.value())
        
        if self.btn_draft.isChecked(): self.config.set('game_mode', 'Normal Draft')
        elif self.btn_aram.isChecked(): self.config.set('game_mode', 'ARAM')
        else: self.config.set('game_mode', 'Ranked Solo/Duo')
        
        self.config.set('auto_ban', self.auto_lock_sw.isChecked())
        self.config.set('auto_lock', self.auto_lock_sw.isChecked())
        self.config.set('auto_pick', self.auto_sel_sw.isChecked())
        self.config.set('auto_sel', self.auto_sel_sw.isChecked())
        
        self.config.set('post_pick_chat', self.post_pick_chat_sw.isChecked())
        self.config.set('chat_message', self.chat_msg_input.text())
        
        self.config.set('role_pref_enabled', self.role_pref.isChecked())
        self.config.set('role_primary', self.primary_role_combo.currentText())
        self.config.set('role_secondary', self.secondary_role_combo.currentText())
        
        for i in range(1, 4):
            self.config.set(f'pick_preference_{i}', self.pick_combos[i-1].currentText())
            self.config.set(f'ban_preference_{i}', self.ban_combos[i-1].currentText())
            
        for k, sw in getattr(self, 'script_switches', {}).items():
            self.config.set(k, sw.isChecked())
            
        self.config.save()
        
    def start_queue(self):
        mode = self.config.get('game_mode', 'Ranked Solo/Duo')
        queue_map = {
            'Normal Draft': 400,
            'ARAM': 450,
            'Ranked Solo/Duo': 420
        }
        queue_id = queue_map.get(mode, 420)
        
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
                self.append_log("Eşleştirme araması başlatıldı!")
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
            try:
                info = self.lcu_client.get_summoner_info()
                if info and isinstance(info, dict):
                    name = info.get('gameName') or info.get('displayName') or 'Oyuncu'
                    self.profile_label.setText(f"Profil: {name} (TR)")
                    self.rank_label.setText(f"Sihirdar: {name} (Lv.{info.get('summonerLevel', '')})")
            except Exception:
                pass
        else:
            self.status_label.setText("Durum: LoL Bekleniyor...")
            self.status_label.setStyleSheet("color: #E2B25A; font-weight: bold;")

    def update_champ_select_labels(self, picked, banned):
        if hasattr(self, 'pb_selected'):
            if picked and picked.strip() and picked not in ("Yok", "-", "None", ""):
                self.pb_selected.setText(f"Seçilen: {picked}")
                self.pb_selected.setStyleSheet("color: #26B47C; font-weight: bold; font-size: 12px;")
            else:
                self.pb_selected.setText("Seçilen: Bekleniyor...")
                self.pb_selected.setStyleSheet("color: #0AC8B9; font-weight: bold; font-size: 12px;")

        if hasattr(self, 'pb_banned'):
            if banned and banned.strip() and banned not in ("Yok", "-", "None", ""):
                self.pb_banned.setText(f"Ban: {banned}")
                self.pb_banned.setStyleSheet("color: #E05656; font-weight: bold; font-size: 12px;")
            else:
                self.pb_banned.setText("Ban: Bekleniyor...")
                self.pb_banned.setStyleSheet("color: #A0B0C0; font-weight: bold; font-size: 12px;")

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
                self.pb_selected.setText("Seçilen: Bekleniyor...")
            if hasattr(self, 'pb_banned') and self.pb_banned.text().endswith("-"):
                self.pb_banned.setText("Ban: Bekleniyor...")
        elif phase == "InProgress":
            # Keep the champion locked in during the game! Don't reset
            pass
        elif phase in ("Lobby", "None", "Matchmaking"):
            if hasattr(self, 'pb_selected'): 
                self.pb_selected.setText("Seçilen: -")
                self.pb_selected.setStyleSheet("color: #A0B0C0; font-weight: bold; font-size: 12px;")
            if hasattr(self, 'pb_banned'): 
                self.pb_banned.setText("Ban: -")
                self.pb_banned.setStyleSheet("color: #A0B0C0; font-weight: bold; font-size: 12px;")

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
        self.lcu_worker.stop()
        self.lcu_worker.wait()  # Thread tamamen durana kadar bekle, yoksa crash olur
        try:
            self.lcu_client.close()
        except Exception:
            pass
        event.accept()
