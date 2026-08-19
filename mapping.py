"""
OVERALL HIERARCHY OF THE CODE: 

Main class: Car (General controls)
    * Start car
    * Leave parking lot (if applicable)
    * Perform main sequence
    * Park (if applicable)
    * Stop

Three systems: Steering, Sensors (Hardware), Map (Software)

Steering: 
    * Turn
    * Drive forward / backward
    * Stop

Sensors: 
    * Read ultrasonic sensor and camera data
    * Output the data to other functions / classes

Map: 
    * Create walls
    * Record seen obstacles
    * Update car position
    * Send instructions to steering
"""



rect_types = {
    "no_collide_outer": "NO_COLLIDE_OUTER", #things you can't hit the outside of, like traffic signs
    "no_collide_inner": "NO_COLLIDE_INNER", #things you can't hit the inside of, like the outer walls)
    }

class Rect:
    def __init__(self, *, bottom_left_corner, width, height, type):
        self.bottom_left_corner = bottom_left_corner
        self.width = width
        self.height = height
        self.type = type 
        """
        Types include: 
        no_collide_outer (things you can't hit the outside of, like traffic signs)
        no_collide_inner (things you can't hit the inside of, like walls)

        (SEE rect_types VARIABLE ABOVE)
        
        """
        
class Wall(Rect):
    def __init__(self, **location: str):
        if location == "outer":
            self.bottom_left_corner = (0,0)
            self.width = 300
            self.height = 300
            self.type = rect_types["no_collide_inner"]
            

class Block(Rect):
    def __init__(self, color, position):
        self.color = color
        self.position = position
    def update_position(self, **data):
        pass

class ParkingLot(Rect):
    def __init__(self):
        pass

class Map:
    __laps = 0 #Private variable
    track_width = 300

    #Coordinates range from (0,0) (bottom left) to (300,300) (top right)

    block_positions =((100,40), (100,60), (150,40), (150,60), (200,40), (200,60), (40,100), (60,100), (40,150), (60,150), (40,200), (60,200), (100,240), (100,260), (150,240), (150,260), (200,240), (200,260), (240,100), (260,100), (240,150), (260,150), (240,200), (260,200))

    def __init__(self):
        pass
    def setup(self):
        #This is the list where all future objects on the map will be added
        self.objects = []

        self.objects.append(Wall(location = "outer"))

        #Set challenge type (open/obstacle) and direction (clockwise/counterclockwise)

        #Set current position

        #Start looking for obstacles
        pass
    def add(self):
        #Add new objects as the car discovers more of the track
        pass
        
    def recalibrate(self):
        pass
    def check_laps(self):
        return self.__laps
    def increment_laps(self):
        pass

class Steering:
    def __init__(self):
        pass

    def start(self):
        pass

    def turn(self, angle: int):
        #Straight: 110
        #Left: 150
        #Right: 60
        pass

    def move(self, *, direction: str, speed: float):
        pass

    def brake(self):
        pass

class Sensors:
    def __init__(self):
        pass
    def read_ultrasonic(self):
        pass
    def read_camera(self):
        pass
    def return_data(self):
        pass

class Car:
    #Insert actual measurements when chassis is complete
    width, height = 20, 30 #in cm

    def __init__(self):
        pass
    def start(self):
        steering = Steering()

        sensors = Sensors()

        map = Map()
        map.setup()

    def leave_parking_lot(self):
        pass
    def park(self):
        pass

car = Car()
car.start()