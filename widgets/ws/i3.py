from gi.repository import Gdk
import json
import asyncio
import struct
from .workspaces import WSProvider

__all__ = ["i3"]

class i3ipc:
	COMMAND, GET_WORKSPACES, SUBSCRIBE, GET_OUTPUTS, GET_TREE, GET_MARKS, GET_BAR_CONFIG, GET_VERSION, GET_BINDING_MODES = range(9)
	E_WORKSPACE, E_OUTPUT, E_MODE, E_WINDOW, E_BARCONFIG_UPDATE, E_BINDING = range(6)

	_MAGIC = b"i3-ipc"
	_FORMAT = "=6sII"

	async def __new__(cls, *args):
		self = super().__new__(cls)
		await self._start()
		self._queue = asyncio.Queue()
		self._eventhandlers = []
		asyncio.ensure_future(self._read())
		return self

	async def _start(self):
		proc = await asyncio.create_subprocess_exec("i3", "--get-socketpath", stdout=asyncio.subprocess.PIPE)
		stdout, _ = await proc.communicate()
		self._r, self._w = await asyncio.open_unix_connection(stdout.decode().strip())

	async def _read(self):
		while True:
			msgtype, payload = await self.recvmsg()
			if msgtype & 0x80000000:
				msgtype &= 0x7FFFFFFF
				asyncio.gather(*(f(msgtype, payload) for f in self._eventhandlers))
			else:
				msgtype2, fut = await self._queue.get()
				assert msgtype2 == msgtype
				fut.set_result(payload)

	async def recvmsg(self):
		magic, length, msgtype = struct.unpack(self._FORMAT, await self._r.read(14))
		assert magic == self._MAGIC
		payload = await self._r.read(length)
		return msgtype, json.loads(payload)

	async def command(self, msgtype, payload=None):
		if payload is None:
			payload = b""
		elif isinstance(payload, (list, dict)):
			payload = json.dumps(payload).encode()
		elif isinstance(payload, str):
			payload = payload.encode()
		else:
			raise ValueError(type(payload))
		fut = asyncio.Future()
		await self._queue.put((msgtype, fut))
		self._w.write(struct.pack(self._FORMAT, self._MAGIC, len(payload), msgtype))
		self._w.write(payload)
		return await fut

	def on_event(self, f):
		self._eventhandlers.append(f)

class i3(WSProvider):
	def __init__(self):
		super().__init__()
		asyncio.ensure_future(self.start())

	async def start(self):
		self.i3 = await i3ipc()
		self.i3.on_event(self.on_event)

		await self.i3.command(i3ipc.SUBSCRIBE, ["workspace", "barconfig_update"])
		self.i3.on_event(self.on_event)
		await self.get_workspaces()
		for bar in await self.i3.command(i3ipc.GET_BAR_CONFIG):
			self.barconfig(await self.i3.command(i3ipc.GET_BAR_CONFIG, bar))

	async def get_workspaces(self):
		ws = []
		for w in await self.i3.command(i3ipc.GET_WORKSPACES):
			c = {
				"focused": w["focused"],
				"focused-other": w["visible"],
				"urgent": w["urgent"],
			}
			ws.append((w["name"], c))
		self.emit("workspaces", ws)

	def barconfig(self, barconfig):
		if "focused_workspace_bg" in barconfig["colors"]:
			color = Gdk.RGBA()
			color.parse(barconfig["colors"]["focused_workspace_bg"])
			self.emit("color", tuple(color))

	async def on_event(self, type, payload):
		if type == i3ipc.E_WORKSPACE:
			if payload["change"] in ["focus", "urgent"]:
				await self.get_workspaces()
		if type == i3ipc.E_BARCONFIG_UPDATE:
			self.barconfig(payload)

	def set_workspace(self, name):
		asyncio.ensure_future(self.i3.command(i3ipc.COMMAND, "workspace " + name))
