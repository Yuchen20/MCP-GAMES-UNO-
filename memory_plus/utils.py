import os
import time
import uuid
from pathlib import Path
from dotenv import load_dotenv

load_dotenv()

def get_app_dir():
    """Get the application directory path"""
    app_dir = Path(os.path.expanduser("~")) / ".brain_in_a_vat"
    app_dir.mkdir(parents=True, exist_ok=True)
    return app_dir

def get_user_uuid():
    uuid_path = get_app_dir() / "user_uuid.txt"
    if uuid_path.exists():
        return uuid_path.read_text().strip()
    user_id = str(uuid.uuid4())
    uuid_path.write_text(user_id)
    return user_id

def get_whether_to_annonimize():
    uuid_path = get_app_dir() / "whether_to_annonimize.txt"
    if uuid_path.exists():
        return uuid_path.read_text().strip()
    return "False" 