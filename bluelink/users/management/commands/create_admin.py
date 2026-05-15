from django.core.management.base import BaseCommand
from users.models import AdminUser
from users.auth_utils import hash_password


class Command(BaseCommand):
    help = 'Create the first admin account for Bluelink'

    def add_arguments(self, parser):
        parser.add_argument('--username', type=str, default='admin')
        parser.add_argument('--password', type=str, default='admin1234')

    def handle(self, *args, **options):
        username = options['username']
        password = options['password']

        if AdminUser.objects.filter(username=username).exists():
            self.stdout.write(self.style.WARNING(f'Admin "{username}" already exists.'))
            return

        AdminUser.objects.create(
            username=username,
            password=hash_password(password)
        )
        self.stdout.write(self.style.SUCCESS(
            f'✓ Admin "{username}" created successfully!'
        ))
        self.stdout.write(self.style.WARNING(
            '  Remember to change the default password in production!'
        ))
