from pygetwindow import getActiveWindow as gw
from frontend import *

terminal = None
while terminal is None:
    terminal = gw.getActiveWindow()
if terminal:
    app = TerminalApp(terminal, klanten)
    app.run()