"""Mac keyboard capture and simulation.

Capture: tkinter <KeyPress> event binding (no system permissions needed).
Simulation: pynput.keyboard.Controller via Quartz/CGEventPost.
"""
from __future__ import annotations
import logging

log = logging.getLogger(__name__)

# ── Simulation: pynput key controller ─────────────────────────────
from pynput import keyboard as _pynput
from pynput.keyboard import Key, KeyCode

_controller = None

def get_controller():
    global _controller
    if _controller is None:
        try:
            _controller = _pynput.Controller()
        except Exception as e:
            log.error(f"Failed to initialize pynput keyboard Controller: {e}")
    return _controller


def _key(name: str):
    return getattr(Key, name, None)


_VK_TO_KEY = {
    0x08: Key.backspace, 0x09: Key.tab,      0x0D: Key.enter,
    0x1B: Key.esc,       0x20: Key.space,    0x2E: Key.delete,
    0x21: Key.page_up,   0x22: Key.page_down, 0x23: Key.end,
    0x24: Key.home,      0x25: Key.left,     0x26: Key.up,
    0x27: Key.right,     0x28: Key.down,     0x2D: _key('insert'),
    0x2C: _key('print_screen'), 0x13: _key('pause'),
    0x14: _key('caps_lock'), 0x90: _key('num_lock'),
    0x6A: KeyCode.from_char("*"), 0x6B: KeyCode.from_char("+"),
    0x6D: KeyCode.from_char("-"), 0x6E: KeyCode.from_char("."),
    0x6F: KeyCode.from_char("/"),
    0x70: Key.f1,  0x71: Key.f2,  0x72: Key.f3,  0x73: Key.f4,
    0x74: Key.f5,  0x75: Key.f6,  0x76: Key.f7,  0x77: Key.f8,
    0x78: Key.f9,  0x79: Key.f10, 0x7A: Key.f11, 0x7B: Key.f12,
}
_VK_TO_KEY = {k: v for k, v in _VK_TO_KEY.items() if v is not None}


def _vk_to_key(vk: int):
    if vk in _VK_TO_KEY:
        return _VK_TO_KEY[vk]
    if 0x20 <= vk <= 0x7E:
        return KeyCode.from_char(chr(vk))
    return None


def key_down(vk: int, modifier: int = 0):
    ctrl = get_controller()
    if not ctrl:
        return
    try:
        if modifier & 0x01: ctrl.press(Key.ctrl_l)
        if modifier & 0x02: ctrl.press(Key.shift_l)
        if modifier & 0x04: ctrl.press(Key.alt_l)
        if modifier & 0x08: ctrl.press(Key.cmd_l)
        if modifier & 0x10: ctrl.press(Key.ctrl_r)
        if modifier & 0x20: ctrl.press(Key.shift_r)
        if modifier & 0x40: ctrl.press(Key.alt_r)
        if modifier & 0x80: ctrl.press(Key.cmd_r)
        key = _vk_to_key(vk)
        if key:
            ctrl.press(key)
    except Exception as e:
        log.error(f"key_down error: {e}")


def key_up(vk: int, modifier: int = 0):
    ctrl = get_controller()
    if not ctrl:
        return
    try:
        key = _vk_to_key(vk)
        if key:
            ctrl.release(key)
        if modifier & 0x80: ctrl.release(Key.cmd_r)
        if modifier & 0x40: ctrl.release(Key.alt_r)
        if modifier & 0x20: ctrl.release(Key.shift_r)
        if modifier & 0x10: ctrl.release(Key.ctrl_r)
        if modifier & 0x08: ctrl.release(Key.cmd_l)
        if modifier & 0x04: ctrl.release(Key.alt_l)
        if modifier & 0x02: ctrl.release(Key.shift_l)
        if modifier & 0x01: ctrl.release(Key.ctrl_l)
    except Exception as e:
        log.error(f"key_up error: {e}")


# ── Key name map (shared with Windows version) ────────────────────
_KEY_NAMES = {
    0x08: "Backspace", 0x09: "Tab", 0x0D: "Enter", 0x10: "Shift",
    0x11: "Ctrl", 0x12: "Alt", 0x13: "Pause", 0x14: "CapsLock",
    0x1B: "Escape", 0x20: "Space", 0x21: "PageUp", 0x22: "PageDown",
    0x23: "End", 0x24: "Home", 0x25: "Left", 0x26: "Up",
    0x27: "Right", 0x28: "Down", 0x2C: "PrintScreen", 0x2D: "Insert",
    0x2E: "Delete",
    0x30: "0", 0x31: "1", 0x32: "2", 0x33: "3", 0x34: "4",
    0x35: "5", 0x36: "6", 0x37: "7", 0x38: "8", 0x39: "9",
    0x41: "A", 0x42: "B", 0x43: "C", 0x44: "D", 0x45: "E",
    0x46: "F", 0x47: "G", 0x48: "H", 0x49: "I", 0x4A: "J",
    0x4B: "K", 0x4C: "L", 0x4D: "M", 0x4E: "N", 0x4F: "O",
    0x50: "P", 0x51: "Q", 0x52: "R", 0x53: "S", 0x54: "T",
    0x55: "U", 0x56: "V", 0x57: "W", 0x58: "X", 0x59: "Y",
    0x5A: "Z", 0x5B: "LCmd", 0x5C: "RCmd",
    0x70: "F1", 0x71: "F2", 0x72: "F3", 0x73: "F4",
    0x74: "F5", 0x75: "F6", 0x76: "F7", 0x77: "F8",
    0x78: "F9", 0x79: "F10", 0x7A: "F11", 0x7B: "F12",
    0xA0: "LShift", 0xA1: "RShift", 0xA2: "LCtrl",
    0xA3: "RCtrl", 0xA4: "LOption", 0xA5: "ROption",
}


def vk_name(vk: int) -> str:
    return _KEY_NAMES.get(vk, f"VK_{vk:02X}")


_MOD_NAMES = [
    (0x01, "LCtrl"), (0x02, "LShift"), (0x04, "LOption"), (0x08, "LCmd"),
    (0x10, "RCtrl"), (0x20, "RShift"), (0x40, "ROption"), (0x80, "RCmd"),
]


def build_display(vk: int, modifier: int) -> str:
    parts = [name for mask, name in _MOD_NAMES if modifier & mask]
    parts.append(vk_name(vk))
    return "+".join(parts)


# ── Capture: tkinter event binding (no system permissions) ─────────
# Simple and reliable: bind <KeyPress> on the root window, capture
# the next key, then unbind.  Works in any tkinter app.

_tk_bind_id = None
_tk_root = None
_tk_callback = None

# tkinter keysym → Windows VK for non-printable special keys
_KEYSYM_TO_VK = {
    "BackSpace": 0x08, "Tab": 0x09, "Return": 0x0D, "Escape": 0x1B,
    "space": 0x20, "Delete": 0x2E,
    "Page_Up": 0x21, "Page_Down": 0x22, "End": 0x23, "Home": 0x24,
    "Left": 0x25, "Up": 0x26, "Right": 0x27, "Down": 0x28,
    "Insert": 0x2D, "Pause": 0x13, "Print": 0x2C,
    "Caps_Lock": 0x14, "Num_Lock": 0x90, "Scroll_Lock": 0x91,
    "Shift_L": 0xA0, "Shift_R": 0xA1,
    "Control_L": 0xA2, "Control_R": 0xA3,
    "Alt_L": 0xA4, "Alt_R": 0xA5,
    "Meta_L": 0x5B, "Meta_R": 0x5C,
    "Menu": 0x5D,
    "KP_Enter": 0x0D, "KP_Multiply": 0x6A, "KP_Add": 0x6B,
    "KP_Subtract": 0x6D, "KP_Decimal": 0x6E, "KP_Divide": 0x6F,
    "F1": 0x70, "F2": 0x71, "F3": 0x72, "F4": 0x73,
    "F5": 0x74, "F6": 0x75, "F7": 0x76, "F8": 0x77,
    "F9": 0x78, "F10": 0x79, "F11": 0x7A, "F12": 0x7B,
}


def _tk_event_to_vk(event) -> int | None:
    """Convert a tkinter <KeyPress> event to Windows VK code."""
    if event.keysym in _KEYSYM_TO_VK:
        return _KEYSYM_TO_VK[event.keysym]
    if event.char and len(event.char) == 1:
        c = event.char.upper()
        if 0x20 <= ord(c) <= 0x7E:
            return ord(c)
    return None


def _on_tk_keypress(event):
    cb = _tk_callback
    if cb is None:
        return
    vk = _tk_event_to_vk(event)
    if vk:
        cb(vk, 0, 0)
    stop_key_capture()


def start_key_capture(callback, tk_root=None):
    """Bind <KeyPress> to capture the next key press.

    `callback(vk, is_extended, scan_code)` — is_extended and scan_code
    are always 0 on macOS (not applicable).

    Does NOT require Accessibility permission. Returns True always.
    """
    global _tk_bind_id, _tk_callback, _tk_root
    _tk_callback = callback
    _tk_root = tk_root
    if tk_root:
        _tk_bind_id = tk_root.bind("<KeyPress>", _on_tk_keypress, add="+")
    log.info("Key capture started (tkinter bind)")
    return True


def stop_key_capture():
    global _tk_bind_id, _tk_callback, _tk_root
    _tk_callback = None
    if _tk_root and _tk_bind_id:
        try:
            _tk_root.unbind("<KeyPress>", _tk_bind_id)
        except Exception:
            pass
        _tk_bind_id = None
        _tk_root = None
    log.info("Key capture stopped")


def map_modifier_vk(vk: int, is_extended: bool) -> int:
    if vk == 0x11:
        return 0xA3 if is_extended else 0xA2
    if vk == 0x10:
        return 0xA1 if is_extended else 0xA0
    if vk == 0x12:
        return 0xA5 if is_extended else 0xA4
    return vk
