import os
import re
import json
import glob
from datetime import datetime

REPO_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DOCS_DIR = os.path.join(REPO_ROOT, 'docs')
HUB_DATA_PATH = os.path.join(REPO_ROOT, 'hub-data.json')

def extract_meta(html_path):
    filename = os.path.basename(html_path)
    rel_path = os.path.relpath(html_path, REPO_ROOT).replace('\\', '/')
    
    # Example: 2026-10-17.html or 2026-W45.html
    m_date = re.match(r'(\d{4})-(\d{2})-(\d{2})\.html', filename, re.IGNORECASE)
    m_week = re.match(r'(\d{4})-W(\d{1,2})\.html', filename, re.IGNORECASE)
    
    if m_date:
        year, month, day = m_date.group(1), m_date.group(2), m_date.group(3)
        report_id = f"{year}-{month}-{day}"
        week_str = f"{int(month)}월 {((int(day)-1)//7)+1}주"
        date_str = f"{year}-{month}-{day}"
    elif m_week:
        year, week_num = m_week.group(1), int(m_week.group(2))
        report_id = f"{year}-W{week_num:02d}"
        week_str = f"W{week_num:02d}"
        date_str = ""
    else:
        report_id = os.path.splitext(filename)[0]
        year = "2026"
        week_str = report_id
        date_str = ""

    # Parse title from html content
    title = f"{year}년 {week_str} 나들이 대시보드"
    summary = "주말 나들이 & 행사 상세 가이드"

    try:
        with open(html_path, 'r', encoding='utf-8') as f:
            content = f.read(5000)
            title_m = re.search(r'<title>(.*?)</title>', content, re.IGNORECASE | re.DOTALL)
            if title_m and title_m.group(1).strip():
                title = title_m.group(1).strip()
            
            if not date_str:
                d_m = re.search(r'(\d{4}[\.-]\d{2}[\.-]\d{2})', content)
                if d_m:
                    date_str = d_m.group(1).replace('.', '-')
    except Exception as e:
        print(f"Error reading {html_path}: {e}")

    if not date_str:
        mtime = os.path.getmtime(html_path)
        date_str = datetime.fromtimestamp(mtime).strftime('%Y-%m-%d')

    return {
        "id": report_id,
        "year": year,
        "week": week_str,
        "title": title,
        "date": date_str,
        "path": rel_path,
        "summary": summary
    }

def update_hub_index():
    pattern = os.path.join(DOCS_DIR, '**', '*.html')
    files = glob.glob(pattern, recursive=True)
    
    reports = []
    for f in files:
        reports.append(extract_meta(f))

    # Sort descending by date/id
    reports.sort(key=lambda x: (x['date'], x['id']), reverse=True)

    with open(HUB_DATA_PATH, 'w', encoding='utf-8') as f:
        json.dump(reports, f, ensure_ascii=False, indent=2)

    print(f"Successfully indexed {len(reports)} reports from docs/ into hub-data.json")

if __name__ == '__main__':
    update_hub_index()
