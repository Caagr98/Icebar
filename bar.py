#!/usr/bin/env python3
import gi
gi.require_version("Gtk", "3.0")
gi.require_version("Keybinder", "3.0")
from gi.repository import Gtk, Gdk, Keybinder

from dbus.mainloop.glib import DBusGMainLoop
DBusGMainLoop(set_as_default=True)

import config

style_provider = Gtk.CssProvider()
style_provider.load_from_data(config.CSS.encode())
Gtk.StyleContext.add_provider_for_screen(Gdk.Screen.get_default(), style_provider, Gtk.STYLE_PROVIDER_PRIORITY_APPLICATION)

def create_strut(win):
	from Xlib import display, Xatom
	screen = win.get_screen()
	curmon = screen.get_monitor_at_window(screen.get_active_window())
	geom = screen.get_monitor_geometry(curmon)

	win.realize()
	disp = display.Display()
	xwin = disp.create_resource_object("window", win.get_window().get_xid())
	xwin.change_property(
		disp.intern_atom("_NET_WM_STRUT_PARTIAL"),
		Xatom.CARDINAL,
		32,
		[0,0,0,config.HEIGHT, 0,0, 0,0, 0,0, 0,geom.width])
	disp.sync()

def mkwin():
	w = Gtk.Window()
	w.set_type_hint(Gdk.WindowTypeHint.DOCK)
	w.set_decorated(False)
	w.set_app_paintable(True)
	w.set_visual(w.get_screen().get_rgba_visual())
	create_strut(w)
	return w

def create_window():
	bg = mkwin()
	bg.set_name("background")

	screen = bg.get_screen()
	curmon = screen.get_monitor_at_window(screen.get_active_window())
	geom = screen.get_monitor_geometry(curmon)
	bg.resize(geom.width, config.HEIGHT)

	fg = mkwin()
	fg.realize()
	fg.get_window().set_override_redirect(True)
	fg.set_name("fg")
	fg.set_transient_for(bg)

	bg.connect("configure-event", lambda win, evt, to: (to.move(*win.get_position()), to.resize(*win.get_size())) and 0, fg)

	bg.connect("show", lambda win: (fg.hide(), fg.show()))
	bg.connect("hide", lambda win: fg.hide())
	bg.connect("destroy", lambda win: fg.destroy())

	return bg, fg

def draw_bg(self, ctx, a2):
	import cairo
	style = self.get_style_context()
	r,g,b,a=style.get_background_color(style.get_state())
	ctx.set_source_rgba(r,g,b,a*a2)
	ctx.set_operator(cairo.OPERATOR_SOURCE)
	ctx.paint()
	ctx.set_operator(cairo.OPERATOR_OVER)

def __main__():
	bg, fg = create_window()
	box = Gtk.Box()
	fg.connect("draw", draw_bg, 1/2)
	bg.connect("draw", draw_bg, 3/4)
	fg.add(box)
	right = []

	def update_seps(_=None):
		lastVisible = False
		for w, sep in right:
			sep.set_visible(lastVisible)
			lastVisible = w.is_visible()

	from widgets import Separator

	for w in config.left():
		box.pack_start(w, False, False, 1)

	for w in config.right():
		sep = Separator()
		right.append((w, sep))
		w.connect("show", update_seps)
		w.connect("hide", update_seps)
		box.pack_end(sep, False, False, 0)
		box.pack_end(w, False, False, 4)

	box.show()
	bg.show()
	fg.show_all()
	update_seps()

	if config.KEYBINDING:
		Keybinder.init()
		def toggle_visibility(key, win):
			win.set_visible(not win.is_visible())
		Keybinder.bind(config.KEYBINDING, toggle_visibility, bg)

	from gi.repository import GLib
	GLib.MainLoop().run()

if __name__ == "__main__": __main__()
