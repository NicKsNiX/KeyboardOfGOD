import ctypes
from ctypes import wintypes
import json
import os
import shutil
import subprocess
import sys
import uuid
from typing import Dict, List, Optional

from PyQt5.QtCore import QCoreApplication, QObject, QRect, QStandardPaths, Qt, QTimer, pyqtSignal
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


def is_windows_10_or_newer() -> bool:
    """Return True if running on Windows 10 or newer (build 10240+)."""
    try:
        return sys.platform == "win32" and sys.getwindowsversion().major >= 10
    except Exception:
        return False


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
    "windows_update": {
        "label": "Windows Update",
        "target": "ms-settings:windowsupdate" if is_windows_10_or_newer() else "wuapp.exe",
        "fallback": "control.exe",
    },
    "installed_apps": {
        "label": "Installed Apps",
        "target": "ms-settings:appsfeatures" if is_windows_10_or_newer() else "appwiz.cpl",
        "fallback": "appwiz.cpl",
    },
    "startup_apps": {
        "label": "Startup Apps",
        "target": "ms-settings:startupapps" if is_windows_10_or_newer() else "msconfig.exe",
        "fallback": "msconfig.exe",
    },
    "optional_features": {
        "label": "Optional Features",
        "target": "ms-settings:optionalfeatures" if is_windows_10_or_newer() else "optionalfeatures.exe",
        "fallback": "optionalfeatures.exe",
    },
    "storage": {
        "label": "Storage",
        "target": "ms-settings:storagesense" if is_windows_10_or_newer() else "cleanmgr.exe",
        "fallback": "cleanmgr.exe",
    },
    "display": {
        "label": "Display",
        "target": "ms-settings:display" if is_windows_10_or_newer() else "desk.cpl",
        "fallback": "desk.cpl",
    },
    "sound_settings": {
        "label": "Sound Settings",
        "target": "ms-settings:sound" if is_windows_10_or_newer() else "mmsys.cpl",
        "fallback": "mmsys.cpl",
    },
    "bluetooth_devices": {
        "label": "Bluetooth & Devices",
        "target": "ms-settings:bluetooth" if is_windows_10_or_newer() else "control.exe",
        "fallback": "control.exe",
    },
    "printers_scanners": {
        "label": "Printers & Scanners",
        "target": "ms-settings:printers" if is_windows_10_or_newer() else "control.exe",
        "fallback": "control.exe",
    },
    "network_internet": {
        "label": "Network & Internet",
        "target": "ms-settings:network" if is_windows_10_or_newer() else "ncpa.cpl",
        "fallback": "ncpa.cpl",
    },
    "about": {
        "label": "About / System Information",
        "target": "ms-settings:about" if is_windows_10_or_newer() else "sysdm.cpl",
        "fallback": "sysdm.cpl",
    },
}
LEGACY_WINDOWS_TOOL_IDS = {
    str(tool["target"]): tool_id
    for tool_id, tool in WINDOWS_TOOLS.items()
    if "target" in tool
}
MASTER_CONFIG_RELEASE = "1.0.1"

DEFAULT_ACTIONS: List[Dict[str, object]] = [
    {
        "id": "3b6dceb3-182e-4d4c-836d-09eae38fb789",
        "name": "sadmin",
        "type": "input_code",
        "username": "sadmin",
        "password": "Teaminw",
    },
    {
        "id": "d921f918-a19e-4d81-839d-3a8b65eab4a9",
        "name": ".8 inw",
        "type": "share_folder",
        "value": "X:/",
    },
    {
        "id": "60a4dd05-20fe-42f7-9dc0-133a63dc93ba",
        "name": ".8 P@ss",
        "type": "input_code",
        "username": "Administrator",
        "password": "P@ss!fa",
    },
    {
        "id": "e2717f92-494d-4051-87fa-789ba35dc0c7",
        "name": "D M",
        "type": "windows_tool",
        "tool_id": "device_manager",
    },
    {
        "id": "e413280b-a626-4584-9dc4-5ecc877b09c8",
        "name": "Programs and Features / Uninstall Programs",
        "type": "windows_tool",
        "tool_id": "uninstall_programs",
    },
    {
        "id": "906e7566-047d-4bd6-a47a-1bea5a92106e",
        "name": "Date and Time",
        "type": "windows_tool",
        "tool_id": "date_and_time",
    },
    {
        "id": "37402fb7-3c87-48f4-ba64-ddd15ae94738",
        "name": "Task Manager",
        "type": "windows_tool",
        "tool_id": "task_manager",
    },
    {
        "id": "bdede50b-9be2-419b-b40a-42ac5e81df50",
        "name": "Network & Internet",
        "type": "windows_tool",
        "tool_id": "network_internet",
    },
]


class ForegroundRecoveryBridge(QObject):
    """Deliver native foreground notifications to the Qt main thread."""

    recovery_requested = pyqtSignal()


user32 = ctypes.windll.user32
LONG_PTR = ctypes.c_ssize_t

if hasattr(user32, "GetWindowLongPtrW"):
    _GetWindowLong = user32.GetWindowLongPtrW
    _SetWindowLong = user32.SetWindowLongPtrW
else:
    _GetWindowLong = user32.GetWindowLongW
    _SetWindowLong = user32.SetWindowLongW

_GetWindowLong.argtypes = (wintypes.HWND, ctypes.c_int)
_GetWindowLong.restype = LONG_PTR
_SetWindowLong.argtypes = (wintypes.HWND, ctypes.c_int, LONG_PTR)
_SetWindowLong.restype = LONG_PTR

user32.GetForegroundWindow.argtypes = ()
user32.GetForegroundWindow.restype = wintypes.HWND

user32.SetForegroundWindow.argtypes = (wintypes.HWND,)
user32.SetForegroundWindow.restype = wintypes.BOOL

user32.SetWindowPos.argtypes = (
    wintypes.HWND,
    wintypes.HWND,
    ctypes.c_int,
    ctypes.c_int,
    ctypes.c_int,
    ctypes.c_int,
    wintypes.UINT,
)
user32.SetWindowPos.restype = wintypes.BOOL

user32.ShowWindow.argtypes = (wintypes.HWND, ctypes.c_int)
user32.ShowWindow.restype = wintypes.BOOL

user32.IsWindow.argtypes = (wintypes.HWND,)
user32.IsWindow.restype = wintypes.BOOL

user32.FindWindowW.argtypes = (wintypes.LPCWSTR, wintypes.LPCWSTR)
user32.FindWindowW.restype = wintypes.HWND

HWND_TOPMOST = ctypes.c_void_p(-1).value


def get_foreground_window_handle() -> int:
    """Return current foreground window handle on Windows."""
    try:
        val = user32.GetForegroundWindow()
        return int(val or 0)
    except Exception:
        return 0


def set_foreground_window_handle(hwnd: int) -> None:
    """Bring target window back to foreground on Windows."""
    if not hwnd:
        return
    try:
        user32.SetForegroundWindow(hwnd)
    except Exception:
        return


def apply_no_activate_style(hwnd: int) -> None:
    """Apply WS_EX_NOACTIVATE so clicking the window never steals focus."""
    GWL_EXSTYLE = -20
    WS_EX_NOACTIVATE = 0x08000000
    WS_EX_TOOLWINDOW = 0x00000080
    try:
        style = _GetWindowLong(hwnd, GWL_EXSTYLE)
        _SetWindowLong(
            hwnd, GWL_EXSTYLE, style | WS_EX_NOACTIVATE | WS_EX_TOOLWINDOW
        )
    except Exception:
        pass


def reassert_topmost_no_activate(hwnd: int) -> None:
    """Put a visible utility window back in the TOPMOST band without activation."""
    if not hwnd:
        return
    SWP_NOSIZE = 0x0001
    SWP_NOMOVE = 0x0002
    SWP_NOACTIVATE = 0x0010
    try:
        user32.SetWindowPos(
            hwnd,
            HWND_TOPMOST,
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
        SWP_NOSIZE = 0x0001
        SWP_NOMOVE = 0x0002
        SWP_SHOWWINDOW = 0x0040
        user32.SetWindowPos(
            hwnd,
            HWND_TOPMOST,
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
        try:
            os.startfile(str(target))
            return
        except OSError:
            fallback = tool.get("fallback")
            if fallback:
                try:
                    os.startfile(str(fallback))
                    return
                except OSError:
                    pass
            raise

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


def disable_wow64_redirection():
    """Disable WOW64 file system redirection if running 32-bit Python on 64-bit Windows."""
    old_value = ctypes.c_void_p()
    kernel32 = ctypes.windll.kernel32
    disable_fn = getattr(kernel32, "Wow64DisableWow64FsRedirection", None)
    if disable_fn:
        try:
            if disable_fn(ctypes.byref(old_value)):
                return old_value
        except Exception:
            pass
    return None


def revert_wow64_redirection(old_value) -> None:
    """Revert WOW64 file system redirection if previously disabled."""
    if old_value is not None:
        kernel32 = ctypes.windll.kernel32
        revert_fn = getattr(kernel32, "Wow64RevertWow64FsRedirection", None)
        if revert_fn:
            try:
                revert_fn(old_value)
            except Exception:
                pass


def find_osk_window() -> int:
    """Return window handle of On-Screen Keyboard (osk.exe) if already open."""
    # OSKMainClass is the standard window class across all Windows versions
    hwnd = user32.FindWindowW("OSKMainClass", None)
    if not hwnd:
        hwnd = user32.FindWindowW(None, "On-Screen Keyboard")
    if hwnd and user32.IsWindow(hwnd):
        return int(hwnd or 0)
    return 0


def launch_on_screen_keyboard() -> bool:
    """Launch Windows On-Screen Keyboard (osk.exe) or bring it to front if already open."""
    # Check if osk.exe window handle exists to avoid duplicate launches
    hwnd = find_osk_window()
    if hwnd:
        SW_RESTORE = 9
        user32.ShowWindow(hwnd, SW_RESTORE)
        user32.SetForegroundWindow(hwnd)
        return True

    # Check paths handling 32-bit and 64-bit File System Redirection across Win 7 / 10 / 11
    windir = os.environ.get("WINDIR", r"C:\Windows")
    sysnative_osk = os.path.join(windir, "sysnative", "osk.exe")
    system32_osk = os.path.join(windir, "System32", "osk.exe")

    SW_SHOWNORMAL = 1
    shell32 = ctypes.windll.shell32

    # 1. Try sysnative if it exists (for 32-bit process on 64-bit Windows)
    if os.path.exists(sysnative_osk):
        result = shell32.ShellExecuteW(None, "open", sysnative_osk, None, None, SW_SHOWNORMAL)
        if int(result or 0) > 32:
            return True

    # 2. Try with WOW64 redirection temporarily disabled (safe on 32-bit and 64-bit)
    cookie = disable_wow64_redirection()
    try:
        if os.path.exists(system32_osk):
            result = shell32.ShellExecuteW(None, "open", system32_osk, None, None, SW_SHOWNORMAL)
            if int(result or 0) > 32:
                return True
    finally:
        revert_wow64_redirection(cookie)

    # 3. Fallback to direct name or startfile
    try:
        result = shell32.ShellExecuteW(None, "open", "osk.exe", None, None, SW_SHOWNORMAL)
        if int(result or 0) > 32:
            return True
    except Exception:
        pass

    try:
        os.startfile("osk.exe")
        return True
    except OSError:
        return False


def get_app_dir() -> str:
    """Return the directory containing the running executable or main script."""
    if getattr(sys, "frozen", False):
        return os.path.dirname(os.path.abspath(sys.executable))
    return os.path.dirname(os.path.abspath(__file__))


def is_directory_writable(directory: str) -> bool:
    """Check if a directory has write permissions."""
    try:
        os.makedirs(directory, exist_ok=True)
        test_file = os.path.join(directory, f".write_test_{uuid.uuid4().hex}.tmp")
        with open(test_file, "w", encoding="utf-8") as f:
            f.write("1")
        os.remove(test_file)
        return True
    except Exception:
        return False


def is_system_install_dir(directory: str) -> bool:
    """Check if directory is inside Program Files or Windows system folders."""
    norm = os.path.normcase(os.path.abspath(directory))
    system_roots = [
        os.environ.get("ProgramFiles", r"C:\Program Files"),
        os.environ.get("ProgramFiles(x86)", r"C:\Program Files (x86)"),
        os.environ.get("WINDIR", r"C:\Windows"),
    ]
    for sroot in system_roots:
        if sroot and norm.startswith(os.path.normcase(os.path.abspath(sroot))):
            return True
    return False


class QuickActionStore:
    """JSON store for per-user or portable Quick Actions."""

    VALID_TYPES = {"input_code", "share_folder", "windows_tool"}

    def __init__(
        self,
        config_path: Optional[str] = None,
        config_dir: Optional[str] = None,
        master_path: Optional[str] = None,
        master_release: str = MASTER_CONFIG_RELEASE,
    ) -> None:
        self.app_dir = get_app_dir()
        self.master_release = master_release

        if config_path:
            self.path = config_path
            self.is_portable = False
        else:
            # 1. Look for portable data.json or quick_actions.json next to executable / script
            local_data_json = os.path.join(self.app_dir, "data.json")
            local_quick_json = os.path.join(self.app_dir, "quick_actions.json")

            if os.path.exists(local_data_json):
                self.path = local_data_json
                self.is_portable = True
            elif os.path.exists(local_quick_json):
                self.path = local_quick_json
                self.is_portable = True
            elif not is_system_install_dir(self.app_dir) and is_directory_writable(self.app_dir):
                # Portable mode by default for standalone folder / USB drive / repo
                self.path = local_data_json
                self.is_portable = True
            else:
                # Installed / restricted mode: fall back to %LOCALAPPDATA%
                base_dir = config_dir or QStandardPaths.writableLocation(QStandardPaths.AppConfigLocation)
                self.path = os.path.join(base_dir, "quick_actions.json")
                self.is_portable = False

        self.master_path = master_path or resource_path(
            os.path.join("defaults", "quick_actions.default.json")
        )
        self.master_marker_path = os.path.join(os.path.dirname(self.path), "master_config.release")

    def load(self) -> List[Dict[str, object]]:
        if not os.path.exists(self.path):
            self._deploy_master_config_if_needed()

        if not os.path.exists(self.path):
            return [dict(a) for a in DEFAULT_ACTIONS]

        try:
            with open(self.path, "r", encoding="utf-8") as config_file:
                document = json.load(config_file)
        except (OSError, json.JSONDecodeError) as error:
            print(f"Could not read Quick Actions configuration: {error}", file=sys.stderr)
            return [dict(a) for a in DEFAULT_ACTIONS]

        actions = self._clean_actions(document)
        if not actions:
            return [dict(a) for a in DEFAULT_ACTIONS]
        return actions

    def _clean_actions(self, document: object) -> List[Dict[str, object]]:
        """Validate and normalize supported Quick Actions without changing credentials."""
        if isinstance(document, list):
            raw_actions = document
        elif isinstance(document, dict) and isinstance(document.get("actions"), list):
            raw_actions = document["actions"]
        else:
            return []

        actions: List[Dict[str, object]] = []
        seen_ids = set()
        for action in raw_actions:
            if not isinstance(action, dict):
                continue
            action_id = action.get("id")
            if not isinstance(action_id, str) or not action_id:
                action_id = str(uuid.uuid4())
            if action_id in seen_ids:
                action_id = str(uuid.uuid4())
            action_type = action.get("type")
            name = action.get("name")
            if action_type not in self.VALID_TYPES or not isinstance(name, str):
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
        """Apply bundled master config, migrate from AppData, or use embedded defaults."""
        if os.path.exists(self.path):
            return

        os.makedirs(os.path.dirname(self.path), exist_ok=True)

        # 1. Migrate existing config from earlier AppData runs if available
        appdata_locations = [
            os.path.join(QStandardPaths.writableLocation(QStandardPaths.AppConfigLocation), "quick_actions.json"),
            os.path.join(os.environ.get("LOCALAPPDATA", ""), "TBKK", "KeyboardGod", "quick_actions.json"),
            os.path.join(os.environ.get("LOCALAPPDATA", ""), "KeyboardGod", "quick_actions.json"),
            os.path.join(os.environ.get("LOCALAPPDATA", ""), "python", "quick_actions.json"),
        ]
        for appdata_file in appdata_locations:
            if appdata_file and os.path.exists(appdata_file) and os.path.abspath(appdata_file) != os.path.abspath(self.path):
                try:
                    with open(appdata_file, "r", encoding="utf-8") as f:
                        doc = json.load(f)
                    cleaned = self._clean_actions(doc)
                    if cleaned:
                        self.save(cleaned)
                        return
                except Exception:
                    pass

        # 2. Bundled master config file if present
        if self.master_path and os.path.exists(self.master_path):
            try:
                with open(self.master_path, "r", encoding="utf-8") as master_file:
                    master_document = json.load(master_file)
                cleaned = self._clean_actions(master_document)
                if cleaned:
                    self.save(cleaned)
                    return
            except Exception as e:
                print(f"Could not deploy master Quick Actions configuration: {e}", file=sys.stderr)

        # 3. Always fallback to embedded DEFAULT_ACTIONS
        self.save(DEFAULT_ACTIONS)

    def save(self, actions: List[Dict[str, object]]) -> None:
        os.makedirs(os.path.dirname(self.path), exist_ok=True)
        document = {"version": 1, "actions": actions}
        temporary_path = f"{self.path}.tmp"
        with open(temporary_path, "w", encoding="utf-8") as config_file:
            json.dump(document, config_file, ensure_ascii=False, indent=2)
        os.replace(temporary_path, self.path)


class FloatingButtonWindow(QWidget):
    """Small always-on-top launcher with Keyboard and Quick controls."""

    def __init__(self, on_open_keyboard, on_open_quick, on_open_data_folder=None):
        super().__init__()
        self.on_open_keyboard = on_open_keyboard
        self.on_open_quick = on_open_quick
        self.on_open_data_folder = on_open_data_folder
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
        self.launch_button.setToolTip("On-Screen Keyboard (Right-click for Menu/Exit)")
        self.launch_button.clicked.connect(self.on_open_keyboard)

        self.quick_button = QPushButton("⚡")
        self.quick_button.setCursor(Qt.PointingHandCursor)
        self.quick_button.setFixedSize(60, 60)
        self.quick_button.setObjectName("quickLauncherButton")
        self.quick_button.setToolTip("Quick Actions (Right-click for Menu/Exit)")
        self.quick_button.clicked.connect(self.on_open_quick)

        self.setContextMenuPolicy(Qt.CustomContextMenu)
        self.customContextMenuRequested.connect(self.show_context_menu)
        self.launch_button.setContextMenuPolicy(Qt.CustomContextMenu)
        self.launch_button.customContextMenuRequested.connect(self.show_context_menu)
        self.quick_button.setContextMenuPolicy(Qt.CustomContextMenu)
        self.quick_button.customContextMenuRequested.connect(self.show_context_menu)

        layout.addWidget(self.launch_button)
        layout.addWidget(self.quick_button)
        self.setLayout(layout)

    def show_context_menu(self, _pos) -> None:
        from PyQt5.QtGui import QCursor
        menu = QMenu(self)
        open_data_action = menu.addAction("Open Data Folder (data.json)")
        menu.addSeparator()
        exit_action = menu.addAction("Exit KeyboardGod")
        selected = menu.exec_(QCursor.pos())
        if selected == open_data_action:
            if self.on_open_data_folder:
                self.on_open_data_folder()
        elif selected == exit_action:
            QApplication.quit()

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


class QuickActionMetrics:
    """Calculates responsive layout metrics for QuickActionWindow and child cards."""

    def __init__(self, scale: float, geom: QRect):
        self.scale = scale
        self.screen_geom = geom

        if scale >= 1.0:
            self.win_width = 560
            self.win_height = 550
            self.outer_margin = 10
            self.layout_spacing = 6
        elif scale >= 0.88:
            self.win_width = int(round(500 * (scale / 0.88)))
            self.win_height = int(round(482 * (scale / 0.88)))
            self.outer_margin = 8
            self.layout_spacing = 5
        elif scale >= 0.80:
            self.win_width = int(round(456 * (scale / 0.80)))
            self.win_height = int(round(440 * (scale / 0.80)))
            self.outer_margin = 7
            self.layout_spacing = 4
        else:  # small screens (800x600)
            self.win_width = max(390, min(420, int(round(560 * scale * 1.06))))
            self.win_height = max(370, min(405, int(round(550 * scale * 0.99))))
            self.outer_margin = 6
            self.layout_spacing = 3

        # Window styling
        self.win_border_radius = max(10, int(round(16 * scale)))

        # Header / Title row
        self.title_font_size = max(13, int(round(19 * scale)))
        self.title_icon_size = max(14, int(round(21 * scale)))

        # Search row
        self.search_height = max(24, int(round(34 * scale)))
        self.search_font_size = max(10, int(round(13 * scale)))
        self.search_border_radius = max(6, int(round(9 * scale)))
        self.search_padding_h = max(6, int(round(10 * scale)))
        self.hide_btn_width = max(46, int(round(68 * scale)))
        self.hide_btn_height = self.search_height
        self.hide_btn_font_size = max(10, int(round(13 * scale)))
        self.hide_btn_radius = max(6, int(round(9 * scale)))

        # Filter row
        self.category_btn_height = max(20, int(round(28 * scale)))
        self.category_font_size = max(9, int(round(12 * scale)))
        self.category_padding_v = max(1, int(round(3 * scale)))
        self.category_padding_h = max(6, int(round(12 * scale)))
        self.category_radius = max(8, int(round(14 * scale)))
        self.filter_spacing = max(4, int(round(6 * scale)))

        # Cards
        self.card_height = max(50, int(round(74 * scale))) if scale < 0.80 else max(52, int(round(78 * scale)))
        self.grid_gap = 5 if scale < 0.80 else max(4, int(round(8 * scale)))
        self.grid_container_height = self.card_height * 4 + self.grid_gap * 3

        self.card_margin_h = max(5, int(round(8 * scale)))
        self.card_margin_v = max(4, int(round(7 * scale)))
        self.card_inner_spacing = max(5, int(round(8 * scale)))
        self.card_border_radius = max(7, int(round(10 * scale)))
        self.card_icon_size = max(27, int(round(42 * scale)))
        self.card_icon_font_size = max(13, int(round(20 * scale)))
        self.card_icon_radius = max(6, int(round(9 * scale)))

        self.card_title_height = max(18, int(round(27 * scale)))
        self.card_title_font_size = max(10, int(round(14 * scale)))
        self.card_subtitle_height = max(11, int(round(16 * scale)))
        self.card_subtitle_font_size = max(8, int(round(11 * scale)))

        self.card_badge_width = max(35, int(round(50 * scale)))
        self.card_badge_height = max(13, int(round(18 * scale)))
        self.card_badge_font_size = max(7, int(round(9 * scale)))
        self.card_badge_radius = max(4, int(round(7 * scale)))
        self.card_detail_font_size = max(7, int(round(10 * scale)))
        self.card_details_spacing = max(3, int(round(6 * scale)))

        self.card_menu_btn_size = max(22, int(round(32 * scale)))
        self.card_menu_btn_font_size = max(14, int(round(22 * scale)))
        self.card_menu_btn_radius = max(5, int(round(8 * scale)))

        # Pagination row
        self.page_btn_width = max(20, int(round(28 * scale)))
        self.page_btn_height = max(18, int(round(26 * scale)))
        self.page_btn_radius = max(4, int(round(6 * scale)))
        self.page_btn_font_size = max(11, int(round(15 * scale)))
        self.page_indicator_font_size = max(9, int(round(12 * scale)))
        self.pagination_spacing = max(5, int(round(8 * scale)))

        # Add button
        self.add_btn_height = max(27, int(round(42 * scale)))
        self.add_btn_font_size = max(10, int(round(15 * scale)))
        self.add_btn_radius = max(6, int(round(10 * scale)))


def compute_quick_action_metrics(geom: Optional[QRect] = None) -> QuickActionMetrics:
    if geom is None:
        screen = QApplication.primaryScreen()
        geom = screen.availableGeometry() if screen else QRect(0, 0, 1920, 1080)

    w = geom.width()
    h = geom.height()

    if w >= 1500 and h >= 840:
        scale = 1.0
    elif w >= 1200 and h >= 660:
        ratio = min((w - 1200) / 300.0, (h - 660) / 180.0)
        scale = round(0.88 + 0.12 * max(0.0, min(1.0, ratio)), 2)
    elif w >= 960 and h >= 580:
        ratio = min((w - 960) / 240.0, (h - 580) / 80.0)
        scale = round(0.80 + 0.08 * max(0.0, min(1.0, ratio)), 2)
    else:
        ratio = min(max(0.0, (w - 700) / 260.0), max(0.0, (h - 450) / 130.0))
        scale = round(0.70 + 0.10 * max(0.0, min(1.0, ratio)), 2)

    return QuickActionMetrics(scale, geom)


def generate_quick_action_stylesheet(metrics: QuickActionMetrics) -> str:
    return f"""
        QWidget#quickActionWindow {{
            background-color: #0B1020;
            border: 1px solid #5B5FC7;
            border-radius: {metrics.win_border_radius}px;
        }}

        QWidget#quickActionWindow > QWidget,
        QWidget#quickActionGrid,
        QWidget#quickActionPagination {{
            background-color: transparent;
            border: none;
        }}

        QWidget#quickActionPlaceholder {{
            background-color: transparent;
            border: none;
        }}

        QLabel#quickActionsTitle {{
            background-color: transparent;
            color: #F8FAFF;
            font-size: {metrics.title_font_size}px;
            font-weight: 700;
            border: none;
        }}

        QLabel#quickActionTitleIcon {{
            background-color: transparent;
            color: #B56CFF;
            font-size: {metrics.title_icon_size}px;
            font-weight: 700;
            border: none;
        }}

        QLineEdit#quickActionSearch {{
            background-color: #121A30;
            color: #F5F3FF;
            border: 1px solid #5667B8;
            border-radius: {metrics.search_border_radius}px;
            padding: 0 {metrics.search_padding_h}px;
            font-size: {metrics.search_font_size}px;
            selection-background-color: #7C3AED;
        }}

        QLineEdit#quickActionSearch:focus {{
            border-color: #A020F0;
            background-color: #151E38;
        }}

        QPushButton#quickActionHideButton {{
            background-color: #151C30;
            color: #F8FAFF;
            border: 1px solid #6865C9;
            border-radius: {metrics.hide_btn_radius}px;
            font-size: {metrics.hide_btn_font_size}px;
            font-weight: 600;
        }}

        QPushButton#quickActionHideButton:hover {{
            background-color: #202A4A;
            border-color: #B56CFF;
        }}

        QPushButton#categoryFilterButton {{
            background-color: #121A30;
            color: #C7CBE0;
            border: 1px solid #465789;
            border-radius: {metrics.category_radius}px;
            padding: {metrics.category_padding_v}px {metrics.category_padding_h}px;
            font-size: {metrics.category_font_size}px;
            font-weight: 600;
        }}

        QPushButton#categoryFilterButton:checked {{
            background-color: qlineargradient(x1:0, y1:0, x2:1, y2:0,
                stop:0 #8A2BE2, stop:1 #B517FF);
            color: #FFFFFF;
            border-color: #D28BFF;
        }}

        QPushButton#categoryFilterButton:hover:!checked {{
            background-color: qlineargradient(x1:0, y1:0, x2:1, y2:0,
                stop:0 #55308B, stop:1 #7136A9);
            color: #FFFFFF;
            border-color: #B56CFF;
        }}

        QWidget#quickActionPagination QLabel {{
            background-color: transparent;
            color: #C7CBE0;
            font-size: {metrics.page_indicator_font_size}px;
            border: none;
        }}

        QWidget#quickActionCard {{
            background-color: #151C30;
            border: 1px solid #4D62AB;
            border-radius: {metrics.card_border_radius}px;
        }}

        QWidget#quickActionCard:hover {{
            background-color: #1B2540;
            border-color: #9A72F2;
        }}

        QWidget#quickActionCard QWidget,
        QWidget#quickActionCard QLabel {{
            background-color: transparent;
            border: none;
        }}

        QLabel#quickActionName {{
            color: #FAFAFF;
            font-size: {metrics.card_title_font_size}px;
            font-weight: 700;
        }}

        QLabel#quickActionBadge {{
            background-color: #32145A;
            color: #F0ABFC;
            border: 1px solid #A020F0;
            border-radius: {metrics.card_badge_radius}px;
            font-size: {metrics.card_badge_font_size}px;
            font-weight: 700;
        }}

        QLabel#quickActionDescription {{
            color: #C4C9DC;
            font-size: {metrics.card_subtitle_font_size}px;
        }}

        QLabel#quickActionDetail {{
            color: #9EA8C8;
            font-size: {metrics.card_detail_font_size}px;
        }}

        QLabel#quickActionIconLogin,
        QLabel#quickActionIconShare,
        QLabel#quickActionIconTool {{
            border-radius: {metrics.card_icon_radius}px;
            font-size: {metrics.card_icon_font_size}px;
            font-weight: 600;
        }}

        QLabel#quickActionIconLogin {{
            background-color: #33205F;
            border: 1px solid #8759DF;
        }}

        QLabel#quickActionIconShare {{
            background-color: #3A344A;
            border: 1px solid #83739C;
        }}

        QLabel#quickActionIconTool {{
            background-color: #202C50;
            border: 1px solid #566FAF;
        }}

        QPushButton#quickActionMenuButton {{
            background-color: #202A49;
            color: #E9E8FF;
            border: 1px solid #5667A8;
            border-radius: {metrics.card_menu_btn_radius}px;
            font-size: {metrics.card_menu_btn_font_size}px;
            font-weight: 400;
            padding: 0 0 {max(1, int(round(3 * metrics.scale)))}px 0;
        }}

        QPushButton#quickActionMenuButton:hover {{
            background-color: qlineargradient(x1:0, y1:0, x2:1, y2:0,
                stop:0 #8A2BE2, stop:0.52 #A020F0, stop:1 #7C3AED);
            color: #FFFFFF;
            border-color: #E0A8FF;
        }}

        QPushButton#quickActionAddButton {{
            background-color: qlineargradient(x1:0, y1:0, x2:1, y2:0,
                stop:0 #8A2BE2, stop:0.52 #A020F0, stop:1 #7C3AED);
            color: #FFFFFF;
            border: 1px solid #D28BFF;
            border-radius: {metrics.add_btn_radius}px;
            font-size: {metrics.add_btn_font_size}px;
            font-weight: 700;
        }}

        QPushButton#quickActionAddButton:hover {{
            background-color: qlineargradient(x1:0, y1:0, x2:1, y2:0,
                stop:0 #9B44EA, stop:0.52 #B638FF, stop:1 #8D55F7);
            border-color: #F0C4FF;
        }}

        QPushButton#secondaryButton {{
            background-color: #222222;
            color: #F7F7F7;
            border: 1px solid #303030;
            border-radius: {metrics.page_btn_radius}px;
            padding: 0;
            font-size: {metrics.page_btn_font_size}px;
            font-weight: 500;
        }}

        QPushButton#secondaryButton:hover {{
            background-color: #2E2E2E;
        }}

        QPushButton#secondaryButton:pressed {{
            background-color: #3A3A3A;
        }}

        QLabel#emptyLabel {{
            color: #A0A0A0;
            padding: 12px;
        }}
    """


class QuickActionCard(QWidget):
    """Uniform premium-style action card with an internal layout scaled to metrics."""

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

    def __init__(
        self,
        action,
        on_run_action,
        on_edit_action,
        on_delete_action,
        metrics: Optional[QuickActionMetrics] = None,
    ):
        super().__init__()
        if metrics is None:
            metrics = QuickActionMetrics(1.0, QRect(0, 0, 1920, 1080))
        self.metrics = metrics
        self.action = action
        self.on_run_action = on_run_action
        self.on_edit_action = on_edit_action
        self.on_delete_action = on_delete_action
        self.setObjectName("quickActionCard")
        self.setCursor(Qt.PointingHandCursor)
        self.setFixedHeight(metrics.card_height)
        self.setSizePolicy(QSizePolicy.Ignored, QSizePolicy.Fixed)
        self.setToolTip("Click to run. Use the arrow for Edit or Delete.")

        icon, badge, description, icon_style = self.TYPE_DETAILS.get(
            action.get("type"), ("•", "ACTION", "Quick Action", "quickActionIconTool")
        )
        layout = QHBoxLayout()
        layout.setContentsMargins(
            metrics.card_margin_h,
            metrics.card_margin_v,
            metrics.card_margin_h,
            metrics.card_margin_v,
        )
        layout.setSpacing(metrics.card_inner_spacing)

        icon_label = QLabel(icon)
        icon_label.setObjectName(icon_style)
        icon_label.setFixedSize(metrics.card_icon_size, metrics.card_icon_size)
        icon_label.setAlignment(Qt.AlignCenter)
        icon_label.setAttribute(Qt.WA_TransparentForMouseEvents, True)

        content = QWidget()
        content.setAttribute(Qt.WA_TransparentForMouseEvents, True)
        content_layout = QVBoxLayout()
        content_layout.setContentsMargins(0, 0, 0, 0)
        content_layout.setSpacing(0)
        name_label = QLabel(str(action.get("name", "")))
        name_label.setObjectName("quickActionName")
        name_label.setWordWrap(True)
        name_label.setFixedHeight(metrics.card_title_height)
        name_label.setToolTip(str(action.get("name", "")))
        name_label.setAttribute(Qt.WA_TransparentForMouseEvents, True)

        subtitle_label = QLabel(description)
        subtitle_label.setObjectName("quickActionDescription")
        subtitle_label.setFixedHeight(metrics.card_subtitle_height)
        subtitle_label.setAttribute(Qt.WA_TransparentForMouseEvents, True)

        details_row = QHBoxLayout()
        details_row.setContentsMargins(0, 0, 0, 0)
        details_row.setSpacing(metrics.card_details_spacing)
        badge_label = QLabel(badge)
        badge_label.setObjectName("quickActionBadge")
        badge_label.setFixedSize(metrics.card_badge_width, metrics.card_badge_height)
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

        self.menu_button = QPushButton("›")
        self.menu_button.setObjectName("quickActionMenuButton")
        self.menu_button.setFixedSize(metrics.card_menu_btn_size, metrics.card_menu_btn_size)
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
    """Responsive no-activate runtime popup with filtered, paged Quick Actions."""

    ACTIONS_PER_PAGE = 8
    QUICK_WINDOW_SIZE = (560, 550)
    QUICK_CARD_HEIGHT = 78
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
        self.metrics = compute_quick_action_metrics()
        self.base_stylesheet: str = ""
        self.setup_ui()

    def setup_ui(self) -> None:
        self.setWindowTitle("Quick Actions")
        self.setObjectName("quickActionWindow")
        self.setFixedSize(self.metrics.win_width, self.metrics.win_height)
        self.setWindowFlags(
            Qt.Window
            | Qt.WindowStaysOnTopHint
            | Qt.CustomizeWindowHint
            | Qt.WindowTitleHint
            | Qt.WindowDoesNotAcceptFocus
        )
        self.setAttribute(Qt.WA_ShowWithoutActivating, True)

        self.root_layout = QVBoxLayout()
        self.root_layout.setContentsMargins(
            self.metrics.outer_margin,
            self.metrics.outer_margin,
            self.metrics.outer_margin,
            self.metrics.outer_margin,
        )
        self.root_layout.setSpacing(self.metrics.layout_spacing)

        self.title_row = QHBoxLayout()
        self.title_row.setContentsMargins(2, 0, 2, 0)
        self.title_icon = QLabel("⚡")
        self.title_icon.setObjectName("quickActionTitleIcon")
        self.title_text = QLabel("Quick Actions")
        self.title_text.setObjectName("quickActionsTitle")
        self.title_row.addWidget(self.title_icon)
        self.title_row.addWidget(self.title_text)
        self.title_row.addStretch()

        self.search_row = QHBoxLayout()
        self.search_row.setSpacing(max(6, int(round(12 * self.metrics.scale))))
        self.search_input = QLineEdit()
        self.search_input.setObjectName("quickActionSearch")
        self.search_input.setPlaceholderText("Search actions")
        self.search_input.setClearButtonEnabled(True)
        self.search_input.setFixedHeight(self.metrics.search_height)
        self.close_button = QPushButton("Hide")
        self.close_button.setObjectName("quickActionHideButton")
        self.close_button.setFixedSize(self.metrics.hide_btn_width, self.metrics.hide_btn_height)
        self.close_button.clicked.connect(self.on_close)
        self.search_row.addWidget(self.search_input, 1)
        self.search_row.addWidget(self.close_button)

        self.filter_row = QHBoxLayout()
        self.filter_row.setSpacing(self.metrics.filter_spacing)
        self.category_group = QButtonGroup(self)
        self.category_group.setExclusive(True)
        self.category_buttons = {}
        for category, label in (("all", "All"), ("login", "Login"), ("share", "Share"), ("tools", "Tools")):
            button = QPushButton(label)
            button.setObjectName("categoryFilterButton")
            button.setCheckable(True)
            button.setFixedHeight(self.metrics.category_btn_height)
            button.clicked.connect(lambda _checked=False, value=category: self.set_category(value))
            self.category_group.addButton(button)
            self.category_buttons[category] = button
            self.filter_row.addWidget(button)
        self.category_buttons["all"].setChecked(True)
        self.filter_row.addStretch()

        self.action_grid_container = QWidget()
        self.action_grid_container.setObjectName("quickActionGrid")
        self.action_grid = QGridLayout()
        self.action_grid.setContentsMargins(0, 0, 0, 0)
        self.action_grid.setHorizontalSpacing(self.metrics.grid_gap)
        self.action_grid.setVerticalSpacing(self.metrics.grid_gap)
        self.action_grid.setColumnStretch(0, 1)
        self.action_grid.setColumnStretch(1, 1)
        for row in range(4):
            self.action_grid.setRowMinimumHeight(row, self.metrics.card_height)
        self.action_grid_container.setLayout(self.action_grid)
        self.action_grid_container.setFixedHeight(self.metrics.grid_container_height)

        self.pagination_widget = QWidget()
        self.pagination_widget.setObjectName("quickActionPagination")
        self.pagination_row = QHBoxLayout()
        self.pagination_row.setContentsMargins(0, 0, 0, 0)
        self.pagination_row.setSpacing(self.metrics.pagination_spacing)
        self.previous_button = QPushButton("‹")
        self.previous_button.setObjectName("secondaryButton")
        self.previous_button.setFixedSize(self.metrics.page_btn_width, self.metrics.page_btn_height)
        self.previous_button.clicked.connect(self.previous_page)
        self.page_indicator = QLabel()
        self.page_indicator.setAlignment(Qt.AlignCenter)
        self.next_button = QPushButton("›")
        self.next_button.setObjectName("secondaryButton")
        self.next_button.setFixedSize(self.metrics.page_btn_width, self.metrics.page_btn_height)
        self.next_button.clicked.connect(self.next_page)
        self.pagination_row.addStretch()
        self.pagination_row.addWidget(self.previous_button)
        self.pagination_row.addWidget(self.page_indicator)
        self.pagination_row.addWidget(self.next_button)
        self.pagination_row.addStretch()
        self.pagination_widget.setLayout(self.pagination_row)

        self.add_button = QPushButton("+ Add Quick Action")
        self.add_button.setObjectName("quickActionAddButton")
        self.add_button.setFixedHeight(self.metrics.add_btn_height)
        self.add_button.clicked.connect(self.on_add_action)

        self.root_layout.addLayout(self.title_row)
        self.root_layout.addLayout(self.search_row)
        self.root_layout.addLayout(self.filter_row)
        self.root_layout.addWidget(self.action_grid_container)
        self.root_layout.addWidget(self.pagination_widget)
        self.root_layout.addWidget(self.add_button)
        self.setLayout(self.root_layout)
        self.search_input.textChanged.connect(self.reset_to_first_page)
        self.update_responsive_style()

    def update_responsive_style(self, base_stylesheet: Optional[str] = None) -> None:
        if base_stylesheet is not None:
            self.base_stylesheet = base_stylesheet
        self.setStyleSheet(self.base_stylesheet + generate_quick_action_stylesheet(self.metrics))

    def apply_metrics(self, metrics: QuickActionMetrics) -> None:
        self.metrics = metrics
        self.setFixedSize(metrics.win_width, metrics.win_height)
        self.root_layout.setContentsMargins(
            metrics.outer_margin,
            metrics.outer_margin,
            metrics.outer_margin,
            metrics.outer_margin,
        )
        self.root_layout.setSpacing(metrics.layout_spacing)

        self.search_row.setSpacing(max(6, int(round(12 * metrics.scale))))
        self.search_input.setFixedHeight(metrics.search_height)
        self.close_button.setFixedSize(metrics.hide_btn_width, metrics.hide_btn_height)

        self.filter_row.setSpacing(metrics.filter_spacing)
        for button in self.category_buttons.values():
            button.setFixedHeight(metrics.category_btn_height)

        self.action_grid.setHorizontalSpacing(metrics.grid_gap)
        self.action_grid.setVerticalSpacing(metrics.grid_gap)
        for row in range(4):
            self.action_grid.setRowMinimumHeight(row, metrics.card_height)
        self.action_grid_container.setFixedHeight(metrics.grid_container_height)

        self.pagination_row.setSpacing(metrics.pagination_spacing)
        self.previous_button.setFixedSize(metrics.page_btn_width, metrics.page_btn_height)
        self.next_button.setFixedSize(metrics.page_btn_width, metrics.page_btn_height)

        self.add_button.setFixedHeight(metrics.add_btn_height)
        self.update_responsive_style()
        self.refresh_actions(reset_page=False)

    def ensure_responsive_metrics(self) -> None:
        screen = self.screen() or QApplication.primaryScreen()
        if screen:
            geom = screen.availableGeometry()
            new_metrics = compute_quick_action_metrics(geom)
            if (
                abs(new_metrics.scale - self.metrics.scale) > 0.001
                or new_metrics.win_width != self.metrics.win_width
                or new_metrics.win_height != self.metrics.win_height
            ):
                self.apply_metrics(new_metrics)

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
                    metrics=self.metrics,
                )
                self.action_grid.addWidget(card, index // 2, index % 2)
            # Keep both columns and all four rows geometrically stable on partial pages.
            for index in range(len(page_actions), self.ACTIONS_PER_PAGE):
                placeholder = QWidget()
                placeholder.setObjectName("quickActionPlaceholder")
                placeholder.setFixedHeight(self.metrics.card_height)
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
        self.ensure_responsive_metrics()
        self.position_near_launcher()
        self.reassert_topmost()

    def position_near_launcher(self) -> None:
        screen = self.screen() or QApplication.primaryScreen()
        avail = screen.availableGeometry() if screen else QRect(0, 0, 1920, 1080)
        margin = max(12, int(round(84 * self.metrics.scale)))
        x = avail.right() - self.width() - margin
        x = max(avail.left() + 8, min(x, avail.right() - self.width() - 8))
        y = avail.top() + (avail.height() - self.height()) // 2
        y = max(avail.top() + 8, min(y, avail.bottom() - self.height() - 8))
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
    """Connects the floating launcher, OSK launcher, and Quick Actions window."""

    def __init__(self):
        self._win_event_callback = None
        self._win_event_hook = None
        self.quick_target_hwnd: int = 0
        self.action_store = QuickActionStore()
        self.actions = self.action_store.load()
        self.keyboard_controller = Controller()
        self.floating_button_window = FloatingButtonWindow(
            self.show_keyboard, self.show_quick_actions, self.open_data_folder
        )
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

    def send_login_sequence(self, username: str, password: str, target_hwnd: int) -> bool:
        """Send Username, Tab, Password, Enter to a frozen external target."""
        if not target_hwnd:
            return False
        set_foreground_window_handle(target_hwnd)
        try:
            self.keyboard_controller.type(username)
            self.keyboard_controller.press(Key.tab)
            self.keyboard_controller.release(Key.tab)
            self.keyboard_controller.type(password)
            self.keyboard_controller.press(Key.enter)
            self.keyboard_controller.release(Key.enter)
            return True
        except (ValueError, OSError) as error:
            print(f"Could not send Quick Action login sequence: {error}", file=sys.stderr)
            return False

    def apply_stylesheet(self) -> None:
        self.base_stylesheet = """
            QWidget {
                background-color: #121212;
                color: #EAEAEA;
                font-family: "Segoe UI";
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

            QPushButton#secondaryButton {
                background-color: #222222;
                color: #F7F7F7;
                border: 1px solid #303030;
                padding: 8px 12px;
                font-size: 15px;
                font-weight: 500;
            }

            QPushButton#secondaryButton:hover {
                background-color: #2E2E2E;
            }

            QPushButton#secondaryButton:pressed {
                background-color: #3A3A3A;
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
        """
        self.stylesheet = self.base_stylesheet + generate_quick_action_stylesheet(self.quick_action_window.metrics)
        self.floating_button_window.setStyleSheet(self.stylesheet)
        self.quick_action_window.update_responsive_style(self.base_stylesheet)

    def show_keyboard(self) -> None:
        launch_on_screen_keyboard()
        self.floating_button_window.reassert_topmost()

    def _is_utility_window(self, hwnd: int) -> bool:
        if not hwnd:
            return True
        utility_windows = (
            self.floating_button_window,
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
            sent = self.send_login_sequence(
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

    def open_data_folder(self) -> None:
        """Open the location containing data.json in Windows Explorer."""
        target_path = os.path.normpath(self.action_store.path)
        if os.path.exists(target_path):
            try:
                subprocess.Popen(f'explorer.exe /select,"{target_path}"')
                return
            except Exception:
                pass
        target_dir = os.path.normpath(os.path.dirname(target_path))
        if os.path.exists(target_dir):
            try:
                subprocess.Popen(f'explorer.exe "{target_dir}"')
            except Exception:
                pass

    def refresh_visible_topmost(self) -> None:
        for window in (
            self.floating_button_window,
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
