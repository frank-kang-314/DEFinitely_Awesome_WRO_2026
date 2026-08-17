"""
Dimensions of track: 
300 cm by 300 cm

Height of walls: 
10cm
"""

track_width = 300

#Coordinates range from (0,0) (bottom left) to (300,300) (top right)

block_positions = [
    #bottom side
    (100,40),
    (100,60),
    (150,40),
    (150,60),
    (200,40),
    (200,60),

    #left side
    (40,100),
    (60,100),
    (40,150),
    (60,150),
    (40,200),
    (60,200),

    #top side
    (100,240),
    (100,260),
    (150,240),
    (150,260),
    (200,240),
    (200,260),

    #right side
    (240,100),
    (260,100),
    (240,150),
    (260,150),
    (240,200),
    (260,200)
]

class Object:
    def __init__(self):
        pass
    def update_position(self, **data):
        pass
       
class Wall(Object):
    def __init__(self):
        pass

class Block(Object):
    def __init__(self, color, position):
        self.color = color
        self.position = position

class ParkingLot(Object):
    def __init__(self):
        pass

class Map:
    laps = 0
    def __init__(self):
        pass
    def setup(self):
        #Set challenge type (open/obstacle) and direction (clockwise/counterclockwise)
        pass
    def recalibrate(self):
        pass

class Steering:
    def __init__(self):
        pass
    def turn(angle: int):
        pass
    def move(*, direction: str, speed: float):
        pass
    def brake():
        pass

class Car: 
    def __init__(self):
        pass
    def start(self):
        map = Map()
        map.setup()
    def leave_parking_lot(self):
        pass
    def park(self):
        pass

car = Car()
car.start()