# Icebar

A i3bar-lookalike using GTK. This allows for much more flexibility - drawing
stuff instead of relying on fonts, popups, scrolling... - and is also a lot
easier to code (i3bar's IPC is just tedious).

A few key features include:

* Customize appearance freely (not particularly free yet)
* Customize the widgets on both sides (i3bar only lets you change the right
  side)
* Compatibility with other window managers (only i3 support builtin, but it
  should be easy to add more)
* Icebar is still visible if a fullscr

## TODO

* Update some more status icons (temp, wifi, volume?, mpd)
* Figure out why the FG window turns invisible when i3 is restarted and when
  toggling with the keybinding
* Add some keybindings to the volume widget (maybe also mpd?)
* Find some way to make the transparent bar visible on text-colored
  backgrounds
* Make escape key close popups
* Add CSS nodes for widgets
* Add a charging bolt to the battery icon
