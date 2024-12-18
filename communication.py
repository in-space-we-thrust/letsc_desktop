from logger_config import setup_logger
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
        self.logger = setup_logger(f"Serial_{config['port']}")
        self.port = config['port']
        self.baudrate = config.get('baudrate', 115200)
        self.connection = None
        self.lock = Lock()
        self.write_timeout = 0.05  # Уменьшаем таймаут для более быстрой реакции
        self.read_timeout = 0.05   # Добавляем таймаут для чтения
        self.last_connect_attempt = 0
        self.connect_retry_interval = 5.0  # Интервал между попытками подключения (секунды)
        self.connection_error_logged = False  # Флаг для отслеживания логирования ошибки

    def connect(self):
        current_time = time.time()
        # Проверяем, прошло ли достаточно времени с последней попытки
        if current_time - self.last_connect_attempt < self.connect_retry_interval:
            return False

        self.last_connect_attempt = current_time
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
            self.logger.info(f"Successfully connected to {self.port}")
            self.connection_error_logged = False  # Сбрасываем флаг при успешном подключении
            return True
        except Exception as e:
            if not self.connection_error_logged:  # Логируем ошибку только один раз
                self.logger.error(f"Connection error: {e}")
                self.connection_error_logged = True
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
            if not self.connection_error_logged:
                self.logger.error(f"Connection check error for {self.port}: {e}")
                self.connection_error_logged = True
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
                self.logger.debug(f"Sent message: {message}")
                return True
        except serial.serialutil.SerialTimeoutException:
            self.logger.warning(f"Write timeout on port {self.port}")
            return False
        except Exception as e:
            self.logger.error(f"Send error: {e}")
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
        self.logger = setup_logger(f"MQTT_{config['broker']}_{config['port']}")
        self.broker = config['broker']
        self.port = config.get('port', 1883)
        self.topic = config['topic']
        self.logger.info(f"Initializing connection for topic: {self.topic}")
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
                self.logger.debug(f"Already connected to {self.broker}")
                return True
                
            self.connected.clear()
            self.logger.info(f"Connecting to broker {self.broker}...")
            
            # Очищаем буфер перед новым подключением
            with self.buffer_lock:
                self.message_buffer.clear()
            
            connect_result = self.client.connect(self.broker, self.port, keepalive=60)
            if connect_result != 0:
                self.logger.error(f"Connection failed with code {connect_result}")
                return False

            self.client.loop_start()
            self.logger.debug("Loop started")
            
            # Ждем подключения
            if not self.connected.wait(timeout=self.connection_timeout):
                self.logger.error("Connection timeout")
                self.client.loop_stop()
                return False

            self.logger.info(f"Successfully connected to {self.broker}:{self.port}")
            return True
            
        except Exception as e:
            self.logger.error(f"Connection error: {e}")
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
                self.logger.error(f"Send error: {e}")
        return False

    def read_message(self):
        self.logger.debug("Read message called")
        current_time = time.time()
        if current_time - self.last_message_time < self.message_rate_limit:
            self.logger.debug("Rate limit active")
            return None

        with self.buffer_lock:
            try:
                if not self.connected.is_set():
                    self.logger.debug("Not connected")
                    return None
                    
                if len(self.message_buffer) > 0:
                    self.logger.debug(f"Buffer size: {len(self.message_buffer)}")
                    message = self.message_buffer.popleft() if self.message_buffer else None
                    if message:
                        self.last_message_time = current_time
                        self.logger.debug(f"Reading message: {message}")
                        return message
                    
                self.logger.debug("Buffer empty")
                return None
            except Exception as e:
                self.logger.error(f"Error reading from buffer: {e}")
                return None

    def _on_connect(self, client, userdata, flags, rc):
        if rc == 0:
            self.logger.info(f"Connected successfully, resubscribing to {self.topic}")
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
            self.logger.error(f"Connection failed - {error} (code {rc})")

    def _on_message(self, client, userdata, msg):
        try:
            with self.buffer_lock:
                decoded_message = msg.payload.decode()
                self.logger.debug(f"Received raw: {decoded_message}")
                if len(self.message_buffer) < self.message_buffer.maxlen:
                    message_tuple = (msg.topic, decoded_message)
                    self.message_buffer.append(message_tuple)
                    self.logger.debug(f"Added to buffer: {message_tuple}")
                else:
                    self.logger.warning("Buffer full, dropping message")
        except Exception as e:
            self.logger.error(f"Message handling error: {e}")

    def _on_disconnect(self, client, userdata, rc):
        self.connected.clear()
        if rc != 0:
            self.logger.warning(f"Disconnected with code {rc}, attempting reconnect...")
            client.reconnect()

def create_connection(config):
    logger = setup_logger("ConnectionFactory")
    try:
        conn_type = config.get('type', 'serial')
        if conn_type == 'serial':
            connection = SerialConnection(config)
        elif conn_type == 'mqtt':
            connection = MQTTConnection(config)
        else:
            logger.error(f"Unknown connection type: {conn_type}")
            return None
            
        # Не пытаемся подключиться здесь, только создаем объект
        return connection
    except Exception as e:
        logger.error(f"Error creating connection with config {config}: {e}")
        return None