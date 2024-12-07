import queue
import threading
import time
import json
import os
import csv
from datetime import datetime
from communication import create_connection  # Remove old imports, just use create_connection
from devices import Sensor, Valve

def make_connection_key(connection_config):
    """Create a unique key for a connection configuration"""
    return json.dumps(connection_config, sort_keys=True)

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
        self.csv_file = None
        self.csv_writer = None
        self.start_time = time.time()
        self.connections = {}  # Dictionary to store all connections
        self.message_queue = queue.Queue()  # Single queue for all messages

        self.load_config_and_connect()
        self.initialize_ui()
        self.start_serial_threads()
        self.initialize_csv_logging()

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
            self.connect_device(sensor)

    def load_valves(self, valves_data):
        for valve_data in valves_data:
            valve = Valve.from_json(valve_data)
            self.valves[valve.id] = valve
            self.connect_device(valve)

    def connect_device(self, device):
        connection_key = make_connection_key(device.connection)
        if connection_key not in self.connections:
            connection = create_connection(device.connection)
            if connection and connection.connect():
                self.connections[connection_key] = connection
                return True
        return connection_key in self.connections

    def connect_to_port(self, port):
        if port not in self.serial_connections:
            connection = connect_to_serial_port(port, 115200)
            if connection is None:
                print(f"Warning: Could not connect to port {port}")
            self.serial_connections[port] = connection

    def initialize_ui(self):
        self.drawing.initialize_ui(self.sensors, self.valves, self.lines, self.toggle_valve)

    def start_serial_threads(self):
        # Start a read thread for each connection
        for connection_key, connection in self.connections.items():
            thread = threading.Thread(
                target=self.read_messages,
                args=(connection_key, connection)
            )
            thread.daemon = True
            thread.start()

    def start_communication_threads(self):
        for conn_key, connection in self.connections.items():
            thread = threading.Thread(
                target=self.read_messages,
                args=(conn_key, connection)
            )
            thread.daemon = True
            thread.start()

    def read_messages(self, connection_key, connection):
        while not self.stop_event.is_set():
            try:
                message = connection.read_message()
                if message:
                    self.message_queue.put((connection_key, message))
            except Exception as e:
                print(f"Error reading from {connection_key}: {e}")
                time.sleep(0.1)

    def serial_read_thread(self, port):
        connection = self.serial_connections[port]
        if connection is None:  # Skip if connection is not available
            print(f"Warning: No connection available for port {port}")
            return
        
        while not self.stop_event.is_set():
            try:
                received_message = receive_message(connection, timeout=1)
                if received_message:
                    self.serial_queue.put((port, received_message))
            except Exception as e:
                print(f"Error reading from {port}: {str(e)}")
                time.sleep(1)  # Add delay to avoid rapid error messages

    def process_serial_data(self):
        try:
            while not self.message_queue.empty():
                connection_key, message = self.message_queue.get_nowait()
                try:
                    parsed_message = json.loads(message)
                    if parsed_message and parsed_message.get('sensor_id'):
                        sensor_id = parsed_message['sensor_id']
                        value = parsed_message['value']
                        self.sensor_data_queue.put({sensor_id: value})
                    else:
                        print(f"Received command from {connection_key}: {message}")
                except json.JSONDecodeError:
                    print(f"Invalid JSON message from {connection_key}: {message}")
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
                        self.write_sensor_data_to_csv()
        finally:
            self.drawing.update_graph(self.sensors)
            self.drawing.root.after(100, self.update_sensor_values_from_queue)

    def initialize_csv_logging(self):
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        filename = f"sensor_data_{timestamp}.csv"
        self.csv_file = open(filename, 'w', newline='')
        
        # Создаем заголовки для CSV файла
        headers = ['Timestamp', 'Relative_Time']
        for sensor in self.sensors.values():
            headers.append(f"{sensor.name} ({sensor.units})")
        
        self.csv_writer = csv.writer(self.csv_file)
        self.csv_writer.writerow(headers)

    def write_sensor_data_to_csv(self):
        current_time = time.time()
        relative_time = current_time - self.start_time
        timestamp = datetime.fromtimestamp(current_time).strftime("%Y-%m-%d %H:%M:%S.%f")[:-3]
        
        # Собираем значения всех сенсоров
        row = [timestamp, f"{relative_time:.3f}"]
        for sensor in self.sensors.values():
            row.append(str(sensor.value) if sensor.value is not None else '')
        
        self.csv_writer.writerow(row)
        self.csv_file.flush()  # Сразу записываем в файл

    def toggle_valve(self, valve):
        connection_key = make_connection_key(valve.connection)
        connection = self.connections.get(connection_key)
        if connection is None:
            print(f"Warning: No connection available for valve {valve.id}")
            return False
            
        try:
            valve.toggle()
            command = {
                "type": 1,
                "command": 17,
                "valve_pin": valve.pin,
                "result": 0
            }
            connection.send_message(json.dumps(command))
            self.drawing.toggle_valve(valve)
            return True
        except Exception as e:
            print(f"Error toggling valve {valve.id}: {e}")
            valve.toggle()  # Revert state if failed
            return False

    def on_closing(self):
        self.stop_event.set()
        time.sleep(1)
        
        # Close all connections
        for connection in self.connections.values():
            connection.disconnect()

        if self.csv_file:
            self.csv_file.close()
            
        self.drawing.root.destroy()