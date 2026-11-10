"""
macOS Spotlight Resident Daemon.
Runs continuously in background, handles Alt+Space global hotkey,
listens on UNIX domain socket for instant IPC toggling,
and pre-warms the GTK window for sub-5ms activation latency.
"""
import os
import sys
import signal
import socket
import select
from typing import Optional

# Ensure directory is in sys.path
SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
if SCRIPT_DIR not in sys.path:
    sys.path.insert(0, SCRIPT_DIR)

import gi
gi.require_version('Gtk', '3.0')
gi.require_version('Gdk', '3.0')
gi.require_version('Keybinder', '3.0')
from gi.repository import Gtk, Gdk, GLib, Keybinder

from app_indexer import AppIndexer
from file_indexer import FileIndexer
from spotlight_ui import SpotlightWindow

def get_socket_path() -> str:
    runtime_dir = os.environ.get('XDG_RUNTIME_DIR')
    if runtime_dir:
        return os.path.join(runtime_dir, 'spotlight.sock')
    return f"/run/user/{os.getuid()}/spotlight.sock"

class SpotlightDaemon:
    def __init__(self):
        self.sock_path = get_socket_path()
        self.server_sock: Optional[socket.socket] = None
        self.win: Optional[SpotlightWindow] = None

    def start(self):
        # 1. Single instance check
        if self._is_already_running():
            print("Spotlight daemon already running. Exiting.")
            sys.exit(0)

        # 2. GTK initialization
        Gtk.init([])

        # 3. Initialize Indexers & UI Window (pre-warmed in memory)
        print("Pre-indexing applications and files...")
        app_indexer = AppIndexer()
        file_indexer = FileIndexer()
        self.win = SpotlightWindow(app_indexer, file_indexer)

        # 4. Global Hotkey Registration via Keybinder
        Keybinder.init()
        bound = Keybinder.bind('<Alt>space', self.on_global_hotkey, None)
        if bound:
            print("Successfully bound global hotkey <Alt>space via Keybinder.")
        else:
            print("Warning: Keybinder could not grab <Alt>space (Cinnamon shortcut or muffin may have it). Socket fallback is active.")

        # 5. Socket IPC setup
        self._setup_socket_server()

        # 6. Signals
        signal.signal(signal.SIGINT, self._handle_signal)
        signal.signal(signal.SIGTERM, self._handle_signal)

        print("Spotlight daemon ready! Window pre-warmed.")
        Gtk.main()

    def _is_already_running(self) -> bool:
        if not os.path.exists(self.sock_path):
            return False
        try:
            test_sock = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
            test_sock.connect(self.sock_path)
            # Daemon is alive!
            test_sock.sendall(b"TOGGLE\n")
            test_sock.close()
            return True
        except Exception:
            # Stale socket file
            try:
                os.unlink(self.sock_path)
            except Exception:
                pass
            return False

    def _setup_socket_server(self):
        if os.path.exists(self.sock_path):
            try:
                os.unlink(self.sock_path)
            except Exception:
                pass

        self.server_sock = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
        self.server_sock.setblocking(False)
        self.server_sock.bind(self.sock_path)
        self.server_sock.listen(5)

        # Attach socket to GLib main event loop
        GLib.io_add_watch(
            self.server_sock.fileno(),
            GLib.PRIORITY_HIGH,
            GLib.IO_IN,
            self._on_socket_activity
        )

    def _on_socket_activity(self, fd, condition):
        try:
            client, _ = self.server_sock.accept()
            client.settimeout(0.1)
            data = client.recv(128).decode('utf-8', errors='ignore').strip()
            client.close()

            if data == 'TOGGLE':
                self.win.toggle()
            elif data == 'SHOW':
                self.win.show_spotlight()
            elif data == 'HIDE':
                self.win.hide()
            elif data == 'RELOAD':
                self.win.app_indexer.reload_apps()
                self.win.file_indexer.refresh_index()
        except Exception as e:
            pass
        return True

    def on_global_hotkey(self, keystring, user_data):
        GLib.idle_add(self.win.toggle)

    def _handle_signal(self, signum, frame):
        print("Shutting down Spotlight daemon...")
        if os.path.exists(self.sock_path):
            try:
                os.unlink(self.sock_path)
            except Exception:
                pass
        Gtk.main_quit()

if __name__ == '__main__':
    daemon = SpotlightDaemon()
    daemon.start()
