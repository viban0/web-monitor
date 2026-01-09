import os
import requests
from bs4 import BeautifulSoup
from datetime import datetime
import re
import pytz
import urllib3

# SSL 인증서 경고 무시
urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

# ▼ 설정 ▼
TARGET_URL = "https://www.kw.ac.kr/ko/life/bachelor_calendar.jsp"
TOKEN = os.environ.get('TELEGRAM_TOKEN')
CHAT_ID = os.environ.get('TELEGRAM_CHAT_ID')

def parse_date(date_str, current_year):
    """
    날짜 문자열을 파싱해서 시작일과 종료일을 반환합니다.
    예: '02.02(월) ~ 02.27(금)' 또는 '02.20(금)'
    """
    # 괄호와 요일 제거
    clean_str = re.sub(r'\([가-힣]\)', '', date_str)
    
    if "~" in clean_str:
        start_str, end_str = clean_str.split("~")
    else:
        start_str = clean_str
        end_str = clean_str
        
    start_str = start_str.strip()
    end_str = end_str.strip()
    
    start_date = datetime.strptime(f"{current_year}.{start_str}", "%Y.%m.%d").date()
    end_date = datetime.strptime(f"{current_year}.{end_str}", "%Y.%m.%d").date()
    
    return start_date, end_date

def get_calendar_events():
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) Chrome/91.0.4472.124 Safari/537.36"
    }
    
    try:
        response = requests.get(TARGET_URL, headers=headers, verify=False, timeout=30)
        soup = BeautifulSoup(response.text, 'html.parser')
        
        events = []
        now = datetime.now()
        current_year = now.year 

        # 광운대 학사일정 구조 파싱 (연도별 텍스트 박스 형태)
        content_div = soup.select_one("div.bachelor_sch")
        if not content_div:
            return []

        # 전체 텍스트에서 한 줄씩 읽으며 날짜 패턴 찾기
        text_lines = content_div.get_text("\n").split("\n")
        
        for line in text_lines:
            line = line.strip()
            if not line: continue
            
            # 정규식으로 '00.00(요일)' 패턴 찾기
            match = re.search(r'(\d{2}\.\d{2}\([가-힣]\)(?:\s*~\s*\d{2}\.\d{2}\([가-힣]\))?)', line)
            
            if match:
                date_part = match.group(1)
                title_part = line.replace(date_part, "").strip()
                
                if len(title_part) < 2: continue # 내용이 없으면 패스
                    
                try:
                    s_date, e_date = parse_date(date_part, current_year)
                    events.append({
                        "title": title_part,
                        "start": s_date,
                        "end": e_date
                    })
                except:
                    continue

        events.sort(key=lambda x: x['start'])
        return events

    except Exception as e:
        print(f"크롤링 에러: {e}")
        return []

def send_telegram(msg):
    if TOKEN and CHAT_ID:
        url = f"https://api.telegram.org/bot{TOKEN}/sendMessage"
        payload = {
            "chat_id": CHAT_ID,
            "text": msg,
            "parse_mode": "Markdown"
        }
        requests.post(url, data=payload)

def run():
    kst = pytz.timezone('Asia/Seoul')
    today = datetime.now(kst).date()
    
    print(f"📅 기준 날짜: {today}")
    
    events = get_calendar_events()
    
    if not events:
        print("일정을 가져오지 못했습니다.")
        return

    today_events = []
    upcoming_events = []
    
    for event in events:
        # 오늘 일정
        if event['start'] <= today <= event['end']:
            today_events.append(event['title'])
        
        # 다가오는 일정 (오늘 이후 시작하는 것만)
        if event['start'] > today:
            d_day = (event['start'] - today).days
            # 60일 이내 일정만
            if d_day <= 60:
                upcoming_events.append({
                    "title": event['title'],
                    "d_day": d_day,
                    "date": event['start'].strftime("%m/%d")
                })

    if not today_events and not upcoming_events:
        return

    msg_lines = []
    
    # 1. 헤더 (구분선 X)
    msg_lines.append(f"📆 *광운대 학사일정* ({today.strftime('%m/%d')})")
    
    # 2. 오늘 일정
    if today_events:
        msg_lines.append("\n🔔 *오늘의 일정*")
        for title in today_events:
            msg_lines.append(f"• {title}")
    
    # 3. 다가오는 일정 (최대 2개만)
    if upcoming_events:
        msg_lines.append("\n⏳ *다가오는 일정*")
        for item in upcoming_events[:2]: 
            msg_lines.append(f"• D-{item['d_day']} {item['title']} ({item['date']})")

    final_msg = "\n".join(msg_lines)
    print(final_msg)
    
    send_telegram(final_msg)

if __name__ == "__main__":
    run()
