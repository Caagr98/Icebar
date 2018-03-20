from gi.repository import Gtk, Gdk, GLib, Keybinder
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

mixp = c.c_void_p
open = fn(asound.snd_mixer_open, errno, P(mixp), c.c_int)
attach = fn(asound.snd_mixer_attach, errno, mixp, c.c_char_p)
selem_register = fn(asound.snd_mixer_selem_register, errno, mixp, c.c_void_p, P(c.c_void_p))
load = fn(asound.snd_mixer_load, errno, mixp)

selemidp = c.c_void_p
selemp = c.c_void_p
def selem_id_alloca(): return c.create_string_buffer(64)
selem_id_set_index = fn(asound.snd_mixer_selem_id_set_index, None, selemidp, c.c_uint)
selem_id_set_name = fn(asound.snd_mixer_selem_id_set_name, None, selemidp, c.c_char_p)
find_selem = fn(asound.snd_mixer_find_selem, selemp, mixp, selemidp)

chanid = c.c_int
selem_ask_playback_vol_dB        = fn(asound.snd_mixer_selem_ask_playback_vol_dB,        errno, selemp, c.c_long, P(c.c_long))
selem_has_playback_channel       = fn(asound.snd_mixer_selem_has_playback_channel,       c.c_bool, selemp, chanid)

selem_has_common_volume          = fn(asound.snd_mixer_selem_has_common_volume,          c.c_bool, selemp)
selem_has_playback_volume        = fn(asound.snd_mixer_selem_has_playback_volume,        c.c_bool, selemp)
selem_has_playback_volume_joined = fn(asound.snd_mixer_selem_has_playback_volume_joined, c.c_bool, selemp)
selem_get_playback_volume        = fn(asound.snd_mixer_selem_get_playback_volume,        errno, selemp, chanid, P(c.c_long))
selem_set_playback_volume        = fn(asound.snd_mixer_selem_set_playback_volume,        errno, selemp, chanid, c.c_long)
selem_set_playback_volume_all    = fn(asound.snd_mixer_selem_set_playback_volume_all,    errno, selemp, c.c_long)
selem_get_playback_dB            = fn(asound.snd_mixer_selem_get_playback_dB,            errno, selemp, chanid, P(c.c_long))
selem_set_playback_dB            = fn(asound.snd_mixer_selem_set_playback_dB,            errno, selemp, chanid, c.c_long)
selem_set_playback_dB_all        = fn(asound.snd_mixer_selem_set_playback_dB_all,        errno, selemp, c.c_long)

selem_has_common_switch          = fn(asound.snd_mixer_selem_has_common_volume,          c.c_bool, selemp)
selem_has_playback_switch        = fn(asound.snd_mixer_selem_has_playback_volume,        c.c_bool, selemp)
selem_has_playback_switch_joined = fn(asound.snd_mixer_selem_has_playback_volume_joined, c.c_bool, selemp)
selem_get_playback_switch        = fn(asound.snd_mixer_selem_get_playback_switch,        errno, selemp, chanid, P(c.c_bool))
selem_set_playback_switch        = fn(asound.snd_mixer_selem_set_playback_switch,        errno, selemp, chanid, c.c_bool)
selem_set_playback_switch_all    = fn(asound.snd_mixer_selem_set_playback_switch_all,    errno, selemp, c.c_bool)

selem_get_playback_volume_range  = fn(asound.snd_mixer_selem_get_playback_volume_range,  errno, selemp, P(c.c_long), P(c.c_long))
selem_set_playback_volume_range  = fn(asound.snd_mixer_selem_set_playback_volume_range,  errno, selemp, c.c_long, c.c_long)
selem_get_playback_dB_range      = fn(asound.snd_mixer_selem_get_playback_dB_range,      errno, selemp, P(c.c_long), P(c.c_long))

class pollfd(c.Structure):
	_fields_ = [
		("fd", c.c_int),
		("events", c.c_short),
		("revents", c.c_short),
	]
poll_descriptors = fn(asound.snd_mixer_poll_descriptors, c.c_int, mixp, P(pollfd), c.c_uint)
poll_descriptors_count = fn(asound.snd_mixer_poll_descriptors_count, c.c_int, mixp)

elem_callback = c.CFUNCTYPE(c.c_int, mixp, c.c_uint)
elem_set_callback = fn(asound.snd_mixer_elem_set_callback, None, selemp, elem_callback)
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

		minp, maxp = c.c_long(), c.c_long()
		selem_get_playback_dB_range(self.elem, minp, maxp)
		self.min, self.max = minp.value, maxp.value

		self.update()
		self.ggg = elem_callback(self.update)
		elem_set_callback(self.elem, self.ggg)

		nfds = poll_descriptors_count(self.handle)
		fds = (pollfd * nfds)()
		poll_descriptors(self.handle, fds, nfds)
		for a in fds:
			GLib.io_add_watch(a.fd, GLib.IO_IN, lambda *_: handle_events(self.handle) or self.update() or True)

		if keys:
			Keybinder.bind("AudioMute", lambda _: self.setMute(not self.getMute()))
			Keybinder.bind("AudioRaiseVolume", lambda _: self.changeVolume(+2))
			Keybinder.bind("AudioLowerVolume", lambda _: self.changeVolume(-2))

	def update(self, *_):
		self.updateVolume()
		self.updateMute()
		return False

	def updateVolume(self):
		self.text.set_text("{:.1f} dB".format(self.getVolume_() / 100 + self.base))
		self.icon.set_text("♪")

	def updateMute(self):
		self.set_opacity(0.5 if self.getMute() else 1)

	def getMute(self):
		a = []
		p = c.c_bool()
		for i in range(32):
			if selem_has_playback_channel(self.elem, i):
				selem_get_playback_switch(self.elem, i, p)
				a.append(p.value)
		return not all(a)

	def setMute(self, m):
		selem_set_playback_switch_all(self.elem, not m)

	def getVolume(self):
		return self.norm(self.getVolume_())
	def getVolume_(self):
		a = []
		p = c.c_long()
		for i in range(32):
			if selem_has_playback_channel(self.elem, i):
				selem_get_playback_dB(self.elem, i, p)
				a.append(p.value)
		return max(a)

	def setVolume(self, v):
		return self.setVolume_(self.denorm(v))
	def setVolume_(self, v):
		selem_set_playback_dB_all(self.elem, v)

	def toDB(self, v):
		return self.denorm(v) / 100

	def norm(self, v):
		return (v-self.min)/(self.max-self.min)
	def denorm(self, v):
		return round(v*(self.max-self.min)+self.min)

	def changeVolume(self, d):
		self.setVolume_(self.getVolume_() + d * 250)
