import gi

gi.require_version("Gtk", "4.0")
from gi.repository import Gtk, Gdk, Gio, GLib  # noqa: E402

from . import engine, preview  # noqa: E402

REFIND_DIR = "/boot/efi/EFI/refind"


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
        box.append(rail)

        self.preview_holder = Gtk.Box()
        self.preview_holder.set_hexpand(True)
        self.preview_holder.set_vexpand(True)
        box.append(self.preview_holder)

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
            self._run(lambda: engine.import_theme(path))
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
        return box

    def _run(self, work):
        """Run a write op; show any failure in a dialog and refresh the list."""
        try:
            work()
        except Exception as exc:  # subprocess.CalledProcessError etc.
            dlg = Gtk.AlertDialog()
            dlg.set_message("Operation failed")
            dlg.set_detail(str(exc))
            dlg.show(self)
        self._reload_themes()


class App(Gtk.Application):
    def __init__(self):
        super().__init__(application_id="com.prettyboot.App")

    def do_activate(self):
        Window(self).present()
