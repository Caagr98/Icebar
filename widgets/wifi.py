from gi.repository import Gtk, Gdk, GLib
import socket
import fcntl
import struct
import array
import ipaddress

__all__ = ["Wifi"]

# see /usr/include/linux/if.h and sockios.h
SIOCGIWESSID = 0x8B1B
SIOCGIWSTATS = 0x8B0F
SIOCGIFFLAGS = 0x8913
SIOCGIFADDR = 0x8915
SIOCGIFHWADDR = 0x8927

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

def get_ipv4(sock, name):
	fmt = "<16sH2s4s"
	buf = array.array("B", struct.pack(fmt, name.encode(), 0, b"", b""))
	fcntl.ioctl(sock.fileno(), SIOCGIFADDR, buf)
	a = struct.unpack(fmt, buf)[3]
	return str(ipaddress.IPv4Address(int.from_bytes(a, "big")))

def get_ipv6(sock, name):
	with open("/proc/net/if_inet6") as f:
		inet6 = f.read().strip().split("\n")
		for line in inet6:
			addr, id, prefix, scope, flags, name_ = line.split()
			if name_ == name:
				return str(ipaddress.IPv6Address(int(addr, 16)))

def get_mac(sock, name):
	fmt = "<16sH6s"
	buf = array.array("B", struct.pack(fmt, name.encode(), 0, b""))
	fcntl.ioctl(sock.fileno(), SIOCGIFHWADDR, buf)
	a = struct.unpack(fmt, buf)[2]
	return ":".join("%02x" % i for i in a)

def wifi_status(name):
	s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
	up = get_up(s, name)
	essid = up and get_essid(s, name)
	quality = essid and get_quality(s, name)
	ipv4 = essid and get_ipv4(s, name)
	ipv6 = essid and get_ipv6(s, name)
	mac = essid and get_mac(s, name)
	s.close()
	return (up, essid, quality, ipv4, ipv6, mac)

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

		self.tooltip = Gtk.Grid()
		def row(l, i):
			left = Gtk.Label(l)
			right = Gtk.Label()
			left.set_xalign(0)
			right.set_xalign(1)
			self.tooltip.attach(left, 0, i, 1, 1)
			self.tooltip.attach(right, 1, i, 1, 1)
			return right
		self.tt_quality = row("Quality", 0)
		self.tt_ipv4 = row("IPv4", 1)
		self.tt_ipv6 = row("IPv6", 2)
		self.tt_mac = row("MAC", 3)
		self.tooltip.show_all()

		def tooltip(self, x, y, keyboard, tooltip):
			tooltip.set_custom(self.tooltip)
			return True
		self.connect("query-tooltip", tooltip)

		GLib.timeout_add_seconds(1, self.update)
		self.update()
		self.set_events(Gdk.EventMask.BUTTON_PRESS_MASK)
		self.connect("button-press-event", self.click)

		self.icon.show()
		self.text.show()
		box.show()
		self.show()

	def update(self):
		up, essid, quality, ipv4, ipv6, mac = wifi_status(self.interface)

		if up is not None and essid is not None:
			self.set_opacity(1)
			self.set_has_tooltip(True)
			self.tt_quality.set_text("{}%".format(quality))
			self.tt_ipv4.set_text(ipv4)
			self.tt_ipv6.set_text(ipv6)
			self.tt_mac.set_text(mac)
		else:
			self.set_opacity(0.5)
			self.set_has_tooltip(False)

		self.icon.set_text({None: "", False:"", True: ""}[up])
		self.text.set_text({None: "ERROR", False: "OFF", True: essid or "DOWN"}[up])

		return True

	def click(self, _, evt):
		pass
