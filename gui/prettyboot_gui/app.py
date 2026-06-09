import os
import threading

import gi

gi.require_version("Gtk", "4.0")
from gi.repository import Gtk, Gdk, Gio, GLib  # noqa: E402

from . import engine, preview  # noqa: E402

# Honor REFIND_DIR like the CLI does, so the GUI can run against a sandbox.
REFIND_DIR = os.environ.get("REFIND_DIR", "/boot/efi/EFI/refind")


class Window(Gtk.ApplicationWindow):
    def __init__(self, app):
        super().__init__(application=app, title="prettyboot")
        self.set_default_size(900, 560)
        notebook = Gtk.Notebook()
        self.set_child(notebook)
        notebook.append_page(self._themes_tab(), Gtk.Label(label="Themes"))
        notebook.append_page(self._settings_tab(), Gtk.Label(label="Settings"))
        notebook.append_page(self._advanced_tab(), Gtk.Label(label="Advanced"))

    # --- Themes tab: slim rail + full-size preview ---
    def _themes_tab(self):
        box = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=12)
        box.set_margin_top(12); box.set_margin_bottom(12)
        box.set_margin_start(12); box.set_margin_end(12)

        rail = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=6)
        rail.set_size_request(180, -1)
        self.theme_list = Gtk.ListBox()
        self.theme_list.connect("row-selected", self._on_theme_selected)
        rail.append(self.theme_list)

        drop = Gtk.Frame(label="Drop theme folder / .zip")
        drop.set_size_request(-1, 80)
        self._enable_drop(drop)
        rail.append(drop)

        apply_btn = Gtk.Button(label="Apply")
        apply_btn.connect("clicked", self._on_apply)
        rail.append(apply_btn)

        if not engine.has_managed_block():
            self.setup_banner = Gtk.Button(label="Set up boot menu")
            self.setup_banner.connect(
                "clicked",
                lambda _b: self._run(
                    engine.setup_boot,
                    on_done=lambda: self.setup_banner.set_visible(False)))
            rail.prepend(self.setup_banner)

        box.append(rail)

        self.preview_holder = Gtk.Box()
        self.preview_holder.set_hexpand(True)
        self.preview_holder.set_vexpand(True)
        box.append(self.preview_holder)

        bg_drop = Gtk.DropTarget.new(Gio.File, Gdk.DragAction.COPY)
        bg_drop.connect("drop", self._on_bg_drop)
        self.preview_holder.add_controller(bg_drop)

        self._reload_themes()
        return box

    def _reload_themes(self):
        child = self.theme_list.get_first_child()
        while child:
            self.theme_list.remove(child)
            child = self.theme_list.get_first_child()
        for name, active, valid in engine.list_themes():
            label = ("● " if active else "") + name + ("" if valid else "  ✗")
            row = Gtk.ListBoxRow()
            row.set_child(Gtk.Label(label=label, xalign=0))
            row.theme_name = name
            self.theme_list.append(row)

    def _on_theme_selected(self, _listbox, row):
        if not row:
            return
        holder = self.preview_holder
        old = holder.get_first_child()
        if old:
            holder.remove(old)
        holder.append(preview.build_widget(f"{REFIND_DIR}/themes/{row.theme_name}"))

    def _on_apply(self, _btn):
        row = self.theme_list.get_selected_row()
        if row:
            self._run(lambda: engine.use_theme(row.theme_name))

    def _enable_drop(self, widget):
        target = Gtk.DropTarget.new(Gio.File, Gdk.DragAction.COPY)
        target.connect("drop", self._on_drop)
        widget.add_controller(target)

    def _on_drop(self, _t, value, _x, _y):
        path = value.get_path()
        if path:
            self._run(lambda: engine.import_path(path))
        return True

    def _on_bg_drop(self, _t, value, _x, _y):
        row = self.theme_list.get_selected_row()
        path = value.get_path()
        if not row:
            dlg = Gtk.AlertDialog()
            dlg.set_message("Select a theme first")
            dlg.set_detail("Pick the theme that should get this background, "
                           "then drop the image again.")
            dlg.show(self)
            return True
        if path:
            self._run(lambda: engine.set_asset(row.theme_name, "background", path),
                      on_done=lambda: self._on_theme_selected(None, row))
        return True

    # --- Settings tab: curated controls ---
    def _settings_tab(self):
        grid = Gtk.Grid(row_spacing=10, column_spacing=10)
        grid.set_margin_top(16); grid.set_margin_start(16)
        self.timeout_entry = Gtk.Entry(text=engine.get_setting("timeout"))
        grid.attach(Gtk.Label(label="Timeout (sec, 0=off):", xalign=0), 0, 0, 1, 1)
        grid.attach(self.timeout_entry, 1, 0, 1, 1)
        self.res_entry = Gtk.Entry(text=engine.get_setting("resolution"))
        grid.attach(Gtk.Label(label="Resolution (W H):", xalign=0), 0, 1, 1, 1)
        grid.attach(self.res_entry, 1, 1, 1, 1)
        save = Gtk.Button(label="Save settings")
        save.connect("clicked", self._on_save_settings)
        grid.attach(save, 1, 2, 1, 1)
        return grid

    def _on_save_settings(self, _btn):
        def work():
            engine.set_timeout(self.timeout_entry.get_text() or "0")
            res = self.res_entry.get_text().strip()
            if res:
                engine.set_setting("resolution", res)
        self._run(work)

    # --- Advanced tab: raw refind.conf ---
    def _advanced_tab(self):
        box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=8)
        box.set_margin_top(12); box.set_margin_start(12); box.set_margin_end(12)
        warn = Gtk.Label(
            label="Editing raw refind.conf. A timestamped backup is made on save. "
                  "Keep the prettyboot >>> / <<< markers.", xalign=0)
        box.append(warn)
        self.raw_view = Gtk.TextView()
        self.raw_view.set_monospace(True)
        try:
            with open(f"{REFIND_DIR}/refind.conf") as fh:
                self.raw_view.get_buffer().set_text(fh.read())
        except OSError:
            pass
        scroll = Gtk.ScrolledWindow()
        scroll.set_child(self.raw_view)
        scroll.set_vexpand(True)
        box.append(scroll)
        save = Gtk.Button(label="Save (backup first)")
        save.connect("clicked", self._on_save_raw)
        box.append(save)
        return box

    def _on_save_raw(self, _btn):
        buf = self.raw_view.get_buffer()
        text = buf.get_text(buf.get_start_iter(), buf.get_end_iter(), True)
        self._run(lambda: engine.write_conf(text))

    def _run(self, work, on_done=None):
        """Run a write op on a worker thread; report failure in a dialog and
        refresh the theme list back on the main thread."""
        def worker():
            try:
                work()
                err = None
            except Exception as exc:
                err = str(exc)
            GLib.idle_add(self._after_run, err, on_done)
        threading.Thread(target=worker, daemon=True).start()

    def _after_run(self, err, on_done):
        if err:
            dlg = Gtk.AlertDialog()
            dlg.set_message("Operation failed")
            dlg.set_detail(err)
            dlg.show(self)
        elif on_done:
            on_done()
        self._reload_themes()
        return False


class App(Gtk.Application):
    def __init__(self):
        super().__init__(application_id="com.prettyboot.App")

    def do_activate(self):
        Window(self).present()
