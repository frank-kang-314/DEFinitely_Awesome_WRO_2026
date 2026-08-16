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
   
class Wall():
    def __init__(self):
        pass

class Block():
    def __init__(self, color, position):
        self.color = color
        self.position = position

class ParkingLot():
    def __init__(self):
        pass

class Map():
    def __init__(self, challenge_type, direction, laps):
        self.challenge_type = challenge_type
        self.direction = direction
        self.laps = laps
    def recalibrate(self):
        pass