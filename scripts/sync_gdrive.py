import os
import re
import json
import io
from datetime import datetime
from google.oauth2 import service_account
from googleapiclient.discovery import build
from googleapiclient.http import MediaIoBaseDownload

REPO_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DOCS_DIR = os.path.join(REPO_ROOT, 'docs')
FOLDER_NAME = os.environ.get('GDRIVE_FOLDER_NAME', 'Dashboard_Incoming')
SA_KEY_JSON = os.environ.get('GDRIVE_SA_KEY')

SCOPES = ['https://www.googleapis.com/auth/drive']

def parse_target_folder_and_file(drive_name):
    """
    Parses drive_name to (year_month_folder, final_html_filename)
    Examples:
    - raw_dashboard_2026-11-13.html -> ('2026-11', '2026-11-13.html')
    - 2026-11-13.html -> ('2026-11', '2026-11-13.html')
    - raw_dashboard_2026-W46_20261113.html -> ('2026-11', '2026-11-13.html')
    """
    m_date = re.search(r'(\d{4})-(\d{2})-(\d{2})', drive_name)
    if m_date:
        year, month, day = m_date.group(1), m_date.group(2), m_date.group(3)
        return f"{year}-{month}", f"{year}-{month}-{day}.html"

    m_ymd = re.search(r'(\d{4})(\d{2})(\d{2})', drive_name)
    if m_ymd:
        year, month, day = m_ymd.group(1), m_ymd.group(2), m_ymd.group(3)
        return f"{year}-{month}", f"{year}-{month}-{day}.html"

    m_week = re.search(r'(\d{4})-W(\d{1,2})', drive_name, re.IGNORECASE)
    if m_week:
        year = m_week.group(1)
        now = datetime.now()
        month = f"{now.month:02d}"
        return f"{year}-{month}", f"{year}-W{int(m_week.group(2)):02d}.html"

    now = datetime.now()
    ym = now.strftime('%Y-%m')
    ymd = now.strftime('%Y-%m-%d')
    return ym, f"{ymd}.html"

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

    q_folder = f"name = '{FOLDER_NAME}' and mimeType = 'application/vnd.google-apps.folder' and trashed = false"
    res = service.files().list(q=q_folder, fields="files(id, name)").execute()
    folders = res.get('files', [])
    if not folders:
        print(f"Folder '{FOLDER_NAME}' not found or not shared with Service Account.")
        return

    folder_id = folders[0]['id']
    print(f"Target Google Drive Folder Found: {FOLDER_NAME} (ID: {folder_id})")

    q_files = f"'{folder_id}' in parents and trashed = false"
    res_files = service.files().list(q=q_files, fields="files(id, name, mimeType, modifiedTime)").execute()
    files = res_files.get('files', [])
    print(f"Found {len(files)} items in {FOLDER_NAME}")

    downloaded_count = 0
    for f in files:
        name = f['name']
        file_id = f['id']
        mime = f.get('mimeType', '')

        if not (name.endswith('.html') or name.endswith('.htm') or 'html' in mime or 'text' in mime):
            print(f"Skipping non-html file: {name}")
            continue

        ym_folder, dest_filename = parse_target_folder_and_file(name)
        target_dir = os.path.join(DOCS_DIR, ym_folder)
        os.makedirs(target_dir, exist_ok=True)
        dest_path = os.path.join(target_dir, dest_filename)

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

    print(f"Sync complete. Total downloaded to docs/: {downloaded_count}")

if __name__ == '__main__':
    main()
