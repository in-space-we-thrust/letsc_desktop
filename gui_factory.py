from lab_pneumo_drawing import TkinterDrawing

def create_gui(gui_type, geometry, title):
    if gui_type.lower() == "tkinter":
        return TkinterDrawing(geometry, title)
    else:
        raise ValueError(f"Unsupported GUI type: {gui_type}")