from gi.repository import GLib, GObject, Gdk
import collections
import json
import subprocess
import socket
import os
from .workspaces import WSProvider

__all__ = ["i3"]

class i3ipc(GObject.Object):
	COMMAND, GET_WORKSPACES, SUBSCRIBE, GET_OUTPUTS, GET_TREE, GET_MARKS, GET_BAR_CONFIG, GET_VERSION, GET_BINDING_MODES = range(9)
	E_WORKSPACE, E_OUTPUT, E_MODE, E_WINDOW, E_BARCONFIG_UPDATE, E_BINDING = range(6)

	_MAGIC = b"i3-ipc"

	@GObject.Signal
	def ready(self): pass
	@GObject.Signal(arg_types=[int, object])
	def event(self, type, payload): pass

	def __init__(self):
		super().__init__()
		self.socketpath = subprocess.check_output(["i3", "--get-socketpath"]).decode().rstrip("\n")
		self._reset()

	def _reset(self):
		self.sock = None
		self.queue = collections.deque()
		self.inbuf = b""
		self.outbuf = b""
		self._source_in = None
		self._source_err = None
		self._source_out = None

		self.state = 0
		self.type, self.length = None, None

	def connect_(self):
		self.sock = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
		try:
			self.sock.connect(self.socketpath)
		except ConnectionRefusedError:
			print("Failed to connect to i3 :(")
			GLib.timeout_add_seconds(1, self.connect_)
			return
		self._source_in = GLib.io_add_watch(self, GLib.IO_IN, self._on_input)
		self._source_err = GLib.io_add_watch(self, GLib.IO_ERR | GLib.IO_HUP, self._on_connection_lost)
		self.emit("ready")

	def disconnect_(self):
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
		print("Connection to i3 lost, attempting to reestablish")
		self.disconnect_()
		self.connect_()
		return False

	def _on_input(self, source, state):
		def skip(n):
			a = self.inbuf[:n]
			self.inbuf = self.inbuf[n:]
			return a
		self.inbuf += os.read(self.fileno(), 1<<16)
		while True:
			if self.state == 0 and len(self.inbuf) >= len(i3ipc._MAGIC) + 8:
				assert skip(len(i3ipc._MAGIC)) == i3ipc._MAGIC
				self.length = int.from_bytes(skip(4), "little")
				self.type = int.from_bytes(skip(4), "little")
				self.state = 1
			if self.state == 1 and len(self.inbuf) >= self.length:
				payload = json.loads(skip(self.length))
				if self.type & 0x80000000:
					self.emit("event", self.type & 0x7FFFFFFF, payload)
				else:
					sent_type, callback = self.queue.popleft()
					assert sent_type == self.type
					if callback:
						callback(payload)
				self.type, self.length = None, None
				self.state = 0
				continue
			break
		return True

	def fileno(self):
		return self.sock.fileno()

	def command(self, type, payload, callback=None):
		self.queue.append((type, callback))
		payload = payload.encode() if payload is not None else b''
		s = (
			i3ipc._MAGIC
			+ int.to_bytes(len(payload), 4, "little")
			+ int.to_bytes(type, 4, "little")
			+ payload
		)
		self.outbuf += s
		self._source_out = GLib.io_add_watch(self, GLib.IO_OUT, self._on_output)

	def _on_output(self, source, state):
		n = os.write(self.fileno(), self.outbuf)
		self.outbuf = self.outbuf[n:]
		if self.outbuf:
			return True
		else:
			self._source_out = None
			return False

class i3(WSProvider):
	def __init__(self):
		super().__init__()
		self.i3 = i3ipc()
		self.i3.connect_()

		self.i3.command(i3ipc.SUBSCRIBE, '["workspace", "barconfig_update"]')
		self.i3.command(i3ipc.GET_WORKSPACES, '', self.get_workspaces)
		self.i3.command(i3ipc.GET_BAR_CONFIG, '',
			lambda bars: [
				self.i3.command(i3ipc.GET_BAR_CONFIG, bar, self.barconfig)
				for bar in bars
			])
		self.i3.connect("event", self.on_event)

	def get_workspaces(self, workspaces):
		ws = []
		for w in workspaces:
			c = 0
			if w["visible"]: c = 1
			if w["focused"]: c = 2
			if w["urgent"]: c = 3
			ws.append((w["name"], c))
		self.emit("workspaces", ws)

	def barconfig(self, barconfig):
		if "focused_workspace_bg" in barconfig["colors"]:
			color = Gdk.RGBA()
			color.parse(barconfig["colors"]["focused_workspace_bg"])
			self.emit("color", tuple(color))

	def on_event(self, i3, type, payload):
		if type == i3ipc.E_WORKSPACE:
			if payload["change"] in ["focus", "urgent"]:
				i3.command(i3ipc.GET_WORKSPACES, '', self.get_workspaces)
		if type == i3ipc.E_BARCONFIG_UPDATE:
			self.barconfig(payload)

	def set_workspace(self, name):
		self.i3.command(i3ipc.COMMAND, "workspace " + name)
