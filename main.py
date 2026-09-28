import ctypes
from ctypes import wintypes
import json
import os
import shutil
import subprocess
import sys
import uuid
from typing import Dict, List, Optional

from PyQt5.QtCore import QCoreApplication, QObject, QStandardPaths, Qt, QTimer, pyqtSignal
from PyQt5.QtGui import QFont
from PyQt5.QtWidgets import (
    QApplication,
    QButtonGroup,
    QComboBox,
    QDialog,
    QFileDialog,
    QFormLayout,
    QGridLayout,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QMessageBox,
    QPushButton,
    QMenu,
    QSizePolicy,
    QVBoxLayout,
    QWidget,
)
from pynput.keyboard import Controller, Key


WINDOWS_TOOLS = {
    "device_manager": {"label": "Device Manager", "target": "devmgmt.msc"},
    "control_panel": {"label": "Control Panel", "target": "control.exe"},
    "uninstall_programs": {
        "label": "Programs and Features / Uninstall Programs",
        "target": "appwiz.cpl",
    },
    "power_options": {"label": "Power Options", "target": "powercfg.cpl"},
    "edit_power_plan": {
        "label": "Edit Power Plan",
        "program": "control.exe",
        "arguments": ["/name", "Microsoft.PowerOptions", "/page", "pagePlanSettings"],
        "fallback": "powercfg.cpl",
    },
    "network_connections": {"label": "Network Connections", "target": "ncpa.cpl"},
    "system_properties": {"label": "System Properties", "target": "sysdm.cpl"},
    "computer_management": {"label": "Computer Management", "target": "compmgmt.msc"},
    "services": {"label": "Services", "target": "services.msc"},
    "event_viewer": {"label": "Event Viewer", "target": "eventvwr.msc"},
    "disk_management": {"label": "Disk Management", "target": "diskmgmt.msc"},
    "task_manager": {"label": "Task Manager", "target": "taskmgr.exe"},
    "windows_features": {"label": "Windows Features", "target": "optionalfeatures.exe"},
    "internet_options": {"label": "Internet Options", "target": "inetcpl.cpl"},
    "sound": {"label": "Sound", "target": "mmsys.cpl"},
    "date_and_time": {"label": "Date and Time", "target": "timedate.cpl"},
    "mouse_properties": {"label": "Mouse Properties", "target": "main.cpl"},
    "windows_update": {"label": "Windows Update", "target": "ms-settings:windowsupdate"},
    "installed_apps": {"label": "Installed Apps", "target": "ms-settings:appsfeatures"},
    "startup_apps": {"label": "Startup Apps", "target": "ms-settings:startupapps"},
    "optional_features": {"label": "Optional Features", "target": "ms-settings:optionalfeatures"},
    "storage": {"label": "Storage", "target": "ms-settings:storagesense"},
    "display": {"label": "Display", "target": "ms-settings:display"},
    "sound_settings": {"label": "Sound Settings", "target": "ms-settings:sound"},
    "bluetooth_devices": {"label": "Bluetooth & Devices", "target": "ms-settings:bluetooth"},
    "printers_scanners": {"label": "Printers & Scanners", "target": "ms-settings:printers"},
    "network_internet": {"label": "Network & Internet", "target": "ms-settings:network"},
    "about": {"label": "About / System Information", "target": "ms-settings:about"},
}
LEGACY_WINDOWS_TOOL_IDS = {
    str(tool["target"]): tool_id
    for tool_id, tool in WINDOWS_TOOLS.items()
    if "target" in tool
}
MASTER_CONFIG_RELEASE = "1.0.1"


class ForegroundRecoveryBridge(QObject):
    """Deliver native foreground notifications to the Qt main thread."""

    recovery_requested = pyqtSignal()


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


def reassert_topmost_no_activate(hwnd: int) -> None:
    """Put a visible utility window back in the TOPMOST band without activation."""
    if not hwnd:
        return
    HWND_TOPMOST = -1
    SWP_NOSIZE = 0x0001
    SWP_NOMOVE = 0x0002
    SWP_NOACTIVATE = 0x0010
    try:
        ctypes.windll.user32.SetWindowPos(
            ctypes.c_void_p(hwnd),
            ctypes.c_void_p(HWND_TOPMOST),
            0,
            0,
            0,
            0,
            SWP_NOSIZE | SWP_NOMOVE | SWP_NOACTIVATE,
        )
    except Exception:
        pass


def apply_floating_window_styles(hwnd: int) -> None:
    """Apply native no-activate and TOPMOST behavior for floating utility windows."""
    apply_no_activate_style(hwnd)
    reassert_topmost_no_activate(hwnd)


def force_window_to_front(widget: QWidget) -> None:
    """Raise a focusable child dialog above this application's utility windows."""
    try:
        hwnd = int(widget.winId())
        HWND_TOPMOST = -1
        SWP_NOSIZE = 0x0001
        SWP_NOMOVE = 0x0002
        SWP_SHOWWINDOW = 0x0040
        ctypes.windll.user32.SetWindowPos(
            ctypes.c_void_p(hwnd),
            ctypes.c_void_p(HWND_TOPMOST),
            0,
            0,
            0,
            0,
            SWP_NOMOVE | SWP_NOSIZE | SWP_SHOWWINDOW,
        )
    except Exception:
        pass
    widget.raise_()
    widget.activateWindow()


def prepare_modal_dialog(dialog: QDialog, parent: Optional[QWidget] = None) -> QDialog:
    """Give a child dialog ownership, modality, and the shared topmost treatment."""
    if parent is not None and dialog.parentWidget() is not parent:
        dialog.setParent(parent)
    dialog.setWindowFlag(Qt.Dialog, True)
    dialog.setWindowFlag(Qt.WindowStaysOnTopHint, True)
    dialog.setWindowModality(Qt.ApplicationModal)
    return dialog


def exec_dialog_on_top(dialog: QDialog, parent: Optional[QWidget] = None) -> int:
    """Execute a modal child after its native window has been made visible and topmost."""
    prepare_modal_dialog(dialog, parent)
    dialog.show()
    QTimer.singleShot(0, lambda: force_window_to_front(dialog))
    return dialog.exec_()


def show_modal_message(
    parent: QWidget,
    icon: QMessageBox.Icon,
    title: str,
    text: str,
    buttons: QMessageBox.StandardButtons = QMessageBox.Ok,
    default_button: QMessageBox.StandardButton = QMessageBox.NoButton,
) -> int:
    """Show a parented, modal message box above all KeyboardOfGOD utility windows."""
    message = QMessageBox(parent)
    message.setIcon(icon)
    message.setWindowTitle(title)
    message.setText(text)
    message.setStandardButtons(buttons)
    if default_button != QMessageBox.NoButton:
        message.setDefaultButton(default_button)
    return exec_dialog_on_top(message, parent)


def resource_path(relative_path: str) -> str:
    """Return a bundled PyInstaller resource path or the development-file path."""
    base_path = getattr(sys, "_MEIPASS", os.path.dirname(os.path.abspath(__file__)))
    return os.path.join(base_path, relative_path)


def launch_windows_tool(tool_id: str) -> None:
    """Launch one hardcoded Windows Tool preset without a command shell."""
    tool = WINDOWS_TOOLS[tool_id]
    target = tool.get("target")
    if target:
        os.startfile(str(target))
        return

    try:
        subprocess.Popen(
            [str(tool["program"]), *[str(argument) for argument in tool["arguments"]]],
            creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0),
        )
    except OSError:
        fallback = tool.get("fallback")
        if not fallback:
            raise
        os.startfile(str(fallback))


class QuickActionStore:
    """Small JSON store for per-user Quick Actions."""

    VALID_TYPES = {"input_code", "share_folder", "windows_tool"}

    def __init__(
        self,
        config_dir: Optional[str] = None,
        master_path: Optional[str] = None,
        master_release: str = MASTER_CONFIG_RELEASE,
    ) -> None:
        config_dir = config_dir or QStandardPaths.writableLocation(QStandardPaths.AppConfigLocation)
        self.path = os.path.join(config_dir, "quick_actions.json")
        self.master_path = master_path or resource_path(
            os.path.join("defaults", "quick_actions.default.json")
        )
        self.master_release = master_release
        self.master_marker_path = os.path.join(config_dir, "master_config.release")

    def load(self) -> List[Dict[str, object]]:
        self._deploy_master_config_if_needed()
        if not os.path.exists(self.path):
            return []
        try:
            with open(self.path, "r", encoding="utf-8") as config_file:
                document = json.load(config_file)
        except (OSError, json.JSONDecodeError) as error:
            print(f"Could not read Quick Actions configuration: {error}", file=sys.stderr)
            return []

        if not isinstance(document, dict) or not isinstance(document.get("actions"), list):
            print("Quick Actions configuration has an invalid structure.", file=sys.stderr)
            return []

        return self._clean_actions(document)

    def _clean_actions(self, document: Dict[str, object]) -> List[Dict[str, object]]:
        """Validate and normalize supported Quick Actions without changing credentials."""
        raw_actions = document.get("actions")
        if not isinstance(raw_actions, list):
            return []

        actions: List[Dict[str, object]] = []
        seen_ids = set()
        for action in raw_actions:
            if not isinstance(action, dict):
                continue
            action_id = action.get("id")
            action_type = action.get("type")
            name = action.get("name")
            if (
                not isinstance(action_id, str)
                or not action_id
                or action_id in seen_ids
                or action_type not in self.VALID_TYPES
                or not isinstance(name, str)
            ):
                continue
            if action_type == "input_code":
                # Legacy actions used value as the one input string. Keep it as a
                # username so users can complete the action by adding a password.
                username = action.get("username", action.get("value", ""))
                password = action.get("password", "")
                if not isinstance(username, str) or not isinstance(password, str):
                    continue
                clean_action: Dict[str, object] = {
                    "id": action_id,
                    "name": name,
                    "type": action_type,
                    "username": username,
                    "password": password,
                }
            elif action_type == "windows_tool":
                tool_id = action.get("tool_id")
                if not isinstance(tool_id, str) or tool_id not in WINDOWS_TOOLS:
                    # Migrate actions saved by the previous allowlist implementation.
                    legacy_value = action.get("value")
                    tool_id = LEGACY_WINDOWS_TOOL_IDS.get(legacy_value) if isinstance(legacy_value, str) else None
                if not tool_id:
                    continue
                clean_action = {
                    "id": action_id,
                    "name": name,
                    "type": action_type,
                    "tool_id": tool_id,
                }
            else:
                value = action.get("value")
                if not isinstance(value, str):
                    continue
                clean_action = {
                    "id": action_id,
                    "name": name,
                    "type": action_type,
                    "value": value,
                }
            actions.append(clean_action)
            seen_ids.add(action_id)
        return actions

    def _deploy_master_config_if_needed(self) -> None:
        """Apply this release's bundled master config once for each user profile."""
        try:
            with open(self.master_path, "r", encoding="utf-8") as master_file:
                master_document = json.load(master_file)
            if not isinstance(master_document, dict) or not isinstance(master_document.get("actions"), list):
                raise ValueError("Master Quick Actions configuration has an invalid structure.")
            if len(self._clean_actions(master_document)) != len(master_document["actions"]):
                raise ValueError("Master Quick Actions configuration contains unsupported actions.")

            try:
                with open(self.master_marker_path, "r", encoding="utf-8") as marker_file:
                    deployed_release = marker_file.read().strip()
            except FileNotFoundError:
                deployed_release = ""
            if deployed_release == self.master_release:
                return

            os.makedirs(os.path.dirname(self.path), exist_ok=True)
            temporary_config_path = f"{self.path}.{uuid.uuid4().hex}.tmp"
            with open(self.master_path, "rb") as source, open(temporary_config_path, "wb") as destination:
                shutil.copyfileobj(source, destination)
            os.replace(temporary_config_path, self.path)

            temporary_marker_path = f"{self.master_marker_path}.{uuid.uuid4().hex}.tmp"
            with open(temporary_marker_path, "w", encoding="utf-8") as marker_file:
                marker_file.write(self.master_release)
            os.replace(temporary_marker_path, self.master_marker_path)
        except (OSError, ValueError, json.JSONDecodeError) as error:
            print(f"Could not deploy master Quick Actions configuration: {error}", file=sys.stderr)

    def save(self, actions: List[Dict[str, object]]) -> None:
        os.makedirs(os.path.dirname(self.path), exist_ok=True)
        document = {"version": 1, "actions": actions}
        temporary_path = f"{self.path}.tmp"
        with open(temporary_path, "w", encoding="utf-8") as config_file:
            json.dump(document, config_file, ensure_ascii=False, indent=2)
        os.replace(temporary_path, self.path)


class FloatingButtonWindow(QWidget):
    """Small always-on-top launcher with Keyboard and Quick controls."""

    def __init__(self, on_open_keyboard, on_open_quick):
        super().__init__()
        self.on_open_keyboard = on_open_keyboard
        self.on_open_quick = on_open_quick
        self.setup_ui()
        self.position_on_right_center()

    def setup_ui(self) -> None:
        self.setWindowTitle("Keyboard Launcher")
        self.setFixedSize(60, 128)
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
        layout.setSpacing(8)

        self.launch_button = QPushButton("⌨")
        self.launch_button.setCursor(Qt.PointingHandCursor)
        self.launch_button.setFixedSize(60, 60)
        self.launch_button.setObjectName("launcherButton")
        self.launch_button.clicked.connect(self.on_open_keyboard)

        self.quick_button = QPushButton("⚡")
        self.quick_button.setCursor(Qt.PointingHandCursor)
        self.quick_button.setFixedSize(60, 60)
        self.quick_button.setObjectName("quickLauncherButton")
        self.quick_button.clicked.connect(self.on_open_quick)

        layout.addWidget(self.launch_button)
        layout.addWidget(self.quick_button)
        self.setLayout(layout)

    def position_on_right_center(self) -> None:
        screen = QApplication.primaryScreen().availableGeometry()
        x = screen.right() - self.width() - 12
        y = screen.y() + (screen.height() - self.height()) // 2
        self.move(x, y)

    def showEvent(self, event) -> None:
        super().showEvent(event)
        self.reassert_topmost()

    def reassert_topmost(self) -> None:
        apply_floating_window_styles(int(self.winId()))


class VirtualKeyboardWindow(QWidget):
    """Full virtual keyboard window with dark, minimal styling."""

    def __init__(self, on_hide_keyboard):
        super().__init__()
        self.on_hide_keyboard = on_hide_keyboard
        self.keyboard = Controller()
        self._last_target_hwnd: int = 0
        self.setup_ui()

    def showEvent(self, event) -> None:
        super().showEvent(event)
        self.reassert_topmost()
        self._position_at_bottom()

    def reassert_topmost(self) -> None:
        apply_floating_window_styles(int(self.winId()))

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

        top_bar.addWidget(title)
        top_bar.addStretch()
        top_bar.addWidget(hide_button)

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

    def send_login_sequence(self, username: str, password: str, target_hwnd: int) -> bool:
        """Send Username, Tab, Password, Enter to a frozen external target."""
        if not target_hwnd:
            return False
        set_foreground_window_handle(target_hwnd)
        try:
            self.keyboard.type(username)
            self.keyboard.press(Key.tab)
            self.keyboard.release(Key.tab)
            self.keyboard.type(password)
            self.keyboard.press(Key.enter)
            self.keyboard.release(Key.enter)
            return True
        except (ValueError, OSError) as error:
            print(f"Could not send Quick Action login sequence: {error}", file=sys.stderr)
            return False

    def _ensure_target_focus(self) -> None:
        """Restore focus to the last known non-keyboard target window."""
        our_hwnd = int(self.winId())
        current = get_foreground_window_handle()
        # Update our target only when the foreground is a real external window
        if current and current != our_hwnd:
            self._last_target_hwnd = current
        if self._last_target_hwnd:
            set_foreground_window_handle(self._last_target_hwnd)


class QuickActionCard(QWidget):
    """Uniform premium-style action card with a fixed internal grid."""

    QUICK_CARD_HEIGHT = 78
    QUICK_ICON_SIZE = 42
    QUICK_ACTION_BUTTON_SIZE = 32
    QUICK_TITLE_HEIGHT = 27
    QUICK_SUBTITLE_HEIGHT = 16
    QUICK_BADGE_WIDTH = 50

    TYPE_DETAILS = {
        "input_code": ("👤", "LOGIN", "Login to target", "quickActionIconLogin"),
        "share_folder": ("📁", "SHARE", "Share Folder", "quickActionIconShare"),
        "windows_tool": ("🛠", "TOOL", "Windows utility", "quickActionIconTool"),
    }

    def __init__(self, action, on_run_action, on_edit_action, on_delete_action):
        super().__init__()
        self.action = action
        self.on_run_action = on_run_action
        self.on_edit_action = on_edit_action
        self.on_delete_action = on_delete_action
        self.setObjectName("quickActionCard")
        self.setCursor(Qt.PointingHandCursor)
        self.setFixedHeight(self.QUICK_CARD_HEIGHT)
        self.setSizePolicy(QSizePolicy.Ignored, QSizePolicy.Fixed)
        self.setToolTip("Click to run. Use the arrow for Edit or Delete.")

        icon, badge, description, icon_style = self.TYPE_DETAILS.get(
            action.get("type"), ("•", "ACTION", "Quick Action", "quickActionIconTool")
        )
        layout = QHBoxLayout()
        layout.setContentsMargins(8, 7, 8, 7)
        layout.setSpacing(8)

        icon_label = QLabel(icon)
        icon_label.setObjectName(icon_style)
        icon_label.setFixedSize(self.QUICK_ICON_SIZE, self.QUICK_ICON_SIZE)
        icon_label.setAlignment(Qt.AlignCenter)
        icon_label.setAttribute(Qt.WA_TransparentForMouseEvents, True)

        content = QWidget()
        content.setAttribute(Qt.WA_TransparentForMouseEvents, True)
        content_layout = QVBoxLayout()
        content_layout.setContentsMargins(0, 0, 0, 0)
        content_layout.setSpacing(0)
        name_label = QLabel(str(action["name"]))
        name_label.setObjectName("quickActionName")
        name_label.setWordWrap(True)
        name_label.setFixedHeight(self.QUICK_TITLE_HEIGHT)
        name_label.setToolTip(str(action["name"]))
        name_label.setAttribute(Qt.WA_TransparentForMouseEvents, True)

        subtitle_label = QLabel(description)
        subtitle_label.setObjectName("quickActionDescription")
        subtitle_label.setFixedHeight(self.QUICK_SUBTITLE_HEIGHT)
        subtitle_label.setAttribute(Qt.WA_TransparentForMouseEvents, True)

        details_row = QHBoxLayout()
        details_row.setContentsMargins(0, 0, 0, 0)
        details_row.setSpacing(6)
        badge_label = QLabel(badge)
        badge_label.setObjectName("quickActionBadge")
        badge_label.setFixedSize(self.QUICK_BADGE_WIDTH, 18)
        badge_label.setAlignment(Qt.AlignCenter)
        badge_label.setAttribute(Qt.WA_TransparentForMouseEvents, True)
        detail_label = QLabel(description)
        detail_label.setObjectName("quickActionDetail")
        detail_label.setAttribute(Qt.WA_TransparentForMouseEvents, True)
        details_row.addWidget(badge_label)
        details_row.addWidget(detail_label, 1)
        content_layout.addWidget(name_label)
        content_layout.addWidget(subtitle_label)
        content_layout.addLayout(details_row)
        content.setLayout(content_layout)

        self.menu_button = QPushButton("⋮")
        self.menu_button.setObjectName("quickActionMenuButton")
        self.menu_button.setText("›")
        self.menu_button.setFixedSize(self.QUICK_ACTION_BUTTON_SIZE, self.QUICK_ACTION_BUTTON_SIZE)
        self.menu_button.setToolTip("Edit or Delete")
        self.menu_button.clicked.connect(self.show_action_menu)

        layout.addWidget(icon_label)
        layout.addWidget(content, 1)
        layout.addWidget(self.menu_button)
        self.setLayout(layout)

    def mouseReleaseEvent(self, event) -> None:
        if event.button() == Qt.LeftButton:
            self.on_run_action(self.action)
            event.accept()
            return
        super().mouseReleaseEvent(event)

    def show_action_menu(self) -> None:
        menu = QMenu(self)
        edit_action = menu.addAction("Edit")
        delete_action = menu.addAction("Delete")
        selected = menu.exec_(self.menu_button.mapToGlobal(self.menu_button.rect().bottomLeft()))
        if selected == edit_action:
            self.on_edit_action(self.action)
        elif selected == delete_action:
            self.on_delete_action(self.action)


class QuickActionWindow(QWidget):
    """No-activate runtime popup with filtered, paged Quick Actions."""

    ACTIONS_PER_PAGE = 8
    QUICK_WINDOW_SIZE = (560, 550)
    QUICK_CARD_HEIGHT = QuickActionCard.QUICK_CARD_HEIGHT
    QUICK_GRID_GAP = 8
    QUICK_OUTER_MARGIN = 10
    CATEGORY_TYPES = {
        "all": None,
        "login": "input_code",
        "share": "share_folder",
        "tools": "windows_tool",
    }

    def __init__(self, on_run_action, on_add_action, on_edit_action, on_delete_action, on_close):
        super().__init__()
        self.on_run_action = on_run_action
        self.on_add_action = on_add_action
        self.on_edit_action = on_edit_action
        self.on_delete_action = on_delete_action
        self.on_close = on_close
        self.actions: List[Dict[str, object]] = []
        self.current_category = "all"
        self.current_page = 0
        self.setup_ui()

    def setup_ui(self) -> None:
        self.setWindowTitle("Quick Actions")
        self.setObjectName("quickActionWindow")
        self.setFixedSize(*self.QUICK_WINDOW_SIZE)
        self.setWindowFlags(
            Qt.Window
            | Qt.WindowStaysOnTopHint
            | Qt.CustomizeWindowHint
            | Qt.WindowTitleHint
            | Qt.WindowDoesNotAcceptFocus
        )
        self.setAttribute(Qt.WA_ShowWithoutActivating, True)

        root = QVBoxLayout()
        root.setContentsMargins(
            self.QUICK_OUTER_MARGIN,
            self.QUICK_OUTER_MARGIN,
            self.QUICK_OUTER_MARGIN,
            self.QUICK_OUTER_MARGIN,
        )
        root.setSpacing(6)

        title_row = QHBoxLayout()
        title_row.setContentsMargins(2, 0, 2, 0)
        title_icon = QLabel("⚡")
        title_icon.setObjectName("quickActionTitleIcon")
        title = QLabel("Quick Actions")
        title.setObjectName("quickActionsTitle")
        title_row.addWidget(title_icon)
        title_row.addWidget(title)
        title_row.addStretch()

        search_row = QHBoxLayout()
        search_row.setSpacing(12)
        self.search_input = QLineEdit()
        self.search_input.setObjectName("quickActionSearch")
        self.search_input.setPlaceholderText("Search actions")
        self.search_input.setClearButtonEnabled(True)
        self.search_input.setFixedHeight(34)
        close_button = QPushButton("Hide")
        close_button.setObjectName("quickActionHideButton")
        close_button.setFixedSize(68, 34)
        close_button.clicked.connect(self.on_close)
        search_row.addWidget(self.search_input, 1)
        search_row.addWidget(close_button)

        filter_row = QHBoxLayout()
        filter_row.setSpacing(6)
        self.category_group = QButtonGroup(self)
        self.category_group.setExclusive(True)
        self.category_buttons = {}
        for category, label in (("all", "All"), ("login", "Login"), ("share", "Share"), ("tools", "Tools")):
            button = QPushButton(label)
            button.setObjectName("categoryFilterButton")
            button.setCheckable(True)
            button.setFixedHeight(28)
            button.clicked.connect(lambda _checked=False, value=category: self.set_category(value))
            self.category_group.addButton(button)
            self.category_buttons[category] = button
            filter_row.addWidget(button)
        self.category_buttons["all"].setChecked(True)
        filter_row.addStretch()

        self.action_grid_container = QWidget()
        self.action_grid_container.setObjectName("quickActionGrid")
        self.action_grid = QGridLayout()
        self.action_grid.setContentsMargins(0, 0, 0, 0)
        self.action_grid.setHorizontalSpacing(self.QUICK_GRID_GAP)
        self.action_grid.setVerticalSpacing(self.QUICK_GRID_GAP)
        self.action_grid.setColumnStretch(0, 1)
        self.action_grid.setColumnStretch(1, 1)
        for row in range(4):
            self.action_grid.setRowMinimumHeight(row, self.QUICK_CARD_HEIGHT)
        self.action_grid_container.setLayout(self.action_grid)
        self.action_grid_container.setFixedHeight(
            self.QUICK_CARD_HEIGHT * 4 + self.QUICK_GRID_GAP * 3
        )

        self.pagination_widget = QWidget()
        self.pagination_widget.setObjectName("quickActionPagination")
        pagination_row = QHBoxLayout()
        pagination_row.setContentsMargins(0, 0, 0, 0)
        pagination_row.setSpacing(8)
        self.previous_button = QPushButton("‹")
        self.previous_button.setObjectName("secondaryButton")
        self.previous_button.setFixedSize(28, 26)
        self.previous_button.clicked.connect(self.previous_page)
        self.page_indicator = QLabel()
        self.page_indicator.setAlignment(Qt.AlignCenter)
        self.next_button = QPushButton("›")
        self.next_button.setObjectName("secondaryButton")
        self.next_button.setFixedSize(28, 26)
        self.next_button.clicked.connect(self.next_page)
        pagination_row.addStretch()
        pagination_row.addWidget(self.previous_button)
        pagination_row.addWidget(self.page_indicator)
        pagination_row.addWidget(self.next_button)
        pagination_row.addStretch()
        self.pagination_widget.setLayout(pagination_row)

        add_button = QPushButton("+ Add Quick Action")
        add_button.setObjectName("quickActionAddButton")
        add_button.setFixedHeight(42)
        add_button.clicked.connect(self.on_add_action)

        root.addLayout(title_row)
        root.addLayout(search_row)
        root.addLayout(filter_row)
        root.addWidget(self.action_grid_container)
        root.addWidget(self.pagination_widget)
        root.addWidget(add_button)
        self.setLayout(root)
        self.search_input.textChanged.connect(self.reset_to_first_page)

    def set_actions(self, actions: List[Dict[str, object]]) -> None:
        self.actions = actions
        self.refresh_actions(reset_page=True)

    def filtered_actions(self) -> List[Dict[str, object]]:
        action_type = self.CATEGORY_TYPES[self.current_category]
        search_text = self.search_input.text().casefold().strip()
        return [
            action
            for action in self.actions
            if (action_type is None or action.get("type") == action_type)
            and (not search_text or search_text in str(action.get("name", "")).casefold())
        ]

    def refresh_actions(self, reset_page: bool = False) -> None:
        if reset_page:
            self.current_page = 0
        filtered_actions = self.filtered_actions()
        page_count = max(1, (len(filtered_actions) + self.ACTIONS_PER_PAGE - 1) // self.ACTIONS_PER_PAGE)
        self.current_page = min(self.current_page, page_count - 1)

        while self.action_grid.count():
            item = self.action_grid.takeAt(0)
            widget = item.widget()
            if widget:
                widget.deleteLater()

        if not filtered_actions:
            empty_label = QLabel("No matching Quick Actions. Use + Add Quick Action to create one.")
            empty_label.setObjectName("emptyLabel")
            empty_label.setWordWrap(True)
            empty_label.setAlignment(Qt.AlignCenter)
            self.action_grid.addWidget(empty_label, 0, 0, 1, 2)
        else:
            first_index = self.current_page * self.ACTIONS_PER_PAGE
            page_actions = filtered_actions[first_index:first_index + self.ACTIONS_PER_PAGE]
            for index, action in enumerate(page_actions):
                card = QuickActionCard(
                    action,
                    self.on_run_action,
                    self.on_edit_action,
                    self.on_delete_action,
                )
                self.action_grid.addWidget(card, index // 2, index % 2)
            # Keep both columns and all four rows geometrically stable on partial pages.
            for index in range(len(page_actions), self.ACTIONS_PER_PAGE):
                placeholder = QWidget()
                placeholder.setObjectName("quickActionPlaceholder")
                placeholder.setFixedHeight(self.QUICK_CARD_HEIGHT)
                placeholder.setSizePolicy(QSizePolicy.Ignored, QSizePolicy.Fixed)
                self.action_grid.addWidget(placeholder, index // 2, index % 2)

        self.previous_button.setEnabled(self.current_page > 0)
        self.next_button.setEnabled(self.current_page < page_count - 1)
        self.page_indicator.setText(f"{self.current_page + 1} / {page_count}")
        self.pagination_widget.setVisible(page_count > 1)

    def reset_to_first_page(self) -> None:
        self.refresh_actions(reset_page=True)

    def set_category(self, category: str) -> None:
        self.current_category = category
        self.refresh_actions(reset_page=True)

    def previous_page(self) -> None:
        if self.current_page:
            self.current_page -= 1
            self.refresh_actions()

    def next_page(self) -> None:
        filtered_actions = self.filtered_actions()
        if (self.current_page + 1) * self.ACTIONS_PER_PAGE < len(filtered_actions):
            self.current_page += 1
            self.refresh_actions()

    def showEvent(self, event) -> None:
        super().showEvent(event)
        self.position_near_launcher()
        self.reassert_topmost()

    def position_near_launcher(self) -> None:
        screen = QApplication.primaryScreen().availableGeometry()
        x = screen.right() - self.width() - 84
        y = screen.y() + (screen.height() - self.height()) // 2
        self.move(x, y)

    def reassert_topmost(self) -> None:
        apply_floating_window_styles(int(self.winId()))

    def closeEvent(self, event) -> None:
        event.ignore()
        self.on_close()


class QuickActionEditDialog(QDialog):
    """Focusable configuration dialog for creating or editing one Quick Action."""

    def __init__(self, action: Optional[Dict[str, object]] = None, parent=None):
        super().__init__(parent)
        self.original_action = action
        self.saved_action: Optional[Dict[str, object]] = None
        self.setup_ui()
        if action:
            self.populate(action)

    def setup_ui(self) -> None:
        self.setWindowTitle("Edit Quick Action" if self.original_action else "Add Quick Action")
        self.setMinimumWidth(420)

        root = QVBoxLayout()
        form = QFormLayout()
        form.setSpacing(10)

        self.name_input = QLineEdit()
        self.name_input.setPlaceholderText("e.g. FA Login")
        self.type_combo = QComboBox()
        self.type_combo.addItem("Input Code", "input_code")
        self.type_combo.addItem("Share Folder", "share_folder")
        self.type_combo.addItem("Windows Tool", "windows_tool")
        self.username_input = QLineEdit()
        self.password_input = QLineEdit()
        self.password_input.setEchoMode(QLineEdit.Password)
        self.folder_input = QLineEdit()
        self.windows_tool_combo = QComboBox()
        for tool_id, tool in WINDOWS_TOOLS.items():
            self.windows_tool_combo.addItem(str(tool["label"]), tool_id)

        self.folder_row = QWidget()
        folder_layout = QHBoxLayout()
        folder_layout.setContentsMargins(0, 0, 0, 0)
        self.browse_button = QPushButton("Browse")
        self.browse_button.clicked.connect(self.browse_folder)
        folder_layout.addWidget(self.folder_input, 1)
        folder_layout.addWidget(self.browse_button)
        self.folder_row.setLayout(folder_layout)

        form.addRow("Quick Action Name", self.name_input)
        form.addRow("Action Type", self.type_combo)
        self.username_label = QLabel("Username")
        self.password_label = QLabel("Password")
        self.folder_label = QLabel("Folder Path")
        self.windows_tool_label = QLabel("Windows Tool")
        form.addRow(self.username_label, self.username_input)
        form.addRow(self.password_label, self.password_input)
        form.addRow(self.folder_label, self.folder_row)
        form.addRow(self.windows_tool_label, self.windows_tool_combo)

        button_row = QHBoxLayout()
        button_row.addStretch()
        cancel_button = QPushButton("Cancel")
        cancel_button.setObjectName("secondaryButton")
        cancel_button.clicked.connect(self.reject)
        save_button = QPushButton("Save")
        save_button.setObjectName("primaryButton")
        save_button.clicked.connect(self.save_action)
        button_row.addWidget(cancel_button)
        button_row.addWidget(save_button)

        root.addLayout(form)
        root.addLayout(button_row)
        self.setLayout(root)
        self.type_combo.currentIndexChanged.connect(self.update_type_fields)
        self.windows_tool_combo.currentIndexChanged.connect(self.suggest_windows_tool_name)
        self.update_type_fields()

    def populate(self, action: Dict[str, object]) -> None:
        self.name_input.setText(str(action.get("name", "")))
        action_type = str(action.get("type", "input_code"))
        index = self.type_combo.findData(action_type)
        self.type_combo.setCurrentIndex(max(index, 0))
        self.username_input.setText(str(action.get("username", action.get("value", ""))))
        self.password_input.setText(str(action.get("password", "")))
        self.folder_input.setText(str(action.get("value", "")))
        tool_id = action.get("tool_id")
        if not isinstance(tool_id, str):
            legacy_value = action.get("value")
            tool_id = LEGACY_WINDOWS_TOOL_IDS.get(legacy_value) if isinstance(legacy_value, str) else None
        tool_index = self.windows_tool_combo.findData(tool_id)
        if tool_index >= 0:
            self.windows_tool_combo.setCurrentIndex(tool_index)
        self.update_type_fields()

    def update_type_fields(self) -> None:
        action_type = self.type_combo.currentData()
        is_input_code = action_type == "input_code"
        is_share_folder = action_type == "share_folder"
        is_windows_tool = action_type == "windows_tool"
        self.username_label.setVisible(is_input_code)
        self.username_input.setVisible(is_input_code)
        self.password_label.setVisible(is_input_code)
        self.password_input.setVisible(is_input_code)
        self.folder_label.setVisible(is_share_folder)
        self.folder_row.setVisible(is_share_folder)
        self.browse_button.setVisible(is_share_folder)
        self.windows_tool_label.setVisible(is_windows_tool)
        self.windows_tool_combo.setVisible(is_windows_tool)

    def suggest_windows_tool_name(self) -> None:
        """Offer the selected tool's friendly name for new, unnamed actions."""
        if self.original_action or self.type_combo.currentData() != "windows_tool":
            return
        if not self.name_input.text().strip():
            self.name_input.setText(self.windows_tool_combo.currentText())

    def browse_folder(self) -> None:
        dialog = QFileDialog(self, "Select Share Folder", self.folder_input.text())
        dialog.setFileMode(QFileDialog.Directory)
        dialog.setOption(QFileDialog.ShowDirsOnly, True)
        if exec_dialog_on_top(dialog, self) == QDialog.Accepted:
            selected_folders = dialog.selectedFiles()
            if selected_folders:
                self.folder_input.setText(selected_folders[0])

    def save_action(self) -> None:
        name = self.name_input.text().strip()
        action_type = self.type_combo.currentData()
        action_id = str(self.original_action["id"]) if self.original_action else str(uuid.uuid4())
        if action_type == "input_code":
            username = self.username_input.text()
            password = self.password_input.text()
            if not name or not username or not password:
                show_modal_message(
                    self,
                    QMessageBox.Warning,
                    "Quick Action",
                    "Input Code actions require a name, username, and password.",
                )
                return
            self.saved_action = {
                "id": action_id,
                "name": name,
                "type": action_type,
                "username": username,
                "password": password,
            }
        elif action_type == "share_folder":
            value = self.folder_input.text().strip()
            if not name or not value:
                show_modal_message(
                    self,
                    QMessageBox.Warning,
                    "Quick Action",
                    "Share Folder actions require a name and folder path.",
                )
                return
            self.saved_action = {
                "id": action_id,
                "name": name,
                "type": action_type,
                "value": value,
            }
        else:
            tool_id = self.windows_tool_combo.currentData()
            if not name or tool_id not in WINDOWS_TOOLS:
                show_modal_message(
                    self,
                    QMessageBox.Warning,
                    "Quick Action",
                    "Please select a predefined Windows tool.",
                )
                return
            self.saved_action = {
                "id": action_id,
                "name": name,
                "type": action_type,
                "tool_id": tool_id,
            }
        self.accept()


class KeyboardAppController:
    """Connects the floating launcher and full keyboard window."""

    def __init__(self):
        self._win_event_callback = None
        self._win_event_hook = None
        self.quick_target_hwnd: int = 0
        self.action_store = QuickActionStore()
        self.actions = self.action_store.load()
        self.floating_button_window = FloatingButtonWindow(self.show_keyboard, self.show_quick_actions)
        self.keyboard_window = VirtualKeyboardWindow(self.hide_keyboard)
        self.quick_action_window = QuickActionWindow(
            self.run_quick_action,
            self.add_quick_action,
            self.edit_quick_action,
            self.delete_quick_action,
            self.hide_quick_actions,
        )
        self.quick_action_window.set_actions(self.actions)
        self.apply_stylesheet()

        self._foreground_recovery_bridge = ForegroundRecoveryBridge()
        self._foreground_recovery_bridge.recovery_requested.connect(
            self._queue_foreground_topmost_refresh, Qt.QueuedConnection
        )
        self._foreground_recovery_timer = QTimer()
        self._foreground_recovery_timer.setSingleShot(True)
        self._foreground_recovery_timer.setInterval(75)
        self._foreground_recovery_timer.timeout.connect(self.refresh_visible_topmost)

        # This remains a low-frequency fallback for shell changes that do not emit a WinEvent.
        self.topmost_refresh_timer = QTimer()
        self.topmost_refresh_timer.setInterval(30000)
        self.topmost_refresh_timer.timeout.connect(self.refresh_visible_topmost)
        self.topmost_refresh_timer.start()

        self._install_foreground_event_hook()
        QApplication.instance().aboutToQuit.connect(self.cleanup)

    def _install_foreground_event_hook(self) -> None:
        """Register one out-of-context foreground hook for Z-order recovery."""
        if sys.platform != "win32" or self._win_event_hook:
            return

        EVENT_SYSTEM_FOREGROUND = 0x0003
        WINEVENT_OUTOFCONTEXT = 0x0000
        WINEVENT_SKIPOWNPROCESS = 0x0002
        win_event_proc_type = ctypes.WINFUNCTYPE(
            None,
            wintypes.HANDLE,
            wintypes.DWORD,
            wintypes.HWND,
            wintypes.LONG,
            wintypes.LONG,
            wintypes.DWORD,
            wintypes.DWORD,
        )

        def on_foreground_changed(
            _hook, _event, _hwnd, _object_id, _child_id, _event_thread, _event_time
        ) -> None:
            # Native callbacks are not a Qt widget context; emit into Qt instead.
            self._foreground_recovery_bridge.recovery_requested.emit()

        self._win_event_callback = win_event_proc_type(on_foreground_changed)
        user32 = ctypes.windll.user32
        user32.SetWinEventHook.argtypes = (
            wintypes.DWORD,
            wintypes.DWORD,
            wintypes.HMODULE,
            win_event_proc_type,
            wintypes.DWORD,
            wintypes.DWORD,
            wintypes.DWORD,
        )
        user32.SetWinEventHook.restype = wintypes.HANDLE
        self._win_event_hook = user32.SetWinEventHook(
            EVENT_SYSTEM_FOREGROUND,
            EVENT_SYSTEM_FOREGROUND,
            None,
            self._win_event_callback,
            0,
            0,
            WINEVENT_OUTOFCONTEXT | WINEVENT_SKIPOWNPROCESS,
        )

    def _queue_foreground_topmost_refresh(self) -> None:
        """Coalesce foreground transitions before touching visible utility windows."""
        if not self._foreground_recovery_timer.isActive():
            self._foreground_recovery_timer.start()

    def cleanup(self) -> None:
        """Release the native hook before the Qt event loop stops."""
        if not self._win_event_hook:
            return
        hook = self._win_event_hook
        self._win_event_hook = None
        try:
            user32 = ctypes.windll.user32
            user32.UnhookWinEvent.argtypes = (wintypes.HANDLE,)
            user32.UnhookWinEvent.restype = wintypes.BOOL
            user32.UnhookWinEvent(hook)
        except Exception:
            pass

    def apply_stylesheet(self) -> None:
        self.stylesheet = """
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

            QWidget#quickActionWindow {
                background-color: #0B1020;
                border: 1px solid #5B5FC7;
                border-radius: 16px;
            }

            QWidget#quickActionWindow > QWidget,
            QWidget#quickActionGrid,
            QWidget#quickActionPagination {
                background-color: transparent;
                border: none;
            }

            QWidget#quickActionPlaceholder {
                background-color: transparent;
                border: none;
            }

            QLabel#quickActionsTitle {
                background-color: transparent;
                color: #F8FAFF;
                font-size: 19px;
                font-weight: 700;
                border: none;
            }

            QLabel#quickActionTitleIcon {
                background-color: transparent;
                color: #B56CFF;
                font-size: 21px;
                font-weight: 700;
                border: none;
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

            QPushButton#quickLauncherButton,
            QPushButton#primaryButton {
                background-color: #7B1FA2;
                color: #FFFFFF;
                border: 1px solid #9C27B0;
                font-size: 16px;
                font-weight: 600;
                padding: 8px 12px;
            }

            QPushButton#quickLauncherButton {
                font-size: 25px;
                border-radius: 10px;
            }

            QPushButton#quickLauncherButton:hover,
            QPushButton#primaryButton:hover {
                background-color: #9C27B0;
            }

            QLineEdit#quickActionSearch {
                background-color: #121A30;
                color: #F5F3FF;
                border: 1px solid #5667B8;
                border-radius: 9px;
                padding: 0 10px;
                font-size: 13px;
                selection-background-color: #7C3AED;
            }

            QLineEdit#quickActionSearch:focus {
                border-color: #A020F0;
                background-color: #151E38;
            }

            QPushButton#quickActionHideButton {
                background-color: #151C30;
                color: #F8FAFF;
                border: 1px solid #6865C9;
                border-radius: 9px;
                font-size: 13px;
                font-weight: 600;
            }

            QPushButton#quickActionHideButton:hover {
                background-color: #202A4A;
                border-color: #B56CFF;
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

            QWidget#quickActionCard {
                background-color: #151C30;
                border: 1px solid #4D62AB;
                border-radius: 10px;
            }

            QWidget#quickActionCard:hover {
                background-color: #1B2540;
                border-color: #9A72F2;
            }

            QWidget#quickActionCard QWidget,
            QWidget#quickActionCard QLabel {
                background-color: transparent;
                border: none;
            }

            QLabel#quickActionName {
                color: #FAFAFF;
                font-size: 14px;
                font-weight: 700;
            }

            QLabel#quickActionBadge {
                background-color: #32145A;
                color: #F0ABFC;
                border: 1px solid #A020F0;
                border-radius: 7px;
                font-size: 9px;
                font-weight: 700;
            }

            QLabel#quickActionDescription {
                color: #C4C9DC;
                font-size: 11px;
            }

            QLabel#quickActionDetail {
                color: #9EA8C8;
                font-size: 10px;
            }

            QLabel#quickActionIconLogin,
            QLabel#quickActionIconShare,
            QLabel#quickActionIconTool {
                border-radius: 9px;
                font-size: 20px;
                font-weight: 600;
            }

            QLabel#quickActionIconLogin {
                background-color: #33205F;
                border: 1px solid #8759DF;
            }

            QLabel#quickActionIconShare {
                background-color: #3A344A;
                border: 1px solid #83739C;
            }

            QLabel#quickActionIconTool {
                background-color: #202C50;
                border: 1px solid #566FAF;
            }

            QPushButton#quickActionMenuButton {
                background-color: #202A49;
                color: #E9E8FF;
                border: 1px solid #5667A8;
                border-radius: 8px;
                font-size: 22px;
                font-weight: 400;
                padding: 0 0 3px 0;
            }

            QPushButton#quickActionMenuButton:hover {
                background-color: qlineargradient(x1:0, y1:0, x2:1, y2:0,
                    stop:0 #8A2BE2, stop:0.52 #A020F0, stop:1 #7C3AED);
                color: #FFFFFF;
                border-color: #E0A8FF;
            }

            QPushButton#categoryFilterButton {
                background-color: #121A30;
                color: #C7CBE0;
                border: 1px solid #465789;
                border-radius: 14px;
                padding: 3px 12px;
                font-size: 12px;
                font-weight: 600;
            }

            QPushButton#categoryFilterButton:checked {
                background-color: qlineargradient(x1:0, y1:0, x2:1, y2:0,
                    stop:0 #8A2BE2, stop:1 #B517FF);
                color: #FFFFFF;
                border-color: #D28BFF;
            }

            QPushButton#categoryFilterButton:hover:!checked {
                background-color: qlineargradient(x1:0, y1:0, x2:1, y2:0,
                    stop:0 #55308B, stop:1 #7136A9);
                color: #FFFFFF;
                border-color: #B56CFF;
            }

            QPushButton#quickActionAddButton {
                background-color: qlineargradient(x1:0, y1:0, x2:1, y2:0,
                    stop:0 #8A2BE2, stop:0.52 #A020F0, stop:1 #7C3AED);
                color: #FFFFFF;
                border: 1px solid #D28BFF;
                border-radius: 10px;
                font-size: 15px;
                font-weight: 700;
            }

            QPushButton#quickActionAddButton:hover {
                background-color: qlineargradient(x1:0, y1:0, x2:1, y2:0,
                    stop:0 #9B44EA, stop:0.52 #B638FF, stop:1 #8D55F7);
                border-color: #F0C4FF;
            }

            QPushButton#dangerButton {
                background-color: #3B1010;
                color: #FF8A80;
                border: 1px solid #5C1A1A;
                padding: 6px 9px;
                font-size: 12px;
            }

            QPushButton#dangerButton:hover {
                background-color: #5C1A1A;
            }

            QLineEdit,
            QComboBox {
                background-color: #222222;
                color: #F7F7F7;
                border: 1px solid #404040;
                border-radius: 6px;
                padding: 7px;
            }

            QLabel#emptyLabel {
                color: #A0A0A0;
                padding: 12px;
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

            QLabel#copyrightLabel {
                color: #555555;
                font-size: 11px;
                padding-top: 4px;
            }
        """
        self.floating_button_window.setStyleSheet(self.stylesheet)
        self.keyboard_window.setStyleSheet(self.stylesheet)
        self.quick_action_window.setStyleSheet(self.stylesheet)

    def show_keyboard(self) -> None:
        # Snapshot current foreground window before we show our keyboard
        self.keyboard_window._last_target_hwnd = get_foreground_window_handle()
        self.keyboard_window.show()
        self.keyboard_window.reassert_topmost()
        self.floating_button_window.hide()

    def hide_keyboard(self) -> None:
        self.keyboard_window.hide()
        self.show_launcher()

    def _is_utility_window(self, hwnd: int) -> bool:
        if not hwnd:
            return True
        utility_windows = (
            self.floating_button_window,
            self.keyboard_window,
            self.quick_action_window,
        )
        return any(hwnd == int(window.winId()) for window in utility_windows)

    def show_launcher(self) -> None:
        self.floating_button_window.show()
        self.floating_button_window.reassert_topmost()

    def show_quick_actions(self) -> None:
        current_hwnd = get_foreground_window_handle()
        if not self._is_utility_window(current_hwnd):
            self.quick_target_hwnd = current_hwnd
            # Preserve the existing keyboard target state as well, without creating another path.
            self.keyboard_window._last_target_hwnd = current_hwnd
        else:
            self.quick_target_hwnd = 0
        self.quick_action_window.set_actions(self.actions)
        self.quick_action_window.show()
        self.quick_action_window.reassert_topmost()
        self.floating_button_window.hide()

    def hide_quick_actions(self) -> None:
        self.quick_action_window.hide()
        self.show_launcher()

    def _save_actions(self) -> bool:
        try:
            self.action_store.save(self.actions)
            return True
        except OSError as error:
            print(f"Could not save Quick Actions configuration: {error}", file=sys.stderr)
            show_modal_message(
                self.quick_action_window,
                QMessageBox.Warning,
                "Quick Actions",
                f"Could not save configuration.\n{error}",
            )
            return False

    def _open_action_dialog(self, action: Optional[Dict[str, object]] = None) -> None:
        self.quick_action_window.hide()
        dialog = QuickActionEditDialog(action, parent=self.quick_action_window)
        dialog.setStyleSheet(self.stylesheet)
        if exec_dialog_on_top(dialog, self.quick_action_window) == QDialog.Accepted and dialog.saved_action:
            if action:
                action_id = action["id"]
                self.actions = [
                    dialog.saved_action if saved_action["id"] == action_id else saved_action
                    for saved_action in self.actions
                ]
            else:
                self.actions.append(dialog.saved_action)
            self._save_actions()
            self.quick_action_window.set_actions(self.actions)
        # Configuration is focusable; do not reuse its foreground window as a Quick target.
        self.quick_target_hwnd = 0
        self.show_launcher()

    def add_quick_action(self) -> None:
        self._open_action_dialog()

    def edit_quick_action(self, action: Dict[str, object]) -> None:
        self._open_action_dialog(action)

    def delete_quick_action(self, action: Dict[str, object]) -> None:
        self.quick_action_window.hide()
        answer = show_modal_message(
            self.quick_action_window,
            QMessageBox.Question,
            "Delete Quick Action",
            f"Delete '{action['name']}'?",
            QMessageBox.Yes | QMessageBox.No,
            QMessageBox.No,
        )
        if answer == QMessageBox.Yes:
            self.actions = [saved_action for saved_action in self.actions if saved_action["id"] != action["id"]]
            self._save_actions()
            self.quick_action_window.set_actions(self.actions)
        self.quick_target_hwnd = 0
        self.show_launcher()

    def run_quick_action(self, action: Dict[str, object]) -> None:
        self.quick_action_window.hide()
        self.show_launcher()
        action_type = action.get("type")
        if action_type == "input_code":
            username = str(action.get("username", action.get("value", "")))
            password = str(action.get("password", ""))
            if not username or not password:
                show_modal_message(
                    self.quick_action_window,
                    QMessageBox.Warning,
                    "Quick Actions",
                    "This Input Code action needs both a username and password. Edit it before running.",
                )
                self.quick_target_hwnd = 0
                return
            sent = self.keyboard_window.send_login_sequence(
                username,
                password,
                self.quick_target_hwnd,
            )
            if not sent:
                print("Quick Action login was skipped because no external target was available.", file=sys.stderr)
        elif action_type == "share_folder":
            try:
                os.startfile(str(action.get("value", "")))
            except OSError as error:
                show_modal_message(
                    self.quick_action_window,
                    QMessageBox.Warning,
                    "Quick Actions",
                    f"Could not open folder.\n{error}",
                )
        elif action_type == "windows_tool":
            tool_id = action.get("tool_id")
            if not isinstance(tool_id, str) or tool_id not in WINDOWS_TOOLS:
                show_modal_message(
                    self.quick_action_window,
                    QMessageBox.Warning,
                    "Quick Actions",
                    "This Windows Tool action is not supported.",
                )
            else:
                try:
                    launch_windows_tool(tool_id)
                except OSError as error:
                    show_modal_message(
                        self.quick_action_window,
                        QMessageBox.Warning,
                        "Quick Actions",
                        f"Could not open Windows tool.\n{error}",
                    )
        self.quick_target_hwnd = 0

    def refresh_visible_topmost(self) -> None:
        for window in (
            self.floating_button_window,
            self.keyboard_window,
            self.quick_action_window,
        ):
            if window.isVisible():
                window.reassert_topmost()

    def run(self) -> None:
        self.show_launcher()


def main() -> None:
    if hasattr(Qt, "AA_EnableHighDpiScaling"):
        QApplication.setAttribute(Qt.AA_EnableHighDpiScaling, True)
    if hasattr(Qt, "AA_UseHighDpiPixmaps"):
        QApplication.setAttribute(Qt.AA_UseHighDpiPixmaps, True)

    QCoreApplication.setOrganizationName("TBKK")
    QCoreApplication.setApplicationName("KeyboardGod")
    app = QApplication(sys.argv)
    app.setQuitOnLastWindowClosed(False)

    controller = KeyboardAppController()
    controller.run()

    sys.exit(app.exec_())


if __name__ == "__main__":
    main()
