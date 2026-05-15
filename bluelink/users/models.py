from django.db import models
from django.utils import timezone
from datetime import timedelta


class AdminUser(models.Model):
    """Separate admin table with limited fields"""
    username = models.CharField(max_length=150, unique=True)
    password = models.CharField(max_length=255)  # stored as hashed
    last_login = models.DateTimeField(null=True, blank=True)

    class Meta:
        db_table = 'bluelink_admin'

    def __str__(self):
        return self.username


class User(models.Model):
    """Main user table"""
    username = models.CharField(max_length=150, unique=True)
    password = models.CharField(max_length=255)  # stored as hashed
    place = models.CharField(max_length=255)
    branch = models.CharField(max_length=255, blank=True, null=True)
    phone_no = models.CharField(max_length=20)
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    admin_override_active = models.BooleanField(default=False)
    admin_override_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        db_table = 'bluelink_users'

    def __str__(self):
        return self.username

    @property
    def effective_is_active(self):
        """
        Logic:
        - After 30 days from created_at -> inactive (base rule)
        - If admin overrides to active -> active, but only until 30 days from override
        - After that 30-day window from override -> inactive again
        """
        now = timezone.now()
        days_since_created = (now - self.created_at).days

        if self.admin_override_active and self.admin_override_at:
            days_since_override = (now - self.admin_override_at).days
            if days_since_override < 30:
                return True  # admin gave a fresh 30-day window
            else:
                return False  # override window expired
        else:
            if days_since_created >= 30:
                return False  # original 30-day rule
            return self.is_active

    def to_dict(self):
        return {
            'id': self.id,
            'username': self.username,
            'place': self.place,
            'branch': self.branch,
            'phone_no': self.phone_no,
            'is_active': self.effective_is_active,
            'created_at': self.created_at.isoformat(),
            'admin_override_active': self.admin_override_active,
            'admin_override_at': self.admin_override_at.isoformat() if self.admin_override_at else None,
        }
