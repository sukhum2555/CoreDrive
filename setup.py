#!/usr/bin/env python
"""
NAS Drive - Setup Script
Run once on first install or when moving to a new machine.
"""
import os, sys, subprocess
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent
os.chdir(BASE_DIR)
os.environ['DJANGO_SETTINGS_MODULE'] = 'NAS.settings'
os.environ['PYTHONIOENCODING'] = 'utf-8'

def ok(msg):    print(f'  [OK] {msg}')
def info(msg):  print(f'  [..] {msg}')
def fail(msg):  print(f'  [!!] {msg}')
def header(msg):
    print()
    print('=' * 50)
    print(f'  {msg}')
    print('=' * 50)

def run(cmd, desc=''):
    if desc:
        info(desc)
    result = subprocess.run(cmd, shell=True)
    if result.returncode != 0:
        fail(f'Command failed: {cmd}')
        sys.exit(1)

# STEP 1
header('STEP 1/5 - Installing dependencies')
run('pip install -r requirements.txt', 'Installing packages...')
ok('Dependencies installed')

# STEP 2
header('STEP 2/5 - Creating folders')
for folder in ['storage', 'media', 'logs']:
    p = BASE_DIR / folder
    p.mkdir(parents=True, exist_ok=True)
    ok(f'{folder}/')

# STEP 3
header('STEP 3/5 - Setting up database')
run('python manage.py makemigrations app', 'Creating migrations...')
run('python manage.py migrate', 'Running migrations...')
ok('Database ready')

# STEP 4
header('STEP 4/5 - Collecting static files')
run('python manage.py collectstatic --noinput', 'Collecting...')
ok('Static files ready')

# STEP 5
header('STEP 5/5 - Creating admin user')
import django
django.setup()
from django.contrib.auth.models import User

if not User.objects.filter(username='admin').exists():
    User.objects.create_superuser('admin', 'admin@nas.local', 'admin1234')
    ok('Admin user created')
    print('       Username : admin')
    print('       Password : admin1234')
    print('       *** Please change password after login ***')
else:
    info('Admin already exists, skipping')

print()
print('=' * 50)
print('  Setup complete!')
print()
print('  Start server : double-click run_server.bat')
print('  URL          : http://127.0.0.1:8000')
print('  Login        : admin / admin1234')
print('=' * 50)
print()
