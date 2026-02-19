import os
import logging
from datetime import datetime, timezone
from typing import Optional
from pathlib import Path

from dotenv import load_dotenv
from pymongo import MongoClient, ASCENDING
from pymongo.errors import ConnectionFailure

_root = Path(__file__).resolve().parent.parent.parent
load_dotenv(_root / ".env")

logger  = logging.getLogger(__name__)
DB_NAME = "opencivil"

class Database:
    _client: Optional[MongoClient] = None
    _db = None

    @classmethod
    def connect(cls):
        if cls._client is not None:
            return
        uri = os.getenv("MONGO_URI", "")
        if not uri:
            raise ConnectionFailure("MONGO_URI not found — check your .env file location.")
        try:
            cls._client = MongoClient(uri, serverSelectionTimeoutMS=5000)
            cls._client.admin.command('ping')
            cls._db = cls._client[DB_NAME]
            cls._ensure_indexes()
            logger.info("MongoDB connected: %s", DB_NAME)
        except ConnectionFailure as exc:
            cls._client = None
            logger.error("MongoDB connection failed: %s", exc)
            raise

    @classmethod
    def _ensure_indexes(cls):
        cls._db["users"].create_index([("email", ASCENDING)], unique=True)

    @classmethod
    def users(cls):
        if cls._db is None:
            cls.connect()
        return cls._db["users"]

def create_user(name, email, password_hash, provider="email"):
    now = datetime.now(timezone.utc)
    doc = {
        "name":          name,
        "email":         email.lower().strip(),
        "password_hash": password_hash,
        "provider":      provider,
        "verified":      False,
        "verify_code":   None,
        "reset_code":    None,
        "reset_expires": None,
        "created_at":    now,
        "last_login":    None,
    }
    Database.users().insert_one(doc)
    return doc

def get_user_by_email(email):
    return Database.users().find_one({"email": email.lower().strip()})

def set_verify_code(email, code):
    Database.users().update_one(
        {"email": email.lower().strip()},
        {"$set": {"verify_code": code}}
    )

def verify_user(email, code):
    result = Database.users().update_one(
        {"email": email.lower().strip(), "verify_code": code},
        {"$set": {"verified": True, "verify_code": None}}
    )
    return result.modified_count > 0

def set_reset_code(email, code, expires):
    Database.users().update_one(
        {"email": email.lower().strip()},
        {"$set": {"reset_code": code, "reset_expires": expires}}
    )

def reset_password(email, code, new_hash):
    now = datetime.now(timezone.utc)
    result = Database.users().update_one(
        {"email":         email.lower().strip(),
         "reset_code":    code,
         "reset_expires": {"$gt": now}},
        {"$set": {"password_hash": new_hash,
                  "reset_code":    None,
                  "reset_expires": None}}
    )
    return result.modified_count > 0

def update_last_login(email):
    Database.users().update_one(
        {"email": email.lower().strip()},
        {"$set": {"last_login": datetime.now(timezone.utc)}}
    )
