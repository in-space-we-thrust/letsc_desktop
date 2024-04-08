import tkinter as tk
import random
import threading
from queue import Queue
import time

import serial
import json

def connect_to_serial_port(port, baudrate=115200):
    try:
        ser = serial.Serial(port, baudrate)
        return ser
    except serial.SerialException as e:
        print(f"Error: {e}")
        return None

def send_message(ser, message):
    ser.write(message.encode())
    ser.write("\n".encode())

def receive_message(ser):
    return ser.readline().decode().strip()

def parse_message(str_msg):
    try:
        result = json.loads(str_msg)
    except ValueError:
        result = None
        print("not json message", str_msg)
    return result

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

        self.canvas.create_line(50, 126, 705, 126, width=2)

        self.valve = self.canvas.create_polygon(50, 116, 65, 126, 50, 136, fill='green', outline='black')
        self.valve_status = tk.BooleanVar(value=True)
        self.valve_text = self.canvas.create_text(50, 150, text="ON", fill='green')

        self.sensors = {
            'velocity': {'id': 'V', 'rectangle': None, 'text': None, 'value': 0},
            'temperature': {'id': 'T', 'rectangle': None, 'text': None, 'value': 0},
            'pressure': {'id': 'P', 'rectangle': None, 'text': None, 'value': 0}
        }

        for sensor_id, sensor in self.sensors.items():
            sensor_x = 250 + (100 * list(self.sensors.keys()).index(sensor_id))  # Adjust x-coordinate based on sensor position
            sensor['rectangle'] = self.canvas.create_rectangle(sensor_x, 76, sensor_x + 40, 116, outline='black')
            sensor['text'] = self.canvas.create_text(sensor_x + 20, 96, text=f"{sensor['value']}", fill='black')

        self.initialize_sensors()

        self.toggle_valve_button = tk.Button(self, text="Toggle Valve", command=self.toggle_valve)
        self.toggle_valve_button.place(x=35, y=170)

        self.sensor_data_queue = Queue()
        self.sensor_thread = threading.Thread(target=self.fetch_sensor_data, daemon=True)
        self.sensor_thread.start()

        self.update_sensor_values_from_queue()

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
                value = None
                received_message = receive_message(serial_connection)
                parsed_message = parse_message(received_message)
                if parsed_message:
                    if parsed_message.get('sensor_id'):
                        sensor_data = {}
                        print(f"Received data: {received_message}")
                        if parsed_message.get('sensor_id') == 1:
                            sensor_data = {
                                'velocity': parsed_message.get('value')
                            }
                        elif parsed_message.get('sensor_id') == 17:
                            sensor_data = {
                                'temperature': parsed_message.get('value')
                            }
                        self.sensor_data_queue.put(sensor_data)
                    else:
                        print(f"Received command: {received_message}")
                    

    def update_sensor_values_from_queue(self):
        try:
            while not self.sensor_data_queue.empty():
                data = self.sensor_data_queue.get_nowait()
                for sensor_id, value in data.items():
                    self.sensors[sensor_id]['value'] = value
                    self.update_sensor(sensor_id)
        finally:
            self.after(500, self.update_sensor_values_from_queue)

    def initialize_sensors(self):
        for sensor_id in self.sensors:
            self.update_sensor(sensor_id)

    def update_sensor(self, sensor_id):
        sensor = self.sensors[sensor_id]
        value = sensor['value']
        sensor_x = 250 + (100 * list(self.sensors.keys()).index(sensor_id))
        self.canvas.coords(sensor['rectangle'], sensor_x, 76, sensor_x + 40, 116)
        self.canvas.itemconfig(sensor['text'], text=f"{value}")

    def toggle_valve(self):
        current_status = self.valve_status.get()
        self.valve_status.set(not current_status)
        new_color = 'green' if self.valve_status.get() else 'red'
        new_text = 'ON' if self.valve_status.get() else 'OFF'
        send_message(serial_connection, json.dumps({"type": 1, "command": 17, "valve": 3, "result": 1}))
        self.canvas.itemconfig(self.valve, fill=new_color)
        self.canvas.itemconfig(self.valve_text, text=new_text, fill=new_color)

if __name__ == "__main__":
    app = LabPneumoStand()
    app.mainloop()
