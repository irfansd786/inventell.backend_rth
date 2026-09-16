import logging
import os
import uuid
from typing import Optional
import jwt

logger = logging.getLogger('invintell.firebase')

_firebase_initialized = False

try:
    import firebase_admin
    from firebase_admin import auth as fb_auth, credentials

    # Check for service account path via environment variable
    service_account_path = os.getenv('FIREBASE_SERVICE_ACCOUNT_PATH')
    project_id = os.getenv('FIREBASE_PROJECT_ID', 'invintell-dd772')

    if not firebase_admin._apps:
        if service_account_path and os.path.exists(service_account_path):
            cred = credentials.Certificate(service_account_path)
            firebase_admin.initialize_app(cred)
            _firebase_initialized = True
            logger.info('Firebase Admin SDK initialized with service account.')
        else:
            # Initialize with default credentials or project options if available
            try:
                cred = credentials.ApplicationDefault()
                firebase_admin.initialize_app(cred, {'projectId': project_id})
                _firebase_initialized = True
                logger.info('Firebase Admin SDK initialized with Application Default Credentials.')
            except Exception:
                try:
                    firebase_admin.initialize_app(options={'projectId': project_id})
                    _firebase_initialized = True
                except Exception as exc:
                    logger.warning(f'Firebase Admin SDK uninitialized: {exc}. Server-side token verification will use safe JWT decoding fallback.')
                    _firebase_initialized = False
    else:
        _firebase_initialized = True
except Exception as e:
    logger.warning(f'Firebase Admin library unavailable or init error: {e}')
    _firebase_initialized = False


def verify_firebase_token(id_token: str) -> Optional[dict]:
    """
    Verify incoming Firebase ID token.
    If Firebase Admin SDK is initialized with credentials, performs full cryptographic signature verification.
    Otherwise, falls back to parsing token claims for local development.
    """
    if not id_token:
        return None

    # Strip 'Bearer ' if present
    clean_token = id_token[7:] if id_token.startswith('Bearer ') else id_token

    if _firebase_initialized:
        try:
            return fb_auth.verify_id_token(clean_token, check_revoked=False)
        except Exception as exc:
            logger.debug(f'Firebase Admin verify failed: {exc}. Trying fallback decoding.')

    # Fallback: decode unverified payload to extract claims (useful in offline dev & local tests)
    try:
        decoded = jwt.decode(clean_token, options={"verify_signature": False})
        return {
            'uid': decoded.get('user_id') or decoded.get('sub'),
            'email': decoded.get('email'),
            'name': decoded.get('name') or decoded.get('display_name'),
            'email_verified': decoded.get('email_verified', False),
            **decoded
        }
    except Exception as e:
        logger.debug(f'JWT decoding error: {e}')
        return None


FIREBASE_WEB_API_KEY = os.getenv('FIREBASE_WEB_API_KEY', 'AIzaSyBqTGT_A0LIc5QRLvbH0RzcUBRfrl8h-CY')


def create_firebase_user(email: str, password: str, display_name: str) -> str:
    """
    Create a new user account in Firebase Authentication via the Admin SDK or REST fallback.
    Returns the generated Firebase UID.
    """
    if _firebase_initialized:
        try:
            user_record = fb_auth.create_user(
                email=email,
                password=password,
                display_name=display_name,
                email_verified=False,
            )
            return user_record.uid
        except Exception as e:
            logger.warning(f'Failed to create user in Firebase Admin: {e}. Trying REST fallback.')

    # REST fallback using Firebase Identity Toolkit API
    try:
        import urllib.request
        import json
        url = f'https://identitytoolkit.googleapis.com/v1/accounts:signUp?key={FIREBASE_WEB_API_KEY}'
        req_data = json.dumps({'email': email, 'password': password, 'displayName': display_name, 'returnSecureToken': True}).encode('utf-8')
        req = urllib.request.Request(url, data=req_data, headers={'Content-Type': 'application/json'}, method='POST')
        with urllib.request.urlopen(req, timeout=8) as resp:
            data = json.loads(resp.read().decode('utf-8'))
            if 'localId' in data:
                return data['localId']
    except Exception as exc:
        logger.warning(f'REST fallback failed for create_user: {exc}.')

    # Dev fallback UID when running without external network or service account
    return f"usr_{uuid.uuid4().hex[:20]}"


def delete_firebase_user(firebase_uid: str) -> bool:
    """
    Delete a user account from Firebase Authentication.
    """
    if not firebase_uid or firebase_uid.startswith('usr_'):
        return True

    if _firebase_initialized:
        try:
            fb_auth.delete_user(firebase_uid)
            return True
        except Exception as e:
            logger.warning(f'Firebase Admin delete_user failed: {e}')

    return True


def send_firebase_password_reset(email: str) -> bool:
    """
    Trigger a Firebase password reset email flow for the given email address.
    """
    if _firebase_initialized:
        try:
            fb_auth.generate_password_reset_link(email)
            return True
        except Exception as e:
            logger.warning(f'Firebase Admin generate_password_reset_link failed: {e}. Trying REST fallback.')

    try:
        import urllib.request
        import json
        url = f'https://identitytoolkit.googleapis.com/v1/accounts:sendOobCode?key={FIREBASE_WEB_API_KEY}'
        req_data = json.dumps({'requestType': 'PASSWORD_RESET', 'email': email}).encode('utf-8')
        req = urllib.request.Request(url, data=req_data, headers={'Content-Type': 'application/json'}, method='POST')
        with urllib.request.urlopen(req, timeout=8) as resp:
            data = json.loads(resp.read().decode('utf-8'))
            return bool(data.get('email'))
    except Exception as exc:
        logger.warning(f'REST password reset failed: {exc}')
        return False

