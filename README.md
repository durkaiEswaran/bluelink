# Bluelink Backend API

Django REST API for the Bluelink app — custom JWT auth, no Django built-in auth.

---

## Project Structure

```
bluelink/
├── bluelink/
│   ├── settings.py
│   ├── urls.py
│   └── wsgi.py
├── users/
│   ├── models.py          # User + AdminUser tables
│   ├── views.py           # All API endpoints
│   ├── auth_utils.py      # JWT + decorators + password hashing
│   ├── urls.py            # URL routing
│   └── management/
│       └── commands/
│           └── create_admin.py
├── requirements.txt
├── render.yaml            # Render deployment config
├── build.sh               # Render build script
└── manage.py
```

---

## Database Tables

### `bluelink_admin`
| Field       | Type        | Notes              |
|-------------|-------------|--------------------|
| id          | BigInt (PK) |                    |
| username    | CharField   | unique             |
| password    | CharField   | SHA-256 hashed     |
| last_login  | DateTime    | nullable           |

### `bluelink_users`
| Field                | Type        | Notes                              |
|----------------------|-------------|------------------------------------|
| id                   | BigInt (PK) |                                    |
| username             | CharField   | unique, required                   |
| password             | CharField   | SHA-256 hashed, required           |
| place                | CharField   | required                           |
| branch               | CharField   | optional                           |
| phone_no             | CharField   | required                           |
| is_active            | Boolean     | default True                       |
| created_at           | DateTime    | auto set on create                 |
| admin_override_active| Boolean     | whether admin gave a fresh window  |
| admin_override_at    | DateTime    | when admin last activated          |

---

## Auto-Inactive Logic

- **30 days after `created_at`** → user becomes inactive automatically
- **Admin sets active = true** → fresh 30-day window starts from that moment
- **30 days after admin override** → inactive again
- This is computed in `User.effective_is_active` (no cron needed)

---

## Local Setup

```bash
# 1. Install dependencies
pip install -r requirements.txt

# 2. Run migrations
python manage.py migrate

# 3. Create admin account
python manage.py create_admin --username admin --password yourpassword

# 4. Start server
python manage.py runserver
```

---

## API Endpoints

Base URL: `https://your-app.onrender.com/api`

### Authentication
All endpoints (except login) require:
```
Authorization: Bearer <token>
```

---

### 1. Admin Login
**POST** `/api/admin/login/`

**Body:**
```json
{ "username": "admin", "password": "yourpassword" }
```

**Response:**
```json
{
  "success": true,
  "token": "<admin_jwt_token>",
  "admin": { "id": 1, "username": "admin", "last_login": "..." }
}
```

---

### 2. Create User *(Admin only)*
**POST** `/api/users/create/`

**Headers:** `Authorization: Bearer <admin_token>`

**Body:**
```json
{
  "username": "john",
  "password": "pass1234",
  "place": "Chennai",
  "branch": "South",       // optional
  "phone_no": "9876543210"
}
```

**Response:** `201 Created`
```json
{ "success": true, "user": { ... } }
```

---

### 3. User Login
**POST** `/api/users/login/`

**Body:**
```json
{ "username": "john", "password": "pass1234" }
```

**Response:**
```json
{ "success": true, "token": "<user_jwt_token>", "user": { ... } }
```
> Returns 403 if user is inactive.

---

### 4. List All Users *(Admin only)*
**GET** `/api/users/`

Optional filter: `?active=true` or `?active=false`

---

### 5. Get Single User *(Admin only)*
**GET** `/api/users/<id>/`

---

### 6. Activate / Deactivate User *(Admin only)*
**PATCH** `/api/users/<id>/status/`

**Body:**
```json
{ "is_active": true }    // or false
```

> Setting `true` starts a fresh 30-day active window.

---

### 7. Delete User *(Admin only)*
**DELETE** `/api/users/<id>/delete/`

---

### 8. Change User Password *(Admin only)*
**PATCH** `/api/users/<id>/change-password/`

**Body:**
```json
{ "new_password": "newpass123" }
```

---

### 9. Update User Info *(Admin only)*
**PATCH** `/api/users/<id>/update/`

**Body (any fields):**
```json
{ "place": "Mumbai", "branch": "North", "phone_no": "9999999999" }
```

---

### 10. Health Check
**GET** `/api/health/`

---

## Deploy on Render

1. Push code to GitHub
2. Go to [render.com](https://render.com) → New → **Blueprint**
3. Connect your repo — Render reads `render.yaml` automatically
4. Set env vars in Render dashboard:
   - `ADMIN_USERNAME` — your admin username
   - `ADMIN_PASSWORD` — strong password
5. Deploy — Render runs `build.sh` then starts gunicorn

### Environment Variables

| Variable       | Description                     | Default          |
|----------------|---------------------------------|------------------|
| SECRET_KEY     | Django secret key               | auto-generated   |
| JWT_SECRET     | JWT signing secret              | auto-generated   |
| DEBUG          | Debug mode                      | False            |
| DB_NAME        | PostgreSQL database name        | bluelink_users   |
| DB_USER        | Database user                   | from Render DB   |
| DB_PASSWORD    | Database password               | from Render DB   |
| DB_HOST        | Database host                   | from Render DB   |
| DB_PORT        | Database port                   | from Render DB   |
| ADMIN_USERNAME | First admin username            | admin            |
| ADMIN_PASSWORD | First admin password            | change_this!     |

---

## Notes

- **No Django admin panel** — pure API
- **No sessions/cookies** — stateless JWT auth
- **Inactive check** is computed at request time via `effective_is_active` — no cron needed
- Passwords are hashed with SHA-256 + salt
- Tokens expire after 24 hours
