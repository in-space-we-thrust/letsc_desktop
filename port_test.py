import serial
import time

def test_serial_communication(port, baud_rate):
    try:
        ser = serial.Serial(port, baud_rate, timeout=1)
        print(f"Connected to {port} at {baud_rate} baud")
        
        for _ in range(10):  # Try 10 times
            try:
                data = ser.readline().decode('utf-8').strip()
                if data:
                    print(f"Received: {data}")
                else:
                    print("No data received")
            except Exception as e:
                print(f"Error reading data: {str(e)}")
            time.sleep(1)
        
        ser.close()
    except Exception as e:
        print(f"Error opening serial port: {str(e)}")

if __name__ == "__main__":
    test_serial_communication("COM6", 115200) 