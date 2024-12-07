import unittest
from unittest.mock import Mock, patch
from communication import connect_to_serial_port, parse_message, send_message

class TestCommunication(unittest.TestCase):
    def test_parse_message_valid_json(self):
        message = '{"sensor_id": 1, "value": 123.45}'
        result = parse_message(message)
        self.assertEqual(result['sensor_id'], 1)
        self.assertEqual(result['value'], 123.45)

    def test_parse_message_invalid_json(self):
        message = 'invalid json'
        result = parse_message(message)
        self.assertIsNone(result)

    @patch('serial.Serial')
    def test_connect_to_serial_port_success(self, mock_serial):
        mock_serial.return_value = Mock()
        connection = connect_to_serial_port('COM1', 115200)
        self.assertIsNotNone(connection)
        mock_serial.assert_called_once_with('COM1', 115200)

    @patch('serial.Serial')
    def test_connect_to_serial_port_failure(self, mock_serial):
        mock_serial.side_effect = Exception('Connection failed')
        connection = connect_to_serial_port('COM1', 115200)
        self.assertIsNone(connection)
        mock_serial.assert_called_once_with('COM1', 115200)

if __name__ == '__main__':
    unittest.main()