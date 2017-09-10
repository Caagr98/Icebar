from gi.repository import Gtk, Gdk, GLib
import socket
import fcntl
import struct
import array

__all__ = ["Wifi"]

SIOCGIWESSID = 0x8B1B
SIOCGIWSTATS = 0x8B0F
SIOCGIFFLAGS = 0x8913

IFF_UP = 1<<0

IW_ESSID_MAX_SIZE = 32

def ioctl_ptr(sock, ctl, name, buffer, flags=0):
	fmt = "<16sQHH"
	buf = array.array("B", struct.pack(fmt, name.encode(), buffer.buffer_info()[0], len(buffer), 0))
	fcntl.ioctl(sock.fileno(), ctl, buf)
	buffer_len = struct.unpack(fmt, buf)[2]
	return buffer.tobytes()[:buffer_len]

def get_essid(sock, name):
	buf = array.array('B', b'\0' * IW_ESSID_MAX_SIZE)
	return ioctl_ptr(sock, SIOCGIWESSID, name, buf).decode() or None

def get_quality(sock, name):
	buf = array.array('B', b'\0' * 32)
	ret = ioctl_ptr(sock, SIOCGIWSTATS, name, buf)
	return ret[2]

def get_up(sock, name):
	fmt = "<16sH"
	buf = array.array("B", struct.pack(fmt, name.encode(), 0))
	fcntl.ioctl(sock.fileno(), SIOCGIFFLAGS, buf)
	flags = struct.unpack(fmt, buf)[1]
	return bool(flags & IFF_UP)

def wifi_status(name):
	try:
		s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
		up = get_up(s, name)
		essid = get_essid(s, name)
		quality = get_quality(s, name) if essid is not None else None
		s.close()
		return (up, essid, quality)
	except OSError:
		return None, None, None

class Wifi(Gtk.EventBox):
	def __init__(self, interface, spacing=3):
		super().__init__()
		self.interface = interface

		self.icon = Gtk.Label()
		self.text = Gtk.Label()
		box = Gtk.Box(spacing=spacing)
		box.pack_start(self.icon, False, False, 0)
		box.pack_start(self.text, False, False, 0)
		self.add(box)

		GLib.timeout_add_seconds(1, self.update)
		self.update()
		self.set_events(Gdk.EventMask.BUTTON_PRESS_MASK)
		self.connect("button-press-event", self.click)

		self.icon.show()
		self.text.show()
		box.show()
		self.show()

	def update(self):
		up, essid, quality = wifi_status(self.interface)

		if up is not None and essid is not None:
			self.set_opacity(1)
			self.set_tooltip_text("Quality: {}%".format(quality))
		else:
			self.set_opacity(0.5)
			self.set_has_tooltip(False)

		self.icon.set_text({None: "", False:"", True: ""}[up])
		self.text.set_text({None: "ERROR", False: "OFF", True: essid or "DOWN"}[up])

		return True

	def click(self, _, evt):
		pass
