#!/usr/bin/env bash
set -o errexit

pip install --upgrade pip
pip install -r requirements.txt
python manage.py migrate contenttypes
python manage.py migrate users
python manage.py migrate
python manage.py collectstatic --no-input
python manage.py create_admin \
  --username "${ADMIN_USERNAME:-Trainee103@378}" \
  --password "${ADMIN_PASSWORD:-123Asd!@#}"
