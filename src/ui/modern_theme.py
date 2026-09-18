MODERN_THEME = """
QMainWindow {
    background-color: #1E2027;
}
QWidget {
    color: #A0B0C0;
    font-family: 'Segoe UI', Arial, sans-serif;
    font-size: 13px;
}
#sidebar {
    background-color: #17181D;
    border-right: 1px solid #282A33;
}
#sidebar QPushButton {
    background-color: transparent;
    text-align: left;
    padding: 12px 20px;
    color: #8A9AAB;
    border: none;
    font-size: 14px;
    font-weight: 500;
}
#sidebar QPushButton:hover {
    color: #FFFFFF;
    background-color: #20222A;
}
#sidebar QPushButton:checked {
    color: #0AC8B9;
    background-color: #20222A;
    border-left: 4px solid #0AC8B9;
    font-weight: bold;
}
#header {
    background-color: #1E2027;
    border-bottom: 1px solid #282A33;
}
#headerTitle {
    color: #FFFFFF;
    font-weight: bold;
    font-size: 16px;
}
QGroupBox {
    background-color: #21242D;
    border: 1px solid #2A2D36;
    border-radius: 12px;
    margin-top: 24px;
    padding: 15px;
}
QGroupBox::title {
    subcontrol-origin: margin;
    subcontrol-position: top left;
    left: 15px;
    top: -5px;
    padding: 0 5px;
    color: #FFFFFF;
    font-weight: bold;
    font-size: 14px;
    letter-spacing: 1px;
}
QSpinBox { 
    background-color: #16161e; 
    border: 1px solid #414868; 
    border-radius: 6px; 
    padding: 4px; 
    color: #FFFFFF; 
    font-weight: bold;
}
QLineEdit {
    background-color: #1A1C23;
    border: 1px solid #2A2D36;
    border-radius: 6px;
    padding: 6px 10px;
    color: #FFFFFF;
}
QLineEdit:focus {
    border: 1px solid #0AC8B9;
}
QTextEdit {
    background-color: #14161C;
    border: 1px solid #282A33;
    border-radius: 8px;
    color: #A0E0D0;
    font-family: 'Consolas', monospace;
    font-size: 12px;
    padding: 10px;
}
QComboBox {
    background-color: #1A1C23;
    border: 1px solid #2A2D36;
    border-radius: 6px;
    padding: 5px 10px;
    color: #FFFFFF;
}
QComboBox:hover {
    border: 1px solid #3A3D46;
}
QComboBox::drop-down {
    border: none;
    width: 20px;
}
QPushButton {
    background-color: #2A2D36;
    border: 1px solid #3A3D46;
    border-radius: 6px;
    padding: 8px 14px;
    color: #FFFFFF;
}
QPushButton:hover {
    background-color: #3A3D46;
}
QPushButton:checked {
    background-color: #0AC8B9;
    border: 1px solid #0AC8B9;
    color: #17181D;
    font-weight: bold;
}
#startQueueBtn {
    background-color: #26B47C;
    border: none;
    color: white;
    font-weight: bold;
    padding: 12px;
    border-radius: 8px;
    font-size: 14px;
}
#startQueueBtn:hover {
    background-color: #2ECB8E;
}
#stopQueueBtn {
    background-color: #2A2D36;
    border: none;
    color: #8A9AAB;
    font-weight: bold;
    padding: 12px;
    border-radius: 8px;
    font-size: 14px;
}
#stopQueueBtn:hover {
    background-color: #3A3D46;
}
QSlider::groove:horizontal {
    border: none;
    height: 6px;
    background: #1A1C23;
    border-radius: 3px;
}
QSlider::handle:horizontal {
    background: #0AC8B9;
    border: none;
    width: 14px;
    height: 14px;
    margin: -4px 0;
    border-radius: 7px;
}
QSlider::sub-page:horizontal {
    background: #0AC8B9;
    border-radius: 3px;
}
QLabel {
    color: #A0B0C0;
}
#highlightText {
    color: #0AC8B9;
    font-weight: bold;
}
#readyText {
    color: #26B47C;
    font-weight: bold;
}
QScrollBar:vertical {
    background: #14161C;
    width: 8px;
    margin: 0px 0px 0px 0px;
    border-radius: 4px;
}
QScrollBar::handle:vertical {
    background: #2A2D36;
    min-height: 20px;
    border-radius: 4px;
}
QScrollBar::handle:vertical:hover {
    background: #3A3D46;
}
QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical {
    height: 0px;
}
QScrollBar::add-page:vertical, QScrollBar::sub-page:vertical {
    background: none;
}
QScrollBar:horizontal {
    background: #14161C;
    height: 8px;
    margin: 0px 0px 0px 0px;
    border-radius: 4px;
}
QScrollBar::handle:horizontal {
    background: #2A2D36;
    min-width: 20px;
    border-radius: 4px;
}
QScrollBar::handle:horizontal:hover {
    background: #3A3D46;
}
QScrollBar::add-line:horizontal, QScrollBar::sub-line:horizontal {
    width: 0px;
}
QScrollBar::add-page:horizontal, QScrollBar::sub-page:horizontal {
    background: none;
}
#createLobbyBtn {
    background-color: #0AC8B9;
    border: 1px solid #0AC8B9;
    color: #0F1218;
    font-weight: bold;
    padding: 8px 14px;
    border-radius: 6px;
    font-size: 13px;
}
#createLobbyBtn:hover {
    background-color: #12E6D5;
    border: 1px solid #12E6D5;
}
#testSoundBtn {
    background-color: #1F2533;
    border: 1px solid #2D374D;
    color: #00D4FF;
    font-weight: bold;
    padding: 6px 14px;
    border-radius: 6px;
}
#testSoundBtn:hover {
    background-color: #283247;
    border-color: #00D4FF;
}
#presetBtn {
    background-color: #181B22;
    border: 1px solid #252A36;
    color: #8A9AAB;
    padding: 3px 8px;
    border-radius: 10px;
    font-size: 11px;
}
#presetBtn:hover {
    background-color: #222631;
    color: #0AC8B9;
    border-color: #0AC8B9;
}
#laneBtn {
    background-color: #181B22;
    border: 1px solid #282C38;
    color: #8A9AAB;
    font-weight: bold;
    font-size: 12px;
    border-radius: 8px;
    padding: 8px 10px;
}
#laneBtn:hover {
    background-color: #222631;
    color: #FFFFFF;
    border-color: #3C4254;
}
#laneBtn[roleState="primary"] {
    background-color: #0AC8B9;
    border: 1px solid #0AC8B9;
    color: #0F1218;
}
#laneBtn[roleState="secondary"] {
    background-color: #7952B3;
    border: 1px solid #9A6EE2;
    color: #FFFFFF;
}
#repeatBtn {
    background-color: #1A1C23;
    border: 1px solid #2A2D36;
    border-radius: 6px;
    padding: 5px;
    color: #8A9AAB;
    font-weight: bold;
}
#repeatBtn:hover {
    color: #FFFFFF;
    border-color: #3A3D46;
}
#repeatBtn:checked {
    background-color: #0AC8B9;
    color: #17181D;
    border-color: #0AC8B9;
}
#dodgeBtn {
    background-color: #381A22;
    border: 1px solid #6E2231;
    color: #FF5E7E;
    font-weight: bold;
    padding: 6px 10px;
    border-radius: 6px;
    font-size: 11px;
}
#dodgeBtn:hover {
    background-color: #4D212E;
    border-color: #FF5E7E;
}
#opggBtn {
    background-color: #1A2638;
    border: 1px solid #23456E;
    color: #5383E8;
    font-weight: bold;
    padding: 6px 10px;
    border-radius: 6px;
    font-size: 11px;
}
#opggBtn:hover {
    background-color: #21334D;
    border-color: #5383E8;
}
"""
