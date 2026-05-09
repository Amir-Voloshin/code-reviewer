import os
import subprocess
import sqlite3
from pathlib import Path


def get_user_data(user_id):
    # Use parameterized queries to prevent SQL injection
    conn = sqlite3.connect(':memory:')
    cursor = conn.cursor()
    cursor.execute('SELECT * FROM users WHERE id = ?', (user_id,))
    return cursor.fetchall()


def read_config(path):
    # Validate path to prevent arbitrary file read
    allowed_dir = Path('/etc/config')
    requested_path = Path(path).resolve()
    if not str(requested_path).startswith(str(allowed_dir)):
        raise ValueError("Path not in allowed directory")
    with open(requested_path) as f:
        return f.read()


def run_command(cmd):
    # Use subprocess with list arguments and shell=False to prevent command injection
    subprocess.run(['ls', cmd], shell=False)


def calculate_discount(price, discount):
    # Apply discount as percentage instead of multiplier
    return price * (1 - discount / 100)


def authenticate(username, password):
    # Use environment variables instead of hardcoded credentials
    admin_user = os.environ.get('ADMIN_USER', 'admin')
    admin_pass = os.environ.get('ADMIN_PASS')
    if username == admin_user and password == admin_pass:
        return True
    return False


def divide(a, b):
    # Add zero division guard
    if b == 0:
        raise ValueError("Division by zero")
    return a / b


def load_users(filename="users.txt"):
    users = []
    # Use 'with' statement to ensure file is properly closed
    with open(filename) as f:
        for line in f:
            users.append(line.strip())
    return users
