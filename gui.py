import tkinter as tk
import random
import os
import threading
from queue import Queue
import time
import math

import serial
import json

from communication import connect_to_serial_port, send_message, receive_message, parse_message
from devices import Sensor, Valve


# serial_port = "COM6"  # Укажите ваш COM-порт
# baud_rate = 115200

# serial_connection = connect_to_serial_port(serial_port, baud_rate)

class LabPneumoStand(tk.Tk):
    def __init__(self):
        super().__init__()
        self.geometry("1280x768")
        self.title("Laboratory Pneumo Stand Control")

        self.canvas = tk.Canvas(self, width=1280, height=768, bg='white')
        self.canvas.pack()

        # Рисование координатной сетки
        for x in range(0, 1280, 50):
            self.canvas.create_line(x, 0, x, 768, fill='lightgray', dash=(2, 2))
            self.canvas.create_text(x, 5, text=str(x), anchor=tk.NW)
        for y in range(0, 768, 50):
            self.canvas.create_line(0, y, 1280, y, fill='lightgray', dash=(2, 2))
            self.canvas.create_text(5, y, text=str(y), anchor=tk.NW)

        self.sensors = {}
        self.valves = {}
        self.lines = []
        self.sensor_data_queue = Queue()
        self.serial_connections = {}  # Словарь для хранения соединений по портам

        self.load_config_and_connect()

        self.initialize_sensors()
        self.initialize_valves()
        self.initialize_lines()

        self.sensor_thread = threading.Thread(target=self.fetch_sensor_data, daemon=True)
        self.sensor_thread.start()

        self.update_sensor_values_from_queue()

    # Пример использования класса Sensor
    # Загрузка конфигурации из JSON-файла
    def load_config(self, file_path):
        with open(file_path, 'r') as file:
            config = json.load(file)
        return config
    
    def load_config_and_connect(self):
        config = self.load_config(os.path.dirname(os.path.abspath(__file__))+'/config.json')
        for sensor_data in config['sensors']:
            sensor = Sensor.from_json(sensor_data)
            self.sensors[sensor.id] = sensor
            if sensor.port not in self.serial_connections:
                self.serial_connections[sensor.port] = connect_to_serial_port(sensor.port, 115200)

        for valve_data in config['valves']:
            valve = Valve.from_json(valve_data)
            self.valves[valve.id] = valve
            # Создаем соединение по порту для каждого клапана
            if valve.port not in self.serial_connections:
                self.serial_connections[valve.port] = connect_to_serial_port(valve.port, 115200)

        self.lines = config['lines']


    def draw_sensor(self, sensor):
        sensor.rectangle = self.canvas.create_rectangle(sensor.coord_x, sensor.coord_y - 20, sensor.coord_x + 40, sensor.coord_y + 20, outline='green')
        sensor.name_text = self.canvas.create_text(sensor.coord_x, sensor.coord_y-13, anchor=tk.W, text=sensor.name, fill='black')
        sensor.text = self.canvas.create_text(sensor.coord_x + 20, sensor.coord_y, text=f"{sensor.value}", fill='black')
        sensor.units_text = self.canvas.create_text(sensor.coord_x+20, sensor.coord_y+13, anchor=tk.W, text=sensor.units, fill='black')


    def draw_valve(self, valve):
        # Отрисовка треугольного клапана на холсте
        # Координаты вершин треугольника
        vertices = [(valve.coord_x-7, valve.coord_y - 10), (valve.coord_x + 7, valve.coord_y), (valve.coord_x - 7, valve.coord_y + 10)]
        valve.shape = self.canvas.create_polygon(vertices, fill='green', outline='black')
        valve.label = self.canvas.create_text(valve.coord_x-7, valve.coord_y+25, text="ON", fill='green')
        valve.button = tk.Button(self, text="Toggle Valve", command=lambda: self.toggle_valve(valve))
        valve.button.place(x=valve.coord_x - 15, y=valve.coord_y+44)

    def draw_tank(self, center_x, center_y, thickness, height, curvature, fill='lightblue'):
        # Вычисляем координаты углов прямоугольника, описывающего бак
        x1 = center_x - thickness / 2
        y1 = center_y - height / 2
        x2 = center_x + thickness / 2
        y2 = center_y + height / 2

        # Отрисовываем прямоугольную часть бака
        tank_rect = self.canvas.create_rectangle(x1, y1, x2, y2, fill=fill, outline='black')

        return tank_rect

    def draw_combustion_chamber(self, center_x, center_y, width, height, nozzle_start_radius, nozzle_end_radius, nozzle_length, nozzle_orientation):
        # Рисуем камеру сгорания
        chamber_left = center_x - width / 2
        chamber_right = center_x + width / 2
        chamber_top = center_y - height / 2
        chamber_bottom = center_y + height / 2
        self.canvas.create_rectangle(chamber_left, chamber_top, chamber_right, chamber_bottom, fill="gray")

        # Рисуем сопло Белла
        nozzle_start_x = chamber_right if nozzle_orientation == "right" else chamber_left - nozzle_length
        nozzle_start_y = center_y
        nozzle_end_x = nozzle_start_x + nozzle_length if nozzle_orientation == "right" else nozzle_start_x - nozzle_length
        nozzle_end_y = center_y

        # Расчет точек кривой Белла
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

        # Рисуем кривую Белла
        self.canvas.create_polygon(bell_curve_points, fill="gray")

    def initialize_lines(self):
        for line in self.lines:
            self.canvas.create_line(line['start_x'], line['start_y'], line['end_x'], line['end_y'], width=line['width'])

        self.draw_tank(50, 500, 50, 100, 0.2)
        self.draw_tank(650, 175, 50, 100, 0.2, 'red')
        self.draw_tank(650, 625, 50, 100, 0.2, 'blue')

        self.draw_combustion_chamber(1050, 325, 30, 52, 20, 40, 80, "right")

    def fetch_sensor_data(self):
        while True:
            for port, connection in self.serial_connections.items():
                if connection:
                    received_message = receive_message(connection)
                    parsed_message = parse_message(received_message)
                    if parsed_message and parsed_message.get('sensor_id'):
                        sensor_id = parsed_message['sensor_id']
                        value = parsed_message['value']
                        sensor_data = {sensor_id: value}
                        self.sensor_data_queue.put(sensor_data)
                    else:
                        print(f"Received command: {received_message}")
                    

    def update_sensor_values_from_queue(self):
        try:
            while not self.sensor_data_queue.empty():
                data = self.sensor_data_queue.get_nowait()
                for sensor_id, value in data.items():
                    sensor = self.sensors.get(sensor_id)
                    sensor.value = value
                    self.update_sensor(sensor)
        finally:
            self.after(500, self.update_sensor_values_from_queue)

    def initialize_sensors(self):
        for sensor in self.sensors.values():
            self.draw_sensor(sensor)

    def initialize_valves(self):
        for valve in self.valves.values():
            self.draw_valve(valve)

    def update_sensor(self, sensor):
        # self.canvas.coords(sensor.rectangle, sensor_x, sensor.coord_y - 20, sensor_x + 40, sensor.coord_y + 20)
        self.canvas.itemconfig(sensor.text, text=f"{sensor.value}")

    def toggle_valve(self, valve):
        connection = self.serial_connections.get(valve.port)
        if connection:
            send_message(connection, json.dumps({"type": 1, "command": 17, "valve": valve.id, "result": 1}))
        else:
            return
        valve.toggle()
        new_color = 'green' if valve.status else 'red'
        new_text = 'ON' if valve.status else 'OFF'
        
        self.canvas.itemconfig(valve.shape, fill=new_color)
        self.canvas.itemconfig(valve.label, text=new_text, fill=new_color)

if __name__ == "__main__":
    app = LabPneumoStand()
    app.mainloop()
