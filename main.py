import sys
import ctypes
from typing import List

from PyQt5.QtCore import Qt
from PyQt5.QtGui import QFont
from PyQt5.QtWidgets import (
    QApplication,
    QGridLayout,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QVBoxLayout,
    QWidget,
)
from pynput.keyboard import Controller, Key


def get_foreground_window_handle() -> int:
    """Return current foreground window handle on Windows."""
    try:
        return ctypes.windll.user32.GetForegroundWindow()
    except Exception:
        return 0


def set_foreground_window_handle(hwnd: int) -> None:
    """Bring target window back to foreground on Windows."""
    if not hwnd:
        return
    try:
        ctypes.windll.user32.SetForegroundWindow(hwnd)
    except Exception:
        return


def apply_no_activate_style(hwnd: int) -> None:
    """Apply WS_EX_NOACTIVATE so clicking the window never steals focus."""
    GWL_EXSTYLE = -20
    WS_EX_NOACTIVATE = 0x08000000
    WS_EX_TOOLWINDOW = 0x00000080
    try:
        style = ctypes.windll.user32.GetWindowLongW(hwnd, GWL_EXSTYLE)
        ctypes.windll.user32.SetWindowLongW(
            hwnd, GWL_EXSTYLE, style | WS_EX_NOACTIVATE | WS_EX_TOOLWINDOW
        )
    except Exception:
        pass


class FloatingButtonWindow(QWidget):
    """Small always-on-top launcher button shown on the right side of the screen."""

    def __init__(self, on_open_keyboard):
        super().__init__()
        self.on_open_keyboard = on_open_keyboard
        self.setup_ui()
        self.position_on_right_center()

    def setup_ui(self) -> None:
        self.setWindowTitle("Keyboard Launcher")
        self.setFixedSize(60, 60)
        self.setWindowFlags(
            Qt.FramelessWindowHint
            | Qt.WindowStaysOnTopHint
            | Qt.Tool
            | Qt.WindowDoesNotAcceptFocus
        )
        self.setAttribute(Qt.WA_TranslucentBackground, True)
        self.setAttribute(Qt.WA_ShowWithoutActivating, True)

        layout = QVBoxLayout()
        layout.setContentsMargins(0, 0, 0, 0)

        self.launch_button = QPushButton("⌨")
        self.launch_button.setCursor(Qt.PointingHandCursor)
        self.launch_button.setFixedSize(60, 60)
        self.launch_button.setObjectName("launcherButton")
        self.launch_button.clicked.connect(self.on_open_keyboard)

        layout.addWidget(self.launch_button)
        self.setLayout(layout)

    def position_on_right_center(self) -> None:
        screen = QApplication.primaryScreen().availableGeometry()
        x = screen.right() - self.width() - 12
        y = screen.y() + (screen.height() - self.height()) // 2
        self.move(x, y)

    def showEvent(self, event) -> None:
        super().showEvent(event)
        apply_no_activate_style(int(self.winId()))


class VirtualKeyboardWindow(QWidget):
    """Full virtual keyboard window with dark, minimal styling."""

    def __init__(self, on_hide_keyboard, on_exit_app):
        super().__init__()
        self.on_hide_keyboard = on_hide_keyboard
        self.on_exit_app = on_exit_app
        self.keyboard = Controller()
        self._last_target_hwnd: int = 0
        self.setup_ui()

    def showEvent(self, event) -> None:
        super().showEvent(event)
        apply_no_activate_style(int(self.winId()))
        self._position_at_bottom()

    def _position_at_bottom(self) -> None:
        screen = QApplication.primaryScreen().availableGeometry()
        x = screen.x() + (screen.width() - self.width()) // 2
        y = screen.bottom() - self.height() - 8
        self.move(x, y)

    def setup_ui(self) -> None:
        self.setWindowTitle("System Keyboard")
        self.setMinimumSize(920, 400)
        self.setWindowFlags(
            Qt.Window
            | Qt.WindowStaysOnTopHint
            | Qt.CustomizeWindowHint
            | Qt.WindowTitleHint
            | Qt.WindowDoesNotAcceptFocus
        )
        self.setAttribute(Qt.WA_ShowWithoutActivating, True)

        root = QVBoxLayout()
        root.setContentsMargins(16, 16, 16, 16)
        root.setSpacing(12)

        top_bar = QHBoxLayout()
        title = QLabel("System Keyboard")
        title.setObjectName("title")

        hide_button = QPushButton("Hide")
        hide_button.setObjectName("secondaryButton")
        hide_button.setFixedHeight(34)
        hide_button.clicked.connect(self.on_hide_keyboard)

        exit_button = QPushButton("✕ Exit")
        exit_button.setObjectName("exitButton")
        exit_button.setFixedHeight(34)
        exit_button.clicked.connect(self.on_exit_app)

        top_bar.addWidget(title)
        top_bar.addStretch()
        top_bar.addWidget(hide_button)
        top_bar.addWidget(exit_button)

        keyboard_grid = QGridLayout()
        keyboard_grid.setHorizontalSpacing(8)
        keyboard_grid.setVerticalSpacing(8)

        row_1 = list("1234567890")
        row_2 = list("QWERTYUIOP")
        row_3 = list("ASDFGHJKL")
        row_4 = list("ZXCVBNM")

        self.add_character_row(keyboard_grid, row_1, 0, 0)
        self.add_character_row(keyboard_grid, row_2, 1, 0)
        self.add_character_row(keyboard_grid, row_3, 2, 1)
        self.add_character_row(keyboard_grid, row_4, 3, 2)

        backspace_btn = self.create_key_button("⌫ Backspace", "specialKey")
        backspace_btn.clicked.connect(lambda: self.press_special_key("backspace"))
        keyboard_grid.addWidget(backspace_btn, 0, len(row_1), 1, 2)

        enter_btn = self.create_key_button("↵ Enter", "specialKey")
        enter_btn.clicked.connect(lambda: self.press_special_key("enter"))
        keyboard_grid.addWidget(enter_btn, 2, len(row_3), 1, 2)

        # Bottom row: Win | Space | Win
        win_left_btn = self.create_key_button("⊞ Win", "specialKey")
        win_left_btn.clicked.connect(lambda: self.press_special_key("win"))
        keyboard_grid.addWidget(win_left_btn, 4, 0, 1, 2)

        space_btn = self.create_key_button("Space", "spaceKey")
        space_btn.clicked.connect(lambda: self.press_special_key("space"))
        keyboard_grid.addWidget(space_btn, 4, 2, 1, 7)

        win_right_btn = self.create_key_button("⊞ Win", "specialKey")
        win_right_btn.clicked.connect(lambda: self.press_special_key("win"))
        keyboard_grid.addWidget(win_right_btn, 4, 9, 1, 2)

        copyright_label = QLabel("© 2026 TBKK (Thailand) Company Limited. All rights reserved.")
        copyright_label.setObjectName("copyrightLabel")
        copyright_label.setAlignment(Qt.AlignCenter)

        root.addLayout(top_bar)
        root.addLayout(keyboard_grid)
        root.addWidget(copyright_label)
        self.setLayout(root)

    def add_character_row(self, grid: QGridLayout, keys: List[str], row: int, start_column: int) -> None:
        for column, char in enumerate(keys):
            key_button = self.create_key_button(char, "keyButton")
            key_button.clicked.connect(lambda _checked=False, c=char: self.type_character(c))
            grid.addWidget(key_button, row, start_column + column)

    def create_key_button(self, text: str, object_name: str) -> QPushButton:
        button = QPushButton(text)
        button.setObjectName(object_name)
        button.setCursor(Qt.PointingHandCursor)
        button.setMinimumHeight(52)
        button.setFont(QFont("Segoe UI", 10))
        return button

    def type_character(self, character: str) -> None:
        self._ensure_target_focus()
        if character.isalpha():
            self.keyboard.press(character.lower())
            self.keyboard.release(character.lower())
        else:
            self.keyboard.press(character)
            self.keyboard.release(character)

    def press_special_key(self, key_name: str) -> None:
        self._ensure_target_focus()
        key_map = {
            "enter": Key.enter,
            "backspace": Key.backspace,
            "space": Key.space,
            "win": Key.cmd,
        }
        key = key_map.get(key_name)
        if key:
            self.keyboard.press(key)
            self.keyboard.release(key)

    def _ensure_target_focus(self) -> None:
        """Restore focus to the last known non-keyboard target window."""
        our_hwnd = int(self.winId())
        current = get_foreground_window_handle()
        # Update our target only when the foreground is a real external window
        if current and current != our_hwnd:
            self._last_target_hwnd = current
        if self._last_target_hwnd:
            set_foreground_window_handle(self._last_target_hwnd)


class KeyboardAppController:
    """Connects the floating launcher and full keyboard window."""

    def __init__(self):
        self.floating_button_window = FloatingButtonWindow(self.show_keyboard)
        self.keyboard_window = VirtualKeyboardWindow(
            self.hide_keyboard,
            self.exit_app,
        )
        self.apply_stylesheet()

    def apply_stylesheet(self) -> None:
        stylesheet = """
            QWidget {
                background-color: #121212;
                color: #EAEAEA;
                font-family: "Segoe UI";
            }

            QLabel#title {
                font-size: 20px;
                font-weight: 600;
                color: #FFFFFF;
            }

            QPushButton {
                border: none;
                border-radius: 10px;
            }

            QPushButton#launcherButton {
                background-color: #1565C0;
                color: #FFFFFF;
                font-size: 28px;
                border: 1px solid #1976D2;
            }

            QPushButton#launcherButton:hover {
                background-color: #1976D2;
            }

            QPushButton#keyButton,
            QPushButton#specialKey,
            QPushButton#spaceKey,
            QPushButton#secondaryButton {
                background-color: #222222;
                color: #F7F7F7;
                border: 1px solid #303030;
                padding: 8px 12px;
                font-size: 15px;
                font-weight: 500;
            }

            QPushButton#keyButton:hover,
            QPushButton#specialKey:hover,
            QPushButton#spaceKey:hover,
            QPushButton#secondaryButton:hover {
                background-color: #2E2E2E;
            }

            QPushButton#keyButton:pressed,
            QPushButton#specialKey:pressed,
            QPushButton#spaceKey:pressed,
            QPushButton#secondaryButton:pressed {
                background-color: #3A3A3A;
            }

            QPushButton#specialKey {
                min-width: 100px;
            }

            QPushButton#spaceKey {
                min-width: 300px;
            }

            QPushButton#exitButton {
                background-color: #3B1010;
                color: #FF6B6B;
                border: 1px solid #5C1A1A;
                border-radius: 8px;
                padding: 4px 14px;
                font-size: 13px;
                font-weight: 600;
            }

            QPushButton#exitButton:hover {
                background-color: #5C1A1A;
            }

            QPushButton#exitButton:pressed {
                background-color: #7A2222;
            }

            QLabel#copyrightLabel {
                color: #555555;
                font-size: 11px;
                padding-top: 4px;
            }
        """
        self.floating_button_window.setStyleSheet(stylesheet)
        self.keyboard_window.setStyleSheet(stylesheet)

    def exit_app(self) -> None:
        QApplication.quit()

    def show_keyboard(self) -> None:
        # Snapshot current foreground window before we show our keyboard
        self.keyboard_window._last_target_hwnd = get_foreground_window_handle()
        self.keyboard_window.show()
        self.keyboard_window.raise_()
        self.floating_button_window.hide()

    def hide_keyboard(self) -> None:
        self.keyboard_window.hide()
        self.floating_button_window.show()
        self.floating_button_window.raise_()

    def run(self) -> None:
        self.floating_button_window.show()


def main() -> None:
    if hasattr(Qt, "AA_EnableHighDpiScaling"):
        QApplication.setAttribute(Qt.AA_EnableHighDpiScaling, True)
    if hasattr(Qt, "AA_UseHighDpiPixmaps"):
        QApplication.setAttribute(Qt.AA_UseHighDpiPixmaps, True)

    app = QApplication(sys.argv)
    app.setQuitOnLastWindowClosed(False)

    controller = KeyboardAppController()
    controller.run()

    sys.exit(app.exec_())


if __name__ == "__main__":
    main()
