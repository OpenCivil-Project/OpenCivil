import logging
from PyQt6.QtCore import QThread, pyqtSignal

from google_auth_oauthlib.flow import InstalledAppFlow
import requests

from .config import GoogleAuthConfig

logger = logging.getLogger(__name__)

class GoogleAuthThread(QThread):
    """
    Runs the Google OAuth2 browser flow in a background thread
    so the UI stays responsive.
    """

    auth_complete = pyqtSignal(dict)                                    
    auth_failed   = pyqtSignal(str)                                    
    auth_progress = pyqtSignal(str)                                           

    def run(self):
        try:
            if not GoogleAuthConfig.validate():
                self.auth_failed.emit(
                    "Missing Google OAuth configuration. "
                    "Please check your environment variables."
                )
                return

            self.auth_progress.emit("Preparing authentication…")

            flow = InstalledAppFlow.from_client_config(
                GoogleAuthConfig.as_client_config(),
                GoogleAuthConfig.SCOPES,
            )

            self.auth_progress.emit("Opening browser — please sign in…")

            try:
                credentials = flow.run_local_server(
                    port=0,
                    prompt='consent',
                    authorization_prompt_message='',
                    success_message='All done! You can close this tab.',
                    open_browser=True,
                )
            except Exception as oauth_err:
                                                                         
                if "Scope has changed" in str(oauth_err):
                    credentials = getattr(flow, 'credentials', None)
                    if not credentials:
                        self.auth_failed.emit(
                            "OAuth scope mismatch. "
                            "Please check your Google Cloud Console settings."
                        )
                        return
                else:
                    raise

            self.auth_progress.emit("Fetching your profile…")

            headers  = {'Authorization': f'Bearer {credentials.token}'}
            response = requests.get(
                GoogleAuthConfig.USER_INFO_URL,
                headers=headers,
                timeout=10,
            )
            response.raise_for_status()
            user_info = response.json()

            if 'email' not in user_info:
                raise ValueError("Google did not return an email address.")

            user_info['credentials'] = credentials
            self.auth_complete.emit(user_info)

        except requests.RequestException as exc:
            logger.error("Network error during auth: %s", exc)
            self.auth_failed.emit(f"Network error: {exc}")
        except ValueError as exc:
            logger.error("Value error during auth: %s", exc)
            self.auth_failed.emit(str(exc))
        except Exception as exc:
            logger.exception("Unexpected auth error")
            self.auth_failed.emit(f"Authentication failed: {exc}")
