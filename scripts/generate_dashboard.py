import os
import re
import json
import time
from datetime import datetime, timedelta
from google import genai
from google.genai import types

REPO_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DOCS_DIR = os.path.join(REPO_ROOT, 'docs')
TEMPLATES_DIR = os.path.join(REPO_ROOT, 'templates')
MASTER_HTML_PATH = os.path.join(TEMPLATES_DIR, 'master_dashboard.html')

GEMINI_API_KEY = os.environ.get('GEMINI_API_KEY')
GEMINI_MODEL = os.environ.get('GEMINI_MODEL', 'gemini-2.5-flash')
THINKING_BUDGET = int(os.environ.get('THINKING_BUDGET', '0'))

def get_target_weekend_dates():
    now = datetime.now()
    days_until_sat = (5 - now.weekday()) % 7
    if days_until_sat == 0 and now.weekday() != 5:
        days_until_sat = 7
    sat = now + timedelta(days=days_until_sat)
    sun = sat + timedelta(days=1)
    
    label = f"{sat.strftime('%m.%d')}~{sun.strftime('%m.%d')}"
    return sat, sun, label

def calculate_ages(year):
    girl_age = year - 2020 + 1
    boy_age = year - 2024 + 1
    return girl_age, boy_age

def generate_dashboard():
    if not GEMINI_API_KEY:
        raise ValueError("GEMINI_API_KEY environment variable is missing.")

    client = genai.Client(api_key=GEMINI_API_KEY)
    
    sat, sun, weekend_label = get_target_weekend_dates()
    today_str = datetime.now().strftime('%Y-%m-%d')
    current_year = datetime.now().year
    current_month_str = datetime.now().strftime('%Y-%m')
    girl_age, boy_age = calculate_ages(current_year)

    prompt = f"""
당신은 동탄(동탄반석로 71) 거주 가족을 위한 전문 주말 나들이 큐레이터입니다.
이번 주말({weekend_label}) 은우(딸, {girl_age}세)와 우준이(아들, {boy_age}세)를 위한 맞춤 나들이 가이드 데이터를 생성해야 합니다.

실시간 구글 검색을 활용하여 다음 정보를 수집하고 정형 JSON 형식으로만 응답하세요:

1. 이번 주말({weekend_label}) 동탄 및 경기 인근의 실시간 날씨, 기온, 미세먼지 예보
2. 동탄반석로 71 출발 기준 자차 15~50분 이내 (화성, 용인, 수원, 오산, 안성, 이천, 과천 등) 장소 6곳:
   - 상시 나들이 3곳 (유모차 가능 평지/데크길, 잔디밭, 놀이터, 수유실/기저귀교환대 필수)
   - 기간 한정 축제·전시 3곳 (이번 주말 실제 운영 중인 가을/겨울 축제 및 특별전)
   - 각 장소별 은우({girl_age}세) 맞춤 활동, 우준({boy_age}세) 맞춤 놀이, 유모차/편의시설 팁
   - 각 장소 인근 맵지 않고 순한 국수 맛집(바지락칼국수, 잔치국수, 사골칼국수, 우동 등) 매칭 (아기의자, 주차 팁 포함)

반드시 아래 JSON 스키마 규격으로만 출력하세요 (마크다운 코드블록 없이 순수 JSON만 반환):
{{
  "weatherPillsHtml": "<span class=\\"weather-pill\\">토(MM.DD) 날씨요약 기온</span><span class=\\"weather-pill\\">일(MM.DD) 날씨요약 기온</span><span class=\\"weather-pill\\">미세먼지 상태</span>",
  "spots": [
    {{
      "type": "outing 또는 festival",
      "day": "sat 또는 sun",
      "driveMin": 25,
      "badgeType": "🌳 나들이 1 (또는 🎉 축제 1)",
      "badgeDay": "☀️ 토요일 추천 (또는 🌧️ 일요일 우천·실내)",
      "title": "장소명",
      "drive": "🚗 자차 약 OO분 (지역명)",
      "summary": "1~2줄 핵심 요약",
      "girl": "은우 맞춤 포인트",
      "boy": "우준 맞춤 포인트",
      "tip": "유모차 동선, 수유실, 주차 팁",
      "noodleTag": "🍜 국수집 이름",
      "noodleName": "🍜 연계 국수집: 식당명 (차로 O분)",
      "noodleDesc": "순한 메뉴 및 아기의자/주차 팁",
      "placeQuery": "네이버 지도 검색어",
      "foodQuery": "네이버 지도 검색어",
      "siteUrl": "공식 누리집 URL 또는 네이버 지도 URL"
    }}
  ]
}}
"""

    # Candidate models to try in case of quota / availability
    candidate_models = [GEMINI_MODEL, 'gemini-2.5-flash', 'gemini-1.5-flash', 'gemini-2.0-flash']
    # Deduplicate preserving order
    seen = set()
    models_to_try = [m for m in candidate_models if not (m in seen or seen.add(m))]

    response = None
    last_err = None

    for model_name in models_to_try:
        try:
            print(f"Trying Gemini model '{model_name}' (thinking_budget={THINKING_BUDGET})...")
            config_args = {
                'tools': [types.Tool(google_search=types.GoogleSearch())],
                'temperature': 0.3,
            }
            if THINKING_BUDGET > 0:
                config_args['thinking_config'] = types.ThinkingConfig(thinking_budget=THINKING_BUDGET)

            response = client.models.generate_content(
                model=model_name,
                contents=prompt,
                config=types.GenerateContentConfig(**config_args),
            )
            print(f"Success with model: {model_name}")
            break
        except Exception as e:
            print(f"Model '{model_name}' attempt failed: {e}")
            last_err = e
            time.sleep(2)

    if not response:
        raise RuntimeError(f"All model attempts failed. Last error: {last_err}")

    raw_text = response.text.strip()
    raw_text = re.sub(r'^```(?:json)?\s*', '', raw_text)
    raw_text = re.sub(r'\s*```$', '', raw_text)
    
    data = json.loads(raw_text)
    weather_pills_html = data['weatherPillsHtml']
    spots_json_str = json.dumps(data['spots'], ensure_ascii=False)

    with open(MASTER_HTML_PATH, 'r', encoding='utf-8') as f:
        template = f.read()

    html = template.replace('{{WEEKEND_LABEL}}', weekend_label)
    html = html.replace('{{GIRL_AGE}}', str(girl_age))
    html = html.replace('{{BOY_AGE}}', str(boy_age))
    html = html.replace('{{WEATHER_PILLS_HTML}}', weather_pills_html)
    html = html.replace('{{SPOTS_JSON}}', spots_json_str)

    month_dir = os.path.join(DOCS_DIR, current_month_str)
    os.makedirs(month_dir, exist_ok=True)
    out_file = os.path.join(month_dir, f"{today_str}.html")

    with open(out_file, 'w', encoding='utf-8') as f:
        f.write(html)

    print(f"Successfully generated and saved dashboard: {out_file}")

if __name__ == '__main__':
    generate_dashboard()
