with open('src/ui/main_window_v2.py', 'r', encoding='utf-8') as f:
    code = f.read()

new_code = code.replace('''    def start_queue(self):
        mode = self.config.get('game_mode', 'Ranked Solo/Duo')
        queue_id = 420
        if mode == 'Normal Draft':
            queue_id = 400
        elif mode == 'ARAM':
            queue_id = 450
            
        self.lcu_client.create_lobby(queue_id)
        
        if self.config.get('role_pref_enabled', False):
            role_map = {
                "Top": "TOP",
                "Jungle": "JUNGLE",
                "Mid": "MIDDLE",
                "ADC": "BOTTOM",
                "Support": "UTILITY"
            }
            primary = role_map.get(self.config.get('role_primary', 'Mid'), "UNSELECTED")
            secondary = role_map.get(self.config.get('role_secondary', 'Jungle'), "UNSELECTED")
            self.lcu_client.set_roles(primary, secondary)

        self.lcu_client.start_matchmaking()''', '''    def start_queue(self):
        mode = self.config.get('game_mode', 'Ranked Solo/Duo')
        queue_id = 420
        if mode == 'Normal Draft':
            queue_id = 400
        elif mode == 'ARAM':
            queue_id = 450
            
        try:
            self.lcu_client.create_lobby(queue_id)
        except Exception:
            pass
            
        if self.config.get('role_pref_enabled', False):
            role_map = {
                "Top": "TOP",
                "Jungle": "JUNGLE",
                "Mid": "MIDDLE",
                "ADC": "BOTTOM",
                "Support": "UTILITY"
            }
            primary = role_map.get(self.config.get('role_primary', 'Mid'), "UNSELECTED")
            secondary = role_map.get(self.config.get('role_secondary', 'Jungle'), "UNSELECTED")
            try:
                self.lcu_client.set_roles(primary, secondary)
            except Exception:
                pass

        try:
            self.lcu_client.start_matchmaking()
        except Exception:
            pass''')

new_code = new_code.replace('''    def stop_queue(self):
        self.lcu_client.stop_matchmaking()''', '''    def stop_queue(self):
        try:
            self.lcu_client.stop_matchmaking()
        except Exception:
            pass''')

with open('src/ui/main_window_v2.py', 'w', encoding='utf-8') as f:
    f.write(new_code)
