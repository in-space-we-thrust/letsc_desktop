import json
import serial
import serial.serialutil
import paho.mqtt.client as mqtt
import time  # Add this import
from abc import ABC, abstractmethod
from queue import Queue, Full
from collections import deque
from threading import Lock, Event

class Connection(ABC):
    @abstractmethod
    def connect(self):
        pass

    @abstractmethod
    def disconnect(self):
        pass

    @abstractmethod
    def send_message(self, message):
        pass

    @abstractmethod
    def read_message(self):
        pass

class SerialConnection(Connection):
    def __init__(self, config):
        self.port = config['port']
        self.baudrate = config.get('baudrate', 115200)
        self.connection = None
        self.lock = Lock()
        self.write_timeout = 0.05  # Уменьшаем таймаут для более быстрой реакции
        self.read_timeout = 0.05   # Добавляем таймаут для чтения

    def connect(self):
        try:
            if (self.connection):  # Если соединение уже существует
                try:
                    self.connection.close()  # Закрываем старое
                except:
                    pass
                    
            self.connection = serial.Serial(
                port=self.port,
                baudrate=self.baudrate,
                timeout=self.read_timeout,
                write_timeout=self.write_timeout
            )
            return True
        except Exception as e:
            print(f"Serial connection error for port {self.port}: {e}")
            self.connection = None
            return False

    def is_connected(self):
        """Неблокирующая проверка соединения"""
        try:
            # Пытаемся переподключиться, если соединение потеряно
            if self.connection is None:
                return self.connect()
            
            if not self.connection.is_open:
                self.connection.open()
            
            return True
        except Exception as e:
            print(f"Connection check error for {self.port}: {e}")
            return False

    def disconnect(self):
        if self.connection:
            self.connection.close()

    def send_message(self, message):
        if not self.is_connected():
            return False
            
        try:
            with self.lock:
                self.connection.write(message.encode())
                self.connection.write(b'\n')
                return True
        except serial.serialutil.SerialTimeoutException:
            print(f"Serial write timeout on port {self.port}")
            return False
        except Exception as e:
            print(f"Serial send error: {e}")
            return False

    def read_message(self):
        if not self.is_connected():
            return None
            
        try:
            with self.lock:
                return self.connection.readline().decode().strip()
        except:
            return None

class MQTTConnection(Connection):
    def __init__(self, config):
        self.broker = config['broker']
        self.port = config.get('port', 1883)
        self.topic = config['topic']
        print(f"MQTT: Initializing connection for topic: {self.topic}")  # Добавляем отладку
        self.client = mqtt.Client(protocol=mqtt.MQTTv311, client_id="letsc_desktop_" + str(time.time()))  # Явно указываем протокол
        self.message_buffer = deque(maxlen=50)  # Уменьшаем размер буфера
        self.buffer_lock = Lock()
        self.connected = Event()
        self.last_message_time = 0
        self.message_rate_limit = 0.05  # 50ms между сообщениями
        self.connection_timeout = 0.05  # Увеличиваем таймаут для первого подключения

        # Оптимизация MQTT клиента
        self.client.on_message = self._on_message
        self.client.on_connect = self._on_connect
        self.client.on_disconnect = self._on_disconnect
        
        # Оптимизация параметров MQTT
        self.client.max_queued_messages_set(10)
        self.client.max_inflight_messages_set(10)
        self.client.reconnect_delay_set(min_delay=1, max_delay=2)

    def connect(self):
        try:
            if self.connected.is_set():
                print(f"MQTT: Already connected to {self.broker}")
                return True
                
            self.connected.clear()
            print(f"MQTT: Connecting to broker {self.broker}...")
            
            # Очищаем буфер перед новым подключением
            with self.buffer_lock:
                self.message_buffer.clear()
            
            connect_result = self.client.connect(self.broker, self.port, keepalive=60)
            if connect_result != 0:
                print(f"MQTT: Connection failed with code {connect_result}")
                return False

            self.client.loop_start()
            print("MQTT: Loop started")
            
            # Ждем подключения
            if not self.connected.wait(timeout=self.connection_timeout):
                print("MQTT: Connection timeout")
                self.client.loop_stop()
                return False

            print(f"MQTT: Successfully connected to {self.broker}:{self.port}")
            return True
            
        except Exception as e:
            print(f"MQTT connection error: {e}")
            self.client.loop_stop()
            return False

    def disconnect(self):
        if self.connected.is_set():
            self.client.loop_stop()
            self.client.disconnect()

    def send_message(self, message):
        if self.connected.is_set():
            try:
                self.client.publish(self.topic, message)
                return True
            except Exception as e:
                print(f"MQTT send error: {e}")
        return False

    def read_message(self):
        print("MQTT read_message called")  # Отладка
        current_time = time.time()
        if current_time - self.last_message_time < self.message_rate_limit:
            print("MQTT: Rate limit active")  # Отладка
            return None

        with self.buffer_lock:
            try:
                if not self.connected.is_set():
                    print("MQTT: Not connected")  # Отладка
                    return None
                    
                if len(self.message_buffer) > 0:
                    print(f"MQTT buffer size: {len(self.message_buffer)}")
                    message = self.message_buffer.popleft() if self.message_buffer else None
                    if message:
                        self.last_message_time = current_time
                        print(f"MQTT reading message: {message}")
                        return message
                    
                print("MQTT: Buffer empty")  # Отладка
                return None
            except Exception as e:
                print(f"Error reading from MQTT buffer: {e}")
                return None

    def _on_connect(self, client, userdata, flags, rc):
        if rc == 0:
            print(f"MQTT: Connected successfully, resubscribing to {self.topic}")
            self.client.subscribe(self.topic, qos=0)  # Переподписываемся после реконнекта
            self.connected.set()
        else:
            error_messages = {
                1: "incorrect protocol version",
                2: "invalid client identifier",
                3: "server unavailable",
                4: "bad username or password",
                5: "not authorized"
            }
            error = error_messages.get(rc, "unknown error")
            print(f"MQTT: Connection failed - {error} (code {rc})")

    def _on_message(self, client, userdata, msg):
        try:
            with self.buffer_lock:
                decoded_message = msg.payload.decode()
                print(f"MQTT received raw: {decoded_message}")
                if len(self.message_buffer) < self.message_buffer.maxlen:
                    message_tuple = (msg.topic, decoded_message)
                    self.message_buffer.append(message_tuple)
                    print(f"Added to MQTT buffer: {message_tuple}")
                else:
                    print("MQTT buffer full, dropping message")
        except Exception as e:
            print(f"Error in MQTT message handling: {e}")

    def _on_disconnect(self, client, userdata, rc):
        self.connected.clear()
        if rc != 0:
            print(f"MQTT disconnected with code {rc}, attempting reconnect...")
            client.reconnect()

def create_connection(config):
    try:
        conn_type = config.get('type', 'serial')
        if conn_type == 'serial':
            connection = SerialConnection(config)
        elif conn_type == 'mqtt':
            connection = MQTTConnection(config)
        else:
            print(f"Unknown connection type: {conn_type}")
            return None
            
        # Не пытаемся подключиться здесь, только создаем объект
        return connection
    except Exception as e:
        print(f"Error creating connection with config {config}: {e}")
        return None