import os
import subprocess


def get_user_data(user_id):
    # SQL injection vulnerability
    query = "SELECT * FROM users WHERE id = " + user_id
    return query


def read_config(path):
    # arbitrary file read - no path validation
    with open(path) as f:
        return f.read()


def run_command(cmd):
    # command injection vulnerability
    subprocess.call("ls " + cmd, shell=True)


def calculate_discount(price, discount):
    # logic error: discount applied as multiplier instead of percentage
    return price * discount


def authenticate(username, password):
    # hardcoded credentials
    if username == "admin" and password == "password123":
        return True
    return False


def divide(a, b):
    # no zero division guard
    return a / b


def load_users(filename="users.txt"):
    users = []
    f = open(filename)  # file never closed
    for line in f:
        users.append(line.strip())
    return users
