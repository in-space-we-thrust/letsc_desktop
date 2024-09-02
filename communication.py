import json
import serial

def connect_to_serial_port(port, baudrate=115200):
    try:
        ser = serial.Serial(port, baudrate)
        return ser
    except serial.SerialException as e:
        print(f"Error: {e}")
        return None

def send_message(ser, message):
    ser.write(message.encode())
    ser.write("\n".encode())

def receive_message(connection, timeout=1):
    connection.timeout = timeout
    try:
        return connection.readline().decode('utf-8').strip()
    except serial.SerialTimeoutException:
        print(f"Error serial port timeout")
        return None
    except Exception as e:
        print(f"Error in receive_message: {str(e)}")
        return None

def parse_message(str_msg):
    try:
        result = json.loads(str_msg)
    except ValueError:
        result = None
        print("not json message", str_msg)
    return result