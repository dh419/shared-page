import os
import json
from datetime import datetime, timezone, timedelta
from google.oauth2 import service_account
from googleapiclient.discovery import build
from googleapiclient.http import MediaIoBaseDownload
import io

REPO_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DOCS_DIR = os.path.join(REPO_ROOT, 'docs')
TEMPLATES_DIR = os.path.join(REPO_ROOT, 'templates')
MASTER_HTML_PATH = os.path.join(TEMPLATES_DIR, 'master_dashboard.html')
FOLDER_ID = '1jQIwN8b4SG536ClUWPAg3qUjo4GTNrJz'
KST = timezone(timedelta(hours=9))


def get_target_weekend_dates(now_kst):
    days_until_sat = (5 - now_kst.weekday()) % 7
    if days_until_sat == 0 and now_kst.weekday() != 5:
        days_until_sat = 7
    sat = now_kst + timedelta(days=days_until_sat)
    sun = sat + timedelta(days=1)
    return f"{sat.strftime('%m.%d')}~{sun.strftime('%m.%d')}"


def main():
    sa_json = os.environ.get('GDRIVE_SA_KEY')
    if not sa_json:
        raise ValueError("GDRIVE_SA_KEY environment variable is missing.")

    creds = service_account.Credentials.from_service_account_info(
        json.loads(sa_json),
        scopes=['https://www.googleapis.com/auth/drive.readonly'],
    )
    service = build('drive', 'v3', credentials=creds)

    res = service.files().list(
        q=f"'{FOLDER_ID}' in parents and name contains '-weekend.json' and trashed = false",
        orderBy='modifiedTime desc',
        pageSize=5,
        fields='files(id, name, modifiedTime)',
    ).execute()
    files = res.get('files', [])
    if not files:
        raise FileNotFoundError("No *-weekend.json found in dashboard_incoming.")

    target = files[0]
    print(f"Fetching {target['name']} (ID: {target['id']})...")
    buf = io.BytesIO()
    downloader = MediaIoBaseDownload(buf, service.files().get_media(fileId=target['id']))
    done = False
    while not done:
        _, done = downloader.next_chunk()

    data = json.loads(buf.getvalue().decode('utf-8'))
    now_kst = datetime.now(KST)
    date_part = target['name'].replace('-weekend.json', '')
    month_part = date_part[:7]

    girl_age = now_kst.year - 2020 + 1
    boy_age = now_kst.year - 2024 + 1
    weekend_label = get_target_weekend_dates(now_kst)

    with open(MASTER_HTML_PATH, 'r', encoding='utf-8') as f:
        tpl = f.read()

    html = tpl.replace('{{WEEKEND_LABEL}}', weekend_label)
    html = html.replace('{{GIRL_AGE}}', str(girl_age))
    html = html.replace('{{BOY_AGE}}', str(boy_age))
    html = html.replace('{{WEATHER_PILLS_HTML}}', data['weatherPillsHtml'])
    html = html.replace('{{SPOTS_JSON}}', json.dumps(data['spots'], ensure_ascii=False))

    out_dir = os.path.join(DOCS_DIR, month_part)
    os.makedirs(out_dir, exist_ok=True)
    out_file = os.path.join(out_dir, f"{date_part}.html")
    with open(out_file, 'w', encoding='utf-8') as f:
        f.write(html)
    print(f"Generated: {out_file}")


if __name__ == '__main__':
    main()
