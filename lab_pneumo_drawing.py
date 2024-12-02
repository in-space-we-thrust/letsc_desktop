import tkinter as tk
import math
import matplotlib.pyplot as plt
import time
from matplotlib.figure import Figure
from matplotlib.backends.backend_tkagg import FigureCanvasTkAgg
from abc import ABC, abstractmethod

GRAPH_TIME_WINDOW = 30  # seconds - окно отображения графика

class DrawingStrategy(ABC):
    @abstractmethod
    def initialize_ui(self, sensors, valves, lines, toggle_valve_callback):
        pass

    @abstractmethod
    def update_sensor(self, sensor):
        pass

    @abstractmethod
    def toggle_valve(self, valve):
        pass

    @abstractmethod
    def run(self):
        pass

class TkinterDrawing(DrawingStrategy):
    def __init__(self, geometry, title):
        self.root = tk.Tk()
        self.root.geometry(geometry)
        self.canvas_width, self.canvas_height = [int(digit) for digit in geometry.split('x')]
        self.root.title(title)
        self.canvas = tk.Canvas(self.root, width=1280, height=768, bg='white')
        self.canvas.pack()
        self.graph_shown = False
        self.current_sensor = None  # Add this line to track current sensor
        self.graph_windows = {}  # Словарь для хранения всех открытых окон графиков
        self.start_time = time.time()  # Добавляем начальное время

    def initialize_ui(self, sensors, valves, lines, toggle_valve_callback):
        self.draw_grid(self.canvas_width, self.canvas_height)
        self.initialize_sensors(sensors)
        self.initialize_valves(valves, toggle_valve_callback)
        self.initialize_lines(lines)
        self.draw_tanks()
        self.draw_combustion_chamber()

    def run(self):
        self.root.mainloop()

    def draw_grid(self, width, height, step=50):
        for x in range(0, width, step):
            self.canvas.create_line(x, 0, x, height, fill='lightgray', dash=(2, 2))
            self.canvas.create_text(x, 5, text=str(x), anchor=tk.NW)
        for y in range(0, height, step):
            self.canvas.create_line(0, y, width, y, fill='lightgray', dash=(2, 2))
            self.canvas.create_text(5, y, text=str(y), anchor=tk.NW)

    def initialize_sensors(self, sensors):
        self.sensors = sensors
        for sensor in sensors.values():
            self.draw_sensor(sensor)

        # Данные для графиков
        self.graph_time_data = []
        self.graph_sensor_data = {sensor_id: [] for sensor_id in sensors}
        
        # Добавляем общую привязку для всех тегов сенсоров
        for sensor in sensors.values():
            self.canvas.tag_bind(
                f"sensor_{sensor.id}",
                '<Button-1>', 
                lambda event, s=sensor: self.show_graph_window(s)
            )

    def initialize_valves(self, valves, toggle_valve_callback):
        for valve in valves.values():
            self.draw_valve(valve)
            valve.button = tk.Button(self.root, text="Toggle Valve", 
                                     command=lambda v=valve: toggle_valve_callback(v))
            valve.button.place(x=valve.coord_x - 15, y=valve.coord_y + 44)

    def initialize_lines(self, lines):
        for line in lines:
            self.canvas.create_line(line['start_x'], line['start_y'], 
                                    line['end_x'], line['end_y'], 
                                    width=line['width'])

    def draw_tanks(self):
        self.draw_tank(50, 500, 50, 100, 0.2)
        self.draw_tank(650, 175, 50, 100, 0.2, 'red')
        self.draw_tank(650, 625, 50, 100, 0.2, 'blue')

    def draw_combustion_chamber(self):
        self.draw_combustion_chamber_shape(1050, 325, 30, 52, 20, 40, 80, "right")

    def draw_sensor(self, sensor):
        sensor_tag = f"sensor_{sensor.id}"
        
        # Создаем прямоугольник с очень светлым фоном
        sensor.rectangle = self.canvas.create_rectangle(
            sensor.coord_x, sensor.coord_y - 20, 
            sensor.coord_x + 40, sensor.coord_y + 20, 
            outline='green',
            fill='#FAFAFA',  # Очень светлый фон вместо прозрачного
            tags=sensor_tag
        )
        
        # Добавляем тег ко всем элементам
        sensor.name_text = self.canvas.create_text(
            sensor.coord_x, sensor.coord_y-13, 
            anchor=tk.W, 
            text=sensor.name, 
            fill='black',
            tags=sensor_tag
        )
        
        sensor.text = self.canvas.create_text(
            sensor.coord_x + 20, 
            sensor.coord_y, 
            text=f"{sensor.value}", 
            fill='black',
            tags=sensor_tag
        )
        
        sensor.units_text = self.canvas.create_text(
            sensor.coord_x+20, 
            sensor.coord_y+13, 
            anchor=tk.W, 
            text=sensor.units, 
            fill='black',
            tags=sensor_tag
        )

    def draw_valve(self, valve):
        vertices = [(valve.coord_x-7, valve.coord_y - 10), (valve.coord_x + 7, valve.coord_y), (valve.coord_x - 7, valve.coord_y + 10)]
        valve.shape = self.canvas.create_polygon(vertices, fill='green', outline='black')
        valve.label = self.canvas.create_text(valve.coord_x-7, valve.coord_y+25, text="ON", fill='green')

    def draw_tank(self, center_x, center_y, thickness, height, curvature, fill='lightblue'):
        x1 = center_x - thickness / 2
        y1 = center_y - height / 2
        x2 = center_x + thickness / 2
        y2 = center_y + height / 2
        return self.canvas.create_rectangle(x1, y1, x2, y2, fill=fill, outline='black')

    def draw_combustion_chamber_shape(self, center_x, center_y, width, height,
                                      nozzle_start_radius, nozzle_end_radius,
                                      nozzle_length, nozzle_orientation):
        chamber_left = center_x - width / 2
        chamber_right = center_x + width / 2
        chamber_top = center_y - height / 2
        chamber_bottom = center_y + height / 2
        self.canvas.create_rectangle(chamber_left, chamber_top, chamber_right, chamber_bottom, fill="gray")

        nozzle_start_x = chamber_right if nozzle_orientation == "right" else chamber_left - nozzle_length
        nozzle_start_y = center_y
        nozzle_end_x = nozzle_start_x + nozzle_length if nozzle_orientation == "right" else nozzle_start_x - nozzle_length
        nozzle_end_y = center_y

        num_points = 50
        bell_curve_points = []
        for i in range(num_points + 1):
            t = i / num_points
            x = nozzle_start_x + t * (nozzle_end_x - nozzle_start_x)
            radius = nozzle_start_radius + (nozzle_end_radius - nozzle_start_radius) * (1 - math.cos(math.pi * t)) / 2
            y_top = nozzle_start_y - radius
            y_bottom = nozzle_start_y + radius
            bell_curve_points.append((x, y_top))

        for i in range(num_points, -1, -1):
            t = i / num_points
            x = nozzle_start_x + t * (nozzle_end_x - nozzle_start_x)
            radius = nozzle_start_radius + (nozzle_end_radius - nozzle_start_radius) * (1 - math.cos(math.pi * t)) / 2
            y_top = nozzle_start_y - radius
            y_bottom = nozzle_start_y + radius
            bell_curve_points.append((x, y_bottom))

        self.canvas.create_polygon(bell_curve_points, fill="gray")

    def update_sensor(self, sensor):
        # Update sensor display
        self.canvas.itemconfig(sensor.text, text=f"{sensor.value}")

    def toggle_valve(self, valve):
        new_color = 'green' if valve.status else 'red'
        new_text = 'ON' if valve.status else 'OFF'
        self.canvas.itemconfig(valve.shape, fill=new_color)
        self.canvas.itemconfig(valve.label, text=new_text, fill=new_color)

    def show_graph_window(self, sensor):
        print(f"Opening graph window for sensor {sensor.name}...")
        
        # Если окно для этого сенсора уже открыто, показываем его
        if sensor.id in self.graph_windows:
            self.graph_windows[sensor.id]['window'].lift()
            return
            
        graph_window = tk.Toplevel(self.root)
        graph_window.title(f"Sensor {sensor.name} Data")
        graph_window.geometry("600x400")
        
        fig = Figure(figsize=(5, 4), dpi=100)
        ax = fig.add_subplot(111)
        
        graph_canvas = FigureCanvasTkAgg(fig, master=graph_window)
        graph_canvas.draw()
        graph_canvas.get_tk_widget().pack(fill=tk.BOTH, expand=True)

        # Сохраняем информацию об окне графика
        self.graph_windows[sensor.id] = {
            'window': graph_window,
            'figure': fig,
            'ax': ax,
            'canvas': graph_canvas,
            'time_data': [],
            'sensor_data': []
        }
        
        # Обработчик закрытия окна
        graph_window.protocol("WM_DELETE_WINDOW", 
                            lambda s=sensor.id: self.on_graph_window_close(s))
        
        self.graph_shown = True

    def on_graph_window_close(self, sensor_id):
        """Обработчик закрытия окна графика"""
        if sensor_id in self.graph_windows:
            self.graph_windows[sensor_id]['window'].destroy()
            del self.graph_windows[sensor_id]
        
        if not self.graph_windows:  # Если больше нет открытых окон
            self.graph_shown = False

    def update_graph(self, sensors):
        if not self.graph_shown or not self.graph_windows:
            return

        current_time = time.time() - self.start_time

        # Обновляем каждый открытый график
        for sensor_id, graph_data in self.graph_windows.items():
            sensor = sensors.get(sensor_id)
            if not sensor or sensor.value is None:
                continue

            # Добавляем новые данные
            graph_data['time_data'].append(current_time)
            graph_data['sensor_data'].append(sensor.value)

            # Удаляе�� старые данные
            while (len(graph_data['time_data']) > 0 and 
                   current_time - graph_data['time_data'][0] > GRAPH_TIME_WINDOW):
                graph_data['time_data'].pop(0)
                graph_data['sensor_data'].pop(0)

            # Обновляем график
            graph_data['ax'].clear()
            graph_data['ax'].plot(graph_data['time_data'], 
                                graph_data['sensor_data'],
                                label=sensor.name)
            
            graph_data['ax'].set_xlim([max(0, current_time - GRAPH_TIME_WINDOW), 
                                     current_time])
            graph_data['ax'].set_xlabel("Time (s)")
            graph_data['ax'].set_ylabel(f"Value ({sensor.units})")
            graph_data['ax'].legend()
            graph_data['canvas'].draw()