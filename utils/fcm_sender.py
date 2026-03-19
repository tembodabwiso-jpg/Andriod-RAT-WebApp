"""
FCM push notification sender.
Sends command payloads to Android devices via Firebase Cloud Messaging.
Falls back gracefully if FCM is not configured.
"""

from logzero import logger
from config.fcm import get_firebase_app


def send_command_to_device(fcm_token: str, command_id: int, command_type: str, payload: dict = None) -> bool:
    """
    Send a command to a device via FCM push notification.
    Returns True if sent successfully, False otherwise.
    """
    app = get_firebase_app()
    if app is None:
        logger.debug("FCM not available, skipping push notification")
        return False

    if not fcm_token:
        logger.debug("No FCM token for device, skipping push")
        return False

    try:
        from firebase_admin import messaging

        data = {
            'command_id': str(command_id),
            'command_type': command_type,
        }
        if payload:
            import json
            data['payload'] = json.dumps(payload)

        message = messaging.Message(
            data=data,
            token=fcm_token,
            android=messaging.AndroidConfig(
                priority='high',
                ttl=300,  # 5 minutes TTL
            ),
        )

        response = messaging.send(message)
        logger.info(f"FCM: Sent command {command_type} (id={command_id}) → response: {response}")
        return True

    except Exception as e:
        logger.error(f"FCM: Failed to send push: {e}")
        return False


def send_to_topic(topic: str, command_type: str, payload: dict = None) -> bool:
    """Send a command to all devices subscribed to a topic."""
    app = get_firebase_app()
    if app is None:
        return False

    try:
        from firebase_admin import messaging
        import json

        data = {
            'command_type': command_type,
        }
        if payload:
            data['payload'] = json.dumps(payload)

        message = messaging.Message(
            data=data,
            topic=topic,
        )
        messaging.send(message)
        return True
    except Exception as e:
        logger.error(f"FCM topic send failed: {e}")
        return False
