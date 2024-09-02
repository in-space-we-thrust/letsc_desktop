import tkinter as tk
import random
import os
import threading
import queue
import time
import math

import serial
import json

from communication import connect_to_serial_port, send_message, receive_message, parse_message
from devices import Sensor, Valve
from drawing import draw_sensor, draw_valve, draw_tank, draw_combustion_chamber, draw_grid



class LabPneumoStand(tk.Tk):
    def __init__(self):
        super().__init__()
        self.geometry("1280x768")
        self.title("Laboratory Pneumo Stand Control")

        self.canvas = tk.Canvas(self, width=1280, height=768, bg='white')
        self.canvas.pack()

        draw_grid(self.canvas, 1280, 768)

        self.sensors = {}
        self.valves = {}
        self.lines = []
        self.sensor_data_queue = queue.Queue()
        self.serial_connections = {}  # Словарь для хранения соединений по портам

        self.load_config_and_connect()

        self.initialize_sensors()
        self.initialize_valves()
        self.initialize_lines()

        self.serial_queue = queue.Queue()
        self.stop_event = threading.Event()

        for port in self.serial_connections:
            thread = threading.Thread(target=self.serial_read_thread, args=(port,))
            thread.daemon = True
            thread.start()

        self.after(100, self.process_serial_data)

        self.update_sensor_values_from_queue()

    def serial_read_thread(self, port):
        connection = self.serial_connections[port]
        while not self.stop_event.is_set():
            try:
                received_message = receive_message(connection, timeout=1)
                if received_message:
                    self.serial_queue.put((port, received_message))
            except Exception as e:
                print(f"Error reading from {port}: {str(e)}")
            #time.sleep(0.1)

    def process_serial_data(self):
        try:
            while not self.serial_queue.empty():
                item = self.serial_queue.get_nowait()
                port, message = item
                parsed_message = parse_message(message)
                if parsed_message and parsed_message.get('sensor_id'):
                    sensor_id = parsed_message['sensor_id']
                    value = parsed_message['value']
                    sensor_data = {sensor_id: value}
                    self.sensor_data_queue.put(sensor_data)
                else:
                    print(f"Received command from {port}: {message}")
        except queue.Empty:
            pass
        finally:
            self.after(100, self.process_serial_data)

    def on_closing(self):
        self.stop_event.set()
        # Подождите, пока все потоки завершатся
        time.sleep(1)
        self.destroy()

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



    def initialize_lines(self):
        for line in self.lines:
            self.canvas.create_line(line['start_x'], line['start_y'], line['end_x'], line['end_y'], width=line['width'])

        draw_tank(self.canvas, 50, 500, 50, 100, 0.2)
        draw_tank(self.canvas, 650, 175, 50, 100, 0.2, 'red')
        draw_tank(self.canvas, 650, 625, 50, 100, 0.2, 'blue')

        draw_combustion_chamber(self.canvas, 1050, 325, 30, 52, 20, 40, 80, "right")

    def fetch_sensor_data(self):
        while True:
            for port, connection in self.serial_connections.items():
                if connection:
                    received_message = receive_message(connection)
                    parsed_message = parse_message(received_message)
                    if parsed_message and parsed_message.get('sensor_id'):
                        print(f"Received message: {parsed_message}")
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
            self.after(100, self.update_sensor_values_from_queue)

    def initialize_sensors(self):
        for sensor in self.sensors.values():
            draw_sensor(self.canvas, sensor)

    def initialize_valves(self):
        for valve in self.valves.values():
            draw_valve(self.canvas, valve)
            valve.button = tk.Button(self, text="Toggle Valve", command=lambda v=valve: self.toggle_valve(v))
            valve.button.place(x=valve.coord_x - 15, y=valve.coord_y+44)

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
    app.protocol("WM_DELETE_WINDOW", app.on_closing)
    app.mainloop()
