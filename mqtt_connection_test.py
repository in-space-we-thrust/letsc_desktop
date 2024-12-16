
import time
from communication import MQTTConnection
import threading

def message_reader(mqtt_conn):
    """Функция для чтения сообщений в отдельном потоке"""
    print("Starting message reader...")
    while True:
        message = mqtt_conn.read_message()
        if message:
            print(f"Received message: {message}")
        time.sleep(0.1)

def test_mqtt_connection():
    # Конфигурация из config.json для сенсора с id 5
    config = {
        'type': 'mqtt',
        'broker': 'localhost',
        'port': 1883,
        'topic': 'commutator/sensors/1'
    }

    print("Creating MQTT connection...")
    mqtt_conn = MQTTConnection(config)

    print("Connecting to broker...")
    if not mqtt_conn.connect():
        print("Failed to connect!")
        return

    print("Starting message reader thread...")
    reader_thread = threading.Thread(target=message_reader, args=(mqtt_conn,))
    reader_thread.daemon = True
    reader_thread.start()

    try:
        print("Waiting for messages (press Ctrl+C to stop)...")
        while True:
            time.sleep(1)
    except KeyboardInterrupt:
        print("\nStopping test...")
    finally:
        print("Disconnecting...")
        mqtt_conn.disconnect()

if __name__ == "__main__":
    test_mqtt_connection()