import os
from pathlib import Path
from dotenv import load_dotenv

_here = Path(__file__).resolve()                                 
_root = _here.parent.parent.parent                       

load_dotenv(_root / ".env")

class GoogleAuthConfig:
    """Google OAuth2 configuration for OpenCivil."""

    CLIENT_ID     = os.getenv("OPENCIVIL_GOOGLE_CLIENT_ID", "")
    CLIENT_SECRET = os.getenv("OPENCIVIL_GOOGLE_CLIENT_SECRET", "")

    SCOPES = [
        'https://www.googleapis.com/auth/userinfo.email',
        'https://www.googleapis.com/auth/userinfo.profile',
        'openid'
    ]

    USER_INFO_URL = "https://www.googleapis.com/oauth2/v2/userinfo"

    CREDENTIALS_DIR  = os.path.join(os.path.expanduser("~"), ".opencivil")
    CREDENTIALS_FILE = os.path.join(CREDENTIALS_DIR, "user_credentials.json")

    @classmethod
    def validate(cls) -> bool:
        return bool(cls.CLIENT_ID and cls.CLIENT_SECRET)

    @classmethod
    def as_client_config(cls) -> dict:
        return {
            "installed": {
                "client_id":     cls.CLIENT_ID,
                "client_secret": cls.CLIENT_SECRET,
                "auth_uri":      "https://accounts.google.com/o/oauth2/auth",
                "token_uri":     "https://oauth2.googleapis.com/token",
                "redirect_uris": ["http://localhost"],
            }
        }
