"""
High performance application indexer with frecency tracking and intelligent scoring.
"""
import os
import json
import time
import re
import shlex
import subprocess
from typing import List, Dict, Any, Optional

import gi
gi.require_version('Gtk', '3.0')
from gi.repository import Gtk, GdkPixbuf

CACHE_DIR = os.path.expanduser('~/.cache/spotlight')
FRECENCY_FILE = os.path.join(CACHE_DIR, 'frecency.json')

class AppEntry:
    __slots__ = (
        'id', 'name', 'generic_name', 'comment', 'exec_cmd', 'icon_name',
        'categories', 'keywords', 'terminal', 'desktop_path', 'frecency_score'
    )

    def __init__(
        self, id: str, name: str, generic_name: str, comment: str,
        exec_cmd: str, icon_name: str, categories: List[str],
        keywords: List[str], terminal: bool, desktop_path: str
    ):
        self.id = id
        self.name = name
        self.generic_name = generic_name
        self.comment = comment
        self.exec_cmd = exec_cmd
        self.icon_name = icon_name
        self.categories = categories
        self.keywords = keywords
        self.terminal = terminal
        self.desktop_path = desktop_path
        self.frecency_score = 0.0

    def to_dict(self) -> Dict[str, Any]:
        return {
            'id': self.id,
            'name': self.name,
            'generic_name': self.generic_name,
            'comment': self.comment,
            'exec_cmd': self.exec_cmd,
            'icon_name': self.icon_name,
            'categories': self.categories,
            'keywords': self.keywords,
            'terminal': self.terminal,
            'desktop_path': self.desktop_path,
        }

class AppIndexer:
    def __init__(self):
        self.apps: List[AppEntry] = []
        self.frecency_data: Dict[str, Dict[str, Any]] = {}
        self.icon_theme = Gtk.IconTheme.get_default()
        self.pixbuf_cache: Dict[str, Optional[GdkPixbuf.Pixbuf]] = {}
        self._load_frecency()
        self.reload_apps()

    def _load_frecency(self):
        try:
            if os.path.exists(FRECENCY_FILE):
                with open(FRECENCY_FILE, 'r', encoding='utf-8') as f:
                    self.frecency_data = json.load(f)
        except Exception:
            self.frecency_data = {}

    def _save_frecency(self):
        try:
            os.makedirs(CACHE_DIR, exist_ok=True)
            with open(FRECENCY_FILE, 'w', encoding='utf-8') as f:
                json.dump(self.frecency_data, f)
        except Exception:
            pass

    def record_launch(self, app_id: str):
        now = time.time()
        info = self.frecency_data.get(app_id, {'count': 0, 'last': now})
        info['count'] += 1
        info['last'] = now
        self.frecency_data[app_id] = info
        self._save_frecency()
        # update in-memory score
        for a in self.apps:
            if a.id == app_id:
                a.frecency_score = self._calc_frecency(app_id)
                break

    def _calc_frecency(self, app_id: str) -> float:
        info = self.frecency_data.get(app_id)
        if not info:
            return 0.0
        count = info.get('count', 0)
        last = info.get('last', 0)
        age_hours = (time.time() - last) / 3600.0
        # Decay over time
        decay = 1.0 / (1.0 + (age_hours / 24.0))
        return count * decay * 10.0

    def reload_apps(self):
        search_dirs = [
            os.path.expanduser('~/.local/share/applications'),
            '/usr/local/share/applications',
            '/usr/share/applications',
            '/var/lib/flatpak/exports/share/applications',
            os.path.expanduser('~/.local/share/flatpak/exports/share/applications'),
        ]

        seen_ids = set()
        apps = []

        for d in search_dirs:
            if not os.path.isdir(d):
                continue
            for root, _, files in os.walk(d):
                for f in files:
                    if f.endswith('.desktop'):
                        path = os.path.join(root, f)
                        app_id = f
                        if app_id in seen_ids:
                            continue
                        entry = self._parse_desktop_file(path, app_id)
                        if entry:
                            entry.frecency_score = self._calc_frecency(app_id)
                            apps.append(entry)
                            seen_ids.add(app_id)

        self.apps = apps

    def _parse_desktop_file(self, filepath: str, app_id: str) -> Optional[AppEntry]:
        try:
            name = None
            generic_name = ""
            comment = ""
            exec_cmd = None
            icon = "application-x-executable"
            categories = []
            keywords = []
            terminal = False
            no_display = False
            hidden = False

            in_desktop_entry = False

            with open(filepath, 'r', encoding='utf-8', errors='replace') as f:
                for line in f:
                    line = line.strip()
                    if line == '[Desktop Entry]':
                        in_desktop_entry = True
                        continue
                    elif line.startswith('[') and line.endswith(']'):
                        in_desktop_entry = False
                        continue

                    if not in_desktop_entry or '=' not in line:
                        continue

                    key, val = line.split('=', 1)
                    key = key.strip()
                    val = val.strip()

                    if key == 'Name' and not name:
                        name = val
                    elif key == 'GenericName' and not generic_name:
                        generic_name = val
                    elif key == 'Comment' and not comment:
                        comment = val
                    elif key == 'Exec' and not exec_cmd:
                        exec_cmd = val
                    elif key == 'Icon' and icon == "application-x-executable":
                        icon = val
                    elif key == 'Categories':
                        categories = [c.strip() for c in val.split(';') if c.strip()]
                    elif key == 'Keywords':
                        keywords = [k.strip() for k in val.split(';') if k.strip()]
                    elif key == 'Terminal':
                        terminal = (val.lower() == 'true')
                    elif key == 'NoDisplay':
                        no_display = (val.lower() == 'true')
                    elif key == 'Hidden':
                        hidden = (val.lower() == 'true')

            if no_display or hidden or not name or not exec_cmd:
                return None

            # Clean Exec: remove %u, %f, %U, %F, %i, %c, %k
            clean_exec = re.sub(r'%[a-zA-Z]', '', exec_cmd).strip()

            return AppEntry(
                id=app_id,
                name=name,
                generic_name=generic_name,
                comment=comment,
                exec_cmd=clean_exec,
                icon_name=icon,
                categories=categories,
                keywords=keywords,
                terminal=terminal,
                desktop_path=filepath
            )
        except Exception:
            return None

    def get_pixbuf(self, icon_name: str, size: int = 32) -> Optional[GdkPixbuf.Pixbuf]:
        cache_key = f"{icon_name}:{size}"
        if cache_key in self.pixbuf_cache:
            return self.pixbuf_cache[cache_key]

        pixbuf = None
        # Check if direct file path
        if os.path.isfile(icon_name):
            try:
                pixbuf = GdkPixbuf.Pixbuf.new_from_file_at_scale(icon_name, size, size, True)
            except Exception:
                pass

        if not pixbuf and self.icon_theme:
            try:
                icon_info = self.icon_theme.lookup_icon(icon_name, size, Gtk.IconLookupFlags.FORCE_SIZE)
                if icon_info:
                    pixbuf = icon_info.load_icon()
            except Exception:
                pass

        if not pixbuf and self.icon_theme:
            # Fallback icon
            try:
                icon_info = self.icon_theme.lookup_icon("application-x-executable", size, Gtk.IconLookupFlags.FORCE_SIZE)
                if icon_info:
                    pixbuf = icon_info.load_icon()
            except Exception:
                pass

        self.pixbuf_cache[cache_key] = pixbuf
        return pixbuf

    def launch(self, app: AppEntry):
        self.record_launch(app.id)
        # 1. Try gtk-launch first: cleanly delegates to desktop session outside our cgroup
        if app.id:
            try:
                if subprocess.call(f"gtk-launch '{app.id}' >/dev/null 2>&1", shell=True) == 0:
                    return
            except Exception:
                pass

        # 2. Build command (with terminal wrapper if needed)
        cmd = app.exec_cmd
        if app.terminal:
            terminals = ['alacritty', 'gnome-terminal', 'konsole', 'xterm']
            found_term = 'xterm'
            for t in terminals:
                if subprocess.call(f"which {t} >/dev/null 2>&1", shell=True) == 0:
                    found_term = t
                    break
            if found_term == 'alacritty':
                cmd = f"alacritty -e {cmd}"
            elif found_term == 'gnome-terminal':
                cmd = f"gnome-terminal -- {cmd}"
            elif found_term == 'konsole':
                cmd = f"konsole -e {cmd}"
            else:
                cmd = f"xterm -e {cmd}"

        # 3. Try systemd-run --user --scope to keep launched app out of spotlight's service unit
        try:
            if subprocess.call(f"systemd-run --user --scope {cmd} >/dev/null 2>&1", shell=True) == 0:
                return
        except Exception:
            pass

        # 4. Fallback detached process
        subprocess.Popen(cmd, shell=True, start_new_session=True)

    def search(self, query: str, limit: int = 15) -> List[Any]:
        q = query.strip().lower()
        if not q:
            # return top frecent apps
            sorted_apps = sorted(self.apps, key=lambda a: a.frecency_score, reverse=True)
            return [(a, a.frecency_score) for a in sorted_apps[:limit]]

        scored = []
        q_words = q.split()

        for a in self.apps:
            name_lower = a.name.lower()
            score = 0.0

            # 1. Exact match
            if name_lower == q:
                score += 1000.0

            # 2. Prefix match
            elif name_lower.startswith(q):
                score += 500.0 + (100.0 / len(name_lower))

            # 3. Word start match (e.g. "Visual Studio Code" -> "vs" or "code")
            name_words = name_lower.split()
            if any(w.startswith(q) for w in name_words):
                score += 300.0

            # 4. Acronym match (e.g. "gc" -> "google chrome")
            acronym = "".join(w[0] for w in name_words if w)
            if acronym.startswith(q):
                score += 350.0

            # 5. Substring match
            elif q in name_lower:
                score += 150.0 - name_lower.index(q) * 2

            # 6. Generic name or comment match
            gen_lower = a.generic_name.lower()
            if gen_lower.startswith(q):
                score += 120.0
            elif q in gen_lower:
                score += 80.0

            # 7. Executable name match
            exec_name = os.path.basename(a.exec_cmd.split()[0]).lower() if a.exec_cmd else ""
            if exec_name.startswith(q):
                score += 140.0
            elif q in exec_name:
                score += 70.0

            # 8. Keywords match
            for kw in a.keywords:
                kw_l = kw.lower()
                if kw_l.startswith(q):
                    score += 90.0
                    break
                elif q in kw_l:
                    score += 40.0
                    break

            # 9. All query words match somewhere
            if len(q_words) > 1:
                search_text = f"{name_lower} {gen_lower} {a.comment.lower()} {exec_name}"
                if all(w in search_text for w in q_words):
                    score += 100.0

            if score > 0:
                # Add frecency bonus
                score += a.frecency_score
                scored.append((a, score))

        scored.sort(key=lambda x: x[1], reverse=True)
        return scored[:limit]
