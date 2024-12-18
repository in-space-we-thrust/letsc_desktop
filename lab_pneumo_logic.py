import queue
import threading
import time
import json
import os
import csv
from datetime import datetime
from communication import create_connection, SerialConnection, MQTTConnection  # Add MQTTConnection
from devices import Sensor, Valve
from logger_config import setup_logger

def make_connection_key(connection_config):
    """Create a unique key for a connection configuration"""
    if isinstance(connection_config, dict):
        if connection_config['type'] == 'serial':
            return connection_config['port']  # Используем порт как ключ для Serial
        elif connection_config['type'] == 'mqtt':
            return f"{connection_config['broker']}:{connection_config['port']}"  # Уникальный ключ для MQTT
    return str(connection_config)  # Для обратной совместимости

class LabPneumoLogic:
    def __init__(self, drawing):
        self.logger = setup_logger("LabPneumoLogic")
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
        self.command_queue = queue.Queue()  # Add command queue
        self.command_thread = threading.Thread(target=self.process_commands)
        self.command_thread.daemon = True
        self.command_thread.start()
        self.mqtt_topics = {}  # Добавляем словарь для отслеживания MQTT топиков

        self.load_config_and_connect()
        self.initialize_connections_thread = threading.Thread(target=self.initialize_all_connections)
        self.initialize_connections_thread.daemon = True
        self.initialize_connections_thread.start()
        self.initialize_connections_thread.join(timeout=5.0)

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
            connection_key = make_connection_key(sensor_data['connection'])
            
            # Особая обработка для MQTT сенсоров
            if sensor_data['connection']['type'] == 'mqtt':
                topic = sensor_data['connection']['topic']
                self.mqtt_topics[topic] = sensor_data['id']
                self.logger.info(f"Registered MQTT topic {topic} for sensor {sensor_data['id']}")

            if connection_key not in self.connections:
                connection = create_connection(sensor_data['connection'])
                if connection:  # Remove the connect() check here - let it happen asynchronously
                    self.connections[connection_key] = connection
                    self.logger.info(f"Created connection for {connection_key}")
                else:
                    self.logger.warning(f"Could not create connection object for {connection_key}")
                    self.connections[connection_key] = None

            sensor = Sensor.from_json(sensor_data)
            self.sensors[sensor.id] = sensor

    def load_valves(self, valves_data):
        for valve_data in valves_data:
            connection_key = make_connection_key(valve_data['connection'])
            if connection_key not in self.connections:
                connection = create_connection(valve_data['connection'])
                if connection:
                    # Для MQTT клапанов нужна особая обработка
                    if valve_data['connection']['type'] == 'mqtt':
                        self.logger.info(f"Initializing MQTT valve connection for {connection_key}...")
                        if connection.connect():
                            # Подписываемся на топик статуса клапана если он указан
                            if 'status_topic' in valve_data['connection']:
                                status_topic = valve_data['connection']['status_topic']
                                connection.client.subscribe(status_topic)
                                self.logger.info(f"Subscribed to valve status topic: {status_topic}")
                            self.connections[connection_key] = connection
                        else:
                            self.logger.error(f"Could not connect MQTT for valve: {valve_data['name']}")
                            self.connections[connection_key] = None
                    else:
                        # Для остальных типов подключений
                        if connection.connect():
                            self.connections[connection_key] = connection
                        else:
                            self.logger.warning(f"Could not connect using config {valve_data['connection']}")
                            self.connections[connection_key] = None

            valve = Valve.from_json(valve_data)
            self.valves[valve.id] = valve

    def connect_device(self, device):
        connection_key = make_connection_key(device.connection)
        if connection_key not in self.connections:
            connection = create_connection(device.connection)
            if connection and connection.connect():
                self.connections[connection_key] = connection
                return True
        return connection_key in self.connections

    def connect_device_port(self, connection_config):
        """Create a single connection for a given port configuration"""
        connection_key = make_connection_key(connection_config)
        if connection_key not in self.connections:
            connection = create_connection(connection_config)
            if connection and connection.connect():
                self.connections[connection_key] = connection
                return True
            else:
                self.logger.warning(f"Could not connect to {connection_config}")
                self.connections[connection_key] = None
        return connection_key in self.connections

    def connect_to_port(self, port):
        if port not in self.serial_connections:
            connection = connect_to_serial_port(port, 115200)
            if connection is None:
                self.logger.warning(f"Could not connect to port {port}")
            self.serial_connections[port] = connection

    def initialize_ui(self):
        self.drawing.initialize_ui(self.sensors, self.valves, self.lines, self.toggle_valve)

    def start_serial_threads(self):
        self.logger.info("Starting communication threads...")
        for connection_key, connection in self.connections.items():
            if connection is None:
                self.logger.warning(f"Skipping thread for {connection_key} - no connection object")
                continue

            # Проверяем готовность MQTT соединения
            if isinstance(connection, MQTTConnection):
                if not connection.connected.is_set():
                    self.logger.warning(f"MQTT connection {connection_key} not ready, retrying connect...")
                    if not connection.connect():
                        self.logger.error(f"Could not establish MQTT connection for {connection_key}")
                        continue
                self.logger.info(f"MQTT connection {connection_key} ready")

            thread = threading.Thread(
                target=self.read_messages,
                args=(connection_key, connection)
            )
            thread.daemon = True
            thread.start()
            self.logger.info(f"Started read thread for {connection_key}")

    def start_communication_threads(self):
        for conn_key, connection in self.connections.items():
            thread = threading.Thread(
                target=self.read_messages,
                args=(conn_key, connection)
            )
            thread.daemon = True
            thread.start()

    def read_messages(self, connection_key, connection):
        consecutive_errors = 0
        self.logger.info(f"Starting read_messages thread for {connection_key}")
        
        # Для MQTT соединений проверяем что подключение установлено
        if isinstance(connection, MQTTConnection):
            if not connection.connected.is_set():
                self.logger.info(f"Waiting for MQTT connection {connection_key}...")
                connection.connected.wait(timeout=5.0)
                if not connection.connected.is_set():
                    self.logger.error(f"Failed to establish MQTT connection for {connection_key}")
                    return
        
        while not self.stop_event.is_set():
            try:
                message = connection.read_message()
                if message:
                    self.logger.debug(f"Got message in read_messages: {connection_key} -> {message}")
                    self.message_queue.put((connection_key, message))
                    consecutive_errors = 0
                else:
                    time.sleep(0.01)

            except Exception as e:
                self.logger.error(f"Error in read_messages for {connection_key}: {str(e)}")
                consecutive_errors += 1
                if consecutive_errors > 5:
                    self.logger.warning(f"Attempting reconnect for {connection_key}")
                    if isinstance(connection, MQTTConnection):
                        if connection.connect():
                            consecutive_errors = 0
                    time.sleep(1)

    def serial_read_thread(self, port):
        connection = self.serial_connections[port]
        if connection is None:  # Skip if connection is not available
            self.logger.warning(f"No connection available for port {port}")
            return
        
        while not self.stop_event.is_set():
            try:
                received_message = receive_message(connection, timeout=1)
                if received_message:
                    self.serial_queue.put((port, received_message))
            except Exception as e:
                self.logger.error(f"Error reading from {port}: {str(e)}")
                time.sleep(1)  # Add delay to avoid rapid error messages

    def process_serial_data(self):
        try:
            while not self.message_queue.empty():
                try:
                    connection_key, message = self.message_queue.get_nowait()
                    self.logger.debug(f"Processing message from {connection_key}, type: {type(message)}") 
                    self.logger.debug(f"Message content: {message}")

                    # Проверяем тип соединения через connections
                    connection = self.connections.get(connection_key)
                    if isinstance(connection, MQTTConnection):
                        self.logger.debug("Processing MQTT message...")
                        try:
                            topic, payload = message  # Распаковываем кортеж (topic, message)
                            # Для MQTT сообщение уже содержит JSON, поэтому парсим его напрямую
                            parsed_message = json.loads(payload)
                            if parsed_message and parsed_message.get('sensor_id'):
                                sensor_id = parsed_message['sensor_id']
                                value = parsed_message['value']
                                self.logger.debug(f"MQTT parsed: sensor_id={sensor_id}, value={value}")
                                self.sensor_data_queue.put({sensor_id: value})
                            else:
                                self.logger.warning(f"Invalid MQTT message format: {payload}")
                        except json.JSONDecodeError as e:
                            self.logger.error(f"JSON parsing error: {e}, payload: {payload}")
                        except Exception as e:
                            self.logger.error(f"Error processing MQTT message: {e}")
                        continue

                    # Обработка обычных JSON сообщений
                    try:
                        parsed_message = json.loads(message)
                        if parsed_message and parsed_message.get('sensor_id'):
                            sensor_id = parsed_message['sensor_id']
                            value = parsed_message['value']
                            self.sensor_data_queue.put({sensor_id: value})
                        else:
                            self.logger.info(f"Received command from {connection_key}: {message}")
                    except json.JSONDecodeError:
                        self.logger.warning(f"Invalid JSON message from {connection_key}: {message}")
                    
                except Exception as e:
                    self.logger.error(f"Error processing message: {e}, key: {connection_key}, message: {message}")
        except Exception as e:
            self.logger.error(f"Error in process_serial_data: {e}")
        finally:
            self.drawing.root.after(100, self.process_serial_data)

    def get_sensor_id_by_mqtt_key(self, connection_key):
        """Получаем ID сенсора по ключу MQTT подключения"""
        for sensor in self.sensors.values():
            if (sensor.connection['type'] == 'mqtt' and 
                make_connection_key(sensor.connection) == connection_key):
                return sensor.id
        return None

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
        
        # Созда��м заголовки для CSV файла
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
        
        if not connection or not hasattr(connection, 'is_connected') or not connection.is_connected():
            self.logger.error(f"No connection object for valve {valve.id}")
            self.drawing.update_valve_error(valve)
            return False
        
        # Prepare command
        command = {
            "type": 1,
            "command": 17,
            "valve_pin": valve.pin,
            "result": 0
        }
        
        # Toggle valve state immediately in GUI
        valve.toggle()
        self.drawing.toggle_valve(valve)
        
        # Put command in queue for async processing
        self.command_queue.put((valve, connection, command))
        return True

    def process_commands(self):
        """Обработка команд в отдельном потоке"""
        while not self.stop_event.is_set():
            try:
                command_data = self.command_queue.get(timeout=0.1)
                if command_data:
                    valve, connection, command = command_data
                    try:
                        if connection.send_message(json.dumps(command)):
                            # Используем after для обновления GUI в основном потоке
                            self.drawing.root.after(0, self.drawing.toggle_valve, valve)
                        else:
                            self.drawing.root.after(0, self.drawing.update_valve_error, valve)
                    except Exception as e:
                        self.logger.error(f"Command processing error: {e}")
                        self.drawing.root.after(0, self.drawing.update_valve_error, valve)
            except queue.Empty:
                continue

    def initialize_all_connections(self):
        self.logger.info("Starting initialize_all_connections...")
        connection_configs = {}
        
        # Собираем все конфигурации
        for sensor in self.sensors.values():
            key = make_connection_key(sensor.connection)
            if key not in connection_configs:
                connection_configs[key] = sensor.connection

        for valve in self.valves.values():
            key = make_connection_key(valve.connection)
            if key not in connection_configs:
                connection_configs[key] = valve.connection

        # Сначала инициализируем MQTT соединения
        for key, config in connection_configs.items():
            if config.get('type') == 'mqtt':
                self.logger.info(f"Initializing MQTT connection for {key}...")
                connection = create_connection(config)
                if connection:
                    for attempt in range(3):
                        if connection.connect():
                            self.logger.info(f"MQTT connection successful for {key}")
                            self.connections[key] = connection
                            break
                        self.logger.warning(f"MQTT connection attempt {attempt + 1} failed")
                        time.sleep(1)
                    else:
                        self.logger.error(f"Failed to connect MQTT for {key}")
                        self.connections[key] = None

        # Затем инициализируем остальные соединения
        for key, config in connection_configs.items():
            if config.get('type') != 'mqtt' and key not in self.connections:
                self.logger.info(f"Initializing connection for {key}...")
                connection = create_connection(config)
                if connection and connection.connect():
                    self.connections[key] = connection
                    self.logger.info(f"Successfully connected to {key}")
                else:
                    self.logger.error(f"Failed to connect to {key}")
                    self.connections[key] = None

        self.logger.info("Finished initialize_all_connections")

    def on_closing(self):
        self.stop_event.set()
        time.sleep(1)
        
        # Close all connections
        for connection in self.connections.values():
            connection.disconnect()

        if self.csv_file:
            self.csv_file.close()
            
        self.drawing.root.destroy()