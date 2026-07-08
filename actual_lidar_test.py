import time
from rplidar import RPLidar, RPLidarException
import serial, serial.tools.list_ports

def main() -> None:
    lidar = RPLidar(detect_port(), baudrate=115200)
    info = lidar.get_info()
    print(info)

    health = lidar.get_health()
    print(health)

    lidar.start_motor()
    time.sleep(2)

    try:
        print('Recording measurments... Press Ctrl+C to stop.')
        while True:
            try:
                for scan in lidar.iter_scans():
                    print(scan)
            except RPLidarException as e:
                print(f'Recoverable error: {e}, resyncing...')
                lidar.clear_input()
                time.sleep(0.1)
                continue
    except KeyboardInterrupt:
        print('Stopping.')
    finally:
        lidar.stop()
        lidar.stop_motor()
        lidar.disconnect()

def detect_port() -> str:
    ports = list(serial.tools.list_ports.comports())  # outputs all the ports connected
    if not ports: 
        print("No USB Serial devices found.")
    else: 
        for port, desc, hwid in sorted(ports):
            print(f'Port: {port}')
            print(f'Description: {desc}')
            print(f'Hardware ID: {hwid}')

            print(hwid.split(" "))
            print(hwid.split(" ")[1])

            if hwid.split(" ")[1] == "VID:PID=1A86:7523":
                print(f"LiDAR port is {port}")
                return port
        print("No LiDAR sensor detected.")
        return

if __name__ == '__main__':
    main()