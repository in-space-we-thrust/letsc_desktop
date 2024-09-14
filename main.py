import tkinter as tk
from lab_pneumo_logic import LabPneumoLogic
from gui_factory import create_gui

class LabPneumoStand(LabPneumoLogic):
    def __init__(self, gui_strategy):
        self.gui = gui_strategy
        LabPneumoLogic.__init__(self, self.gui)

    def run(self):
        self.gui.run()

if __name__ == "__main__":
    gui_strategy = create_gui("tkinter", "1280x768", "Laboratory Pneumo Stand Control")
    app = LabPneumoStand(gui_strategy)
    app.run()