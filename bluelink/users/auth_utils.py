import jwt
import hashlib
import json
from datetime import datetime, timedelta, timezone as dt_timezone
from functools import wraps
from django.http import JsonResponse
from django.conf import settings


# ──────────────────────────────────────────────
# Password hashing (SHA-256 with salt)
# ──────────────────────────────────────────────

def hash_password(password: str) -> str:
    """Hash password with SHA-256"""
    salt = "bluelink_salt_2024"
    return hashlib.sha256(f"{salt}{password}".encode()).hexdigest()


def verify_password(password: str, hashed: str) -> bool:
    return hash_password(password) == hashed


# ──────────────────────────────────────────────
# JWT Token helpers
# ──────────────────────────────────────────────

def generate_token(payload: dict, expiry_hours: int = None) -> str:
    expiry_hours = expiry_hours or settings.JWT_EXPIRY_HOURS
    payload = payload.copy()
    payload['exp'] = datetime.now(dt_timezone.utc) + timedelta(hours=expiry_hours)
    payload['iat'] = datetime.now(dt_timezone.utc)
    return jwt.encode(payload, settings.JWT_SECRET, algorithm='HS256')


def decode_token(token: str) -> dict | None:
    try:
        return jwt.decode(token, settings.JWT_SECRET, algorithms=['HS256'])
    except jwt.ExpiredSignatureError:
        return None
    except jwt.InvalidTokenError:
        return None


def get_token_from_request(request) -> str | None:
    auth_header = request.headers.get('Authorization', '')
    if auth_header.startswith('Bearer '):
        return auth_header[7:]
    return None


# ──────────────────────────────────────────────
# JSON helper
# ──────────────────────────────────────────────

def json_response(data: dict, status: int = 200) -> JsonResponse:
    return JsonResponse(data, status=status)


def json_error(message: str, status: int = 400) -> JsonResponse:
    return JsonResponse({'success': False, 'error': message}, status=status)


def parse_json_body(request) -> dict:
    try:
        return json.loads(request.body)
    except Exception:
        return {}


# ──────────────────────────────────────────────
# Admin-only decorator
# ──────────────────────────────────────────────

def admin_required(view_func):
    """Decorator: only allows requests with a valid admin JWT token"""
    @wraps(view_func)
    def wrapper(request, *args, **kwargs):
        token = get_token_from_request(request)
        if not token:
            return json_error('Authentication token missing', 401)

        payload = decode_token(token)
        if not payload:
            return json_error('Invalid or expired token', 401)

        if payload.get('role') != 'admin':
            return json_error('Admin access required', 403)

        request.admin_id = payload.get('admin_id')
        request.admin_username = payload.get('username')
        return view_func(request, *args, **kwargs)
    return wrapper


# ──────────────────────────────────────────────
# User-auth decorator
# ──────────────────────────────────────────────

def user_required(view_func):
    """Decorator: allows valid user JWT tokens"""
    @wraps(view_func)
    def wrapper(request, *args, **kwargs):
        token = get_token_from_request(request)
        if not token:
            return json_error('Authentication token missing', 401)

        payload = decode_token(token)
        if not payload:
            return json_error('Invalid or expired token', 401)

        if payload.get('role') not in ('user', 'admin'):
            return json_error('Access denied', 403)

        request.user_id = payload.get('user_id')
        request.token_role = payload.get('role')
        return view_func(request, *args, **kwargs)
    return wrapper
