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
    """
    POST /api/admin/login
    Body: { "username": "...", "password": "..." }
    Returns admin JWT token
    """
    data = parse_json_body(request)
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
        'role': 'admin',
        'admin_id': admin.id,
        'username': admin.username,
    })

    return json_response({
        'success': True,
        'message': 'Admin login successful',
        'token': token,
        'admin': {
            'id': admin.id,
            'username': admin.username,
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
    """
    POST /api/users/create
    Headers: Authorization: Bearer <admin_token>
    Body: { "username", "password", "place", "branch"(opt), "phone_no" }
    """
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
    )

    return json_response({
        'success': True,
        'message': 'User created successfully',
        'user': user.to_dict()
    }, status=201)


# ══════════════════════════════════════════════════════════════
#  USER — LOGIN
# ══════════════════════════════════════════════════════════════

@csrf_exempt
@require_http_methods(['POST'])
def user_login(request):
    """
    POST /api/users/login
    Body: { "username": "...", "password": "..." }
    """
    data = parse_json_body(request)
    username = data.get('username', '').strip()
    password = data.get('password', '').strip()

    if not username or not password:
        return json_error('Username and password are required')

    try:
        user = User.objects.get(username=username)
    except User.DoesNotExist:
        return json_error('Invalid credentials', 401)

    if not verify_password(password, user.password):
        return json_error('Invalid credentials', 401)

    if not user.effective_is_active:
        return json_error('Account is inactive. Contact admin.', 403)

    token = generate_token({
        'role': 'user',
        'user_id': user.id,
        'username': user.username,
    })

    return json_response({
        'success': True,
        'message': 'Login successful',
        'token': token,
        'user': user.to_dict()
    })


# ══════════════════════════════════════════════════════════════
#  USER — LIST ALL  (Admin only)
# ══════════════════════════════════════════════════════════════

@csrf_exempt
@require_http_methods(['GET'])
@admin_required
def list_users(request):
    """
    GET /api/users/
    Headers: Authorization: Bearer <admin_token>
    Optional query: ?active=true|false
    """
    users = User.objects.all().order_by('-created_at')

    filter_active = request.GET.get('active')
    user_list = [u.to_dict() for u in users]

    if filter_active == 'true':
        user_list = [u for u in user_list if u['is_active']]
    elif filter_active == 'false':
        user_list = [u for u in user_list if not u['is_active']]

    return json_response({
        'success': True,
        'count': len(user_list),
        'users': user_list
    })


# ══════════════════════════════════════════════════════════════
#  USER — GET SINGLE  (Admin only)
# ══════════════════════════════════════════════════════════════

@csrf_exempt
@require_http_methods(['GET'])
@admin_required
def get_user(request, user_id):
    """
    GET /api/users/<user_id>/
    Headers: Authorization: Bearer <admin_token>
    """
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
    """
    PATCH /api/users/<user_id>/status/
    Headers: Authorization: Bearer <admin_token>
    Body: { "is_active": true | false }

    When admin sets active=true:
      - Sets admin_override_active=True
      - Sets admin_override_at=now  (fresh 30-day window starts)
    When admin sets active=false:
      - Sets is_active=False and clears override
    """
    try:
        user = User.objects.get(id=user_id)
    except User.DoesNotExist:
        return json_error('User not found', 404)

    data = parse_json_body(request)
    if 'is_active' not in data:
        return json_error('is_active field is required (true/false)')

    new_status = bool(data['is_active'])

    if new_status:
        # Admin activates → fresh 30-day window
        user.is_active = True
        user.admin_override_active = True
        user.admin_override_at = timezone.now()
    else:
        # Admin deactivates
        user.is_active = False
        user.admin_override_active = False
        user.admin_override_at = None

    user.save(update_fields=['is_active', 'admin_override_active', 'admin_override_at'])

    action = 'activated' if new_status else 'deactivated'
    return json_response({
        'success': True,
        'message': f'User {action} successfully',
        'user': user.to_dict()
    })


# ══════════════════════════════════════════════════════════════
#  USER — DELETE  (Admin only)
# ══════════════════════════════════════════════════════════════

@csrf_exempt
@require_http_methods(['DELETE'])
@admin_required
def delete_user(request, user_id):
    """
    DELETE /api/users/<user_id>/
    Headers: Authorization: Bearer <admin_token>
    """
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
    """
    PATCH /api/users/<user_id>/change-password/
    Headers: Authorization: Bearer <admin_token>
    Body: { "new_password": "..." }
    """
    try:
        user = User.objects.get(id=user_id)
    except User.DoesNotExist:
        return json_error('User not found', 404)

    data = parse_json_body(request)
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
    """
    PATCH /api/users/<user_id>/update/
    Headers: Authorization: Bearer <admin_token>
    Body: any of { "place", "branch", "phone_no", "username" }
    """
    try:
        user = User.objects.get(id=user_id)
    except User.DoesNotExist:
        return json_error('User not found', 404)

    data = parse_json_body(request)
    updatable = ['place', 'branch', 'phone_no', 'username']
    changed = []

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
        'user': user.to_dict()
    })


# ══════════════════════════════════════════════════════════════
#  HEALTH CHECK
# ══════════════════════════════════════════════════════════════

@require_http_methods(['GET'])
def health_check(request):
    return json_response({
        'success': True,
        'service': 'Bluelink API',
        'status': 'running'
    })
