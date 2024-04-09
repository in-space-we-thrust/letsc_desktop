import json


class Sensor:
    def __init__(self, id, port, name, units, coord_x, coord_y):
        self.id = id
        self.port = port
        self.name = name
        self.units = units
        self.coord_x = coord_x
        self.coord_y = coord_y
        self.value = None
        self.rectangle = None
        self.text = None

    def __str__(self):
        return f"Sensor {self.id}: {self.name} ({self.units})"

    @classmethod
    def from_json(cls, json_data):
        return cls(
            id=json_data['id'],
            port=json_data['port'],
            name=json_data['name'],
            units=json_data['units'],
            coord_x=json_data['coord_x'],
            coord_y=json_data['coord_y']
        )

class Valve:
    def __init__(self, id, port, name, coord_x, coord_y):
        self.id = id
        self.port = port
        self.name = name
        self.coord_x = coord_x
        self.coord_y = coord_y
        self.status = False  # Изначально клапан закрыт
        self.shape = None
        self.label = None
        self.button = None

    def __str__(self):
        return f"Valve {self.id}: {self.name}"

    def toggle(self):
        self.status = not self.status

    def open(self):
        self.status = True

    def close(self):
        self.status = False

    def send_command(self):
        # Здесь вы можете реализовать отправку команды на управление клапаном через последовательный порт
        pass

    @classmethod
    def from_json(cls, json_data):
        return cls(
            id=json_data['id'],
            port=json_data['port'],
            name=json_data['name'],
            coord_x=json_data['coord_x'],
            coord_y=json_data['coord_y']
        )