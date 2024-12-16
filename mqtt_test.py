from communication import create_connection
import time

def test_mqtt_connection():
    # Конфигурация для тестового подключения
    config = {
        'type': 'mqtt',
        'broker': 'localhost',
        'port': 1883,
        'topic': 'commutator/sensors/1'
    }

    # Создаем подключение
    print("Creating MQTT connection...")
    connection = create_connection(config)
    
    if not connection:
        print("Failed to create connection object")
        return

    # Пробуем подключиться
    print("Attempting to connect...")
    connected = connection.connect()
    print(f"Connect result: {connected}")

    if connected:
        # Тестируем отправку сообщения
        #print("Sending test message...")
        #connection.send_message("Hello MQTT")
        
        # Ждем немного и пробуем прочитать сообщения
        #time.sleep(2)
        print("Reading messages...")
        for _ in range(5):
            msg = connection.read_message()
            if msg:
                print(f"Received: {msg}")
            time.sleep(0.5)

        # Отключаемся
        print("Disconnecting...")
        connection.disconnect()
    else:
        print("Connection failed!")

if __name__ == "__main__":
    test_mqtt_connection()