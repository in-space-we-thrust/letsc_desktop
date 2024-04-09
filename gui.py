import tkinter as tk
import random
import os
import threading
from queue import Queue
import time

import serial
import json

from communication import connect_to_serial_port, send_message, receive_message, parse_message
from devices import Sensor, Valve

serial_port = "COM6"  # Укажите ваш COM-порт
baud_rate = 115200

serial_connection = connect_to_serial_port(serial_port, baud_rate)

class LabPneumoStand(tk.Tk):
    def __init__(self):
        super().__init__()
        self.geometry("755x252")
        self.title("Laboratory Pneumo Stand Control")

        self.canvas = tk.Canvas(self, width=755, height=252)
        self.canvas.pack()


        # self.valve = self.canvas.create_polygon(50, 116, 65, 126, 50, 136, fill='green', outline='black')
        # self.valve_status = tk.BooleanVar(value=True)
        # self.valve_text = self.canvas.create_text(50, 150, text="ON", fill='green')

        # Загрузка конфигурации датчиков из файла
        config = self.load_config(os.path.dirname(os.path.abspath(__file__))+'/config.json')

        sensors_raw = [Sensor.from_json(sensor_data) for sensor_data in config['sensors']]
        self.sensors = {s.id: s for s in sensors_raw}

        valves_raw = [Valve.from_json(valve_data) for valve_data in config['valves']]
        self.valves = {v.id: v for v in valves_raw}

        self.draw_elements(config)




        # Создание списка объектов Sensor на основе конфигурации
        

        # Вывод информации о датчиках
        for sensor in self.sensors:
            print(sensor)

        self.initialize_sensors()

        # self.toggle_valve_button = tk.Button(self, text="Toggle Valve", command=self.toggle_valve)
        # self.toggle_valve_button.place(x=35, y=170)

        self.sensor_data_queue = Queue()
        self.sensor_thread = threading.Thread(target=self.fetch_sensor_data, daemon=True)
        self.sensor_thread.start()

        self.update_sensor_values_from_queue()

    # Пример использования класса Sensor
    # Загрузка конфигурации из JSON-файла
    def load_config(self, file_path):
        with open(file_path, 'r') as file:
            config = json.load(file)
        return config

    def draw_sensor(self, sensor):
        sensor.rectangle = self.canvas.create_rectangle(sensor.coord_x, sensor.coord_y - 20, sensor.coord_x + 40, sensor.coord_y + 20, outline='black')
        sensor.text = self.canvas.create_text(sensor.coord_x + 20, sensor.coord_y, text=f"{sensor.value}", fill='black')

    def draw_valve(self, valve):
        # Отрисовка треугольного клапана на холсте
        # Координаты вершин треугольника
        vertices = [(valve.coord_x-7, valve.coord_y - 10), (valve.coord_x + 7, valve.coord_y), (valve.coord_x - 7, valve.coord_y + 10)]
        valve.shape = self.canvas.create_polygon(vertices, fill='green', outline='black')
        valve.label = self.canvas.create_text(valve.coord_x-7, valve.coord_y+25, text="ON", fill='green')
        valve.button = tk.Button(self, text="Toggle Valve", command=lambda: self.toggle_valve(valve))
        valve.button.place(x=valve.coord_x - 15, y=valve.coord_y+44)

    def draw_elements(self, config):
        for line in config['lines']:
            self.canvas.create_line(line['start_x'], line['start_y'], line['end_x'], line['end_y'], width=line['width'])

        for sensor in self.sensors.values():
            self.draw_sensor(sensor)

        for valve in self.valves.values():
            self.draw_valve(valve)

    def fetch_sensor_test_data(self):
        while True:
            sensor_data = {
                'velocity': random.randint(0, 100),
                'temperature': random.randint(20, 30),
                'pressure': random.randint(1, 10)
            }
            self.sensor_data_queue.put(sensor_data)
            time.sleep(0.5)  # Simulate the delay of data fetching

    def fetch_sensor_data(self):
        if serial_connection:
            while True:
                received_message = receive_message(serial_connection)
                parsed_message = parse_message(received_message)
                if parsed_message:
                    if parsed_message.get('sensor_id'):
                        print(f"Received data: {received_message}")
                        sensor_data = {
                                parsed_message.get('sensor_id'): parsed_message.get('value')
                            }
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
            self.update_sensor(sensor)

    def update_sensor(self, sensor):
        # self.canvas.coords(sensor.rectangle, sensor_x, sensor.coord_y - 20, sensor_x + 40, sensor.coord_y + 20)
        self.canvas.itemconfig(sensor.text, text=f"{sensor.value}")

    def toggle_valve(self, valve):
        valve.toggle()
        new_color = 'green' if valve.status else 'red'
        new_text = 'ON' if valve.status else 'OFF'
        send_message(serial_connection, json.dumps({"type": 1, "command": 17, "valve": valve.id, "result": 1}))
        self.canvas.itemconfig(valve.shape, fill=new_color)
        self.canvas.itemconfig(valve.label, text=new_text, fill=new_color)

if __name__ == "__main__":
    app = LabPneumoStand()
    app.mainloop()
