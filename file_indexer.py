"""
File and document searcher with recent files support for macOS Spotlight clone.
"""
import os
import time
import urllib.parse
import xml.etree.ElementTree as ET
from datetime import datetime
from typing import List, Dict, Any, Optional

import gi
gi.require_version('Gtk', '3.0')
from gi.repository import Gio, Gtk, GdkPixbuf

class FileEntry:
    __slots__ = ('name', 'path', 'mime_type', 'size_str', 'mtime_str', 'icon_name', 'score')

    def __init__(self, name: str, path: str, mime_type: str, size_str: str, mtime_str: str, icon_name: str, score: float = 0.0):
        self.name = name
        self.path = path
        self.mime_type = mime_type
        self.size_str = size_str
        self.mtime_str = mtime_str
        self.icon_name = icon_name
        self.score = score

def format_file_size(bytes_val: int) -> str:
    for unit in ['B', 'KB', 'MB', 'GB', 'TB']:
        if bytes_val < 1024.0:
            return f"{bytes_val:.1f} {unit}" if unit != 'B' else f"{bytes_val} B"
        bytes_val /= 1024.0
    return f"{bytes_val:.1f} PB"

def format_mtime(timestamp: float) -> str:
    dt = datetime.fromtimestamp(timestamp)
    now = datetime.now()
    if dt.date() == now.date():
        return f"Today at {dt.strftime('%-I:%M %p')}"
    elif (now - dt).days == 1:
        return f"Yesterday at {dt.strftime('%-I:%M %p')}"
    elif (now - dt).days < 7:
        return dt.strftime('%A at %-I:%M %p')
    return dt.strftime('%b %-d, %Y')

class FileIndexer:
    def __init__(self):
        self.recent_files: List[str] = []
        self.indexed_files: List[FileEntry] = []
        self.last_index_time = 0.0
        self.refresh_index()

    def refresh_index(self):
        now = time.time()
        if now - self.last_index_time < 30.0:  # cache index for 30s
            return
        self.last_index_time = now

        recent = self._load_recent_files()
        file_paths = set(recent)

        # Scan user directories (up to depth 2)
        home = os.path.expanduser('~')
        target_dirs = [
            os.path.join(home, 'Desktop'),
            os.path.join(home, 'Documents'),
            os.path.join(home, 'Downloads'),
            os.path.join(home, 'Pictures'),
            os.path.join(home, 'Videos'),
            os.path.join(home, 'Music'),
        ]

        for d in target_dirs:
            if not os.path.isdir(d):
                continue
            try:
                for root, dirs, files in os.walk(d):
                    # limit depth to 2
                    depth = root[len(d):].count(os.sep)
                    if depth > 2:
                        continue
                    # ignore hidden
                    dirs[:] = [dr for dr in dirs if not dr.startswith('.')]
                    for f in files:
                        if f.startswith('.'):
                            continue
                        file_paths.add(os.path.join(root, f))
            except Exception:
                pass

        entries = []
        for p in file_paths:
            if not os.path.exists(p):
                continue
            entry = self._create_file_entry(p)
            if entry:
                entries.append(entry)

        self.indexed_files = entries

    def _load_recent_files(self) -> List[str]:
        xbel_path = os.path.expanduser('~/.local/share/recently-used.xbel')
        if not os.path.exists(xbel_path):
            return []
        try:
            tree = ET.parse(xbel_path)
            root = tree.getroot()
            paths = []
            for bookmark in root.findall('bookmark'):
                href = bookmark.get('href')
                if href and href.startswith('file://'):
                    decoded = urllib.parse.unquote(href[7:])
                    if os.path.exists(decoded):
                        paths.append(decoded)
            return paths[::-1]  # most recent first
        except Exception:
            return []

    def _create_file_entry(self, path: str) -> Optional[FileEntry]:
        try:
            st = os.stat(path)
            name = os.path.basename(path)
            if not name:
                name = path
            is_dir = os.path.isdir(path)
            size_str = format_file_size(st.st_size) if not is_dir else "Folder"
            mtime_str = format_mtime(st.st_mtime)

            content_type, _ = Gio.content_type_guess(name, None)
            icon = Gio.content_type_get_icon(content_type)
            icon_name = "text-x-generic"
            if icon:
                names = icon.get_names()
                if names:
                    icon_name = names[0]
            if is_dir:
                icon_name = "folder"

            return FileEntry(
                name=name,
                path=path,
                mime_type=content_type or ("inode/directory" if is_dir else "unknown"),
                size_str=size_str,
                mtime_str=mtime_str,
                icon_name=icon_name
            )
        except Exception:
            return None

    def search(self, query: str, limit: int = 8) -> List[FileEntry]:
        q = query.strip().lower()
        if not q or len(q) < 2:
            return []

        results = []
        for entry in self.indexed_files:
            name_lower = entry.name.lower()
            score = 0.0

            if name_lower == q:
                score = 500.0
            elif name_lower.startswith(q):
                score = 300.0
            elif q in name_lower:
                score = 150.0

            if score > 0:
                entry.score = score
                results.append(entry)

        results.sort(key=lambda x: x.score, reverse=True)
        return results[:limit]

    def open_file(self, entry: FileEntry):
        try:
            gfile = Gio.File.new_for_path(entry.path)
            Gio.AppInfo.launch_default_for_uri(gfile.get_uri(), None)
        except Exception:
            os.system(f"xdg-open '{entry.path}' &")

    def reveal_in_folder(self, entry: FileEntry):
        parent = os.path.dirname(entry.path)
        os.system(f"xdg-open '{parent}' &")
