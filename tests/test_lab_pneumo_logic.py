import unittest
from unittest.mock import Mock, patch, call
import json
import os
from lab_pneumo_logic import LabPneumoLogic

class MockDrawing:
    def __init__(self):
        self.root = Mock()
        self.sensors = {}
        self.valves = {}

    def initialize_ui(self, sensors, valves, lines, toggle_valve_callback):
        self.sensors = sensors
        self.valves = valves

    def update_sensor(self, sensor):
        pass

    def update_graph(self, sensors):
        pass

    def toggle_valve(self, valve):
        pass

class TestLabPneumoLogic(unittest.TestCase):
    def setUp(self):
        self.mock_drawing = MockDrawing()
        with patch('communication.connect_to_serial_port') as mock_connect:
            mock_connect.return_value = Mock()
            self.logic = LabPneumoLogic(self.mock_drawing)

    def test_load_config(self):
        self.assertGreater(len(self.logic.sensors), 0)
        self.assertGreater(len(self.logic.valves), 0)
        self.assertGreater(len(self.logic.lines), 0)

    def test_process_serial_data(self):
        # Simulate received sensor data
        test_message = {'sensor_id': 1, 'value': 123.45}
        self.logic.serial_queue.put(('COM6', json.dumps(test_message)))
        
        # Process the data
        self.logic.process_serial_data()
        
        # Check if data was queued for processing
        data = self.logic.sensor_data_queue.get_nowait()
        self.assertEqual(data, {1: 123.45})

    def test_toggle_valve(self):
        # Get first valve
        valve = next(iter(self.logic.valves.values()))
        initial_state = valve.status
        
        # Create mock with proper write method
        mock_connection = Mock()
        written_data = []
        def mock_write(data):
            written_data.append(data.decode() if isinstance(data, bytes) else data)
        mock_connection.write = mock_write
        
        self.logic.serial_connections[valve.port] = mock_connection
        
        # Test toggle
        self.logic.toggle_valve(valve)
        
        # Get complete message (combine all writes)
        sent_message = ''.join(written_data).strip()
        
        # Expected command format
        expected_command = {
            "type": 1,
            "command": 17,
            "valve_pin": valve.pin,
            "result": 0
        }
        
        # Compare JSON objects
        self.assertEqual(json.loads(sent_message), expected_command)
        self.assertNotEqual(initial_state, valve.status)

    def tearDown(self):
        if hasattr(self.logic, 'csv_file') and self.logic.csv_file:
            self.logic.csv_file.close()
            # Clean up test CSV file if it exists
            csv_files = [f for f in os.listdir() if f.startswith('sensor_data_')]
            for file in csv_files:
                try:
                    os.remove(file)
                except:
                    pass

if __name__ == '__main__':
    unittest.main()