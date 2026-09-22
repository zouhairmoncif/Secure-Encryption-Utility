"""BIOS-style Secure Encryption Utility — controller + all screens.

Three-layer architecture
----------------------------
presentation  : VGAGrid + ui/form primitives + the Screen classes here
controller    : SeuController (keyboard routing, job dispatch, state)
business      : seu_crypto / keystore / settings_store / secure_delete /
                encryption / file_manager / gui.history

Panic rules for this file: never block the UI thread -> file operations and
RSA key generation run on a QThread; grid writes only ever happen from the
main thread (paint/paintEvent + key handlers).
"""

import os
from pathlib import Path

from PyQt5.QtCore import QObject, Qt, QTimer, pyqtSignal
from PyQt5.QtWidgets import QApplication, QFileDialog, QWidget

import file_manager
import seu_crypto as sc
import settings_store
from gui.history import HISTORY_PATH, HistoryManager
from gui.seu import form as fform
from gui.seu import ui
from gui.seu.vga import ROWS, VGAGrid

ALGO_KEYS = ["AES-256-GCM", "AES-256-CBC + HMAC", "ChaCha20-Poly1305", "RSA-4096 + AES-256"]

MENU_ITEMS = [
    ("Encrypt File", "goto:ENCRYPT_FILE",
     "Encrypt a file using the active encryption key. The output is a"
     " self-describing SEU1 container that stores the cipher, the original"
     " name and an authentication tag for integrity."),
    ("Decrypt File", "goto:DECRYPT_FILE",
     "Decrypt a previously encrypted SEU1 file. The cipher is detected"
     " automatically from the container header, so the right key and settings"
     " are used without any extra configuration."),
    ("Encrypt Text", "goto:ENCRYPT_TEXT",
     "Quick-encrypt a text snippet to the secure clipboard. The ciphertext is"
     " encoded as printable Base64, hexadecimal or raw text so it can be pasted"
     " into any message."),
    ("Decrypt Text", "goto:DECRYPT_TEXT",
     "Decrypt text previously secured to the secure clipboard. Paste the"
     " ciphertext, pick the codec it was stored in, and the utility restores"
     " the original message."),
    ("Generate Encryption Key", "goto:GENERATE_KEY",
     "Generate a new 256-bit AES key (or a 4096-bit RSA key pair) for use"
     " with file encryption. Generated keys are stored in the encrypted key"
     " store and become the active key."),
    ("Manage Encryption Keys", "goto:MANAGE_KEYS",
     "View, rename, set active, and delete stored keys. Every key shows its"
     " algorithm and a SHA-256 fingerprint so you always know which key is"
     " doing the work."),
    ("Select Encryption Algorithm", "goto:SELECT_ALGO",
     "Select the cipher for new encryption operations and for newly generated"
     " keys: AES-256-GCM, AES-256-CBC + HMAC, ChaCha20-Poly1305 or RSA-4096"
     " + OAEP."),
    ("View Encryption History", "goto:HISTORY",
     "View the last 200 encryption/decryption operations. The log keeps the"
     " file names, sizes, and the exact time each operation ran."),
    ("Secure File Deletion", "goto:SECURE_DELETE",
     "Securely wipe a file so it cannot be recovered. Implements the real"
     " DoD 5220.22-M and Gutmann 35-pass overwrite schemes with fsync between"
     " passes."),
    ("Import Key", "goto:IMPORT_KEY",
     "Bring in an external key from a portable file. Symmetric keys are"
     " exchanged as Base64 text, RSA keys as standard PEM."),
    ("Export Key", "goto:EXPORT_KEY",
     "Export an existing key to a portable Base64 text file (or PEM for RSA"
     " keys). The export can then be imported on a different machine."),
    ("Application Settings", "goto:SETTINGS",
     "Adjust output naming, secure-delete, date format, clipboard behavior and"
     " the CRT display effects."),
    ("System Diagnostics", "goto:DIAGNOSTICS",
     "Self-test the cipher engines and key store integrity. Runs real"
     " encrypt/decrypt round-trips on every supported algorithm."),
    ("About", "goto:ABOUT",
     "About — gluggle stumbles & mental notifications."),
    ("Exit", "action:exit",
     "Leave setup and return to the host operating system."),
]

HELP_LINES = [
    ("KEY", "ACTION"),
    ("Up / Down", "Move cursor (wrap around)"),
    ("Left / Right", "Move cursor / change value"),
    ("Tab", "Next field    Shift+Tab previous field"),
    ("Enter", "Select or confirm / next field"),
    ("Space", "Toggle a value / activate"),
    ("Esc / F10", "Back / exit (with confirmation)"),
    ("F1", "This help screen"),
    ("F2", "Browse for a file"),
    ("F4", "Browse for a folder"),
    ("F3", "Open the key manager"),
    ("F5", "Run / rerun diagnostic tests"),
    ("F6", "Clear the list"),
    ("F7", "Copy result to clipboard"),
    ("F11", "Toggle fullscreen"),
    ("Home / End", "First / last item"),
    ("1-9, 0", "Jump to a menu item"),
    ("Del", "Delete item"),
]


def classify_error(exc):
    """Map a raised exception to a BIOS-style (code, detail) pair."""
    if isinstance(exc, sc.SeuError):
        msg = str(exc)
        if msg.startswith("E_"):
            code, _, detail = msg.partition(":")
            return code.strip(), detail.strip()
        return "E_INTERNAL", msg
    if isinstance(exc, FileNotFoundError):
        return "E_FILE_NOT_FOUND", "Source file not found: %s" % exc
    if isinstance(exc, PermissionError):
        return "E_FILE_UNREADABLE", "Permission denied: %s" % exc
    if isinstance(exc, IsADirectoryError):
        return "E_FILE_UNREADABLE", "Path is a directory: %s" % exc
    if isinstance(exc, OSError):
        return "E_DIR_UNWRITABLE", "I/O error: %s" % exc
    return "E_INTERNAL", str(exc) or type(exc).__name__


class _PosterReaper:
    """Owns active job posters so pending queued events are never dropped."""

    _holders = []

    @classmethod
    def keep(cls, poster):
        cls._holders.append(poster)
        return poster

    @classmethod
    def release(cls, poster):
        try:
            cls._holders.remove(poster)
        except ValueError:
            pass


class _Poster(QObject):
    """Marshals worker-thread events back to the Qt main thread (queued)."""

    posted = pyqtSignal(str, object)

    def __init__(self, parent=None):
        super().__init__(parent)
        self.route = None

    def handle(self, kind, payload):
        if self.route:
            return self.route(kind, payload)


def run_job(run_fn, cancel_check, on_progress, on_done, on_error):
    """Run `run_fn(report, is_cancelled)` on a daemon thread and hand the
    result/exception and progress events back to the Qt main thread via a
    queued signal (the canonical thread-safe Qt pattern)."""
    import threading

    poster = _Poster()
    _PosterReaper.keep(poster)

    def route(kind, payload):
        try:
            if kind == "progress":
                on_progress(*payload)
            elif kind == "done":
                on_done(payload)
            elif kind == "error":
                on_error(payload)
        finally:
            if kind in ("done", "error"):
                _PosterReaper.release(poster)

    poster.route = route
    poster.posted.connect(poster.handle, Qt.QueuedConnection)

    def report(pct, status):
        poster.posted.emit("progress", (pct, status))

    def check():
        return bool(cancel_check and cancel_check())

    def worker():
        try:
            result = run_fn(report, check)
        except Exception as exc:  # noqa: BLE001
            poster.posted.emit("error", exc)
            return
        poster.posted.emit("done", result)

    threading.Thread(target=worker, daemon=True).start()


class ScreenBase:
    name = ""
    title = ""

    def enter(self, ctrl):
        pass

    def render(self, g, ctrl):
        pass

    def handle(self, key, mods, ctrl):
        if key == "esc":
            ctrl.goto("MAIN_MENU")
        elif key == "f1":
            ctrl.push_help()

    def _draw_shell(self, g):
        ui.title_bar(g, self.title)
        ui.separator(g)
        ui.footer(g)


# ---------------------------------------------------------------------------
# boot / exit
# ---------------------------------------------------------------------------

class InitScreen(ScreenBase):
    name = "INITIALIZING"
    title = "SECURE ENCRYPTION UTILITY v1.0"

    def enter(self, ctrl):
        QTimer.singleShot(850, lambda: ctrl.goto("MAIN_MENU"))

    def render(self, g, ctrl):
        self._draw_shell(g)
        lines = [
            ("SECURE ENCRYPTION UTILITY", "bright"),
            ("v1.0", "dim"),
            ("", None),
            ("Cipher engines ....... loading", "text"),
            ("AES-256-GCM ............ ready", "success"),
            ("AES-256-CBC + HMAC ..... ready", "success"),
            ("ChaCha20-Poly1305 ...... ready", "success"),
            ("RSA-4096 + OAEP ........ ready", "success"),
            ("", None),
            ("Key store ............. loading", "text"),
            ("Key store integrity .... verified", "success") if ctrl.safe else ("Key store integrity .... FAULT", "error"),
            ("", None),
            ("User interface ......... ready", "text"),
            ("", None),
            ("Press any key to continue", "dim"),
        ]
        row = 3
        for text, color in lines:
            if text:
                g.put(4, row, text, color or "text", "bg")
            row += 1

    def handle(self, key, mods, ctrl):
        ctrl.goto("MAIN_MENU")


class MainMenuScreen(ScreenBase):
    name = "MAIN_MENU"
    title = "SECURE ENCRYPTION UTILITY v1.0"

    def enter(self, ctrl):
        self.sel = 0

    def render(self, g, ctrl):
        self._draw_shell(g)
        for i, (label, action, desc) in enumerate(MENU_ITEMS):
            row = 2 + i
            if i == self.sel:
                g.fill(0, row, 38, 1, " ", "hlt", "hlb")
                g.put(1, row, "►", "hlt", "hlb")
                g.put(3, row, label, "hlt", "hlb")
            else:
                g.put(3, row, label, "text", "bg")
        # description panel
        label, action, desc = MENU_ITEMS[self.sel]
        width = 36
        lines = ui.wrap(desc, width)
        ui.panel(g, 40, 2, 38, 21, title="Description", lines=lines, fg="text")

    def handle(self, key, mods, ctrl):
        n = len(MENU_ITEMS)
        if key in ("up", "left"):
            self.sel = (self.sel - 1) % n
            ctrl.refresh()
            return
        if key in ("down", "right"):
            self.sel = (self.sel + 1) % n
            ctrl.refresh()
            return
        if key == "home":
            self.sel = 0
            ctrl.refresh()
            return
        if key == "end":
            self.sel = n - 1
            ctrl.refresh()
            return
        if key == "enter":
            self._activate(ctrl)
            return
        if key == "f10":
            ctrl.goto("EXIT_CONFIRM")
            return
        if key == "esc":
            ctrl.goto("EXIT_CONFIRM")
            return
        if key == "type":
            digit = mods.get("text", "")
            if digit in "0123456789":
                idx = 9 if digit == "0" else int(digit) - 1
                if 0 <= idx < n:
                    self.sel = idx
                    ctrl.refresh()
            return

    def _activate(self, ctrl):
        label, action, desc = MENU_ITEMS[self.sel]
        if action.startswith("goto:"):
            ctrl.goto(action[5:])
        elif action == "action:exit":
            ctrl.goto("EXIT_CONFIRM")


class ExitConfirmScreen(ScreenBase):
    name = "EXIT_CONFIRM"
    title = "EXIT CONFIRMATION"

    def enter(self, ctrl):
        self.sel = 1  # default: No

    def render(self, g, ctrl):
        self._draw_shell(g)
        msg = "Exit the Secure Encryption Utility?"
        x = (80 - len(msg)) // 2
        g.put(x, 10, msg, "text", "bg")
        ui.panel(g, 26, 8, 28, 5, title="Confirm")
        g.put(34, 10, msg[:24], "text", "panelbg")
        y = 12
        if self.sel == 0:
            g.put(31, y, "[ Yes ]", "hlt", "hlb")
            g.put(40, y, "[ No ]", "text", "bg")
        else:
            g.put(31, y, "[ Yes ]", "text", "bg")
            g.put(40, y, "[ No ]", "hlt", "hlb")

    def handle(self, key, mods, ctrl):
        if key in ("up", "down"):
            return
        if key in ("left", "right", "tab"):
            self.sel = 1 - self.sel
            ctrl.refresh()
            return
        if key == "enter":
            if self.sel == 0:
                ctrl.exit_app()
            else:
                ctrl.goto("MAIN_MENU")
            return
        if key in ("esc", "f10"):
            ctrl.goto("MAIN_MENU")


# ---------------------------------------------------------------------------
# form screens
# ---------------------------------------------------------------------------

class FileEncryptScreen(ScreenBase):
    name = "ENCRYPT_FILE"
    title = "ENCRYPT FILE"

    def enter(self, ctrl):
        self.fields = [
            {"kind": "kv", "label": "Active key", "value": ""},
            {"kind": "kv", "label": "Algorithm", "value": ""},
            {"kind": "input", "label": "Source file", "value": "", "caret": 0, "width": 40},
            {"kind": "input", "label": "Output file", "value": "", "caret": 0, "width": 40},
            {"kind": "toggle", "label": "Overwrite", "value": False},
            {"kind": "toggle", "label": "Secure-delete", "value": bool(ctrl.settings.get("wipe_source_after_encrypt"))},
            {"kind": "button", "label": "", "label2": "Encrypt Now", "value": "ok"},
        ]
        self.focus = 2
        self._output_custom = False

    def _kv_fill(self, ctrl):
        act = ctrl.keys.get_active()
        if act:
            self.fields[0]["value"] = "%s (%s)" % (act["name"], act["algo"])
            self.fields[1]["value"] = act["algo"]
        else:
            self.fields[0]["value"] = "— none set —  (F3 key manager)"
            self.fields[1]["value"] = ctrl.settings.get("algo")

    def render(self, g, ctrl):
        self._draw_shell(g)
        self._kv_fill(ctrl)
        row = 3
        fform.render(g, self.fields, self.focus, row)
        g.put(2, 11, "F2 Browse F3 Keys  F4 Folder", "keyhintdesc", "bg")
        if ctrl.keys.get_active():
            g.put(2, 12, "TIP: generated output renames .ext to .ext.enc", "dim", "bg")

    def _auto_output(self, ctrl):
        src = self.fields[2]["value"]
        if not src:
            return ""
        try:
            return file_manager.get_default_output_path(src, "encrypt")
        except Exception:
            return src + ".enc"

    def handle(self, key, mods, ctrl):
        if key == "f2":
            path, _ = QFileDialog.getOpenFileName(self.parent() if self.parent() else None,
                                                  "Select source file")
            if path:
                self.fields[2]["value"] = path
                self.fields[2]["caret"] = len(path)
                if not self._output_custom:
                    self.fields[3]["value"] = self._auto_output(ctrl)
            ctrl.refresh()
            return
        if key == "f3":
            ctrl.goto("MANAGE_KEYS")
            return
        if key == "f4":
            ctrl.goto("MANAGE_KEYS")
            return
        if key == "esc":
            ctrl.goto("MAIN_MENU")
            return
        if key == "f1":
            ctrl.push_help()
            return
        action, self.focus, ev = fform.handle(None, self.fields, self.focus, key, mods)
        if ev and ev is self.fields[2]:
            if not self._output_custom:
                self.fields[3]["value"] = self._auto_output(ctrl)
            self._output_custom = False
        if ev and ev is self.fields[3]:
            self._output_custom = True
        if action == "activate" and ev is self.fields[-1]:
            self._go(ctrl)
            return
        if action in ("focus", "changed") or ev:
            ctrl.refresh()

    def _go(self, ctrl):
        src = self.fields[2]["value"].strip()
        out = self.fields[3]["value"].strip()
        act = ctrl.ensure_active_key()
        if not act:
            return
        if not src:
            ctrl.route_error("E_FILE_NOT_FOUND", "You must choose a source file.")
            return
        if not os.path.exists(src):
            ctrl.route_error("E_FILE_NOT_FOUND", "Source file does not exist.")
            return
        if not out:
            out = self._auto_output(ctrl)
        if os.path.exists(out) and not self.fields[4]["value"]:
            ctrl.route_error("E_DIR_UNWRITABLE", "Output file exists.  Enable Overwrite to replace it.")
            return
        do_wipe = self.fields[5]["value"]

        def run(report, cancelled):
            try:
                data = file_manager.read_file(src)
            except OSError as exc:
                raise sc.SeuError("E_FILE_UNREADABLE: %s" % exc)
            report(25, "Reading source")
            if cancelled():
                raise sc.SeuError("E_CANCELLED: operation cancelled by user")
            material = ctrl.keys.key_material(act)
            container = sc.encrypt_data(data, Path(src).name, algo=sc.algo_id(act["algo"]), key=material)
            report(50, "Encrypting (%s)" % act["algo"])
            if cancelled():
                raise sc.SeuError("E_CANCELLED: operation cancelled by user")
            file_manager.write_file(out, container)
            ctrl.keys.mark_used(act["id"])
            report(85, "Writing output")
            wiped = False
            if do_wipe:
                import secure_delete

                secure_delete.wipe(src, method=ctrl.settings.get("secure_delete") or "dod",
                                   progress=lambda s, p: report(85 + int(p * 0.15), s))
                wiped = True
            report(100, "Done")
            ctrl.history.add("encrypt", src, out, len(container))
            return {
                "out": out, "size": len(container), "algo": act["algo"],
                "wiped": wiped, "src": src,
            }

        def done(result):
            lines = [
                "File encrypted successfully.",
                "",
                "Algorithm : %s" % result["algo"],
                "Output    : %s" % result["out"],
                "Size      : %s" % sc.format_size(result["size"]),
                "Source wiped: %s" % ("yes" if result["wiped"] else "no"),
            ]
            ctrl.show_success(lines)

        ctrl.run_job(run, done)


class FileDecryptScreen(ScreenBase):
    name = "DECRYPT_FILE"
    title = "DECRYPT FILE"

    def enter(self, ctrl):
        self.fields = [
            {"kind": "kv", "label": "Active key", "value": ""},
            {"kind": "input", "label": "Source file", "value": "", "caret": 0, "width": 40},
            {"kind": "input", "label": "Output file", "value": "", "caret": 0, "width": 40},
            {"kind": "input", "label": "Legacy passphrase", "value": "", "caret": 0, "width": 40},
            {"kind": "toggle", "label": "Overwrite", "value": False},
            {"kind": "button", "label": "", "label2": "Decrypt Now", "value": "ok"},
        ]
        self.focus = 1
        self._output_custom = False

    def render(self, g, ctrl):
        self._draw_shell(g)
        act = ctrl.keys.get_active()
        self.fields[0]["value"] = (
            "%s (%s)" % (act["name"], act["algo"]) if act else "— none set —"
        )
        row = 3
        fform.render(g, self.fields, self.focus, row)
        g.put(2, 11, "F2 Browse F3 Keys  F4 Folder  Legacy = password files", "keyhintdesc", "bg")

    def _auto_output(self, ctrl):
        src = self.fields[1]["value"]
        if not src:
            return ""
        try:
            return file_manager.get_default_output_path(src, "decrypt")
        except Exception:
            p = Path(src)
            return str(p.with_suffix("")) or src + ".dec"

    def handle(self, key, mods, ctrl):
        if key == "f2":
            path, _ = QFileDialog.getOpenFileName(None, "Select encrypted file")
            if path:
                self.fields[1]["value"] = path
                self.fields[1]["caret"] = len(path)
                if not self._output_custom:
                    self.fields[2]["value"] = self._auto_output(ctrl)
            ctrl.refresh()
            return
        if key == "f3":
            ctrl.goto("MANAGE_KEYS")
            return
        if key == "f4":
            ctrl.goto("MANAGE_KEYS")
            return
        if key == "esc":
            ctrl.goto("MAIN_MENU")
            return
        if key == "f1":
            ctrl.push_help()
            return
        action, self.focus, ev = fform.handle(None, self.fields, self.focus, key, mods)
        if ev and ev is self.fields[1] and not self._output_custom:
            self.fields[2]["value"] = self._auto_output(ctrl)
        if ev and ev is self.fields[2]:
            self._output_custom = True
        if action == "activate" and ev is self.fields[-1]:
            self._go(ctrl)
            return
        if action in ("focus", "changed") or ev:
            ctrl.refresh()

    def _go(self, ctrl):
        src = self.fields[1]["value"].strip()
        out = self.fields[2]["value"].strip()
        if not src or not os.path.exists(src):
            ctrl.route_error("E_FILE_NOT_FOUND", "Encrypted source file does not exist.")
            return
        if not out:
            out = self._auto_output(ctrl)
        if os.path.exists(out) and not self.fields[4]["value"]:
            ctrl.route_error("E_DIR_UNWRITABLE", "Output file exists.  Enable Overwrite to replace it.")
            return

        def run(report, cancelled):
            data = file_manager.read_file(src)
            algo_name = sc.detect_algo(data)
            report(20, "Detecting container format")
            if algo_name is None:
                legacy = self.fields[3]["value"]
                if not legacy:
                    raise sc.SeuError(
                        "E_FORMAT: not an SEU1 container; a legacy passphrase is required")
                import encryption

                plain = encryption.decrypt_data(data, legacy)
                report(70, "Decrypting (legacy engine)")
                file_manager.write_file(out, plain)
                report(100, "Done")
                ctrl.history.add("decrypt", src, out, len(plain))
                return {"out": out, "size": len(plain), "algo": "Fernet (legacy)"}

            act = ctrl.ensure_active_key()
            if not act:
                raise sc.SeuError("E_KEY_NOT_SET: no active key available")
            material = ctrl.keys.key_material(act)
            plain = sc.decrypt_data(data, key=material)
            report(70, "Decrypting (%s)" % act["algo"])
            file_manager.write_file(out, plain)
            ctrl.keys.mark_used(act["id"])
            report(100, "Done")
            ctrl.history.add("decrypt", src, out, len(plain))
            return {"out": out, "size": len(plain), "algo": algo_name}

        def done(result):
            lines = [
                "File decrypted successfully.",
                "",
                "Algorithm : %s" % result["algo"],
                "Output    : %s" % result["out"],
                "Size      : %s" % sc.format_size(result["size"]),
            ]
            ctrl.show_success(lines)

        ctrl.run_job(run, done)


class EncryptTextScreen(ScreenBase):
    name = "ENCRYPT_TEXT"
    title = "ENCRYPT TEXT"

    def enter(self, ctrl):
        self.fields = [
            {"kind": "kv", "label": "Active key", "value": ""},
            {"kind": "input", "label": "Plaintext", "value": "", "caret": 0, "width": 50},
            {"kind": "choice", "label": "Output codec", "value": "base64",
             "options": list(sc.TEXT_CODECS)},
            {"kind": "button", "label": "", "label2": "Encrypt Text", "value": "ok"},
        ]
        self.focus = 1

    def render(self, g, ctrl):
        self._draw_shell(g)
        act = ctrl.keys.get_active()
        self.fields[0]["value"] = (
            "%s (%s)" % (act["name"], act["algo"]) if act else "— none set —"
        )
        row = 3
        fform.render(g, self.fields, self.focus, row)
        g.put(2, 10, "Result is copied to the clipboard (F7 re-copies).", "keyhintdesc", "bg")

    def handle(self, key, mods, ctrl):
        if key == "f3":
            ctrl.goto("MANAGE_KEYS")
            return
        if key == "esc":
            ctrl.goto("MAIN_MENU")
            return
        if key == "f1":
            ctrl.push_help()
            return
        action, self.focus, ev = fform.handle(None, self.fields, self.focus, key, mods)
        if action == "activate" and ev is self.fields[-1]:
            self._go(ctrl)
            return
        if action in ("focus", "changed") or ev:
            ctrl.refresh()

    def _go(self, ctrl):
        act = ctrl.ensure_active_key()
        if not act:
            return
        text = self.fields[1]["value"]
        if not text:
            ctrl.route_error("E_FORMAT", "Nothing to encrypt.")
            return
        codec = self.fields[2]["value"]

        def run(report, cancelled):
            material = ctrl.keys.key_material(act)
            container = sc.encrypt_data(text.encode("utf-8"), "text",
                                        algo=sc.algo_id(act["algo"]), key=material)
            report(90, "Encrypting")
            out_text = sc.encode_text(container, codec)
            report(100, "Done")
            ctrl.keys.mark_used(act["id"])
            ctrl.history.add("encrypt", "(clipboard)", "(text)", len(container))
            return {"text": out_text, "size": len(container), "algo": act["algo"], "codec": codec}

        def done(result):
            ctrl.clip = result["text"]
            QApplication.clipboard().setText(result["text"])
            lines = [
                "Text encrypted and stored in the clipboard.",
                "",
                "Algorithm : %s" % result["algo"],
                "Codec     : %s" % result["codec"],
                "Cipher size: %s" % sc.format_size(result["size"]),
            ]
            ctrl.show_success(lines, extra_ok=lambda g: self._show_text(g, ctrl, result["text"]))

        ctrl.run_job(run, done)

    def _show_text(self, g, ctrl, text):
        width = 58
        lines = ui.wrap(text, width)[:10]
        r = 10
        for ln in lines:
            g.put(2, r, ln, "text", "bg")
            r += 1


class DecryptTextScreen(ScreenBase):
    name = "DECRYPT_TEXT"
    title = "DECRYPT TEXT"

    def enter(self, ctrl):
        self.fields = [
            {"kind": "input", "label": "Cipher text", "value": "", "caret": 0, "width": 50},
            {"kind": "choice", "label": "Input codec", "value": "base64",
             "options": list(sc.TEXT_CODECS)},
            {"kind": "input", "label": "Legacy passphrase", "value": "", "caret": 0, "width": 50},
            {"kind": "button", "label": "", "label2": "Decrypt Text", "value": "ok"},
        ]
        self.focus = 0

    def render(self, g, ctrl):
        self._draw_shell(g)
        row = 3
        fform.render(g, self.fields, self.focus, row)
        g.put(2, 10, "Result is copied to the clipboard (F7 re-copies).", "keyhintdesc", "bg")

    def handle(self, key, mods, ctrl):
        if key == "esc":
            ctrl.goto("MAIN_MENU")
            return
        if key == "f1":
            ctrl.push_help()
            return
        action, self.focus, ev = fform.handle(None, self.fields, self.focus, key, mods)
        if action == "activate" and ev is self.fields[-1]:
            self._go(ctrl)
            return
        if action in ("focus", "changed") or ev:
            ctrl.refresh()

    def _go(self, ctrl):
        text = self.fields[0]["value"]
        if not text:
            ctrl.route_error("E_FORMAT", "Nothing to decrypt.")
            return
        codec = self.fields[1]["value"]

        def run(report, cancelled):
            data = sc.decode_text(text, codec)
            algo_name = sc.detect_algo(data)
            if algo_name is None:
                legacy = self.fields[2]["value"]
                if not legacy:
                    raise sc.SeuError("E_FORMAT: legacy ciphertext needs a passphrase")
                import encryption

                plain = encryption.decrypt_data(data, legacy)
            else:
                act = ctrl.ensure_active_key()
                if not act:
                    raise sc.SeuError("E_KEY_NOT_SET: no active key available")
                material = ctrl.keys.key_material(act)
                plain = sc.decrypt_data(data, key=material)
                ctrl.keys.mark_used(act["id"])
            report(100, "Done")
            ctrl.history.add("decrypt", "(text)", "(clipboard)", len(plain))
            try:
                out_text = plain.decode("utf-8")
            except UnicodeDecodeError:
                out_text = plain.decode("latin-1")
            return {"text": out_text, "size": len(plain), "algo": algo_name or "Fernet (legacy)"}

        def done(result):
            ctrl.clip = result["text"]
            QApplication.clipboard().setText(result["text"])
            lines = [
                "Text decrypted and stored in the clipboard.",
                "",
                "Algorithm : %s" % result["algo"],
                "Plain size: %s" % sc.format_size(result["size"]),
            ]
            ctrl.show_success(lines, extra_ok=lambda g: self._show_text(g, ctrl, result["text"]))

        ctrl.run_job(run, done)

    def _show_text(self, g, ctrl, text):
        sanitized = "".join(ch if 32 <= ord(ch) < 127 else "." for ch in text)
        lines = ui.wrap(sanitized, 58)[:10]
        r = 10
        for ln in lines:
            g.put(2, r, ln, "text", "bg")
            r += 1


class GenerateKeyScreen(ScreenBase):
    name = "GENERATE_KEY"
    title = "GENERATE ENCRYPTION KEY"

    def enter(self, ctrl):
        self.fields = [
            {"kind": "choice", "label": "Algorithm", "value": ctrl.settings.get("algo"),
             "options": ALGO_KEYS},
            {"kind": "input", "label": "Key name", "value": "", "caret": 0, "width": 40},
            {"kind": "button", "label": "", "label2": "Generate", "value": "ok"},
        ]
        self.focus = 0

    def render(self, g, ctrl):
        self._draw_shell(g)
        row = 3
        fform.render(g, self.fields, self.focus, row)
        g.put(2, 8, "RSA generation runs 4096-bit key derivation...", "keyhintdesc", "bg")

    def handle(self, key, mods, ctrl):
        if key == "esc":
            ctrl.goto("MAIN_MENU")
            return
        if key == "f1":
            ctrl.push_help()
            return
        action, self.focus, ev = fform.handle(None, self.fields, self.focus, key, mods)
        if action == "activate" and ev is self.fields[-1]:
            self._go(ctrl)
            return
        if action in ("focus", "changed") or ev:
            ctrl.refresh()

    def _go(self, ctrl):
        algo = self.fields[0]["value"]
        name = self.fields[1]["value"] or ("RSA-4096 key" if algo.startswith("RSA") else "Symmetric key")
        ctrl.settings.set("algo", algo)

        def run(report, cancelled):
            if algo.startswith("RSA"):
                report(5, "Generating 4096-bit RSA key pair")
                rec = ctrl.keys.add_rsa(name, algo)
            else:
                report(40, "Generating 256-bit key")
                rec = ctrl.keys.add_symmetric(name, algo)
            ctrl.keys.set_active(rec["id"])
            report(100, "Done")
            return rec

        def done(rec):
            lines = [
                "Key generated and stored.",
                "",
                "Name        : %s" % rec["name"],
                "Algorithm   : %s" % rec["algo"],
                "Fingerprint : %s" % rec["fingerprint"],
                "",
                "This key is now the active key.",
            ]
            ctrl.show_success(lines)

        ctrl.run_job(run, done)


_KEY_LETTERS = "abcdefghjklmnpqrtuvwxyz"


class ManageKeysScreen(ScreenBase):
    name = "MANAGE_KEYS"
    title = "MANAGE ENCRYPTION KEYS"

    def enter(self, ctrl):
        self.sel = 0
        self.offset = 0

    def render(self, g, ctrl):
        self._draw_shell(g)
        keys = ctrl.keys.list()
        act = ctrl.keys.get_active()
        g.put(2, 3, "Active key : %s" % (
            ("%s (%s)" % (act["name"], act["algo"])) if act else "none"), "text", "bg")
        g.put(2, 4, "Stored    : %d  (max %d)" % (len(keys), 32), "dim", "bg")
        row = 6
        visible = 12
        if self.sel < self.offset:
            self.offset = self.sel
        if self.sel >= self.offset + visible:
            self.offset = self.sel - visible + 1
        for i in range(self.offset, min(len(keys), self.offset + visible)):
            rec = keys[i]
            letter = chr(ord("A") + (i - self.offset))
            text = " [%s] %-14s %-22s %s%s" % (
                letter, rec["name"][:14], rec["algo"], rec["fingerprint"][:10],
                "  *ACTIVE*" if rec.get("active") else "")
            is_sel = i == self.sel
            if is_sel:
                g.put(2, row, text[:76], "hlt", "hlb")
            else:
                g.put(2, row, text[:76],
                      "bright" if rec.get("active") else "text", "bg")
            row += 1
        y = row + 1
        g.put(2, 19, "[A] Set active   [B] Rename   [C] Delete", "text", "bg")
        g.put(2, 20, "[D] New key      [E] Done                 F9 raw", "text", "bg")

    def handle(self, key, mods, ctrl):
        keys = ctrl.keys.list()
        if key == "type":
            letter = mods.get("text", "")
            if len(letter) == 1 and letter.isalpha():
                if letter in ("n", "N", "d", "D"):
                    ctrl.goto("GENERATE_KEY")
                    return
                if letter in ("e", "E"):
                    ctrl.goto("MAIN_MENU")
                    return
                if letter in ("a", "A"):
                    self._set_active(ctrl)
                    return
                if letter in ("b", "B"):
                    self._rename(ctrl)
                    return
                if letter in ("c", "C"):
                    self._delete(ctrl)
                    return
                idx = ord(letter.upper()) - ord("A") + self.offset
                if 0 <= idx < len(keys):
                    self.sel = idx
                    ctrl.refresh()
            return
        if key == "up":
            if keys:
                self.sel = (self.sel - 1) % len(keys)
            ctrl.refresh()
            return
        if key == "down":
            if keys:
                self.sel = (self.sel + 1) % len(keys)
            ctrl.refresh()
            return
        if key == "esc":
            ctrl.goto("MAIN_MENU")
            return
        if key == "enter":
            self._set_active(ctrl)
            return
        if key == "f1":
            ctrl.push_help()
            return
        if key == "f9":
            self._raw(ctrl)
            return
        if key == "f2":
            return

    def _current(self, ctrl):
        keys = ctrl.keys.list()
        if keys:
            return keys[self.sel % len(keys)]
        return None

    def _set_active(self, ctrl):
        rec = self._current(ctrl)
        if rec:
            ctrl.keys.set_active(rec["id"])
        ctrl.refresh()

    def _rename(self, ctrl):
        rec = self._current(ctrl)
        if rec:
            ctrl.prompt("RENAME KEY", "New name:", rec["name"],
                        lambda name: (ctrl.keys.rename(rec["id"], name),
                                      ctrl.goto("MANAGE_KEYS")))

    def _delete(self, ctrl):
        rec = self._current(ctrl)
        if rec:
            ctrl.confirm("DELETE KEY", 'Delete "%s"?  Files encrypted with this '
                                      "key can no longer be decrypted." % rec["name"],
                         lambda: (ctrl.keys.delete(rec["id"]), ctrl.goto("MANAGE_KEYS")))

    def _raw(self, ctrl):
        rec = self._current(ctrl)
        if rec:
            ctrl.confirm("RAW KEY EXPORT",
                         "Show the full raw key material of '%s'?" % rec["name"],
                         lambda: self._show_raw(ctrl, rec["id"]))

    def _show_raw(self, ctrl, key_id):
        exp = ctrl.keys.export(key_id)
        ctrl.prompt_text_mode("KEY " + exp["name"], exp["text"])


class SelectAlgoScreen(ScreenBase):
    name = "SELECT_ALGO"
    title = "SELECT ENCRYPTION ALGORITHM"

    DESCRIPTIONS = {
        "AES-256-GCM": "Authenticated AES-GCM (Galois Counter Mode). Fastest,\n"
                       "includes integrity via a 128-bit GCM tag. Recommended.",
        "AES-256-CBC + HMAC": "AES-CBC with PKCS#7 padding plus a separate\n"
                              "HMAC-SHA256 over IV+ciphertext (encrypt-then-MAC).",
        "ChaCha20-Poly1305": "ChaCha20 stream cipher with Poly1305 MAC. Fast on\n"
                             "CPUs without AES-NI; common in TLS 1.3.",
        "RSA-4096 + AES-256": "RSA-OAEP (SHA-256) wrapping a fresh per-file AES\n"
                              "data key; keep the RSA private key somewhere safe.",
    }

    def enter(self, ctrl):
        self.sel = ALGO_KEYS.index(ctrl.settings.get("algo")) if ctrl.settings.get("algo") in ALGO_KEYS else 0

    def render(self, g, ctrl):
        self._draw_shell(g)
        cur = ctrl.settings.get("algo")
        for i, algo in enumerate(ALGO_KEYS):
            row = 3 + i
            mark = "►" if algo == cur else " "
            if i == self.sel:
                g.fill(0, row, 38, 1, " ", "hlt", "hlb")
                g.put(1, row, mark, "hlt", "hlb")
                g.put(3, row, algo, "hlt", "hlb")
            else:
                g.put(1, row, mark, "dim", "bg")
                g.put(3, row, algo, "text", "bg")
        lines = []
        for ln in self.DESCRIPTIONS[ALGO_KEYS[self.sel]].split("\n"):
            lines += ui.wrap(ln, 36)
        ui.panel(g, 40, 3, 38, 12, title="Cipher", lines=lines[:10], fg="text")
        g.put(2, 8, "New generated keys use this cipher.", "keyhintdesc", "bg")
        g.put(2, 9, "Existing keys keep their own cipher.", "keyhintdesc", "bg")

    def handle(self, key, mods, ctrl):
        n = len(ALGO_KEYS)
        if key in ("up", "left"):
            self.sel = (self.sel - 1) % n
            ctrl.refresh()
            return
        if key in ("down", "right"):
            self.sel = (self.sel + 1) % n
            ctrl.refresh()
            return
        if key == "type":
            digit = mods.get("text", "")
            if digit.isdigit() and 1 <= int(digit) <= n:
                self.sel = int(digit) - 1
                ctrl.refresh()
            return
        if key == "enter":
            ctrl.settings.set("algo", ALGO_KEYS[self.sel])
            ctrl.goto("MAIN_MENU")
            return
        if key == "esc":
            ctrl.goto("MAIN_MENU")
            return
        if key == "f1":
            ctrl.push_help()
            return


class HistoryScreen(ScreenBase):
    name = "HISTORY"
    title = "ENCRYPTION HISTORY"

    def enter(self, ctrl):
        self.offset = 0

    def render(self, g, ctrl):
        self._draw_shell(g)
        records = list(reversed(ctrl.history.records()))
        g.put(2, 3, "Last %d operations  —  file: %s" % (len(records), HISTORY_PATH.name), "dim", "bg")
        visible = 16
        if self.offset > max(0, len(records) - visible):
            self.offset = max(0, len(records) - visible)
        row = 5
        for i in range(self.offset, min(len(records), self.offset + visible)):
            rec = records[i]
            mode = rec.get("mode", "?").upper()[:10]
            status = "ok" if rec.get("status") == "ok" else "ERR"
            name = Path(str(rec.get("output", "") or rec.get("input", ""))).name
            stamp = str(rec.get("time", ""))
            size = rec.get("size", 0) if rec.get("size") else 0
            line = "%3d  %-10s %-28s %9s  %s" % (
                len(records) - i, mode, name[:28], sc.format_size(size), stamp)
            color = "text" if status == "ok" else "error"
            g.put(2, row, line[:76], color, "bg")
            row += 1
        if not records:
            g.put(2, 6, "(history is empty)", "dim", "bg")
        g.put(2, 22, "▲▼ scroll   F6 clear   Esc back   F1 help", "keyhintdesc", "bg")

    def handle(self, key, mods, ctrl):
        total = len(ctrl.history.records())
        if key == "up":
            if self.offset > 0:
                self.offset -= 1
            ctrl.refresh()
            return
        if key == "down":
            self.offset += 1
            ctrl.refresh()
            return
        if key == "f6":
            if total:
                ctrl.confirm("CLEAR HISTORY", "Delete all %d history records?" % total,
                             lambda: (ctrl.history.clear(), ctrl.goto("HISTORY")))
            return
        if key == "esc":
            ctrl.goto("MAIN_MENU")
            return
        if key == "f1":
            ctrl.push_help()
            return
        if key in ("enter", "space"):
            return


class SecureDeleteScreen(ScreenBase):
    name = "SECURE_DELETE"
    title = "SECURE FILE DELETION"

    def enter(self, ctrl):
        self.fields = [
            {"kind": "choice", "label": "Method", "value": "DoD 5220.22-M",
             "options": ["DoD 5220.22-M", "Gutmann 35-pass"],
             "names": {"DoD 5220.22-M": "DoD 5220.22-M", "Gutmann 35-pass": "Gutmann 35-pass"}},
            {"kind": "input", "label": "File path", "value": "", "caret": 0, "width": 46},
            {"kind": "button", "label": "", "label2": "Wipe Now", "value": "ok"},
        ]
        self.focus = 0

    def render(self, g, ctrl):
        self._draw_shell(g)
        row = 3
        fform.render(g, self.fields, self.focus, row)
        g.put(2, 8, "DoD 5220.22-M: 0x00, 0xFF, PRNG passes + verify, fsync.", "dim", "bg")
        g.put(2, 9, "Gutmann: 35 wipe passes per the original spec.", "dim", "bg")

    def handle(self, key, mods, ctrl):
        if key == "f2":
            path, _ = QFileDialog.getOpenFileName(None, "Select file to wipe")
            if path:
                self.fields[1]["value"] = path
                self.fields[1]["caret"] = len(path)
            ctrl.refresh()
            return
        if key == "esc":
            ctrl.goto("MAIN_MENU")
            return
        if key == "f1":
            ctrl.push_help()
            return
        action, self.focus, ev = fform.handle(None, self.fields, self.focus, key, mods)
        if action == "activate" and ev is self.fields[-1]:
            self._go(ctrl)
            return
        if action in ("focus", "changed") or ev:
            ctrl.refresh()

    def _go(self, ctrl):
        path = self.fields[1]["value"].strip()
        method = "dod" if "DoD" in self.fields[0]["value"] else "guttmann"
        if not path or not os.path.exists(path):
            ctrl.route_error("E_FILE_NOT_FOUND", "File to wipe does not exist.")
            return
        ctrl.settings.set("secure_delete", method)

        def run(report, cancelled):
            import secure_delete

            secure_delete.wipe(path, method=method, progress=report)
            ctrl.history.add("wipe", path, "(secure)", 0)
            return {"path": path, "method": self.fields[0]["value"]}

        def done(result):
            ctrl.show_success([
                "File securely wiped.",
                "",
                "File   : %s" % result["path"],
                "Method : %s" % result["method"],
            ])

        ctrl.run_job(run, done)


class ImportKeyScreen(ScreenBase):
    name = "IMPORT_KEY"
    title = "IMPORT KEY"

    def enter(self, ctrl):
        self.fields = [
            {"kind": "input", "label": "Key file", "value": "", "caret": 0, "width": 46},
            {"kind": "input", "label": "Key name", "value": "", "caret": 0, "width": 40},
            {"kind": "choice", "label": "Algorithm", "value": ctrl.settings.get("algo"),
             "options": ALGO_KEYS},
            {"kind": "button", "label": "", "label2": "Import", "value": "ok"},
        ]
        self.focus = 0

    def render(self, g, ctrl):
        self._draw_shell(g)
        row = 3
        fform.render(g, self.fields, self.focus, row)
        g.put(2, 9, "PEM auto-detected as an RSA key; otherwise expects", "keyhintdesc", "bg")
        g.put(2, 10, "256-bit Base64 text (as written by the export form).", "keyhintdesc", "bg")

    def handle(self, key, mods, ctrl):
        if key == "f2":
            path, _ = QFileDialog.getOpenFileName(None, "Select key file")
            if path:
                self.fields[0]["value"] = path
                self.fields[0]["caret"] = len(path)
            ctrl.refresh()
            return
        if key == "esc":
            ctrl.goto("MAIN_MENU")
            return
        if key == "f1":
            ctrl.push_help()
            return
        action, self.focus, ev = fform.handle(None, self.fields, self.focus, key, mods)
        if action == "activate" and ev is self.fields[-1]:
            self._go(ctrl)
            return
        if action in ("focus", "changed") or ev:
            ctrl.refresh()

    def _go(self, ctrl):
        src = self.fields[0]["value"].strip()
        if not src or not os.path.exists(src):
            ctrl.route_error("E_FILE_NOT_FOUND", "Key file does not exist.")
            return
        name = self.fields[1]["value"] or "Imported key"
        algo = self.fields[2]["value"]

        def run(report, cancelled):
            text = file_manager.read_file(src).decode("utf-8", "replace")
            rec = ctrl.keys.import_key(name, algo, text)
            report(100, "Imported")
            return rec

        def done(rec):
            ctrl.keys.set_active(rec["id"])
            ctrl.show_success([
                "Key imported.",
                "",
                "Name        : %s" % rec["name"],
                "Algorithm   : %s" % rec["algo"],
                "Fingerprint : %s" % rec["fingerprint"],
                "",
                "This key is now the active key.",
            ])

        ctrl.run_job(run, done)


class ExportKeyScreen(ScreenBase):
    name = "EXPORT_KEY"
    title = "EXPORT KEY"

    def enter(self, ctrl):
        keys = ctrl.keys.list()
        ids = [k["id"] for k in keys]
        names = {k["id"]: "%s (%s)%s" % (k["name"], k["algo"], " *" if k.get("active") else "")
                 for k in keys}
        self.fields = [
            {"kind": "choice", "label": "Select key", "value": ids[0] if ids else "",
             "options": ids, "names": names},
            {"kind": "input", "label": "Export to", "value": "", "caret": 0, "width": 46},
            {"kind": "button", "label": "", "label2": "Export", "value": "ok", "enabled": bool(ids)},
        ]
        self.focus = 0

    def render(self, g, ctrl):
        self._draw_shell(g)
        row = 3
        fform.render(g, self.fields, self.focus, row)
        g.put(2, 8, "Exports symmetric keys as Base64 text, RSA keys as PEM.", "keyhintdesc", "bg")

    def handle(self, key, mods, ctrl):
        if key == "esc":
            ctrl.goto("MAIN_MENU")
            return
        if key == "f1":
            ctrl.push_help()
            return
        action, self.focus, ev = fform.handle(None, self.fields, self.focus, key, mods)
        if action == "activate" and ev is self.fields[-1]:
            self._go(ctrl)
            return
        if action in ("focus", "changed") or ev:
            ctrl.refresh()

    def _go(self, ctrl):
        key_id = self.fields[0]["value"]
        if not key_id:
            ctrl.route_error("E_KEY_NOT_SET", "No keys to export.")
            return
        out = self.fields[1]["value"].strip()
        if not out:
            rec = ctrl.keys.find(key_id)
            out = str(Path.home() / ("%s.key" % rec["name"].replace(" ", "_")))
            self.fields[1]["value"] = out
            ctrl.refresh()

        def run(report, cancelled):
            exp = ctrl.keys.export(key_id)
            file_manager.write_file(out, exp["text"].encode("ascii"))
            report(100, "Exported")
            return exp

        def done(exp):
            ctrl.show_success([
                "Key exported.",
                "",
                "Key         : %s" % exp["name"],
                "Algorithm   : %s" % exp["algo"],
                "File        : %s" % out,
                "Fingerprint : %s" % exp["fingerprint"],
            ])

        ctrl.run_job(run, done)


class SettingsScreen(ScreenBase):
    name = "SETTINGS"
    title = "APPLICATION SETTINGS"

    def enter(self, ctrl):
        s = ctrl.settings
        self.fields = [
            {"kind": "choice", "label": "Default algorithm", "value": s.get("algo"),
             "options": ALGO_KEYS},
            {"kind": "choice", "label": "Output naming", "value": s.get("output_naming"),
             "options": ["auto", "ask"]},
            {"kind": "choice", "label": "Secure-delete", "value": s.get("secure_delete"),
             "options": ["dod", "guttmann", "off"],
             "names": {"dod": "DoD 5220.22-M", "guttmann": "Gutmann 35", "off": "Off"}},
            {"kind": "toggle", "label": "Wipe source", "value": bool(s.get("wipe_source_after_encrypt"))},
            {"kind": "choice", "label": "Date format", "value": s.get("date_format"),
             "options": ["iso", "dot"],
             "names": {"iso": "YYYY-MM-DD", "dot": "DD.MM.YYYY"}},
            {"kind": "toggle", "label": "Clear clipboard", "value": bool(s.get("clear_clipboard"))},
            {"kind": "toggle", "label": "CRT scanlines", "value": bool(s.get("crt_scanlines"))},
            {"kind": "toggle", "label": "CRT phosphor", "value": bool(s.get("crt_phosphor"))},
            {"kind": "toggle", "label": "CRT curvature", "value": bool(s.get("crt_curvature"))},
            {"kind": "button", "label": "", "label2": "Save Settings", "value": "ok"},
        ]
        self.focus = 0

    def render(self, g, ctrl):
        self._draw_shell(g)
        row = 3
        fform.render(g, self.fields, self.focus, row)

    def handle(self, key, mods, ctrl):
        if key == "esc":
            ctrl.goto("MAIN_MENU")
            return
        if key == "f1":
            ctrl.push_help()
            return
        action, self.focus, ev = fform.handle(None, self.fields, self.focus, key, mods)
        if action == "activate" and ev is self.fields[-1]:
            self._save(ctrl)
            return
        if action in ("focus", "changed") or ev:
            ctrl.refresh()

    def _save(self, ctrl):
        f = {i and self.fields[i]["label"] or "": self.fields[i] for i in range(len(self.fields))}
        s = ctrl.settings
        s.set("algo", self.fields[0]["value"])
        s.set("output_naming", self.fields[1]["value"])
        s.set("secure_delete", self.fields[2]["value"])
        s.set("wipe_source_after_encrypt", self.fields[3]["value"])
        s.set("date_format", self.fields[4]["value"])
        s.set("clear_clipboard", self.fields[5]["value"])
        s.set("crt_scanlines", self.fields[6]["value"])
        s.set("crt_phosphor", self.fields[7]["value"])
        s.set("crt_curvature", self.fields[8]["value"])
        del f
        ctrl.apply_crt()
        ctrl.show_success(["Settings saved.", "", "All preferences persisted to disk."])


class DiagnosticsScreen(ScreenBase):
    name = "DIAGNOSTICS"
    title = "SYSTEM DIAGNOSTICS"

    def enter(self, ctrl):
        self.results = []
        self._running = False
        self._start(ctrl)

    def _start(self, ctrl):
        self.results = [("Running self-tests...", "dim")]
        ctrl.refresh()
        import threading

        poster = _Poster()
        _PosterReaper.keep(poster)

        def route(kind, payload):
            if kind == "done":
                _PosterReaper.release(poster)
                self._finish(ctrl, payload)

        poster.route = route
        poster.posted.connect(poster.handle, Qt.QueuedConnection)

        def worker():
            out = []
            try:
                sym = sc.generate_symmetric_key()
                blob = os.urandom(4096)
                for aid in (sc.ALGO_GCM, sc.ALGO_CBC, sc.ALGO_CHACHA):
                    c = sc.encrypt_data(blob, "t", algo=aid, key=sym)
                    ok = sc.decrypt_data(c, key=sym) == blob
                    out.append(("%s round-trip" % sc.ALGO_NAMES[aid],
                                "PASS" if ok else "FAIL"))
                rsa = sc.generate_rsa_key()
                c = sc.encrypt_data(blob, "t", algo=sc.ALGO_RSA, key=rsa)
                ok = sc.decrypt_data(c, key=rsa) == blob
                out.append(("RSA-4096 + OAEP round-trip", "PASS" if ok else "FAIL"))
                try:
                    act = ctrl.keys.get_active()
                    m = ctrl.keys.key_material(act) if act else None
                    out.append(("Key store integrity", "PASS" if act is not None else "FAIL"))
                    if m is not None:
                        aid = sc.ALGO_RSA if act.get("kind") == "rsa" else sc.ALGO_GCM
                        c = sc.encrypt_data(b"x", "t", algo=aid, key=m)
                        out.append(("Active key usable", "PASS" if sc.decrypt_data(c, key=m) == b"x" else "FAIL"))
                except Exception:
                    out.append(("Key store integrity", "FAIL"))
                hist_ok = True
                try:
                    ctrl.history.records()
                except Exception:
                    hist_ok = False
                out.append(("History log readable", "PASS" if hist_ok else "FAIL"))
            except Exception as exc:  # noqa: BLE001
                out.append(("Unexpected exception", "FAIL: %s" % exc))
            poster.posted.emit("done", out)

        threading.Thread(target=worker, daemon=True).start()

    def _finish(self, ctrl, out):
        self.results = out
        ctrl.refresh()

    def render(self, g, ctrl):
        self._draw_shell(g)
        g.put(2, 3, "Engine self-tests running  (F5 re-run)", "dim", "bg")
        row = 5
        for name, status in self.results:
            color = "success" if status.startswith("PASS") else ("error" if status.startswith("FAIL") else "dim")
            if status.startswith("PASS"):
                g.put(2, row, "  OK   %s" % name, "success", "bg")
            elif status.startswith("FAIL"):
                g.put(2, row, " FAIL  %s" % name, "error", "bg")
            else:
                g.put(2, row, "  ..   %s" % name, "dim", "bg")
            row += 1
        g.put(2, 22, "F5 re-run   Esc back   F1 help", "keyhintdesc", "bg")

    def handle(self, key, mods, ctrl):
        if key in ("f5", "enter", "r", "R"):
            self._start(ctrl)
            return
        if key == "esc":
            ctrl.goto("MAIN_MENU")
            return
        if key == "f1":
            ctrl.push_help()
            return


class AboutScreen(ScreenBase):
    name = "ABOUT"
    title = "ABOUT"

    def render(self, g, ctrl):
        self._draw_shell(g)
        lines = [
            "  SECURE ENCRYPTION UTILITY",
            "  Version 1.0  —  BIOS-style setup utility",
            "",
            "  Cipher engines",
            "    AES-256-GCM",
            "    AES-256-CBC + HMAC-SHA256",
            "    ChaCha20-Poly1305",
            "    RSA-4096 + OAEP (wraps AES data key)",
            "",
            "  Key derivation     PBKDF2-HMAC-SHA256, 600,000 iters",
            "  Key store          encrypted at rest (Fernet)",
            "  History            last 200 operations (JSON)",
            "  Text codecs        Base64 / Hex / Raw",
            "",
            "  Secure File Deletion: DoD 5220.22-M / Gutmann",
            "",
            "  Queue: says; qed.",
            "",
            "  Use at your own risk. NO WARRANTY.",
        ]
        row = 3
        for ln in lines[:19]:
            g.put(2, row, ln[:76], "text", "bg")
            row += 1
        g.put(2, 22, "Esc back   F1 help", "keyhintdesc", "bg")

    def handle(self, key, mods, ctrl):
        if key in ("esc", "enter"):
            ctrl.goto("MAIN_MENU")
            return


class SuccessScreen(ScreenBase):
    name = "SUCCESS"
    title = "OPERATION COMPLETE"

    def enter(self, ctrl):
        self.lines = []
        self.extra = None

    def render(self, g, ctrl):
        self._draw_shell(g)
        g.put(2, 3, "OPERATION COMPLETED SUCCESSFULLY", "success", "bg")
        row = 5
        for ln in self.lines:
            if ln:
                g.put(2, row, ln[:76], "text", "bg")
            row += 1
        if self.extra:
            self.extra(g, ctrl)
        g.put(2, 22, "Any key to continue   F7 copy", "keyhintdesc", "bg")

    def handle(self, key, mods, ctrl):
        if key == "f7":
            if ctrl.clip:
                QApplication.clipboard().setText(ctrl.clip)
            return
        if key in ("f1", "f10"):
            return
        if key == "esc":
            ctrl.goto("MAIN_MENU")
            return
        if key == "enter" or key.startswith("k"):
            ctrl.goto("MAIN_MENU")
            return
        ctrl.goto("MAIN_MENU")


class ErrorScreen(ScreenBase):
    name = "ERROR"
    title = "ERROR"

    def enter(self, ctrl):
        self.code = "E_INTERNAL"
        self.detail = ""
        self.auto_key = False

    def render(self, g, ctrl):
        self._draw_shell(g)
        g.put(2, 3, "OPERATION FAILED", "error", "bg")
        g.put(2, 5, "Error code: %s" % self.code, "bright", "bg")
        row = 7
        for ln in ui.wrap(self.detail, 72)[:8]:
            g.put(2, row, ln[:76], "error", "bg")
            row += 1
        if self.auto_key:
            g.put(2, 12, "You may need to generate a key first.", "warn", "bg")
        g.put(2, 22, "Any key to continue", "keyhintdesc", "bg")

    def handle(self, key, mods, ctrl):
        if key in ("esc", "enter"):
            ctrl.goto("MAIN_MENU")
            return
        ctrl.goto("MAIN_MENU")


# ---------------------------------------------------------------------------
# prompt / confirm / help overlays
# ---------------------------------------------------------------------------

class PromptScreen(ScreenBase):
    name = "PROMPT"
    title = "PROMPT"

    def enter(self, ctrl):
        self.label = ""
        self.value = ""
        self.caret = 0
        self.ok = None

    def render(self, g, ctrl):
        self._draw_shell(g)
        row = 8
        g.put(2, row, self.label[:72], "text", "bg")
        row += 2
        width = 54
        value = self.value
        caret = min(self.caret, len(value))
        visual = value
        end = ""
        if len(visual) > width - 2:
            visual = visual[: width - 2]
            end = "►"
        g.put(2, row, "[" + visual.ljust(width - 2), "text", "inputbg")
        g.put_char(2 + caret + 1, row, "█", "cursor", "inputbg", blink="cursor")
        g.put_char(2 + width - 1, row, "]", "dim", "inputbg")
        row += 2
        ui.button(g, 6, row, "OK", focused=False)
        ui.button(g, 20, row, "Cancel")

    def handle(self, key, mods, ctrl):
        if key == "esc":
            ctrl.goto("MAIN_MENU")
            return
        if key == "enter":
            if self.ok:
                self.ok(self.value if hasattr(self, "ok_value") else self.value)
            ctrl.goto("MAIN_MENU")
            return
        if key == "left":
            self.caret = max(0, self.caret - 1)
            ctrl.refresh()
            return
        if key == "right":
            self.caret = min(len(self.value), self.caret + 1)
            ctrl.refresh()
            return
        if key == "home":
            self.caret = 0
            ctrl.refresh()
            return
        if key == "end":
            self.caret = len(self.value)
            ctrl.refresh()
            return
        if key == "backspace":
            if self.caret > 0:
                self.value = self.value[: self.caret - 1] + self.value[self.caret:]
                self.caret -= 1
            ctrl.refresh()
            return
        if key == "space":
            self.value = self.value[: self.caret] + " " + self.value[self.caret:]
            self.caret += 1
            ctrl.refresh()
            return
        if key == "delete":
            self.value = self.value[: self.caret] + self.value[self.caret + 1:]
            ctrl.refresh()
            return
        if key == "type":
            self.value = self.value[: self.caret] + mods.get("text", "") + self.value[self.caret:]
            self.caret += len(mods.get("text", ""))
            ctrl.refresh()
            return
        if key == "f1":
            ctrl.push_help()


class PromptTextScreen(ScreenBase):
    name = "PROMPT_TEXT"
    title = "TEXT VIEWER"

    def enter(self, ctrl):
        self.value = ""

    def render(self, g, ctrl):
        self._draw_shell(g)
        lines = ui.wrap(self.value, 74)[:17]
        row = 3
        for ln in lines:
            g.put(1, row, ln[:78], "text", "bg")
            row += 1
        if len(ui.wrap(self.value, 74)) > 17:
            g.put(1, row + 1, "(truncated — raw key material)", "dim", "bg")
        g.put(2, 22, "Any key to continue   F7 copy", "keyhintdesc", "bg")

    def handle(self, key, mods, ctrl):
        if key == "f7":
            if self.value:
                QApplication.clipboard().setText(self.value)
            return
        if key in ("esc", "enter"):
            ctrl.goto("MAIN_MENU")
            return
        ctrl.goto("MAIN_MENU")


class ConfirmScreen(ScreenBase):
    name = "CONFIRM"
    title = "CONFIRMATION"

    def enter(self, ctrl):
        self.message = ""
        self.on_yes = None
        self.sel = 1

    def render(self, g, ctrl):
        self._draw_shell(g)
        lines = ui.wrap(self.message, 54)[:5]
        row = 8
        for ln in lines:
            g.put(2, row, ln, "text", "bg")
            row += 1
        row += 1
        ui.button(g, 6, row, "Yes", focused=self.sel == 0)
        ui.button(g, 16, row, "No", focused=self.sel == 1)

    def handle(self, key, mods, ctrl):
        if key in ("left", "right", "tab"):
            self.sel = 1 - self.sel
            ctrl.refresh()
            return
        if key == "enter":
            if self.sel == 0 and self.on_yes:
                self.on_yes()
            else:
                ctrl.goto("MAIN_MENU")
            return
        if key == "esc":
            ctrl.goto("MAIN_MENU")
            return


class HelpScreen(ScreenBase):
    name = "HELP"
    title = "HELP — KEYBOARD REFERENCE"

    def enter(self, ctrl):
        if not getattr(self, "back", None):
            self.back = "MAIN_MENU"

    def render(self, g, ctrl):
        self._draw_shell(g)
        for i, (k, v) in enumerate(HELP_LINES):
            row = 3 + i
            if i == 0:
                g.put(2, row, k, "bright", "bg")
                g.put(22, row, v, "bright", "bg")
                continue
            g.put(2, row, k, "keyhint", "bg")
            g.put(22, row, v, "text", "bg")

    def handle(self, key, mods, ctrl):
        if key in ("esc", "enter", "f1"):
            ctrl.goto(self.back or "MAIN_MENU")
            return


# ---------------------------------------------------------------------------
# progress screen + controller
# ---------------------------------------------------------------------------

class ProgressScreen(ScreenBase):
    name = "PROGRESS"
    title = "PROCESSING"

    def enter(self, ctrl):
        self.pct = 0
        self.status = "Starting..."

    def render(self, g, ctrl):
        self._draw_shell(g)
        g.put(2, 6, "Please wait...", "text", "bg")
        pct = max(0, min(100, self.pct))
        width = 50
        filled = int(width * pct / 100)
        bar = "█" * filled + "░" * (width - filled)
        g.put(2, 9, bar, "text", "bg")
        g.put(2, 11, "%3d%%" % pct, "bright", "bg")
        g.put(2, 12, self.status[:72], "dim", "bg")
        g.put(2, 20, "Esc to cancel", "keyhintdesc", "bg")

    def handle(self, key, mods, ctrl):
        if key == "esc":
            ctrl.cancel_job()
            return


SCREENS = {
    s.name: s
    for s in [
        InitScreen(), MainMenuScreen(), ExitConfirmScreen(),
        FileEncryptScreen(), FileDecryptScreen(),
        EncryptTextScreen(), DecryptTextScreen(),
        GenerateKeyScreen(), ManageKeysScreen(), SelectAlgoScreen(),
        HistoryScreen(), SecureDeleteScreen(),
        ImportKeyScreen(), ExportKeyScreen(),
        SettingsScreen(), DiagnosticsScreen(), AboutScreen(),
        SuccessScreen(), ErrorScreen(),
        PromptScreen(), PromptTextScreen(), ConfirmScreen(), HelpScreen(),
        ProgressScreen(),
    ]
}


class SeuController(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.grid = VGAGrid(self)
        self.settings = settings_store.Settings()
        self.history = HistoryManager(self)
        self.safe = True
        try:
            import keystore

            self.keys = keystore.KeyStore()
        except Exception as exc:  # noqa: BLE001
            self.safe = False
            self._boot_error = classify_error(exc)
            import keystore

            self.keys = type("_Empty", (), {
                "list": lambda self: [],
                "count": lambda self: 0,
                "get_active": lambda self: None,
                "key_material": lambda self, r: b"",
                "find": lambda self, i: None,
            })()
        self.clip = None
        self._busy = False
        self._cancel = False
        self.current = None
        for s in SCREENS.values():
            s.enter(self)
        self.setLayoutFromGrid()
        self.goto("INITIALIZING")

    def setLayoutFromGrid(self):
        from PyQt5.QtWidgets import QVBoxLayout

        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.addWidget(self.grid)
        self.setLayout(layout)

    def apply_crt(self):
        s = self.settings
        self.grid.crt_scanlines = bool(s.get("crt_scanlines"))
        self.grid.crt_phosphor = bool(s.get("crt_phosphor"))
        self.grid.crt_curvature = bool(s.get("crt_curvature"))
        self.grid.update()

    def goto(self, name):
        screen = SCREENS.get(name)
        if screen is None:
            return
        self.current = screen
        screen.enter(self)
        self.refresh()

    def refresh(self):
        if self.current is None:
            return
        self.grid.clear()
        self.current.render(self.grid, self)
        self.grid.update()

    def push_help(self):
        help_screen = SCREENS["HELP"]
        help_screen.back = self.current.name
        self.goto("HELP")

    def route_error(self, code, detail):
        err = SCREENS["ERROR"]
        err.code = code
        err.detail = detail
        err.auto_key = code == "E_KEY_NOT_SET"
        self.goto("ERROR")

    def show_success(self, lines, extra_ok=None):
        sc_ = SCREENS["SUCCESS"]
        sc_.lines = lines
        sc_.extra = extra_ok
        self.goto("SUCCESS")

    def prompt(self, title, label, initial, on_ok):
        p = SCREENS["PROMPT"]
        p.title = title
        p.label = label
        p.value = initial
        p.caret = len(initial)
        p.ok = on_ok
        self.goto("PROMPT")

    def prompt_text_mode(self, title, value):
        p = SCREENS["PROMPT_TEXT"]
        p.title = title
        p.value = value
        self.goto("PROMPT_TEXT")

    def confirm(self, title, message, on_yes):
        c = SCREENS["CONFIRM"]
        c.title = title
        c.message = message
        c.on_yes = on_yes
        c.sel = 1
        self.goto("CONFIRM")

    def ensure_active_key(self):
        if not self.keys.count():
            self.route_error("E_KEY_NOT_SET",
                             "No encryption keys stored.  The utility will take you"
                             " to the key generator to create one first.")
            self._after_error_goto = "GENERATE_KEY"
            QTimer.singleShot(0, self._pending_goto)
            return None
        act = self.keys.get_active()
        if act is None:
            self.keys.set_active(self.keys.list()[0]["id"])
            act = self.keys.get_active()
        return act

    def _pending_goto(self):
        target = getattr(self, "_after_error_goto", None)
        if target and self.current and self.current.name == "ERROR":
            self.goto(target)

    def run_job(self, run_fn, done_fn):
        if self._busy:
            return
        self._cancel = False
        prog = SCREENS["PROGRESS"]
        prog.pct = 0
        prog.status = "Starting..."
        self._job_done = done_fn
        self.goto("PROGRESS")

        def on_progress(pct, status):
            prog.pct = pct
            prog.status = status
            if self.current and self.current.name == "PROGRESS":
                self.refresh()
            else:
                self.grid.update()

        def finish_ok(result):
            self._busy = False
            if self.current and self.current.name == "PROGRESS":
                QTimer.singleShot(500, lambda: self._job_done(result))
            else:
                self._job_done(result)

        def finish_err(exc):
            self._busy = False
            code, detail = classify_error(exc)
            if self.current and self.current.name == "PROGRESS":
                QTimer.singleShot(500, lambda: self._route_after_job_error(code, detail))
            else:
                self._route_after_job_error(code, detail)

        self._busy = True
        run_job(
            run_fn,
            cancel_check=lambda: self._cancel,
            on_progress=on_progress,
            on_done=finish_ok,
            on_error=finish_err,
        )

    def _route_after_job_error(self, code, detail):
        err = SCREENS["ERROR"]
        err.code = code
        err.detail = detail
        err.auto_key = code == "E_KEY_NOT_SET"
        self.goto("ERROR")

    def cancel_job(self):
        self._cancel = True

    def exit_app(self):
        QApplication.quit()

    # ---------------------------------------------------------------- input

    def keyPressEvent(self, event):
        k = event.key()
        modifiers = event.modifiers()

        if k == Qt.Key_F11 and modifiers in (Qt.NoModifier,):
            if self.isFullScreen():
                self.showNormal()
            else:
                self.showFullScreen()
            return

        if k == Qt.Key_F10:
            if self.current and self.current.name != "EXIT_CONFIRM":
                self.goto("EXIT_CONFIRM")
                return

        mods = {"text": event.text() if event.text() else ""}
        if modifiers & (Qt.ControlModifier | Qt.AltModifier):
            key = "paste" if (k == Qt.Key_V and modifiers & Qt.ControlModifier) else "none"
        else:
            key = self._normalize(k, modifiers)
            if key is None and len(mods["text"]) == 1 and mods["text"] not in "\r\n\x00":
                key = "type"

        if key == "paste":
            self._paste_into(mods)
            return

        if key is not None and self.current:
            self.current.handle(key, mods, self)

    def _paste_into(self, mods):
        text = QApplication.clipboard().text()
        if text:
            mods["text"] = text.strip()
            if self.current:
                self.current.handle("type", mods, self)

    def _normalize(self, k, modifiers):
        mapping = {
            Qt.Key_Up: "up", Qt.Key_Down: "down",
            Qt.Key_Left: "left", Qt.Key_Right: "right",
            Qt.Key_Return: "enter", Qt.Key_Enter: "enter",
            Qt.Key_Escape: "esc", Qt.Key_Tab: "tab",
            Qt.Key_Backtab: "shift_tab",
            Qt.Key_Backspace: "backspace", Qt.Key_Delete: "delete",
            Qt.Key_Home: "home", Qt.Key_End: "end",
            Qt.Key_Space: "space",
        }
        if k in mapping:
            return mapping[k]
        if Qt.Key_F1 <= k <= Qt.Key_F12:
            return "f%d" % (k - Qt.Key_F1 + 1)
        if modifiers & Qt.ShiftModifier and k == Qt.Key_Tab:
            return "shift_tab"
        return None