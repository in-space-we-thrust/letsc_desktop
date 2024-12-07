import json
import serial
import paho.mqtt.client as mqtt
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

    def connect(self):
        try:
            self.connection = serial.Serial(self.port, self.baudrate)
            return True
        except Exception as e:
            print(f"Serial connection error: {e}")
            return False

    def disconnect(self):
        if self.connection:
            self.connection.close()

    def send_message(self, message):
        with self.lock:
            if self.connection:
                try:
                    self.connection.write(message.encode())
                    self.connection.write(b'\n')
                    return True
                except Exception as e:
                    print(f"Serial send error: {e}")
        return False

    def read_message(self):
        with self.lock:
            if self.connection:
                try:
                    return self.connection.readline().decode().strip()
                except Exception:
                    return None
        return None

class MQTTConnection(Connection):
    def __init__(self, config):
        self.broker = config['broker']
        self.port = config.get('port', 1883)
        self.topic = config['topic']
        self.client = mqtt.Client(protocol=mqtt.MQTTv311)  # Явно указываем протокол
        self.message_buffer = deque(maxlen=50)  # Уменьшаем размер буфера
        self.buffer_lock = Lock()
        self.connected = Event()
        self.last_message_time = 0
        self.message_rate_limit = 0.05  # 50ms между сообщениями

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
            # Оптимизация параметров подключения
            self.client.connect_async(self.broker, self.port, keepalive=60)
            self.client.subscribe(self.topic, qos=0)
            self.client.socket_timeout = 1
            self.client.loop_start()
            return self.connected.wait(timeout=2.0)
        except Exception as e:
            print(f"MQTT connection error: {e}")
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
        current_time = time.time()
        if current_time - self.last_message_time < self.message_rate_limit:
            return None

        with self.buffer_lock:
            try:
                message = self.message_buffer.popleft() if self.message_buffer else None
                if message:
                    self.last_message_time = current_time
                return message
            except Exception:
                return None

    def _on_connect(self, client, userdata, flags, rc):
        if rc == 0:
            self.connected.set()
        else:
            print(f"MQTT Connection failed with code {rc}")

    def _on_message(self, client, userdata, msg):
        try:
            with self.buffer_lock:
                if len(self.message_buffer) < self.message_buffer.maxlen:
                    self.message_buffer.append(msg.payload.decode())
        except Exception:
            pass

    def _on_disconnect(self, client, userdata, rc):
        self.connected.clear()
        if rc != 0:
            print(f"MQTT disconnected with code {rc}, attempting reconnect...")
            client.reconnect()

def create_connection(config):
    conn_type = config.get('type', 'serial')
    if conn_type == 'serial':
        return SerialConnection(config)
    elif conn_type == 'mqtt':
        return MQTTConnection(config)
    raise ValueError(f"Unknown connection type: {conn_type}")