from lab_pneumo_logic import LabPneumoLogic
from gui_factory import create_gui
from logger_config import set_log_level
import logging

class LabPneumoStand(LabPneumoLogic):
    def __init__(self, gui_strategy):
        self.gui = gui_strategy
        LabPneumoLogic.__init__(self, self.gui)

    def run(self):
        self.gui.run()

if __name__ == "__main__":
    # Установка уровня логирования перед созданием приложения
    # Можно установить один из уровней: DEBUG, INFO, WARNING, ERROR, CRITICAL
    set_log_level(level="WARNING")  # Для всех логгеров
    # Или для конкретного логгера:
    # set_log_level(name="LabPneumoLogic", level="DEBUG")
    
    gui_strategy = create_gui("tkinter", "1280x768", "Laboratory Pneumo Stand Control")
    app = LabPneumoStand(gui_strategy)
    app.run()