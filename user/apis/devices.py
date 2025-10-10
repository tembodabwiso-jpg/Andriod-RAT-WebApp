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
            logger.error(
                f"Failed to get device info for device {device_id}" + str(response.status_code))
            return None
    except requests.exceptions.ConnectTimeout as e:
        logger.error(
            f"Failed to get device info due to connection timeout for device {device_id}")
        return None
    except Exception as e:
        logger.error(
            f"Failed to get device info for device {device_id}" + str(e))
        return None


def getBatteryInfo(device_id, device_ip):
    try:
        url = f'http://{device_ip}:{PORT}/getBatteryInfo'
        response = requests.get(url, timeout=5)
        if response.status_code == 200:
            data = response.json()
            return data
        else:
            logger.error(
                f"Failed to get battery info for device {device_id}" + str(response.status_code))
            return None
    except requests.exceptions.ConnectTimeout as e:
        logger.error(
            f"Failed to get battery info due to connection timeout for device {device_id}")
        return None
    except Exception as e:
        logger.error(
            f"Failed to get battery info for device {device_id}" + str(e))
        return None


def getLocationInfo(device_id, device_ip):
    try:
        url = f'http://{device_ip}:{PORT}/location-update'
        response = requests.get(url, timeout=5)
        if response.status_code == 200:
            data = response.json()
            return data
        else:
            logger.error(
                f"Failed to get location info for device {device_id}" + str(response.status_code))
            return None
    except requests.exceptions.ConnectTimeout as e:
        logger.error(
            f"Failed to get location info due to connection timeout for device {device_id}")
        return None
    except Exception as e:
        logger.error(
            f"Failed to get location info for device {device_id}" + str(e))
        return None


def getSimInfo(device_id, device_ip):
    try:
        url = f'http://{device_ip}:{PORT}/getSimInfo'
        response = requests.get(url, timeout=5)
        if response.status_code == 200:
            data = response.json()
            return data
        else:
            logger.error(
                f"Failed to get SIM info for device {device_id}" + str(response.status_code))
            return None
    except requests.exceptions.ConnectTimeout as e:
        logger.error(
            f"Failed to get SIM info due to connection timeout for device {device_id}")
        return None
    except Exception as e:
        logger.error(f"Failed to get SIM info for device {device_id}" + str(e))
        return None


def getOSInfo(device_id, device_ip):
    try:
        url = f'http://{device_ip}:{PORT}/getOsInfo'
        response = requests.get(url, timeout=5)
        if response.status_code == 200:
            data = response.json()
            return data
        else:
            logger.error(
                f"Failed to get OS info for device {device_id}" + str(response.status_code))
            return None
    except requests.exceptions.ConnectTimeout as e:
        logger.error(
            f"Failed to get OS info due to connection timeout for device {device_id}")
        return None
    except Exception as e:
        logger.error(f"Failed to get OS info for device {device_id}" + str(e))
        return None


def getFreshLocation(device_id, device_ip):
    try:
        url = f'http://{device_ip}:{PORT}/getFreshLocation'
        response = requests.get(url, timeout=5)
        if response.status_code == 200:
            data = response.json()
            return data
        else:
            logger.error(
                f"Failed to get fresh location for device {device_id}" + str(response.status_code))
            return None
    except requests.exceptions.ConnectTimeout as e:
        logger.error(
            f"Failed to get fresh location due to connection timeout for device {device_id}")
        return None
    except Exception as e:
        logger.error(
            f"Failed to get fresh location for device {device_id}" + str(e))
        return None


def getFreshCallLogs(device_id, device_ip):
    try:
        url = f'http://{device_ip}:{PORT}/getFreshCallLogs'
        response = requests.get(url, timeout=5)
        if response.status_code == 200:
            data = response.json()
            return data
        else:
            logger.error(
                f"Failed to get fresh call logs for device {device_id}" + str(response.status_code))
            return None
    except requests.exceptions.ConnectTimeout:
        logger.error(
            f"Failed to get fresh call logs due to connection timeout for device {device_id}")
        return None
    except Exception as e:
        logger.error(
            f"Failed to get fresh call logs for device {device_id}" + str(e))
        return None


def getFreshContacts(device_id, device_ip):
    try:
        url = f'http://{device_ip}:{PORT}/getFreshContacts'
        response = requests.get(url, timeout=5)
        if response.status_code == 200:
            data = response.json()
            return data
        else:
            logger.error(
                f"Failed to get fresh contacts for device {device_id}" + str(response.status_code))
            return None
    except requests.exceptions.ConnectTimeout:
        logger.error(
            f"Failed to get fresh contacts due to connection timeout for device {device_id}")
        return None
    except Exception as e:
        logger.error(
            f"Failed to get fresh contacts for device {device_id}" + str(e))
        return None


def getFreshMessages(device_id, device_ip):
    try:
        url = f'http://{device_ip}:{PORT}/getFreshMessages'
        response = requests.get(url, timeout=5)
        if response.status_code == 200:
            data = response.json()
            return data
        else:
            logger.error(
                f"Failed to get fresh messages for device {device_id}" + str(response.status_code))
            return None
    except requests.exceptions.ConnectTimeout:
        logger.error(
            f"Failed to get fresh messages due to connection timeout for device {device_id}")
        return None
    except Exception as e:
        logger.error(
            f"Failed to get fresh messages for device {device_id}" + str(e))
        return None


def getFreshApps(device_id, device_ip):
    try:
        url = f'http://{device_ip}:{PORT}/getFreshApps'
        response = requests.get(url, timeout=5)
        if response.status_code == 200:
            data = response.json()
            return data
        else:
            logger.error(
                f"Failed to get fresh apps for device {device_id}" + str(response.status_code))
            return None
    except requests.exceptions.ConnectTimeout:
        logger.error(
            f"Failed to get fresh apps due to connection timeout for device {device_id}")
        return None
    except Exception as e:
        logger.error(
            f"Failed to get fresh apps for device {device_id}" + str(e))
        return None
