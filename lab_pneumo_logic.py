import queue
import threading
import time
import json
import os
from communication import connect_to_serial_port, send_message, receive_message, parse_message
from devices import Sensor, Valve

class LabPneumoLogic:
    def __init__(self, drawing):
        self.drawing = drawing
        self.sensors = {}
        self.valves = {}
        self.lines = []
        self.sensor_data_queue = queue.Queue()
        self.serial_connections = {}
        self.serial_queue = queue.Queue()
        self.stop_event = threading.Event()

        self.load_config_and_connect()
        self.initialize_ui()
        self.start_serial_threads()

        self.drawing.root.after(100, self.process_serial_data)
        self.drawing.root.after(100, self.update_sensor_values_from_queue)

    def load_config_and_connect(self):
        config = self.load_config(os.path.dirname(os.path.abspath(__file__)) + '/config.json')
        self.load_sensors(config['sensors'])
        self.load_valves(config['valves'])
        self.lines = config['lines']

    def load_config(self, file_path):
        with open(file_path, 'r') as file:
            return json.load(file)

    def load_sensors(self, sensors_data):
        for sensor_data in sensors_data:
            sensor = Sensor.from_json(sensor_data)
            self.sensors[sensor.id] = sensor
            self.connect_to_port(sensor.port)

    def load_valves(self, valves_data):
        for valve_data in valves_data:
            valve = Valve.from_json(valve_data)
            self.valves[valve.id] = valve
            self.connect_to_port(valve.port)

    def connect_to_port(self, port):
        if port not in self.serial_connections:
            self.serial_connections[port] = connect_to_serial_port(port, 115200)

    def initialize_ui(self):
        self.drawing.initialize_ui(self.sensors, self.valves, self.lines, self.toggle_valve)

    def start_serial_threads(self):
        for port in self.serial_connections:
            thread = threading.Thread(target=self.serial_read_thread, args=(port,))
            thread.daemon = True
            thread.start()

    def serial_read_thread(self, port):
        connection = self.serial_connections[port]
        while not self.stop_event.is_set():
            try:
                received_message = receive_message(connection, timeout=1)
                if received_message:
                    self.serial_queue.put((port, received_message))
            except Exception as e:
                print(f"Error reading from {port}: {str(e)}")

    def process_serial_data(self):
        try:
            while not self.serial_queue.empty():
                port, message = self.serial_queue.get_nowait()
                parsed_message = parse_message(message)
                if parsed_message and parsed_message.get('sensor_id'):
                    sensor_id = parsed_message['sensor_id']
                    value = parsed_message['value']
                    self.sensor_data_queue.put({sensor_id: value})
                else:
                    print(f"Received command from {port}: {message}")
        except queue.Empty:
            pass
        finally:
            self.drawing.root.after(100, self.process_serial_data)

    def update_sensor_values_from_queue(self):
        try:
            while not self.sensor_data_queue.empty():
                data = self.sensor_data_queue.get_nowait()
                for sensor_id, raw_value in data.items():
                    sensor = self.sensors.get(sensor_id)
                    if sensor:
                        sensor.process_signal(raw_value)
                        self.drawing.update_sensor(sensor)
        finally:
            self.drawing.update_graph(self.sensors)
            self.drawing.root.after(100, self.update_sensor_values_from_queue)
            

    def toggle_valve(self, valve):
        connection = self.serial_connections.get(valve.port)
        if connection:
            send_message(connection, json.dumps({"type": 1, "command": 17, "valve": valve.id, "result": 0}))
            valve.toggle()
            self.drawing.toggle_valve(valve)
        else:
            print(f"No connection for valve {valve.id}")

    def on_closing(self):
        self.stop_event.set()
        time.sleep(1)
        self.drawing.root.destroy()