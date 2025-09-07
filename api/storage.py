import os
import json

DATA_DIR = "data"
os.makedirs(DATA_DIR, exist_ok=True)

def paste_path(paste_id):
    return os.path.join(DATA_DIR, f"{paste_id}.json")

def save_paste(paste_id, content, password_hash=None):
    with open(paste_path(paste_id), "w") as f:
        json.dump({
            "content": content,
            "password_hash": password_hash
        }, f)

def get_paste(paste_id):
    try:
        with open(paste_path(paste_id), "r") as f:
            return json.load(f)
    except FileNotFoundError:
        return None
