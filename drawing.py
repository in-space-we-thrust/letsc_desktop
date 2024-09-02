import tkinter as tk
import math

def draw_sensor(canvas, sensor):
    sensor.rectangle = canvas.create_rectangle(sensor.coord_x, sensor.coord_y - 20, sensor.coord_x + 40, sensor.coord_y + 20, outline='green')
    sensor.name_text = canvas.create_text(sensor.coord_x, sensor.coord_y-13, anchor=tk.W, text=sensor.name, fill='black')
    sensor.text = canvas.create_text(sensor.coord_x + 20, sensor.coord_y, text=f"{sensor.value}", fill='black')
    sensor.units_text = canvas.create_text(sensor.coord_x+20, sensor.coord_y+13, anchor=tk.W, text=sensor.units, fill='black')

def draw_valve(canvas, valve):
    vertices = [(valve.coord_x-7, valve.coord_y - 10), (valve.coord_x + 7, valve.coord_y), (valve.coord_x - 7, valve.coord_y + 10)]
    valve.shape = canvas.create_polygon(vertices, fill='green', outline='black')
    valve.label = canvas.create_text(valve.coord_x-7, valve.coord_y+25, text="ON", fill='green')

def draw_tank(canvas, center_x, center_y, thickness, height, curvature, fill='lightblue'):
    x1 = center_x - thickness / 2
    y1 = center_y - height / 2
    x2 = center_x + thickness / 2
    y2 = center_y + height / 2
    return canvas.create_rectangle(x1, y1, x2, y2, fill=fill, outline='black')

def draw_combustion_chamber(canvas, center_x, center_y, width, height, nozzle_start_radius, nozzle_end_radius, nozzle_length, nozzle_orientation):
    chamber_left = center_x - width / 2
    chamber_right = center_x + width / 2
    chamber_top = center_y - height / 2
    chamber_bottom = center_y + height / 2
    canvas.create_rectangle(chamber_left, chamber_top, chamber_right, chamber_bottom, fill="gray")

    nozzle_start_x = chamber_right if nozzle_orientation == "right" else chamber_left - nozzle_length
    nozzle_start_y = center_y
    nozzle_end_x = nozzle_start_x + nozzle_length if nozzle_orientation == "right" else nozzle_start_x - nozzle_length
    nozzle_end_y = center_y

    num_points = 50
    bell_curve_points = []
    for i in range(num_points + 1):
        t = i / num_points
        x = nozzle_start_x + t * (nozzle_end_x - nozzle_start_x)
        radius = nozzle_start_radius + (nozzle_end_radius - nozzle_start_radius) * (1 - math.cos(math.pi * t)) / 2
        y_top = nozzle_start_y - radius
        y_bottom = nozzle_start_y + radius
        bell_curve_points.append((x, y_top))

    for i in range(num_points, -1, -1):
        t = i / num_points
        x = nozzle_start_x + t * (nozzle_end_x - nozzle_start_x)
        radius = nozzle_start_radius + (nozzle_end_radius - nozzle_start_radius) * (1 - math.cos(math.pi * t)) / 2
        y_top = nozzle_start_y - radius
        y_bottom = nozzle_start_y + radius
        bell_curve_points.append((x, y_bottom))

    canvas.create_polygon(bell_curve_points, fill="gray")

def draw_grid(canvas, width, height, step=50):
    for x in range(0, width, step):
        canvas.create_line(x, 0, x, height, fill='lightgray', dash=(2, 2))
        canvas.create_text(x, 5, text=str(x), anchor=tk.NW)
    for y in range(0, height, step):
        canvas.create_line(0, y, width, y, fill='lightgray', dash=(2, 2))
        canvas.create_text(5, y, text=str(y), anchor=tk.NW)