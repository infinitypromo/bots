import json
from replit import db
from typing import Any, Optional, Union

def get(key: str) -> Optional[str]:
    """Get a string value from Replit DB."""
    return db.get(key)

def set(key: str, value: str) -> None:
    """Set a string value in Replit DB."""
    db[key] = value

def delete(key: str) -> None:
    """Delete a key from Replit DB."""
    if key in db:
        del db[key]

def get_json(key: str) -> Optional[Any]:
    """Get a JSON-serializable value from Replit DB.
    Returns None if key does not exist or value is not valid JSON.
    """
    raw = db.get(key)
    if raw is None:
        return None
    try:
        return json.loads(raw)
    except (json.JSONDecodeError, TypeError):
        return None

def set_json(key: str, value: Any) -> None:
    """Set a JSON-serializable value in Replit DB."""
    db[key] = json.dumps(value)