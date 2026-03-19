"""
Firebase Cloud Messaging configuration.
Gracefully skips initialization if credentials are not configured.
"""

import os
from logzero import logger

_firebase_app = None
_initialized = False


def init_fcm():
    """Initialize Firebase Admin SDK. Call once at app startup."""
    global _firebase_app, _initialized

    if _initialized:
        return _firebase_app

    _initialized = True
    cred_path = os.getenv('FIREBASE_CREDENTIALS_PATH')

    if not cred_path or not os.path.exists(cred_path):
        logger.warning("FCM: No firebase credentials found. Push notifications disabled.")
        logger.warning(f"  Set FIREBASE_CREDENTIALS_PATH in .env (current: {cred_path})")
        return None

    try:
        import firebase_admin
        from firebase_admin import credentials
        cred = credentials.Certificate(cred_path)
        _firebase_app = firebase_admin.initialize_app(cred)
        logger.info("FCM: Firebase Admin SDK initialized successfully")
        return _firebase_app
    except ImportError:
        logger.warning("FCM: firebase-admin not installed. Run: pip install firebase-admin")
        return None
    except Exception as e:
        logger.error(f"FCM: Failed to initialize Firebase: {e}")
        return None


def get_firebase_app():
    """Get the initialized Firebase app, or None if not available."""
    global _firebase_app, _initialized
    if not _initialized:
        init_fcm()
    return _firebase_app
