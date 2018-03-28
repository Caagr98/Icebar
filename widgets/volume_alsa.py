from gi.repository import Gtk, GLib, Keybinder
import ctypes as c
import struct

__all__ = ["AlsaVolume"]

P = c.POINTER
p = c.pointer
def errno(i):
	if i != 0:
		raise ValueError(i)
def fn(f, ret, *args):
	f.restype = ret
	f.argtypes = args
	return f
asound = c.CDLL("libasound.so")

class _alsa_array:
	__slots__ = ["__selem", "__get", "__set", "__setall", "__type"]
	def __init__(self, selem, get, set, setall, type):
		self.__selem = selem
		self.__get = get
		self.__set = set
		self.__setall = setall
		self.__type = type
	def __setitem__(self, k, v):
		return self.__set(self.__selem, k, v)
	def __getitem__(self, k):
		p = self.__type()
		self.__get(self.__selem, k, p)
		return p.value
	def __iter__(self):
		for a in range(32):
			if a in self.__selem:
				yield self[a]
	@property
	def all(self):
		return max(self)
	@all.setter
	def all(self, v):
		self.__setall(self.__selem, v)

class selem(c.c_void_p):
	@property
	def mB(self): # The ALSA functions are named dB, but they actually use millibel.
		return _alsa_array(self, selem_get_playback_dB, selem_set_playback_dB, selem_set_playback_dB_all, c.c_long)
	@property
	def switch(self):
		return _alsa_array(self, selem_get_playback_switch, selem_set_playback_switch, selem_set_playback_switch_all, c.c_bool)

	@property
	def mB_range(self):
		p1, p2 = c.c_long(), c.c_long()
		selem_get_playback_dB_range(self, p1, p2)
		return int(p1.value), int(p2.value)

	def __contains__(self, k):
		return selem_has_playback_channel(self, k)

chanid = c.c_int

mixp = c.c_void_p
open            = fn(asound.snd_mixer_open,            errno, P(mixp), c.c_int)
attach          = fn(asound.snd_mixer_attach,          errno, mixp, c.c_char_p)
selem_register  = fn(asound.snd_mixer_selem_register,  errno, mixp, c.c_void_p, P(c.c_void_p))
load            = fn(asound.snd_mixer_load,            errno, mixp)

find_selem                       = fn(asound.snd_mixer_find_selem,                       selem, mixp, c.c_void_p)

selem_has_playback_channel       = fn(asound.snd_mixer_selem_has_playback_channel,       c.c_bool, selem, chanid)

selem_get_playback_dB            = fn(asound.snd_mixer_selem_get_playback_dB,            errno, selem, chanid, P(c.c_long))
selem_set_playback_dB            = fn(asound.snd_mixer_selem_set_playback_dB,            errno, selem, chanid, c.c_long)
selem_set_playback_dB_all        = fn(asound.snd_mixer_selem_set_playback_dB_all,        errno, selem, c.c_long)

selem_get_playback_switch        = fn(asound.snd_mixer_selem_get_playback_switch,        errno, selem, chanid, P(c.c_bool))
selem_set_playback_switch        = fn(asound.snd_mixer_selem_set_playback_switch,        errno, selem, chanid, c.c_bool)
selem_set_playback_switch_all    = fn(asound.snd_mixer_selem_set_playback_switch_all,    errno, selem, c.c_bool)

selem_get_playback_dB_range      = fn(asound.snd_mixer_selem_get_playback_dB_range,      errno, selem, P(c.c_long), P(c.c_long))

class pollfd(c.Structure):
	_fields_ = [
		("fd", c.c_int),
		("events", c.c_short),
		("revents", c.c_short),
	]
poll_descriptors = fn(asound.snd_mixer_poll_descriptors, c.c_int, mixp, P(pollfd), c.c_uint)
poll_descriptors_count = fn(asound.snd_mixer_poll_descriptors_count, c.c_int, mixp)

elem_callback = c.CFUNCTYPE(c.c_int, mixp, c.c_uint)
elem_set_callback = fn(asound.snd_mixer_elem_set_callback, None, selem, elem_callback)
handle_events = fn(asound.snd_mixer_handle_events, mixp)


class AlsaVolume(Gtk.EventBox):
	def __init__(self, card="hw:0", name="Master", id=0, base=80, keys=False, spacing=3):
		super().__init__()

		self.icon = Gtk.Label()
		self.text = Gtk.Label()
		box = Gtk.Box(spacing=spacing)
		box.pack_start(self.icon, False, False, 0)
		box.pack_start(self.text, False, False, 0)
		self.add(box)

		self.icon.show()
		self.text.show()
		box.show()
		self.show()

		self.base = base

		self.handle = c.c_void_p()
		open(self.handle, 0)
		attach(self.handle, card.encode())
		selem_register(self.handle, None, None)
		load(self.handle)
		self.elem = find_selem(self.handle, struct.pack("<60sI", name.encode(), id))

		self.min, self.max = self.elem.mB_range

		self.update()
		self.ggg = elem_callback(self.update)
		elem_set_callback(self.elem, self.ggg)

		nfds = poll_descriptors_count(self.handle)
		fds = (pollfd * nfds)()
		poll_descriptors(self.handle, fds, nfds)
		for a in fds:
			GLib.io_add_watch(a.fd, GLib.IO_IN, lambda *_: handle_events(self.handle) or self.update() or True)

		if keys:
			def toggleSwitch(): self.elem.switch.all = not self.elem.switch.all
			def setSwitch(v): self.elem.switch.all = v
			def changeVolume(n): self.elem.mB.all += n
			Keybinder.bind("AudioMute", lambda _: toggleSwitch())
			Keybinder.bind("AudioRaiseVolume", lambda _: changeVolume(+250))
			Keybinder.bind("AudioLowerVolume", lambda _: changeVolume(-250))
			Keybinder.bind("<Shift>AudioMute", lambda _: setSwitch(False))
			Keybinder.bind("<Shift>AudioRaiseVolume", lambda _: changeVolume(+50))
			Keybinder.bind("<Shift>AudioLowerVolume", lambda _: changeVolume(-50))

	def update(self, *_):
		self.text.set_text("{:.1f} dB".format(self.elem.mB.all / 100 + self.base))
		self.icon.set_text("♪")
		self.set_opacity(1 if self.elem.switch.all else 0.5)
		return False
