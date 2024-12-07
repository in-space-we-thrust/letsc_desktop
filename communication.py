import json
import serial
import paho.mqtt.client as mqtt
from abc import ABC, abstractmethod
from queue import Queue
from threading import Lock

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
        self.client = mqtt.Client()
        self.messages = Queue()
        self.connected = False
        
        self.client.on_message = self._on_message
        self.client.on_connect = self._on_connect

    def connect(self):
        try:
            self.client.connect(self.broker, self.port)
            self.client.subscribe(self.topic)
            self.client.loop_start()
            return True
        except Exception as e:
            print(f"MQTT connection error: {e}")
            return False

    def disconnect(self):
        if self.connected:
            self.client.loop_stop()
            self.client.disconnect()

    def send_message(self, message):
        if self.connected:
            try:
                self.client.publish(self.topic, message)
                return True
            except Exception as e:
                print(f"MQTT send error: {e}")
        return False

    def read_message(self):
        try:
            return self.messages.get_nowait()
        except:
            return None

    def _on_connect(self, client, userdata, flags, rc):
        self.connected = rc == 0

    def _on_message(self, client, userdata, msg):
        try:
            self.messages.put(msg.payload.decode())
        except:
            pass

def create_connection(config):
    conn_type = config.get('type', 'serial')
    if conn_type == 'serial':
        return SerialConnection(config)
    elif conn_type == 'mqtt':
        return MQTTConnection(config)
    raise ValueError(f"Unknown connection type: {conn_type}")