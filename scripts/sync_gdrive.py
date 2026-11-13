import os
import re
import json
import io
from datetime import datetime
from google.oauth2 import service_account
from googleapiclient.discovery import build
from googleapiclient.http import MediaIoBaseDownload

REPO_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
REPORTS_DIR = os.path.join(REPO_ROOT, 'reports')
FOLDER_NAME = os.environ.get('GDRIVE_FOLDER_NAME', 'Dashboard_Incoming')
SA_KEY_JSON = os.environ.get('GDRIVE_SA_KEY')

SCOPES = ['https://www.googleapis.com/auth/drive']

def parse_target_filename(drive_name):
    """
    drive_name examples:
    - raw_dashboard_2026-W46_20261113.html -> 2026-W46.html
    - 2026-W46.html -> 2026-W46.html
    - dashboard_w46.html -> 2026-W46.html
    """
    m = re.search(r'(\d{4})-W(\d{1,2})', drive_name, re.IGNORECASE)
    if m:
        year = m.group(1)
        week = f"W{int(m.group(2)):02d}"
        return year, f"{year}-{week}.html"
    
    m_w = re.search(r'W(\d{1,2})', drive_name, re.IGNORECASE)
    year = str(datetime.now().year)
    if m_w:
        week = f"W{int(m_w.group(1)):02d}"
        return year, f"{year}-{week}.html"

    # Fallback to current year & iso week
    now = datetime.now()
    iso_year, iso_week, _ = now.isocalendar()
    return str(iso_year), f"{iso_year}-W{iso_week:02d}.html"

def main():
    if not SA_KEY_JSON:
        print("Notice: GDRIVE_SA_KEY environment variable is not set. Skipping Drive sync.")
        return

    try:
        sa_info = json.loads(SA_KEY_JSON)
        creds = service_account.Credentials.from_service_account_info(sa_info, scopes=SCOPES)
        service = build('drive', 'v3', credentials=creds)
    except Exception as e:
        print(f"Error initializing Google Drive client: {e}")
        return

    # 1. Find folder ID
    q_folder = f"name = '{FOLDER_NAME}' and mimeType = 'application/vnd.google-apps.folder' and trashed = false"
    res = service.files().list(q=q_folder, fields="files(id, name)").execute()
    folders = res.get('files', [])
    if not folders:
        print(f"Folder '{FOLDER_NAME}' not found or not shared with Service Account.")
        return

    folder_id = folders[0]['id']
    print(f"Target Google Drive Folder Found: {FOLDER_NAME} (ID: {folder_id})")

    # 2. List HTML files in folder
    q_files = f"'{folder_id}' in parents and trashed = false"
    res_files = service.files().list(q=q_files, fields="files(id, name, mimeType, modifiedTime)").execute()
    files = res_files.get('files', [])
    print(f"Found {len(files)} items in {FOLDER_NAME}")

    downloaded_count = 0
    for f in files:
        name = f['name']
        file_id = f['id']
        mime = f.get('mimeType', '')

        # Process html or text or doc exported to html
        if not (name.endswith('.html') or name.endswith('.htm') or 'html' in mime or 'text' in mime):
            print(f"Skipping non-html file: {name}")
            continue

        year, dest_filename = parse_target_filename(name)
        year_dir = os.path.join(REPORTS_DIR, year)
        os.makedirs(year_dir, exist_ok=True)
        dest_path = os.path.join(year_dir, dest_filename)

        print(f"Downloading '{name}' -> '{dest_path}'...")
        request = service.files().get_media(fileId=file_id)
        fh = io.BytesIO()
        downloader = MediaIoBaseDownload(fh, request)
        done = False
        while not done:
            status, done = downloader.next_chunk()

        with open(dest_path, 'wb') as out_f:
            out_f.write(fh.getvalue())
        
        downloaded_count += 1
        print(f"Saved: {dest_path}")

    print(f"Sync complete. Total downloaded: {downloaded_count}")

if __name__ == '__main__':
    main()
