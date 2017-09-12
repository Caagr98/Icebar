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

def create_window():
	bg = Gtk.Window()
	bg.set_name("background")
	bg.set_type_hint(Gdk.WindowTypeHint.DOCK)
	bg.set_decorated(False)

	create_strut(bg)

	screen = bg.get_screen()
	curmon = screen.get_monitor_at_window(screen.get_active_window())
	geom = screen.get_monitor_geometry(curmon)
	bg.resize(geom.width, config.HEIGHT)

	fg = Gtk.Window()
	fg.set_name("fg")
	fg.set_app_paintable(True)
	fg.set_visual(fg.get_screen().get_rgba_visual())
	fg.set_type_hint(Gdk.WindowTypeHint.DOCK)
	fg.realize()
	fg.get_window().set_override_redirect(True)

	fg.set_transient_for(bg)
	bg.connect("configure-event", lambda win, evt, to: (to.move(*win.get_position()), to.resize(*win.get_size())) and 0, fg)

	bg.connect("show", lambda win: fg.show())
	bg.connect("hide", lambda win: fg.hide())
	bg.connect("destroy", lambda win: fg.destroy())

	return bg, fg

def create_window2():
	bg = Gtk.Window()
	bg.set_name("fg")
	bg.set_type_hint(Gdk.WindowTypeHint.DOCK)
	bg.set_decorated(False)

	create_strut(bg)

	screen = bg.get_screen()
	curmon = screen.get_monitor_at_window(screen.get_active_window())
	geom = screen.get_monitor_geometry(curmon)
	bg.resize(geom.width, config.HEIGHT)
	return bg, bg

class BG(Gtk.Bin):
	def __init__(self, child=None):
		super().__init__()
		if child is not None:
			self.add(child)

	def do_draw(self, ctx):
		import cairo
		img = cairo.ImageSurface(cairo.FORMAT_ARGB32, self.get_allocated_width(), self.get_allocated_height())
		Gtk.Bin.do_draw(self, cairo.Context(img))
		style = bg.get_style_context()
		ctx.set_source_rgba(*style.get_background_color(style.get_state()))
		f=0.33
		F=-f
		ctx.mask_surface(img, 0, 0)
		ctx.mask_surface(img, f, F)
		ctx.mask_surface(img, 0, F)
		ctx.mask_surface(img, F, F)
		ctx.mask_surface(img, F, 0)
		ctx.mask_surface(img, F, f)
		ctx.mask_surface(img, 0, f)
		ctx.mask_surface(img, f, f)
		ctx.mask_surface(img, f, 0)
		ctx.set_source_surface(img)
		ctx.paint()

bg, fg = create_window()
box = Gtk.Box()
fg.add(BG(box))
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
