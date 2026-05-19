from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_http_methods
from django.utils import timezone

from .models import User, AdminUser
from .auth_utils import (
    hash_password, verify_password,
    generate_token, admin_required, user_required,
    json_response, json_error, parse_json_body
)


# ══════════════════════════════════════════════════════════════
#  ADMIN AUTH
# ══════════════════════════════════════════════════════════════

@csrf_exempt
@require_http_methods(['POST'])
def admin_login(request):
    data     = parse_json_body(request)
    username = data.get('username', '').strip()
    password = data.get('password', '').strip()

    if not username or not password:
        return json_error('Username and password are required')

    try:
        admin = AdminUser.objects.get(username=username)
    except AdminUser.DoesNotExist:
        return json_error('Invalid credentials', 401)

    if not verify_password(password, admin.password):
        return json_error('Invalid credentials', 401)

    admin.last_login = timezone.now()
    admin.save(update_fields=['last_login'])

    token = generate_token({
        'role':     'admin',
        'admin_id': admin.id,
        'username': admin.username,
    })

    return json_response({
        'success': True,
        'message': 'Admin login successful',
        'token':   token,
        'admin': {
            'id':         admin.id,
            'username':   admin.username,
            'last_login': admin.last_login.isoformat(),
        }
    })


# ══════════════════════════════════════════════════════════════
#  USER — CREATE  (Admin only)
# ══════════════════════════════════════════════════════════════

@csrf_exempt
@require_http_methods(['POST'])
@admin_required
def create_user(request):
    data = parse_json_body(request)

    required = ['username', 'password', 'place', 'phone_no']
    for field in required:
        if not data.get(field, '').strip():
            return json_error(f'Field "{field}" is required')

    username = data['username'].strip()
    if User.objects.filter(username=username).exists():
        return json_error('Username already exists', 409)

    user = User.objects.create(
        username=username,
        password=hash_password(data['password']),
        place=data['place'].strip(),
        branch=data.get('branch', '').strip() or None,
        phone_no=data['phone_no'].strip(),
        is_active=True,
        device_id=None,  # no device bound yet
    )

    return json_response({
        'success': True,
        'message': 'User created successfully',
        'user':    user.to_dict()
    }, status=201)


# ══════════════════════════════════════════════════════════════
#  USER — LOGIN  (with device binding)
# ══════════════════════════════════════════════════════════════

@csrf_exempt
@require_http_methods(['POST'])
def user_login(request):
    """
    POST /api/users/login/
    Body: { "username": "...", "password": "...", "device_id": "..." }

    Device binding rules:
      1. device_id missing in request         → 400 error
      2. Credentials wrong                    → 401 error
      3. Account inactive / expired           → 403 error
      4. device_id is None (first login)      → bind device, allow login
      5. device_id matches stored             → allow login
      6. device_id does NOT match stored      → 403 "already logged in on another device"
    """
    data      = parse_json_body(request)
    username  = data.get('username',  '').strip()
    password  = data.get('password',  '').strip()
    device_id = data.get('device_id', '').strip()

    if not username or not password:
        return json_error('Username and password are required')

    if not device_id:
        return json_error('device_id is required', 400)

    try:
        user = User.objects.get(username=username)
    except User.DoesNotExist:
        return json_error('Invalid credentials', 401)

    if not verify_password(password, user.password):
        return json_error('Invalid credentials', 401)

    # ── Device binding check ──────────────────────────────────
    if user.device_id is None or user.device_id == '':
        # First login — bind this device permanently
        user.device_id = device_id
        user.save(update_fields=['device_id'])
    elif user.device_id != device_id:
        # Different device trying to login — block it
        return json_error(
            'This account is already logged in on another device. '
            'Contact admin to reset your device binding.',
            403
        )
    # Else: same device_id — fall through normally

    # ── Active / expiry check ─────────────────────────────────
    if not user.effective_is_active:
        return json_error('Account is inactive. Contact admin.', 403)

    token = generate_token({
        'role':      'user',
        'user_id':   user.id,
        'username':  user.username,
        'device_id': device_id,
    })

    return json_response({
        'success': True,
        'message': 'Login successful',
        'token':   token,
        'user':    user.to_dict()
    })


# ══════════════════════════════════════════════════════════════
#  USER — LIST ALL  (Admin only)
# ══════════════════════════════════════════════════════════════

@csrf_exempt
@require_http_methods(['GET'])
@admin_required
def list_users(request):
    users = User.objects.all().order_by('-created_at')
    filter_active = request.GET.get('active')
    user_list = [u.to_dict() for u in users]

    if filter_active == 'true':
        user_list = [u for u in user_list if u['is_active']]
    elif filter_active == 'false':
        user_list = [u for u in user_list if not u['is_active']]

    return json_response({
        'success': True,
        'count':   len(user_list),
        'users':   user_list
    })


# ══════════════════════════════════════════════════════════════
#  USER — GET SINGLE  (Admin only)
# ══════════════════════════════════════════════════════════════

@csrf_exempt
@require_http_methods(['GET'])
@admin_required
def get_user(request, user_id):
    try:
        user = User.objects.get(id=user_id)
    except User.DoesNotExist:
        return json_error('User not found', 404)
    return json_response({'success': True, 'user': user.to_dict()})


# ══════════════════════════════════════════════════════════════
#  USER — ACTIVATE / DEACTIVATE  (Admin only)
# ══════════════════════════════════════════════════════════════

@csrf_exempt
@require_http_methods(['PATCH'])
@admin_required
def toggle_user_status(request, user_id):
    try:
        user = User.objects.get(id=user_id)
    except User.DoesNotExist:
        return json_error('User not found', 404)

    data = parse_json_body(request)
    if 'is_active' not in data:
        return json_error('is_active field is required (true/false)')

    new_status = bool(data['is_active'])

    if new_status:
        user.is_active             = True
        user.admin_override_active = True
        user.admin_override_at     = timezone.now()
    else:
        user.is_active             = False
        user.admin_override_active = False
        user.admin_override_at     = None

    user.save(update_fields=['is_active', 'admin_override_active', 'admin_override_at'])

    action = 'activated' if new_status else 'deactivated'
    return json_response({
        'success': True,
        'message': f'User {action} successfully',
        'user':    user.to_dict()
    })


# ══════════════════════════════════════════════════════════════
#  USER — RESET DEVICE BINDING  (Admin only)
#  Clears stored device_id so user can login from a new device
# ══════════════════════════════════════════════════════════════

@csrf_exempt
@require_http_methods(['POST'])
@admin_required
def reset_device(request, user_id):
    """
    POST /api/users/<user_id>/reset-device/
    Clears device_id so the user can login from a new/different device.
    Use when user gets a new phone or device binding needs to change.
    """
    try:
        user = User.objects.get(id=user_id)
    except User.DoesNotExist:
        return json_error('User not found', 404)

    old_device = user.device_id or 'none'
    user.device_id = None
    user.save(update_fields=['device_id'])

    return json_response({
        'success': True,
        'message': f'Device binding reset for "{user.username}". '
                   f'They can now login from any device.',
        'previous_device_id': old_device,
        'user': user.to_dict()
    })


# ══════════════════════════════════════════════════════════════
#  USER — DELETE  (Admin only)
# ══════════════════════════════════════════════════════════════

@csrf_exempt
@require_http_methods(['DELETE'])
@admin_required
def delete_user(request, user_id):
    try:
        user = User.objects.get(id=user_id)
    except User.DoesNotExist:
        return json_error('User not found', 404)

    username = user.username
    user.delete()
    return json_response({
        'success': True,
        'message': f'User "{username}" deleted successfully'
    })


# ══════════════════════════════════════════════════════════════
#  USER — CHANGE PASSWORD  (Admin only)
# ══════════════════════════════════════════════════════════════

@csrf_exempt
@require_http_methods(['PATCH'])
@admin_required
def change_password(request, user_id):
    try:
        user = User.objects.get(id=user_id)
    except User.DoesNotExist:
        return json_error('User not found', 404)

    data         = parse_json_body(request)
    new_password = data.get('new_password', '').strip()

    if not new_password:
        return json_error('new_password is required')
    if len(new_password) < 6:
        return json_error('Password must be at least 6 characters')

    user.password = hash_password(new_password)
    user.save(update_fields=['password'])

    return json_response({
        'success': True,
        'message': f'Password updated for user "{user.username}"'
    })


# ══════════════════════════════════════════════════════════════
#  USER — UPDATE PROFILE  (Admin only)
# ══════════════════════════════════════════════════════════════

@csrf_exempt
@require_http_methods(['PATCH'])
@admin_required
def update_user(request, user_id):
    try:
        user = User.objects.get(id=user_id)
    except User.DoesNotExist:
        return json_error('User not found', 404)

    data      = parse_json_body(request)
    updatable = ['place', 'branch', 'phone_no', 'username']
    changed   = []

    for field in updatable:
        if field in data:
            val = data[field].strip() if data[field] else None
            if field == 'username':
                if User.objects.exclude(id=user_id).filter(username=val).exists():
                    return json_error('Username already taken', 409)
            setattr(user, field, val)
            changed.append(field)

    if not changed:
        return json_error('No valid fields to update')

    user.save(update_fields=changed)
    return json_response({
        'success': True,
        'message': 'User updated successfully',
        'user':    user.to_dict()
    })


# ══════════════════════════════════════════════════════════════
#  HEALTH CHECK
# ══════════════════════════════════════════════════════════════

@require_http_methods(['GET'])
def health_check(request):
    return json_response({
        'success': True,
        'service': 'Bluelink API',
        'status':  'running'
    })
