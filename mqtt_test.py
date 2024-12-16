import paho.mqtt.client as mqtt
import time
import random

def on_connect(client, userdata, flags, rc):
    print(f"Connected with result code {rc}")

def on_publish(client, userdata, mid):
    print(f"Message {mid} published")

def test_publish():
    client = mqtt.Client()
    client.on_connect = on_connect
    client.on_publish = on_publish
    
    try:
        print("Connecting to MQTT broker...")
        client.connect("localhost", 1883, 60)
        client.loop_start()
        
        topic = "commutator/sensors/1"
        print(f"Publishing to topic: {topic}")
        
        while True:  # Бесконечная публикация
            value = 20 + random.uniform(-1, 1)
            result = client.publish(topic, f"{value:.2f}")
            print(f"Published: {value:.2f}, result: {result}")
            time.sleep(1)
            
    except KeyboardInterrupt:
        print("\nStopping...")
        client.loop_stop()
        client.disconnect()
    except Exception as e:
        print(f"Error: {e}")

if __name__ == "__main__":
    test_publish()