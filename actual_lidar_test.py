import time
from rplidar import RPLidar, RPLidarException

from usbmonitor import USBMonitor
from usbmonitor.attributes import ID_MODEL, ID_MODEL_ID, ID_VENDOR_ID
        

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
    # Create the USBMonitor instance
    monitor = USBMonitor()

    # Get the current devices
    devices_dict = monitor.get_available_devices()

    # Print them
    for device_id, device_info in devices_dict.items():
        print(f"{device_id} -- {device_info[ID_MODEL]} ({device_info[ID_MODEL_ID]} - {device_info[ID_VENDOR_ID]})")
        if f"{device_info[ID_MODEL_ID]}-{device_info[ID_VENDOR_ID]}" == "7523-1A86":
            return ID_MODEL_ID
    print("LiDAR not detected.")
    return None

if __name__ == '__main__':
    main()