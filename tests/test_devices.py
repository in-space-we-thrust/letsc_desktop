import unittest
from devices import Sensor, Valve

class TestSensor(unittest.TestCase):
    def setUp(self):
        self.sensor_data = {
            "id": 1,
            "port": "COM6",
            "name": "PS_1",
            "units": "psi",
            "coord_x": 350,
            "coord_y": 80,
            "processing": {
                "offset": 10,
                "calibration_factor": 1.5
            }
        }
        self.sensor = Sensor.from_json(self.sensor_data)

    def test_sensor_creation(self):
        self.assertEqual(self.sensor.id, 1)
        self.assertEqual(self.sensor.name, "PS_1")
        self.assertEqual(self.sensor.units, "psi")

    def test_process_signal(self):
        # Test with simple offset and calibration
        raw_value = 100
        # Process order should be: (raw_value - offset) * calibration_factor
        expected = (raw_value - 10) * 1.5  # = (100 - 10) * 1.5 = 135.0
        processed_value = self.sensor.process_signal(raw_value)
        self.assertAlmostEqual(processed_value, expected)

    def test_process_signal_with_filters(self):
        # Test with filters separately
        self.sensor.processing['filters'] = {
            "moving_average": 3
        }
        values = [10, 20, 30]
        for val in values:
            processed = self.sensor.process_signal(val)
        # Last value should be average of all three values after processing
        expected = sum([(v - 10) * 1.5 for v in values]) / len(values)
        self.assertAlmostEqual(processed, expected)

    def test_moving_average(self):
        values = [10, 20, 30, 40]
        for val in values:
            result = self.sensor.moving_average(val, 3)
        # Should be average of last 3 values
        self.assertEqual(result, sum([20, 30, 40]) / 3)

class TestValve(unittest.TestCase):
    def setUp(self):
        self.valve_data = {
            "id": 1,
            "name": "V_1",
            "pin": 22,
            "port": "COM6",
            "coord_x": 200,
            "coord_y": 100
        }
        self.valve = Valve.from_json(self.valve_data)

    def test_valve_creation(self):
        self.assertEqual(self.valve.id, 1)
        self.assertEqual(self.valve.name, "V_1")
        self.assertEqual(self.valve.pin, 22)

    def test_valve_toggle(self):
        initial_state = self.valve.status
        self.valve.toggle()
        self.assertNotEqual(initial_state, self.valve.status)
        self.valve.toggle()
        self.assertEqual(initial_state, self.valve.status)

if __name__ == '__main__':
    unittest.main()