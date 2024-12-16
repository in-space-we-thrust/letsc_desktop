import importlib
import numpy as np
from signal_processing import KalmanFilter

class Device:
    def __init__(self, id, connection, name, coord_x, coord_y):
        self.id = id
        self.connection = connection  # Changed from port to connection
        self.name = name
        self.coord_x = coord_x
        self.coord_y = coord_y

    def __str__(self):
        return f"{self.__class__.__name__} {self.id}: {self.name}"

    @classmethod
    def from_json(cls, json_data):
        return cls(
            id=json_data['id'],
            connection=json_data['connection'],  # Changed from port to connection
            name=json_data['name'],
            coord_x=json_data['coord_x'],
            coord_y=json_data['coord_y']
        )

class Sensor(Device):
    def __init__(self, id, connection, name, units, coord_x, coord_y, processing=None):
        super().__init__(id, connection, name, coord_x, coord_y)
        self.units = units
        self.value = None
        self.rectangle = None
        self.text = None
        self.processing = processing or {}
        self.previous_values = []
        self.kalman_filter = None

    @classmethod
    def from_json(cls, json_data):
        return cls(
            id=json_data['id'],
            connection=json_data['connection'],  # Changed from port to connection
            name=json_data['name'],
            units=json_data['units'],
            coord_x=json_data['coord_x'],
            coord_y=json_data['coord_y'],
            processing=json_data.get('processing', {})
        )

    def process_signal(self, raw_value):
        value = raw_value

        # 1. Тарировка (смещение)
        offset = self.processing.get('offset', 0)
        value = self.compensate_offset(value, offset)

        # 2. Калибровка - применяется после смещения
        calibration_factor = self.processing.get('calibration_factor', 1.0)
        value = self.calibrate_signal(value, calibration_factor)

        # 3. Применение калибровочной таблицы
        if self.processing.get('calibration_table', {}).get('enabled', False):
            value = self.apply_calibration_table(value)

        # 4. Фильтрация
        filters = self.processing.get('filters', {})
        if 'moving_average' in filters:
            window_size = filters['moving_average']
            value = self.moving_average(value, window_size)
        if 'kalman' in filters:
            kalman_config = filters['kalman']
            value = self.apply_kalman_filter(value, kalman_config)

        # 5. Удаление выбросов
        if self.processing.get('outlier_detection', {}).get('enabled', False):
            threshold = self.processing['outlier_detection']['threshold']
            value = self.detect_outliers(value, threshold)

        # 6. Температурная компенсация
        if self.processing.get('temperature_compensation', {}).get('enabled', False):
            compensation_factor = self.processing['temperature_compensation']['compensation_factor']
            value = self.compensate_temperature(value, compensation_factor)

        # 7. Выполнение произвольного кода обработки
        if 'custom_processing' in self.processing:
            value = self.apply_custom_processing(value)

        self.value = value
        return value

    # Функция для смещения (тарировки)
    def compensate_offset(self, raw_value, offset):
        return raw_value - offset

    # Функция для применения калибровочной таблицы
    def apply_calibration_table(self, value):
        calibration_table = self.processing['calibration_table']['points']
        if calibration_table:
            # Преобразуем калибровочную таблицу в массив numpy для интерполяции
            table = np.array(calibration_table)
            input_values = table[:, 0]
            output_values = table[:, 1]
            # Интерполяция по таблице
            calibrated_value = np.interp(value, input_values, output_values)
            return calibrated_value
        return value
    
    # Функция для калибровки
    def calibrate_signal(self, value, calibration_factor):
        return value * calibration_factor

    # Функция для применения скользящего среднего
    def moving_average(self, value, window_size):
        self.previous_values.append(value)
        if len(self.previous_values) > window_size:
            self.previous_values.pop(0)
        return sum(self.previous_values) / len(self.previous_values)

    # Функция для фильтра Калмана
    def apply_kalman_filter(self, value, kalman_config):
        if not self.kalman_filter:
            self.kalman_filter = KalmanFilter(
                kalman_config['process_noise'],
                kalman_config['measurement_noise']
            )
        return self.kalman_filter.apply(value)

    # Функция для удаления выбросов
    def detect_outliers(self, value, threshold):
        if self.previous_values and abs(value - self.previous_values[-1]) > threshold:
            return self.previous_values[-1]  # Игнорируем выброс
        return value

    # Функция для температурной компенсации
    def compensate_temperature(self, value, compensation_factor):
        # Допустим, у нас есть функция для получения текущей температуры
        current_temperature = self.get_current_temperature()
        return value * (1 + compensation_factor * (current_temperature - 25))

    def get_current_temperature(self):
        # Эта функция может возвращать температуру с дополнительного сенсора
        return 25  # Здесь условно возвращаем комнатную температуру

    # Функция для вызова произвольного кода обработки
    def apply_custom_processing(self, value):
        custom_processing = self.processing['custom_processing']
        module_path = custom_processing['module']
        function_name = custom_processing['function']
        params = custom_processing.get('params', {})

        try:
            # Динамическая загрузка модуля
            module = importlib.import_module(module_path)
            # Получаем функцию
            processing_function = getattr(module, function_name)
            # Вызываем функцию с передачей параметров
            return processing_function(value, **params)
        except Exception as e:
            print(f"Ошибка при вызове произвольной обработки: {e}")
            return value  # Возвращаем исходное значение, если произошла ошибка

class Valve(Device):
    def __init__(self, id, connection, name, coord_x, coord_y, pin, default_status=False):
        super().__init__(id, connection, name, coord_x, coord_y)
        self.pin = pin
        self.status = default_status
        self.shape = None
        self.label = None
        self.button = None
        self.name_text = None

    @classmethod
    def from_json(cls, json_data):
        return cls(
            id=json_data['id'],
            connection=json_data['connection'],
            name=json_data['name'],
            coord_x=json_data['coord_x'],
            coord_y=json_data['coord_y'],
            pin=json_data['pin'],
            default_status=json_data.get('default_status', False)
        )

    def toggle(self):
        self.status = not self.status

    def open(self):
        self.status = True

    def close(self):
        self.status = False

    def send_command(self):
        pass