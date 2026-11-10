"""
macOS Spotlight UI in GTK+ 3.
Replicates the authentic macOS Sonoma / Sequoia Spotlight interface and interaction model.
"""
import os
import sys
import cairo
import html
import urllib.parse
from typing import List, Dict, Any, Optional, Tuple

import gi
gi.require_version('Gtk', '3.0')
gi.require_version('Gdk', '3.0')
gi.require_version('GdkPixbuf', '2.0')
from gi.repository import Gtk, Gdk, GdkPixbuf, GLib, Pango

from app_indexer import AppIndexer, AppEntry
from math_eval import evaluate_expression
from file_indexer import FileIndexer, FileEntry
from system_actions import search_system_actions, SystemAction, SYSTEM_ACTIONS

SPOTLIGHT_WIDTH = 680
SPOTLIGHT_COLLAPSED_HEIGHT = 58
SPOTLIGHT_EXPANDED_HEIGHT = 440

MACOS_CSS = """
window.spotlight-window {
    background-color: transparent;
}

.spotlight-frame {
    background-color: rgba(28, 28, 30, 0.94);
    border: 1px solid rgba(255, 255, 255, 0.14);
    border-radius: 16px;
    box-shadow: 0 20px 48px rgba(0, 0, 0, 0.7);
}

.search-header {
    padding: 10px 18px;
    background: transparent;
}

.search-entry {
    background: transparent;
    border: none;
    box-shadow: none;
    color: #ffffff;
    font-family: -apple-system, BlinkMacSystemFont, "SF Pro Display", "SF Pro Text", "Fira Sans", "Noto Sans", sans-serif;
    font-size: 19px;
    font-weight: 300;
    padding: 6px 10px;
    caret-color: #0a84ff;
}

.search-entry:focus {
    border: none;
    box-shadow: none;
}

.search-entry placeholder,
entry.search-entry placeholder {
    color: #8e8e93;
    font-weight: 300;
}

.search-icon {
    color: #8e8e93;
    margin-right: 6px;
}

.clear-btn {
    background: rgba(255, 255, 255, 0.1);
    color: #8e8e93;
    border-radius: 12px;
    border: none;
    padding: 2px 6px;
    min-height: 20px;
    min-width: 20px;
}
.clear-btn:hover {
    background: rgba(255, 255, 255, 0.2);
    color: #ffffff;
}

.h-divider {
    background-color: rgba(255, 255, 255, 0.08);
    min-height: 1px;
}

.v-divider {
    background-color: rgba(255, 255, 255, 0.08);
    min-width: 1px;
}

.results-scroll {
    background: transparent;
}

.results-list {
    background: transparent;
    padding: 6px 4px;
}

.category-header {
    padding: 8px 14px 4px 14px;
}

.category-header label {
    color: #8e8e93;
    font-family: -apple-system, BlinkMacSystemFont, "SF Pro Display", "SF Pro Text", "Fira Sans", sans-serif;
    font-size: 10px;
    font-weight: 700;
    letter-spacing: 0.8px;
}

.result-row {
    background: transparent;
    border-radius: 8px;
    margin: 1px 6px;
    padding: 6px 10px;
    transition: all 100ms ease;
}

.result-row:selected, .result-row:hover:selected {
    background-color: #0a84ff;
}

.result-row:hover:not(:selected) {
    background-color: rgba(255, 255, 255, 0.06);
}

.row-title {
    color: #ffffff;
    font-family: -apple-system, BlinkMacSystemFont, "SF Pro Display", "SF Pro Text", "Fira Sans", sans-serif;
    font-size: 13.5px;
    font-weight: 500;
}

.row-subtitle {
    color: #8e8e93;
    font-family: -apple-system, BlinkMacSystemFont, "SF Pro Display", "SF Pro Text", "Fira Sans", sans-serif;
    font-size: 11px;
}

.result-row:selected .row-subtitle {
    color: rgba(255, 255, 255, 0.85);
}

.preview-pane {
    background: transparent;
    padding: 24px 22px;
}

.preview-title {
    color: #ffffff;
    font-family: -apple-system, BlinkMacSystemFont, "SF Pro Display", "SF Pro Text", "Fira Sans", sans-serif;
    font-size: 20px;
    font-weight: 600;
    margin-top: 12px;
}

.preview-kind {
    color: #8e8e93;
    font-family: -apple-system, BlinkMacSystemFont, "SF Pro Display", "SF Pro Text", "Fira Sans", sans-serif;
    font-size: 11.5px;
    font-weight: 500;
    margin-top: 2px;
}

.preview-desc {
    color: #b0b0b8;
    font-family: -apple-system, BlinkMacSystemFont, "SF Pro Display", "SF Pro Text", "Fira Sans", sans-serif;
    font-size: 12px;
    margin-top: 8px;
}

.preview-meta-table label {
    font-family: -apple-system, BlinkMacSystemFont, "SF Pro Display", "SF Pro Text", "Fira Sans", sans-serif;
    font-size: 11px;
}

.preview-meta-label {
    color: #8e8e93;
}

.preview-meta-value {
    color: #d1d1d6;
}

.preview-calc-eq {
    color: #8e8e93;
    font-family: -apple-system, BlinkMacSystemFont, "SF Pro Display", "SF Pro Text", "Fira Sans", sans-serif;
    font-size: 15px;
}

.preview-calc-val {
    color: #ffffff;
    font-family: -apple-system, BlinkMacSystemFont, "SF Pro Display", "SF Pro Text", "Fira Sans", sans-serif;
    font-size: 30px;
    font-weight: 700;
}

.action-pill {
    background-color: rgba(255, 255, 255, 0.08);
    border: 1px solid rgba(255, 255, 255, 0.12);
    border-radius: 8px;
    padding: 6px 12px;
    color: #d1d1d6;
    font-family: -apple-system, BlinkMacSystemFont, "SF Pro Display", "SF Pro Text", "Fira Sans", sans-serif;
    font-size: 11.5px;
    font-weight: 500;
}

scrollbar, scrollbar button, scrollbar trough {
    background: transparent;
    border: none;
}
scrollbar slider {
    background: rgba(255, 255, 255, 0.2);
    border-radius: 4px;
    min-width: 4px;
}
"""

class ResultItem:
    def __init__(self, kind: str, title: str, subtitle: str, icon_name: str, payload: Any, pixbuf: Optional[GdkPixbuf.Pixbuf] = None):
        self.kind = kind  # 'app', 'calc', 'file', 'system', 'web', 'shell'
        self.title = title
        self.subtitle = subtitle
        self.icon_name = icon_name
        self.payload = payload
        self.pixbuf = pixbuf

class SpotlightWindow(Gtk.Window):
    def __init__(self, app_indexer: AppIndexer, file_indexer: FileIndexer):
        super().__init__(type=Gtk.WindowType.TOPLEVEL)
        self.app_indexer = app_indexer
        self.file_indexer = file_indexer
        self.icon_theme = Gtk.IconTheme.get_default()

        # Window properties
        self.set_title("Spotlight")
        self.set_decorated(False)
        self.set_app_paintable(True)
        self.set_skip_taskbar_hint(True)
        self.set_skip_pager_hint(True)
        self.set_keep_above(True)
        self.set_type_hint(Gdk.WindowTypeHint.DIALOG)
        self.get_style_context().add_class('spotlight-window')

        # Translucency
        screen = self.get_screen()
        visual = screen.get_rgba_visual()
        if visual:
            self.set_visual(visual)

        self.connect('draw', self.on_draw)
        self.connect('focus-out-event', self.on_focus_out)
        self.connect('key-press-event', self.on_key_press)

        # Apply CSS
        css_provider = Gtk.CssProvider()
        css_provider.load_from_data(MACOS_CSS.encode('utf-8'))
        Gtk.StyleContext.add_provider_for_screen(
            screen, css_provider, Gtk.STYLE_PROVIDER_PRIORITY_APPLICATION
        )

        # Internal state
        self.results: List[ResultItem] = []
        self.selected_index = 0
        self.is_expanded = False

        self._build_ui()

    def on_draw(self, widget, cr):
        # Clear background so window alpha is transparent
        cr.set_source_rgba(0, 0, 0, 0)
        cr.set_operator(cairo.OPERATOR_SOURCE)
        cr.paint()
        cr.set_operator(cairo.OPERATOR_OVER)
        return False

    def _build_ui(self):
        # Outer wrapper with padding for drop shadow
        self.outer_box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL)
        self.outer_box.set_margin_top(12)
        self.outer_box.set_margin_bottom(12)
        self.outer_box.set_margin_left(12)
        self.outer_box.set_margin_right(12)
        self.add(self.outer_box)

        # The rounded macOS spotlight frame
        self.frame = Gtk.Box(orientation=Gtk.Orientation.VERTICAL)
        self.frame.get_style_context().add_class('spotlight-frame')
        self.frame.set_size_request(SPOTLIGHT_WIDTH, -1)
        self.outer_box.pack_start(self.frame, True, True, 0)

        # ── 1. Top Search Header ──
        self.header_box = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL)
        self.header_box.get_style_context().add_class('search-header')
        self.frame.pack_start(self.header_box, False, False, 0)

        # Magnifying glass icon
        search_icon = Gtk.Image.new_from_icon_name("system-search-symbolic", Gtk.IconSize.LARGE_TOOLBAR)
        search_icon.get_style_context().add_class('search-icon')
        self.header_box.pack_start(search_icon, False, False, 0)

        # Search Entry
        self.entry = Gtk.Entry()
        self.entry.get_style_context().add_class('search-entry')
        self.entry.set_placeholder_text("Spotlight Search")
        self.entry.connect('changed', self.on_search_changed)
        self.entry.connect('activate', self.on_entry_activate)
        self.header_box.pack_start(self.entry, True, True, 0)

        # Clear button
        self.clear_btn = Gtk.Button(label="✕")
        self.clear_btn.get_style_context().add_class('clear-btn')
        self.clear_btn.connect('clicked', lambda b: self.entry.set_text(""))
        self.clear_btn.set_visible(False)
        self.header_box.pack_start(self.clear_btn, False, False, 0)

        # ── 2. Horizontal Divider ──
        self.h_divider = Gtk.Box()
        self.h_divider.get_style_context().add_class('h-divider')
        self.h_divider.set_visible(False)
        self.frame.pack_start(self.h_divider, False, False, 0)

        # ── 3. Split Body View ──
        self.body_box = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL)
        self.body_box.set_visible(False)
        self.body_box.set_size_request(SPOTLIGHT_WIDTH, SPOTLIGHT_EXPANDED_HEIGHT - SPOTLIGHT_COLLAPSED_HEIGHT)
        self.frame.pack_start(self.body_box, True, True, 0)

        # Left Column: Scrolled Results List
        self.results_scroll = Gtk.ScrolledWindow()
        self.results_scroll.get_style_context().add_class('results-scroll')
        self.results_scroll.set_policy(Gtk.PolicyType.NEVER, Gtk.PolicyType.AUTOMATIC)
        self.results_scroll.set_size_request(320, -1)
        self.body_box.pack_start(self.results_scroll, False, False, 0)

        self.listbox = Gtk.ListBox()
        self.listbox.get_style_context().add_class('results-list')
        self.listbox.set_selection_mode(Gtk.SelectionMode.SINGLE)
        self.listbox.connect('row-selected', self.on_row_selected)
        self.listbox.connect('row-activated', self.on_row_activated)
        self.results_scroll.add(self.listbox)

        # Vertical Divider
        self.v_divider = Gtk.Box()
        self.v_divider.get_style_context().add_class('v-divider')
        self.body_box.pack_start(self.v_divider, False, False, 0)

        # Right Column: Preview Pane
        self.preview_box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL)
        self.preview_box.get_style_context().add_class('preview-pane')
        self.preview_box.set_size_request(358, -1)
        self.body_box.pack_start(self.preview_box, True, True, 0)

    def on_key_press(self, widget, event):
        keyval = event.keyval
        # Escape -> Hide window
        if keyval == Gdk.KEY_Escape:
            self.hide()
            return True

        # Down Arrow -> Next item
        if keyval == Gdk.KEY_Down:
            self.select_next()
            return True

        # Up Arrow -> Previous item
        if keyval == Gdk.KEY_Up:
            self.select_prev()
            return True

        # Tab -> Focus next or complete
        if keyval == Gdk.KEY_Tab:
            self.select_next()
            return True

        # Shift + Return on file -> Reveal in Nemo
        if (keyval in (Gdk.KEY_Return, Gdk.KEY_KP_Enter)) and (event.state & Gdk.ModifierType.SHIFT_MASK):
            item = self.get_selected_item()
            if item and item.kind == 'file':
                self.file_indexer.reveal_in_folder(item.payload)
                self.hide()
                return True

        return False

    def on_focus_out(self, widget, event):
        self.hide()
        return False

    def toggle(self):
        if self.is_visible():
            self.hide()
        else:
            self.show_spotlight()

    def show_spotlight(self):
        # Refresh indexed files lightly
        self.file_indexer.refresh_index()

        # Center on screen
        screen = self.get_screen()
        display = screen.get_display()
        pointer = display.get_default_seat().get_pointer()
        _, x, y = pointer.get_position()
        monitor = display.get_monitor_at_point(x, y)
        if not monitor:
            monitor = display.get_primary_monitor() or display.get_monitor(0)

        if monitor:
            geom = monitor.get_geometry()
            target_x = geom.x + (geom.width - (SPOTLIGHT_WIDTH + 24)) // 2
            target_y = geom.y + int(geom.height * 0.18)
            self.move(target_x, target_y)

        self.show_all()
        # Initial collapsed state if entry is empty
        if not self.entry.get_text().strip():
            self.collapse_view()
        else:
            self.update_search()

        self.present_with_time(Gtk.get_current_event_time())
        gdk_win = self.get_window()
        if gdk_win:
            gdk_win.focus(Gdk.CURRENT_TIME)
        self.entry.grab_focus()
        # Select all text so typing replaces it or user can delete
        self.entry.select_region(0, -1)

    def collapse_view(self):
        self.is_expanded = False
        self.clear_btn.hide()
        self.h_divider.hide()
        self.body_box.hide()
        self.resize(SPOTLIGHT_WIDTH + 24, SPOTLIGHT_COLLAPSED_HEIGHT + 24)

    def expand_view(self):
        self.is_expanded = True
        self.clear_btn.show()
        self.h_divider.show()
        self.body_box.show_all()
        self.resize(SPOTLIGHT_WIDTH + 24, SPOTLIGHT_EXPANDED_HEIGHT + 24)

    def on_search_changed(self, entry):
        self.update_search()

    def update_search(self):
        query = self.entry.get_text()
        raw = query.strip()

        if not raw:
            self.collapse_view()
            return

        self.expand_view()
        self._populate_results(query)

    def _populate_results(self, query: str):
        # Clear existing listbox rows
        for child in self.listbox.get_children():
            self.listbox.remove(child)

        self.results = []
        raw = query.strip()

        # 1. Check Math calculation
        math_res = evaluate_expression(raw)
        if math_res:
            expr, val = math_res
            pb = self._get_themed_pixbuf("calc", 32)
            self.results.append(ResultItem(
                kind='calc',
                title=f"= {val}",
                subtitle=expr,
                icon_name='calc',
                payload=(expr, val),
                pixbuf=pb
            ))

        # 2. Check System actions
        sys_matches = search_system_actions(raw)
        for act in sys_matches[:3]:
            pb = self._get_themed_pixbuf(act.icon_name, 32)
            self.results.append(ResultItem(
                kind='system',
                title=act.name,
                subtitle=act.description,
                icon_name=act.icon_name,
                payload=act,
                pixbuf=pb
            ))

        # 3. Check Applications
        app_matches = self.app_indexer.search(raw, limit=10)
        for app, score in app_matches:
            pb = self.app_indexer.get_pixbuf(app.icon_name, 32)
            sub = app.generic_name or app.comment or "Application"
            self.results.append(ResultItem(
                kind='app',
                title=app.name,
                subtitle=sub,
                icon_name=app.icon_name,
                payload=app,
                pixbuf=pb
            ))

        # 4. Check Files & Documents
        file_matches = self.file_indexer.search(raw, limit=6)
        for f in file_matches:
            pb = self._get_themed_pixbuf(f.icon_name, 32)
            self.results.append(ResultItem(
                kind='file',
                title=f.name,
                subtitle=f"{f.size_str} • {f.mtime_str}",
                icon_name=f.icon_name,
                payload=f,
                pixbuf=pb
            ))

        # 5. Fallback Web search & Shell command
        if raw.startswith(('>', '$')):
            cmd_text = raw[1:].strip()
            pb = self._get_themed_pixbuf("utilities-terminal", 32)
            self.results.append(ResultItem(
                kind='shell',
                title=f"Run: {cmd_text}",
                subtitle="Execute in terminal",
                icon_name="utilities-terminal",
                payload=cmd_text,
                pixbuf=pb
            ))
        elif raw.startswith(('http://', 'https://', 'www.')):
            pb = self._get_themed_pixbuf("web-browser", 32)
            self.results.append(ResultItem(
                kind='web',
                title=f"Open: {raw}",
                subtitle="Open in default browser",
                icon_name="web-browser",
                payload=raw if raw.startswith(('http://', 'https://')) else f"https://{raw}",
                pixbuf=pb
            ))
        else:
            pb = self._get_themed_pixbuf("web-browser", 32)
            self.results.append(ResultItem(
                kind='web',
                title=f"Search Google for \"{raw}\"",
                subtitle="Brave Browser",
                icon_name="web-browser",
                payload=f"https://www.google.com/search?q={urllib.parse.quote_plus(raw)}",
                pixbuf=pb
            ))

        # Group and build list rows
        current_category = None
        for idx, item in enumerate(self.results):
            # Category Header
            cat_name = self._get_category_label(item.kind, idx)
            if cat_name != current_category:
                current_category = cat_name
                header_row = Gtk.ListBoxRow()
                header_row.set_selectable(False)
                header_row.set_activatable(False)
                h_box = Gtk.Box()
                h_box.get_style_context().add_class('category-header')
                lbl = Gtk.Label(label=cat_name)
                lbl.set_xalign(0)
                h_box.pack_start(lbl, True, True, 0)
                header_row.add(h_box)
                self.listbox.add(header_row)

            # Row item
            row = Gtk.ListBoxRow()
            row.get_style_context().add_class('result-row')
            row.result_item = item
            row.item_index = idx

            r_box = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=10)

            # Icon
            if item.pixbuf:
                img = Gtk.Image.new_from_pixbuf(item.pixbuf)
            else:
                img = Gtk.Image.new_from_icon_name(item.icon_name, Gtk.IconSize.DND)
            r_box.pack_start(img, False, False, 0)

            # Text Box
            t_box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=2)
            lbl_title = Gtk.Label(label=item.title)
            lbl_title.get_style_context().add_class('row-title')
            lbl_title.set_xalign(0)
            lbl_title.set_ellipsize(Pango.EllipsizeMode.END)
            lbl_title.set_max_width_chars(28)

            lbl_sub = Gtk.Label(label=item.subtitle)
            lbl_sub.get_style_context().add_class('row-subtitle')
            lbl_sub.set_xalign(0)
            lbl_sub.set_ellipsize(Pango.EllipsizeMode.END)
            lbl_sub.set_max_width_chars(32)

            t_box.pack_start(lbl_title, False, False, 0)
            t_box.pack_start(lbl_sub, False, False, 0)
            r_box.pack_start(t_box, True, True, 0)

            row.add(r_box)
            self.listbox.add(row)

        self.listbox.show_all()
        self.results_scroll.show_all()

        # Select first result row
        self._select_first_result_row()

    def _get_category_label(self, kind: str, index: int) -> str:
        if index == 0:
            return "TOP HIT"
        if kind == 'calc':
            return "CALCULATOR"
        if kind == 'app':
            return "APPLICATIONS"
        if kind == 'file':
            return "DOCUMENTS"
        if kind == 'system':
            return "SYSTEM"
        return "WEB SEARCH"

    def _select_first_result_row(self):
        for row in self.listbox.get_children():
            if getattr(row, 'result_item', None):
                self.listbox.select_row(row)
                row.grab_focus()
                self.entry.grab_focus_without_selecting()
                self._update_preview(row.result_item)
                break

    def select_next(self):
        selected = self.listbox.get_selected_row()
        children = self.listbox.get_children()
        selectable_rows = [r for r in children if getattr(r, 'result_item', None)]
        if not selectable_rows:
            return

        if not selected or selected not in selectable_rows:
            self.listbox.select_row(selectable_rows[0])
            self._update_preview(selectable_rows[0].result_item)
            return

        idx = selectable_rows.index(selected)
        if idx < len(selectable_rows) - 1:
            next_row = selectable_rows[idx + 1]
            self.listbox.select_row(next_row)
            self._ensure_row_visible(next_row)
            self._update_preview(next_row.result_item)

    def select_prev(self):
        selected = self.listbox.get_selected_row()
        children = self.listbox.get_children()
        selectable_rows = [r for r in children if getattr(r, 'result_item', None)]
        if not selectable_rows:
            return

        if not selected or selected not in selectable_rows:
            self.listbox.select_row(selectable_rows[0])
            self._update_preview(selectable_rows[0].result_item)
            return

        idx = selectable_rows.index(selected)
        if idx > 0:
            prev_row = selectable_rows[idx - 1]
            self.listbox.select_row(prev_row)
            self._ensure_row_visible(prev_row)
            self._update_preview(prev_row.result_item)

    def _ensure_row_visible(self, row):
        adj = self.results_scroll.get_vadjustment()
        alloc = row.get_allocation()
        val = adj.get_value()
        page = adj.get_page_size()
        if alloc.y < val:
            adj.set_value(alloc.y)
        elif alloc.y + alloc.height > val + page:
            adj.set_value(alloc.y + alloc.height - page)

    def get_selected_item(self) -> Optional[ResultItem]:
        selected = self.listbox.get_selected_row()
        if selected and hasattr(selected, 'result_item'):
            return selected.result_item
        return None

    def on_row_selected(self, listbox, row):
        if row and hasattr(row, 'result_item'):
            self._update_preview(row.result_item)

    def on_row_activated(self, listbox, row):
        if row and hasattr(row, 'result_item'):
            self.activate_item(row.result_item)

    def on_entry_activate(self, entry):
        item = self.get_selected_item()
        if item:
            self.activate_item(item)
        else:
            # If nothing selected, execute web search for entered text
            raw = entry.get_text().strip()
            if raw:
                import urllib.parse
                os.system(f"xdg-open 'https://www.google.com/search?q={urllib.parse.quote_plus(raw)}' &")
                self.hide()

    def activate_item(self, item: ResultItem):
        self.hide()
        if item.kind == 'app':
            self.app_indexer.launch(item.payload)
        elif item.kind == 'calc':
            expr, val = item.payload
            # Copy result to clipboard
            clipboard = Gtk.Clipboard.get(Gdk.SELECTION_CLIPBOARD)
            clipboard.set_text(val, -1)
            clipboard.store()
        elif item.kind == 'file':
            self.file_indexer.open_file(item.payload)
        elif item.kind == 'system':
            item.payload.execute()
        elif item.kind == 'web':
            os.system(f"xdg-open '{item.payload}' &")
        elif item.kind == 'shell':
            # Execute in terminal
            cmd = item.payload
            os.system(f"alacritty -e {cmd} &")

    def _update_preview(self, item: ResultItem):
        for child in self.preview_box.get_children():
            self.preview_box.remove(child)

        if item.kind == 'app':
            self._render_app_preview(item.payload)
        elif item.kind == 'calc':
            self._render_calc_preview(item.payload)
        elif item.kind == 'file':
            self._render_file_preview(item.payload)
        elif item.kind == 'system':
            self._render_system_preview(item.payload)
        elif item.kind in ('web', 'shell'):
            self._render_web_shell_preview(item)

        self.preview_box.show_all()

    def _render_app_preview(self, app: AppEntry):
        # Big Icon
        pb = self.app_indexer.get_pixbuf(app.icon_name, 80)
        img = Gtk.Image.new_from_pixbuf(pb) if pb else Gtk.Image.new_from_icon_name(app.icon_name, Gtk.IconSize.DIALOG)
        img.set_alignment(0.5, 0.5)
        self.preview_box.pack_start(img, False, False, 4)

        # Title
        lbl_title = Gtk.Label(label=app.name)
        lbl_title.get_style_context().add_class('preview-title')
        lbl_title.set_line_wrap(True)
        lbl_title.set_justify(Gtk.Justification.CENTER)
        self.preview_box.pack_start(lbl_title, False, False, 0)

        # Kind
        lbl_kind = Gtk.Label(label="Kind: Application")
        lbl_kind.get_style_context().add_class('preview-kind')
        self.preview_box.pack_start(lbl_kind, False, False, 0)

        # Comment / Description
        if app.comment or app.generic_name:
            desc_text = app.comment or app.generic_name
            lbl_desc = Gtk.Label(label=desc_text)
            lbl_desc.get_style_context().add_class('preview-desc')
            lbl_desc.set_line_wrap(True)
            lbl_desc.set_justify(Gtk.Justification.CENTER)
            lbl_desc.set_max_width_chars(32)
            self.preview_box.pack_start(lbl_desc, False, False, 6)

        # Meta info
        grid = Gtk.Grid()
        grid.get_style_context().add_class('preview-meta-table')
        grid.set_column_spacing(10)
        grid.set_row_spacing(4)
        grid.set_halign(Gtk.Align.CENTER)
        grid.set_margin_top(12)

        row_idx = 0
        if app.categories:
            cat_lbl = Gtk.Label(label="Category:")
            cat_lbl.get_style_context().add_class('preview-meta-label')
            cat_lbl.set_xalign(1)
            cat_val = Gtk.Label(label=", ".join(app.categories[:2]))
            cat_val.get_style_context().add_class('preview-meta-value')
            cat_val.set_xalign(0)
            grid.attach(cat_lbl, 0, row_idx, 1, 1)
            grid.attach(cat_val, 1, row_idx, 1, 1)
            row_idx += 1

        exec_lbl = Gtk.Label(label="Command:")
        exec_lbl.get_style_context().add_class('preview-meta-label')
        exec_lbl.set_xalign(1)
        exec_base = os.path.basename(app.exec_cmd.split()[0]) if app.exec_cmd else ""
        exec_val = Gtk.Label(label=exec_base)
        exec_val.get_style_context().add_class('preview-meta-value')
        exec_val.set_xalign(0)
        grid.attach(exec_lbl, 0, row_idx, 1, 1)
        grid.attach(exec_val, 1, row_idx, 1, 1)

        self.preview_box.pack_start(grid, False, False, 4)

        # Action pill at bottom
        spacer = Gtk.Box()
        self.preview_box.pack_start(spacer, True, True, 0)

        action_box = Gtk.Box()
        action_box.set_halign(Gtk.Align.CENTER)
        action_lbl = Gtk.Label(label="Press ↵ to Open")
        action_lbl.get_style_context().add_class('action-pill')
        action_box.pack_start(action_lbl, False, False, 0)
        self.preview_box.pack_start(action_box, False, False, 6)

    def _render_calc_preview(self, payload: Tuple[str, str]):
        expr, val = payload

        # Calculator Icon
        pb = self._get_themed_pixbuf("calc", 64) or self._get_themed_pixbuf("accessories-calculator", 64)
        img = Gtk.Image.new_from_pixbuf(pb) if pb else Gtk.Image.new_from_icon_name("accessories-calculator", Gtk.IconSize.DIALOG)
        img.set_alignment(0.5, 0.5)
        self.preview_box.pack_start(img, False, False, 10)

        # Equation
        lbl_eq = Gtk.Label(label=expr)
        lbl_eq.get_style_context().add_class('preview-calc-eq')
        lbl_eq.set_line_wrap(True)
        lbl_eq.set_justify(Gtk.Justification.CENTER)
        self.preview_box.pack_start(lbl_eq, False, False, 2)

        # Giant Answer
        lbl_val = Gtk.Label(label=f"= {val}")
        lbl_val.get_style_context().add_class('preview-calc-val')
        lbl_val.set_line_wrap(True)
        lbl_val.set_justify(Gtk.Justification.CENTER)
        self.preview_box.pack_start(lbl_val, False, False, 4)

        lbl_desc = Gtk.Label(label="Calculation Result")
        lbl_desc.get_style_context().add_class('preview-kind')
        self.preview_box.pack_start(lbl_desc, False, False, 2)

        # Action pill at bottom
        spacer = Gtk.Box()
        self.preview_box.pack_start(spacer, True, True, 0)

        action_box = Gtk.Box()
        action_box.set_halign(Gtk.Align.CENTER)
        action_lbl = Gtk.Label(label="Press ↵ to Copy to Clipboard")
        action_lbl.get_style_context().add_class('action-pill')
        action_box.pack_start(action_lbl, False, False, 0)
        self.preview_box.pack_start(action_box, False, False, 6)

    def _render_file_preview(self, file_entry: FileEntry):
        # File icon or thumbnail
        pb = None
        if file_entry.mime_type.startswith('image/'):
            try:
                pb = GdkPixbuf.Pixbuf.new_from_file_at_scale(file_entry.path, 110, 110, True)
            except Exception:
                pass
        if not pb:
            pb = self._get_themed_pixbuf(file_entry.icon_name, 72)

        img = Gtk.Image.new_from_pixbuf(pb) if pb else Gtk.Image.new_from_icon_name("text-x-generic", Gtk.IconSize.DIALOG)
        img.set_alignment(0.5, 0.5)
        self.preview_box.pack_start(img, False, False, 4)

        # Name
        lbl_title = Gtk.Label(label=file_entry.name)
        lbl_title.get_style_context().add_class('preview-title')
        lbl_title.set_line_wrap(True)
        lbl_title.set_justify(Gtk.Justification.CENTER)
        lbl_title.set_max_width_chars(28)
        self.preview_box.pack_start(lbl_title, False, False, 0)

        # Kind
        lbl_kind = Gtk.Label(label=f"Kind: {file_entry.mime_type}")
        lbl_kind.get_style_context().add_class('preview-kind')
        self.preview_box.pack_start(lbl_kind, False, False, 0)

        # Metadata grid
        grid = Gtk.Grid()
        grid.get_style_context().add_class('preview-meta-table')
        grid.set_column_spacing(10)
        grid.set_row_spacing(4)
        grid.set_halign(Gtk.Align.CENTER)
        grid.set_margin_top(8)

        # Size
        s_lbl = Gtk.Label(label="Size:")
        s_lbl.get_style_context().add_class('preview-meta-label')
        s_lbl.set_xalign(1)
        s_val = Gtk.Label(label=file_entry.size_str)
        s_val.get_style_context().add_class('preview-meta-value')
        s_val.set_xalign(0)
        grid.attach(s_lbl, 0, 0, 1, 1)
        grid.attach(s_val, 1, 0, 1, 1)

        # Modified
        m_lbl = Gtk.Label(label="Modified:")
        m_lbl.get_style_context().add_class('preview-meta-label')
        m_lbl.set_xalign(1)
        m_val = Gtk.Label(label=file_entry.mtime_str)
        m_val.get_style_context().add_class('preview-meta-value')
        m_val.set_xalign(0)
        grid.attach(m_lbl, 0, 1, 1, 1)
        grid.attach(m_val, 1, 1, 1, 1)

        self.preview_box.pack_start(grid, False, False, 4)

        # Action pill at bottom
        spacer = Gtk.Box()
        self.preview_box.pack_start(spacer, True, True, 0)

        action_box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=4)
        action_box.set_halign(Gtk.Align.CENTER)
        action_lbl = Gtk.Label(label="Press ↵ to Open")
        action_lbl.get_style_context().add_class('action-pill')
        action_sub = Gtk.Label(label="Press Shift+↵ to Show in Nemo")
        action_sub.get_style_context().add_class('preview-kind')
        action_box.pack_start(action_lbl, False, False, 0)
        action_box.pack_start(action_sub, False, False, 0)
        self.preview_box.pack_start(action_box, False, False, 6)

    def _render_system_preview(self, action: SystemAction):
        pb = self._get_themed_pixbuf(action.icon_name, 72)
        img = Gtk.Image.new_from_pixbuf(pb) if pb else Gtk.Image.new_from_icon_name(action.icon_name, Gtk.IconSize.DIALOG)
        img.set_alignment(0.5, 0.5)
        self.preview_box.pack_start(img, False, False, 10)

        lbl_title = Gtk.Label(label=action.name)
        lbl_title.get_style_context().add_class('preview-title')
        self.preview_box.pack_start(lbl_title, False, False, 0)

        lbl_desc = Gtk.Label(label=action.description)
        lbl_desc.get_style_context().add_class('preview-desc')
        lbl_desc.set_line_wrap(True)
        lbl_desc.set_justify(Gtk.Justification.CENTER)
        self.preview_box.pack_start(lbl_desc, False, False, 6)

        spacer = Gtk.Box()
        self.preview_box.pack_start(spacer, True, True, 0)

        action_box = Gtk.Box()
        action_box.set_halign(Gtk.Align.CENTER)
        action_lbl = Gtk.Label(label="Press ↵ to Execute")
        action_lbl.get_style_context().add_class('action-pill')
        action_box.pack_start(action_lbl, False, False, 0)
        self.preview_box.pack_start(action_box, False, False, 6)

    def _render_web_shell_preview(self, item: ResultItem):
        pb = self._get_themed_pixbuf(item.icon_name, 72)
        img = Gtk.Image.new_from_pixbuf(pb) if pb else Gtk.Image.new_from_icon_name(item.icon_name, Gtk.IconSize.DIALOG)
        img.set_alignment(0.5, 0.5)
        self.preview_box.pack_start(img, False, False, 10)

        lbl_title = Gtk.Label(label=item.title)
        lbl_title.get_style_context().add_class('preview-title')
        lbl_title.set_line_wrap(True)
        lbl_title.set_justify(Gtk.Justification.CENTER)
        lbl_title.set_max_width_chars(28)
        self.preview_box.pack_start(lbl_title, False, False, 0)

        lbl_desc = Gtk.Label(label=item.subtitle)
        lbl_desc.get_style_context().add_class('preview-desc')
        self.preview_box.pack_start(lbl_desc, False, False, 4)

        spacer = Gtk.Box()
        self.preview_box.pack_start(spacer, True, True, 0)

        action_box = Gtk.Box()
        action_box.set_halign(Gtk.Align.CENTER)
        hint = "Press ↵ to Search" if item.kind == 'web' else "Press ↵ to Run"
        action_lbl = Gtk.Label(label=hint)
        action_lbl.get_style_context().add_class('action-pill')
        action_box.pack_start(action_lbl, False, False, 0)
        self.preview_box.pack_start(action_box, False, False, 6)

    def _get_themed_pixbuf(self, name: str, size: int) -> Optional[GdkPixbuf.Pixbuf]:
        if not self.icon_theme:
            return None
        try:
            icon_info = self.icon_theme.lookup_icon(name, size, Gtk.IconLookupFlags.FORCE_SIZE)
            if icon_info:
                return icon_info.load_icon()
        except Exception:
            pass
        return None
