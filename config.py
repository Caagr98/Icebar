import widgets
import widgets.ws
from urllib.parse import urlparse
import re

KEYBINDING = "<Super>F2"
HEIGHT = 21

CSS = """
#fg { font-family: monospace; font-size: 9.5pt }
"""

def left():
	yield widgets.ws.Workspaces(widgets.ws.i3())

def right():
	yield widgets.Clock()
	yield widgets.IBus({"kkc": "日本語"})
	yield widgets.Battery("/sys/class/power_supply/BAT0")
	yield widgets.Temperature("coretemp-isa-0000", "Package id 0", 45)
	yield widgets.Wifi("wlan0")
	yield widgets.RAM()
	yield widgets.CPUGraph()
	yield widgets.Volume()
	yield widgets.Feeds(
		widgets.RSSFeed("xkcd", "http://xkcd.com/rss.xml"),
		widgets.RSSFeed("what-if", "http://what-if.xkcd.com/feed.atom"),
		widgets.RSSFeed("SaW", "http://www.sandraandwoo.com/feed/", match=lambda e: e.category == "Comics"),
		widgets.RSSFeed("EGS", "http://www.egscomics.com/rss.php", match=lambda e: urlparse(e.link).path == "/index.php", titlefmt=lambda l: re.sub("^El Goonish Shive", "EGS", l), title="El Goonish Shive"),
		widgets.RSSFeed("EGS-NP", "http://www.egscomics.com/rss.php", match=lambda e: urlparse(e.link).path == "/egsnp.php", titlefmt=lambda l: re.sub("^El Goonish Shive - EGS:NP", "EGS:NP", l), title="El Goonish Shive - EGS:NP"),
		widgets.RSSFeed("SD", "http://www.sdamned.com/rss.php"),
		widgets.RSSFeed("AD", "http://feeds.feedburner.com/AvasDemon"),
		widgets.RSSFeed("OotS", "http://www.giantitp.com/comics/oots.rss"),
		widgets.RSSFeed("HG", "http://www.harpygee.com/rss.php"),
		widgets.RSSFeed("CT", "http://www.cuttimecomic.com/rss.php"),
		widgets.RSSFeed("defan", "https://defan752.wordpress.com/feed/", match=lambda e: e.category == "Sword Art Online"),
		None,
		widgets.FFNFeed("HPGTT", 10870770),
		widgets.FFNFeed("MO", 10552390),
		widgets.FFNFeed("MKO", 11815818),
		widgets.FFNFeed("HP&G", 11950816),
		widgets.FFNFeed("TFB", 10666740),
	)
	yield widgets.MPD()
