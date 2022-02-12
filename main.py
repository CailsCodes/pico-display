import gc
import math
from collections import deque

import picodisplay as display  # type: ignore
import uasyncio
from machine import ADC as temp
from utime import time, localtime, sleep

import planets

gc.enable()

width = display.get_width()
height = display.get_height()
display_height = 135
display_buffer = bytearray(width * height * 2)
display.init(display_buffer)
display.set_backlight(0.5)

last_pressed = seconds_absolute = time()
current_temp = forward = 0

conversion_factor = 3.3 / (65535)
temperatures = deque((), 1)

# colour_pallet = {
#     "dark green" : (102, 140, 74),
#     "green" : (166, 191, 75),
#     "white" : (242, 240, 213),
#     "yellow" : (242, 197, 71),
#     "grey" : (177, 177, 172),
#     "red" : (255, 102, 90),
#     "orange" : (255, 140, 100),
#     "blue" : (154, 207, 221)
#     }

async def time_sync():
    while time() < 1609545601:
        for _ in range(3):
            display.set_led(255, 102, 90)
            await uasyncio.sleep(0.2)
            display.set_led(0, 0, 0)
            await uasyncio.sleep(0.2)
        await uasyncio.sleep(1)
    else:
        display.set_led(166, 191, 75)
        uasyncio.sleep(10)
        display.set_led(0, 0, 0)
    return


def hello_world():
    display.set_pen(102, 140, 74)
    display.clear()
    display.set_pen(242, 240, 213)
    display.text("Hello there", 10, 10, 240, 6)
    display.update()

def clock():
    year, month, mday, hour, minute, *_ = localtime()
    display.set_pen(177, 177, 172)
    display.clear()
    display.set_pen(242, 197, 71)
    t = "{h:02d}:{m:02d}".format(h=hour, m=minute)
    d = "{day:02d}/{mon:02d}/{y}".format(day=mday, mon=month, y=year)
    display.text(t, 10, 10, 240, 8)
    display.text(d, 10, 80, 240, 4)
    display.update()

def circle(xpos0, ypos0, rad):
    x = rad - 1
    y = 0
    dx = dy = 1
    err = dx - (rad << 1)
    while x >= y:
        display.pixel(xpos0 + x, ypos0 + y)
        display.pixel(xpos0 + y, ypos0 + x)
        display.pixel(xpos0 - y, ypos0 + x)
        display.pixel(xpos0 - x, ypos0 + y)
        display.pixel(xpos0 - x, ypos0 - y)
        display.pixel(xpos0 - y, ypos0 - x)
        display.pixel(xpos0 + y, ypos0 - x)
        display.pixel(xpos0 + x, ypos0 - y)
        if err <= 0:
            y += 1
            err += dy
            dy += 2
        if err > 0:
            x -= 1
            dx += 2
            err += dx - (rad << 1)

def draw_planets(ti):
    PL_CENTER = (90, 67)
    # draw the sun
    display.set_pen(255, 255, 0)
    display.circle(PL_CENTER[0], PL_CENTER[1], 4)
    planets_dict = planets.coordinates(ti[0], ti[1], ti[2], ti[3], ti[4])
    for i, el in enumerate(planets_dict):
        r = 8 * (i + 1) + 2
        display.set_pen(40, 40, 40)
        circle(PL_CENTER[0], PL_CENTER[1], r)
        feta = math.atan2(el[0], el[1])
        coordinates = (r * math.sin(feta), r * math.cos(feta))
        coordinates = (coordinates[0] + PL_CENTER[0], 135 - (coordinates[1] + PL_CENTER[1]))
        for ar in range(0, len(planets.planets_a[i][0]), 5):
            x = planets.planets_a[i][0][ar] - 50 + coordinates[0]
            y = planets.planets_a[i][0][ar + 1] - 50 + coordinates[1]
            if x >= 0 and y >= 0:
                display.set_pen(planets.planets_a[i][0][ar + 2], planets.planets_a[i][0][ar + 3], planets.planets_a[i][0][ar + 4])
                display.pixel(int(x), int(y))

def solar_system():
    display.set_pen(0, 0, 0)
    display.clear()
    ti = localtime(seconds_absolute + forward)
    draw_planets(ti)
    display.set_pen(242, 197, 71)
    display.text("Sol", 160, 105, 99, 4)
    display.update()

async def fetch_temp():
    while True:
        sensor_temp = temp(4)
        reading = sensor_temp.read_u16() * conversion_factor
        temperature = 27 - (reading - 0.706) / 0.001721
        temperatures.append(round(temperature, 1))
        await uasyncio.sleep(5)

def thermometer():
    global current_temp
    try:
        current_temp = temperatures.popleft()
    except IndexError:
        pass
    display.set_pen(242, 240, 213)
    display.clear()
    display.set_pen(154, 207, 221)
    display.text("On-board temp sensor", 15, 110, 230, 2)
    display.set_pen(255, 102, 90)
    display.text("{t}C".format(t=current_temp), 40, 30, 80, 8)
    display.update()

def select_func(func):
    f = None
    if display.is_pressed(display.BUTTON_A):
        f = hello_world
    elif display.is_pressed(display.BUTTON_B):
        f = clock
    elif display.is_pressed(display.BUTTON_X):
        f = thermometer
    elif display.is_pressed(display.BUTTON_Y):
        f = solar_system
        
    if f:
        global last_pressed
        last_pressed = time()
        return f
    return func

def sleeping():
    while True:
        func = select_func(None)
        if func:
            display.set_backlight(0.5)
            return func
        sleep(0.1)

def dim():
    for i in (0.5, 0.45,0.4,0.35,0.3,0.25,0.2,0.15,0.1,0.05,0.0):
        display.set_backlight(i)
        yield

async def main():
    global forward
    uasyncio.create_task(fetch_temp())
    uasyncio.create_task(time_sync())
    func = hello_world
    dim_factor = dim()

    while True:
        if (time() - last_pressed) > 120:
            try:
                next(dim_factor)
            except StopIteration:
                func = sleeping()
                dim_factor = dim()
        func = select_func(func)
        func()

        if func == solar_system:
            gc.collect()
            forward += 86400

        await uasyncio.sleep(0.1)

uasyncio.run(main())
