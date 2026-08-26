leave_parking()
while True: 
    detect_blocks()
    add_blocks_to_map()
    navigate_around_blocks_on_map()
    if corner:
        turn_corner(direction)
        corners = corners + 1 #on map
    if corners == 12: 
        break

park()
    