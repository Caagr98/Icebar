from gi.repository import Gtk, Gdk, GLib
import os.path
import time
import configparser
import cairo

__all__ = ["Battery"]

class Battery(Gtk.EventBox):
	def __init__(self, path, spacing=3):
		super().__init__()
		self.path = os.path.join(path, "uevent")

		self.icon = BatteryIcon()
		self.text = Gtk.Label()
		box = Gtk.Box(spacing=spacing)
		box.pack_start(self.icon, False, False, 0)
		box.pack_start(self.text, False, False, 0)
		self.add(box)

		GLib.timeout_add_seconds(1, self.update)
		self.update()
		self.set_events(Gdk.EventMask.BUTTON_PRESS_MASK)
		self.connect("button-press-event", self.click)

	def update(self):
		if os.path.exists(self.path):
			self.show()
		else:
			self.hide()
			return True

		cfg = configparser.ConfigParser()
		with open(self.path, "r") as f:
			cfg.read_string("[_]\n" + f.read())
		battery = {}
		for k in cfg["_"]:
			val = cfg["_"][k]
			try:
				val = int(val)
			except ValueError:
				pass
			battery[k.lower()[13:]] = val
		def get(a, b=None): # Because XPS 9560 is weird
			if a in battery:
				return battery[a] / 1000000
			if b in battery:
				return battery[b] / 100000
			return 0

		status = battery["status"]
		energy_now = get("energy_now", "charge_now")
		energy_full = get("energy_full", "charge_full")
		energy_design = get("energy_full_design", "charge_full_design")
		current = get("power_now", "current_now")
		voltage_now = get("voltage_now")
		voltage_design = get("voltage_min_design")

		self.set_tooltip_text(__import__("textwrap").dedent(f"""
		Status: {status}
		Energy: {energy_now}/{energy_full} Wh ({energy_now/energy_full*100:.1f}%)
		Current: {current:+} W

		Voltage: {voltage_now}/{voltage_design} V ({(voltage_now/voltage_design-1)*100:+.1f}%)
		Capacity: {energy_full}/{energy_design} Wh ({energy_full/energy_design*100:.1f}%)
		""").strip("\n"))

		self.icon.set_value(energy_now / energy_full)

		charge = energy_now / energy_full
		text = "{:.0f}%".format(100 * charge)

		if abs(current) > 0.01:
			charging = status == "Charging"
			symbol = {"Charging": "↑", "Discharging": "↓"}.get(status, "")

			if charging:
				remaining = energy_full - energy_now
			else:
				remaining = energy_now
			remainingTime = time.strftime("%H:%M", time.gmtime(remaining / current * 60**2))
			text += " {}{:.2f}W ({})".format(symbol, current, remainingTime)
		self.text.set_text(text)

		return True

	def click(self, _, evt):
		pass

class BatteryIcon(Gtk.DrawingArea):
	def __init__(self):
		super().__init__()
		self.set_value(0)

	def set_value(self, v):
		self.value = v
		self.queue_draw()

	def do_draw(self, ctx):
		ctx.set_fill_rule(cairo.FILL_RULE_EVEN_ODD)
		style = self.get_style_context()
		r, g, b, a = style.get_color(style.get_state())
		ctx.set_source_rgba(r, g, b, a)

		pango = self.get_pango_context()
		metrics = pango.get_metrics()
		fontsize = (metrics.get_ascent() - metrics.get_descent()) / 1024
		pos = (self.get_allocated_height() - fontsize) // 2
		ctx.translate(0, pos)

		def path(pts):
			ctx.new_sub_path()
			for x, y in pts:
				ctx.line_to(x, y)
			ctx.close_path()

		t = max(1, int(fontsize/10))
		h = int(fontsize)
		w = int(fontsize * 1.7) # Doesn't include the nub
		self.set_size_request(w+t, h)

		T = t*2
		W = (w-T*2+0.25)*min(self.value, 1)
		path([
			(T, h-T),
			(T + W, h-T),
			(T + W, T),
			(T, T),
		])

		path([
			(t, h-t),
			(w-t, h-t),
			(w-t, h*3/4-t),
			(w, h*3/4-t),
			(w, h*1/4+t),
			(w-t, h*1/4+t),
			(w-t, t),
			(t, t),
		])

		path([
			(0, h),
			(w, h),
			(w, h*3/4),
			(w+t, h*3/4),
			(w+t, h*1/4),
			(w, h*1/4),
			(w, 0),
			(0, 0),
		])

		ctx.fill()
