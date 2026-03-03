"""Google Drive backup adapter — uploads encrypted SQLite backups to Drive."""

import logging
import os
import shutil
import subprocess
import tempfile
from datetime import date

log = logging.getLogger(__name__)


class GoogleDriveBackup:
    """Upload encrypted SQLite backups to Google Drive."""

    name = "google_drive"
    source = "google_drive"

    def __init__(self):
        self._service = None
        self._key_path = os.environ.get("GOOGLE_SA_KEY_PATH", "")
        self._folder_id = os.environ.get("BACKUP_FOLDER_ID", "")
        self._age_public_key = os.environ.get("BACKUP_PUBLIC_KEY", "")

    async def init(self) -> None:
        """Initialize the Drive API service."""
        from google.oauth2.service_account import Credentials
        from googleapiclient.discovery import build

        scopes = ["https://www.googleapis.com/auth/drive.file"]
        creds = Credentials.from_service_account_file(self._key_path, scopes=scopes)
        self._service = build("drive", "v3", credentials=creds)
        log.info("Google Drive backup adapter initialized")

    async def ping(self) -> bool:
        """Check if the Drive API is reachable."""
        if not self._service:
            return False
        try:
            self._service.files().list(
                q=f"'{self._folder_id}' in parents",
                pageSize=1, fields="files(id)"
            ).execute()
            return True
        except Exception as e:
            log.warning(f"Drive ping failed: {e}")
            return False

    async def poll(self) -> list:
        """Drive adapter does not poll."""
        return []

    async def upload_backup(self, db_path: str = "/opt/pib/data/pib.db") -> dict:
        """Create an encrypted backup and upload to Google Drive.

        Steps:
        1. Copy the SQLite database (safe with WAL mode)
        2. Encrypt with age if BACKUP_PUBLIC_KEY is set
        3. Upload to Google Drive folder

        Returns:
            Dict with upload result
        """
        if not self._service:
            return {"ok": False, "error": "Drive service not initialized"}

        if not os.path.exists(db_path):
            return {"ok": False, "error": f"Database not found: {db_path}"}

        today = date.today().isoformat()
        tmp_dir = tempfile.mkdtemp(prefix="pib_backup_")

        try:
            # Step 1: Copy the database
            backup_name = f"pib-{today}.db"
            backup_path = os.path.join(tmp_dir, backup_name)
            shutil.copy2(db_path, backup_path)

            # Also copy WAL and SHM if they exist
            for ext in ["-wal", "-shm"]:
                wal_path = db_path + ext
                if os.path.exists(wal_path):
                    shutil.copy2(wal_path, backup_path + ext)

            upload_path = backup_path
            upload_name = backup_name

            # Step 2: Encrypt with age if key is available
            if self._age_public_key:
                encrypted_path = backup_path + ".age"
                try:
                    subprocess.run(
                        ["age", "-r", self._age_public_key, "-o", encrypted_path, backup_path],
                        check=True, capture_output=True, text=True,
                    )
                    upload_path = encrypted_path
                    upload_name = backup_name + ".age"
                    log.info("Backup encrypted with age")
                except FileNotFoundError:
                    log.warning("age binary not found — uploading unencrypted")
                except subprocess.CalledProcessError as e:
                    log.warning(f"age encryption failed: {e.stderr} — uploading unencrypted")

            # Step 3: Upload to Google Drive
            from googleapiclient.http import MediaFileUpload

            file_metadata = {
                "name": upload_name,
                "parents": [self._folder_id],
            }
            media = MediaFileUpload(upload_path, resumable=True)

            file = self._service.files().create(
                body=file_metadata, media_body=media, fields="id,name,size"
            ).execute()

            log.info(f"Backup uploaded to Drive: {file.get('name')} ({file.get('size')} bytes)")
            return {
                "ok": True,
                "file_id": file.get("id"),
                "name": file.get("name"),
                "size": file.get("size"),
                "encrypted": bool(self._age_public_key and upload_name.endswith(".age")),
            }

        except Exception as e:
            log.error(f"Drive backup upload failed: {e}", exc_info=True)
            return {"ok": False, "error": str(e)}

        finally:
            # Clean up temp directory
            shutil.rmtree(tmp_dir, ignore_errors=True)

    async def send(self, message) -> None:
        """Drive adapter does not send messages."""
        raise NotImplementedError("Google Drive does not send messages")
