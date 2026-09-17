with open('src/ui/main_window_v2.py', 'r', encoding='utf-8') as f:
    code = f.read()

code = code.replace('queue_status = QLabel("Sıra Durumu: [Boşta]")', 'self.queue_status = QLabel("Sıra Durumu: [Boşta]")')
code = code.replace('queue_status.setObjectName', 'self.queue_status.setObjectName')
code = code.replace('layout.addWidget(queue_status)', 'layout.addWidget(self.queue_status)')

code = code.replace('layout.addWidget(QLabel("Sıra Durumu: Bekleniyor...", objectName="highlightText"))', 'self.live_status = QLabel("Sıra Durumu: Bekleniyor...", objectName="highlightText")\n        layout.addWidget(self.live_status)')

code = code.replace('layout.addWidget(QLabel("Lobideki Oyuncular: 1", objectName="highlightText"))', 'self.lobby_count = QLabel("Lobideki Oyuncular: 0", objectName="highlightText")\n        layout.addWidget(self.lobby_count)')

code = code.replace('layout.addWidget(QLabel("Durum: [Lobi Bekleniyor]", objectName="highlightText"))', 'self.pb_status = QLabel("Durum: [Lobi Bekleniyor]", objectName="highlightText")\n        layout.addWidget(self.pb_status)')

# Inject connection in init_ui
init_pos = code.find('def init_ui(self):')
if init_pos != -1:
    conn_code = "        self.lcu_worker.gameflow_changed.connect(self.update_gameflow)\n"
    code = code[:init_pos+19] + conn_code + code[init_pos+19:]

# Inject update_gameflow method
method_code = '''
    def update_gameflow(self, phase):
        phase_map = {
            "None": "Bekleniyor...",
            "Lobby": "Lobi Kuruldu",
            "Matchmaking": "Sıra Aranıyor",
            "ReadyCheck": "Maç Bulundu!",
            "ChampSelect": "Şampiyon Seçimi",
            "InProgress": "Oyun İçi",
            "PreEndOfGame": "Maç Bitiyor",
            "EndOfGame": "Maç Bitti"
        }
        text = phase_map.get(phase, phase)
        
        if hasattr(self, 'queue_status'): self.queue_status.setText(f"Sıra Durumu: [{text}]")
        if hasattr(self, 'live_status'): self.live_status.setText(f"Canlı Durum: {text}")
        if hasattr(self, 'pb_status'): self.pb_status.setText(f"Durum: [{text}]")

'''
class_end_pos = code.rfind('def closeEvent')
if class_end_pos != -1:
    code = code[:class_end_pos] + method_code + code[class_end_pos:]

with open('src/ui/main_window_v2.py', 'w', encoding='utf-8') as f:
    f.write(code)
