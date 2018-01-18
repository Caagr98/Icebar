from gi.repository import Gtk, Gdk, GLib, Pango, Keybinder
import cairo
import os
import os.path
import socket
import collections
import re
import util

__all__ = ["MPD"]

def stripfname(title, num=False):
	title = os.path.basename(title)
	if not num:
		title = re.sub(r"^[0-9\-]+(\.| -) ", "", title) # Strip leading numbers ("xx. " and "xx - ") (and also "x-xx - " for multiparts)
	title = re.sub(r"\.[^.]+?$", "", title) # Strip file extension
	return title

def gettitle(track, num=False):
	if "Title" in track:
		title = track["Title"]
		if num and "Track" in track:
			title = f"{track['Track']} - {track['Title']}"
		else:
			title = track["Title"]
	elif "file" in track:
		title = stripfname(track["file"], num=num)
	else:
		title = "<Unknown>"
	return title

class MPDClient: # {{{1
	def __init__(self, *, on_connect=None):
		self.host = os.getenv("MPD_HOST", "localhost")
		self.port = os.getenv("MPD_PORT", None)
		self.on_connect = on_connect
		self._reset()

	def _reset(self):
		self.sock = None
		self.queue = collections.deque()
		self.header = False
		self.input = b""
		self.output = b""
		self._source_in = None
		self._source_err = None
		self._source_out = None

	def connect(self):
		assert self.host[:1] == "/" # Currently only support unix sockets
		self.sock = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
		try:
			self.sock.connect(self.host)
		except ConnectionRefusedError:
			print("Failed to connect to MPD :(")
			GLib.timeout_add_seconds(1, self.connect)
			return
		self._source_in = GLib.io_add_watch(self, GLib.IO_IN, self._on_input)
		self._source_err = GLib.io_add_watch(self, GLib.IO_ERR | GLib.IO_HUP, self._on_connection_lost)

	def disconnect(self):
		if self._source_in is not None: GLib.source_remove(self._source_in)
		if self._source_err is not None: GLib.source_remove(self._source_err)
		if self._source_out is not None: GLib.source_remove(self._source_out)
		self.sock.close()
		for a in self.queue:
			if a is not None:
				a(None)
		self._reset()

	def _on_connection_lost(self, source, state):
		assert source == self
		print("Connection to MPD lost, attempting to reestablish")
		self.disconnect()
		self.connect()
		return False

	def _on_input(self, source, state):
		assert source == self
		self.input += os.read(self.fileno(), 1<<16)
		while True:
			idx = self.input.find(ord("\n"))
			if idx == -1:
				break
			line = self.input[:idx].decode("utf-8")
			self.input = self.input[idx+1:]
			if not self.header:
				assert line == "OK MPD 0.20.0"
				self.header = True
				self.response = []
				if self.on_connect:
					self.on_connect()
				continue
			assert not line.startswith("ACK ")
			if line == "OK":
				callback = self.queue.popleft()
				if callback is not None:
					GLib.idle_add(callback, self.response, priority=100)
				self.response = []
				continue
			k, v = line.split(": ", 1)
			self.response.append((k, v))
		return True

	def fileno(self):
		return self.sock.fileno()

	def command(self, command, *args, callback=None):
		self.queue.append(callback)
		s = []
		s.append("noidle\n")
		s.append(command)
		for a in args:
			s.append(' "')
			s.append(a.replace('\\', '\\\\').replace('"', '\\"'))
			s.append('"')
		s.append("\n")
		self.output += "".join(s).encode()
		self._source_out = GLib.io_add_watch(self, GLib.IO_OUT, self._on_output)

	def _on_output(self, source, state):
		n = os.write(self.fileno(), self.output)
		self.output = self.output[n:]
		if self.output:
			return True
		else:
			self._source_out = None
			return False
# }}}

class MPD(Gtk.EventBox):
	def __init__(self, keys=False, spacing=3):
		super().__init__()

		self.icon = Gtk.Label()
		self.text = ProgressLabel()
		scroll = util.scrollable(self.text, h=False, v=None)
		scroll.set_propagate_natural_width(True)
		self.text.connect("hide", lambda _: scroll.hide())
		self.text.connect("show", lambda _: scroll.show())
		box = Gtk.Box(spacing=spacing)
		box.pack_start(self.icon, False, False, 0)
		box.pack_start(scroll, False, False, 0)
		self.add(box)

		self.mpd = MPDClient(on_connect=self.on_connect)
		self.mpd.connect()
		self.mpd_state = None
		self.current_song = None

		self.treestore = Gtk.TreeStore(str, str, str) # Display name, search name, filename

		self.set_events(Gdk.EventMask.BUTTON_PRESS_MASK)
		self.connect("button-press-event", self.click_body)
		self.icon.set_has_window(True)
		self.icon.set_events(Gdk.EventMask.BUTTON_PRESS_MASK)
		self.icon.connect("button-press-event", self.click_icon)
		self.text.set_has_window(True)
		self.text.set_events(Gdk.EventMask.BUTTON_PRESS_MASK)
		self.text.connect("button-press-event", self.click_text)

		self.ticker = None
		self.popup = None

		if keys:
			Keybinder.bind("AudioPlay", self.do_toggle)
			Keybinder.bind("<Shift>AudioPlay", self.do_stop)
			Keybinder.bind("AudioPrev", self.do_prev)
			Keybinder.bind("AudioNext", self.do_next)

	def search_function(self, model, column, key, rowiter, tree):
		if key == key.lower():
			match = lambda row: key.lower() in row[column].lower()
		else:
			match = lambda row: key in row[column]
		def expand_row(row):
			should_expand = any([expand_row(child) for child in row.iterchildren()])
			if should_expand:
				tree.expand_to_path(row.path)
			else:
				tree.collapse_row(row.path)
			return should_expand or match(row)
		row = model[rowiter]
		expand_row(row)
		return not match(row)

	def tree_activate_row(self, tree, path, column):
		if getattr(Gtk.get_current_event(), "state", 0) & Gdk.ModifierType.SHIFT_MASK:
			self.mpd.command("add", tree.get_model()[path][-1])
		else:
			self.mpd.command("clear")
			self.mpd.command("add", tree.get_model()[path][-1])
			self.mpd.command(self.mpd_state)

	def on_connect(self):
		self.idle([("change", "player"), ("change", "database")])

	def idle(self, response):
		if response is None: return
		for k, v in response:
			if v == "player":
				self.mpd.command("status", callback=self.update_status)
				self.mpd.command("currentsong", callback=self.update_song)
			if v == "database":
				self.treestore.clear()
				self.treestore.append(None, row=["—", "", ""])
				self.mpd.command("lsinfo", callback=lambda r: self.create_playlist(r, self.treestore, None))
		self.mpd.command("idle", callback=self.idle)

	def tick(self):
		self.mpd.command("status", callback=self.update_status)
		return True

	def update_status(self, response):
		if response is None: return
		status = dict(response)
		self.mpd_state = status["state"]
		self.icon.set_text({"play": "", "pause": "", "stop": ""}[self.mpd_state])
		self.text.set_visible(self.mpd_state != "stop")
		self.set_opacity(1 if self.mpd_state != "stop" else 0.25)

		if self.ticker is None and self.mpd_state == "play":
			self.ticker = GLib.timeout_add(100, self.tick)
		if self.ticker is not None and self.mpd_state != "play":
			GLib.source_remove(self.ticker)
			self.ticker = None

		if "elapsed" in status and "duration" in status:
			self.text.set_bounds(float(status.get("elapsed")), float(status.get("duration")))

	def update_song(self, response):
		if not response: return
		currentsong = dict(response)
		self.text.set_text(gettitle(currentsong))
		self.current_song = currentsong["file"]

	def create_playlist(self, response, tree, node):
		files = []
		for k, v in response:
			if k in ["file", "directory"]:
				files.append({"_type": k})
			files[-1][k] = v
		for f in files:
			if f["_type"] == "file":
				tree.append(node, row=[gettitle(f, num=True), gettitle(f), f["file"]])
			elif f["_type"] == "directory":
				dirname = os.path.basename(f["directory"])
				child = tree.append(node, row=[dirname, dirname, f["directory"]])
				self.mpd.command("lsinfo", f["directory"], callback=lambda r, child=child: self.create_playlist(r, self.treestore, child))
			else:
				assert False

	def click_icon(self, icon, evt):
		if evt.type != Gdk.EventType.BUTTON_PRESS: return
		if evt.button == 1:
			self.do_toggle()
		if evt.button == 2:
			self.do_stop()

	def do_toggle(self, _=0):
		if self.mpd_state != "play":
			self.mpd.command("play")
		else:
			self.mpd.command("pause")

	def do_stop(self, _=0):
		self.mpd.command("stop")

	def do_prev(self, _=0):
		def f(response):
			if response is None: return
			status = dict(response)
			if "elapsed" in status and float(status["elapsed"]) < 1:
				self.mpd.command("previous")
			else:
				self.mpd.command("seekcur", "0")
		self.mpd.command("status", callback=f)

	def do_next(self, _=0):
		self.mpd.command("next")

	def click_text(self, label, evt):
		if evt.type != Gdk.EventType.BUTTON_PRESS: return
		if evt.button == 1:
			if evt.x < 5:
				self.do_prev()
			elif evt.x >= label.get_allocated_width() - 5:
				self.do_next()
			else:
				self.mpd.command("seekcur", str(evt.x / label.get_allocated_width() * label.max))
	
	def click_body(self, body, evt):
		if evt.type != Gdk.EventType.BUTTON_PRESS: return
		if evt.button == 3:
			tree = Gtk.TreeView(self.treestore)
			tree.insert_column_with_attributes(0, "Title", Gtk.CellRendererText(), text=0)
			tree.set_enable_search(True)
			tree.set_search_column(1)
			tree.set_search_equal_func(self.search_function, tree)
			tree.set_headers_visible(False)
			tree.connect("row-activated", self.tree_activate_row)
			def walk(model, path, iter):
				if model[iter][-1] == self.current_song:
					tree.expand_to_path(path)
					tree.scroll_to_cell(path, None, True, 0.5, 0.5)
					tree.set_cursor(path, None, False)
			self.treestore.foreach(walk)
			self.popup = util.make_popup(util.framed(util.scrollable(tree, h=None)), self)
			self.popup.set_default_size(0, 300)
			self.popup.show_all()

class ProgressLabel(Gtk.Label):
	def __init__(self):
		Gtk.Label.__init__(self)
		self.set_bounds(0, 0)

	def set_bounds(self, current, max):
		self.current = current
		self.max = max
		self.queue_draw()

	def do_draw(self, ctx):
		Gtk.Label.do_draw(self, ctx) # super() doesn't work for some reason

		if not self.current or not self.max: return

		style = self.get_style_context()
		color = style.get_color(style.get_state())

		ctx.set_line_cap(cairo.LINE_CAP_BUTT)
		ctx.set_source_rgba(*color)

		pango = self.get_pango_context()
		metrics = pango.get_metrics()
		height = self.get_allocated_height() * Pango.SCALE
		pos = (height + metrics.get_ascent()-metrics.get_descent())/2

		upos, thick = metrics.get_underline_position(), metrics.get_underline_thickness()
		pos -= upos
		pos /= Pango.SCALE
		thick /= Pango.SCALE

		len = self.current / self.max * self.get_allocated_width()
		ctx.move_to(0, pos)
		ctx.line_to(len, pos)
		ctx.line_to(len, pos + thick)
		ctx.line_to(0, pos + thick)
		ctx.fill()
