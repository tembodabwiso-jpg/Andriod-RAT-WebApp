import requests
from logzero import logger

PORT = 8080

def getDeviceInfo(device_id, device_ip):
    try:
        url = f'http://{device_ip}:{PORT}/getDeviceInfo'
        response = requests.get(url, timeout=5)
        if response.status_code == 200:
            data = response.json()
            return data
        else:
            logger.error(f"Failed to get device info for device {device_id}" + str(response.status_code))
            return None
    except requests.exceptions.ConnectTimeout as e:
        logger.error(f"Failed to get device info due to connection timeout for device {device_id}")
        return None
    except Exception as e:
        logger.error(f"Failed to get device info for device {device_id}" + str(e))
        return None
    
def getBatteryInfo(device_id, device_ip):
    try:
        url = f'http://{device_ip}:{PORT}/getBatteryInfo'
        response = requests.get(url, timeout=5)
        if response.status_code == 200:
            data = response.json()
            return data
        else:
            logger.error(f"Failed to get battery info for device {device_id}" + str(response.status_code))
            return None
    except requests.exceptions.ConnectTimeout as e:
        logger.error(f"Failed to get battery info due to connection timeout for device {device_id}")
        return None
    except Exception as e:
        logger.error(f"Failed to get battery info for device {device_id}" + str(e))
        return None