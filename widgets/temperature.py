from gi.repository import Gtk, Gdk, GLib
import re
import subprocess
import util

__all__ = ["Temperature"]

input_re = re.compile(r"^  temp\d+_input: (\d+\.\d+)$")
max_re = re.compile(r"^  temp\d+_max: (\d+\.\d+)$")
crit_re = re.compile(r"^  temp\d+_crit: (\d+\.\d+)$")

class Temperature(Gtk.EventBox):
	def __init__(self, chip, which, idle, crit=None, spacing=3):
		super().__init__()
		self.chip = chip
		self.which = which
		self.idle = idle
		self.crit = crit

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
		out = subprocess.check_output(["sensors", "-uA", self.chip]).decode().splitlines()[1:]
		temp = None
		crit = self.crit
		for line in out:
			if line.endswith(":"):
				which = line[:-1]
			elif which == self.which:
				if not temp:
					_input = input_re.match(line)
					if _input:
						temp = float(_input.group(1))
				if not crit:
					_max = max_re.match(line)
					if _max:
						crit = float(_max.group(1))
				if not crit:
					_crit = crit_re.match(line)
					if _crit:
						crit = float(_crit.group(1))

		self.icon.set_text(util.symbol(["", "", "", "", ""], (temp-self.idle)/(crit-self.idle)))
		self.text.set_text("{:.0f}°C".format(temp))

		return True

	def click(self, _, evt):
		pass
