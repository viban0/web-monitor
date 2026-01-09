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
    '02.20(금)' 또는 '02.02(월) ~ 02.27(금)' 형태를 파싱
    """
    # 괄호와 요일 제거 -> '02.20' 또는 '02.02 ~ 02.27'
    clean_str = re.sub(r'\([가-힣]\)', '', date_str)
    
    if "~" in clean_str:
        start_str, end_str = clean_str.split("~")
    else:
        start_str = clean_str
        end_str = clean_str
        
    start_str = start_str.strip()
    end_str = end_str.strip()
    
    # 연도 붙여서 날짜 객체로 변환
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

        # ▼ 수정된 부분: 스크린샷의 HTML 구조 반영 (div.schedule-list-box > ul > li)
        # 개발자 도구 사진에 나온 class="schedule-list-box" 안의 ul li를 찾습니다.
        list_items = soup.select("div.schedule-list-box ul li")
        
        if not list_items:
            # 혹시 div.list가 중간에 껴있을 경우 대비 (스크린샷 구조: div.list > ul > li)
            list_items = soup.select("div.list ul li")

        for item in list_items:
            # strong 태그: 날짜 (예: 02.20(금))
            date_tag = item.select_one("strong")
            # p 태그: 행사명 (예: 신입생 수강신청)
            title_tag = item.select_one("p")
            
            if not date_tag or not title_tag:
                continue
                
            date_text = date_tag.get_text(strip=True)
            title_text = title_tag.get_text(strip=True)
            
            # 내용이 없으면 패스
            if not date_text or not title_text:
                continue

            try:
                s_date, e_date = parse_date(date_text, current_year)
                events.append({
                    "title": title_text,
                    "start": s_date,
                    "end": e_date
                })
            except Exception as e:
                # 날짜 형식이 특이한 경우(예: '미정') 건너뜀
                continue

        # 날짜순 정렬
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
        # 1. 오늘 일정 (시작일 <= 오늘 <= 종료일)
        if event['start'] <= today <= event['end']:
            today_events.append(event['title'])
        
        # 2. 다가오는 일정 (오늘 < 시작일)
        if event['start'] > today:
            d_day = (event['start'] - today).days
            # 60일 이내 일정만 표시
            if d_day <= 60:
                upcoming_events.append({
                    "title": event['title'],
                    "d_day": d_day,
                    "date": event['start'].strftime("%m/%d")
                })

    # 보낼 내용이 아예 없으면 조용히 종료
    if not today_events and not upcoming_events:
        print("전송할 알림이 없습니다.")
        return

    msg_lines = []
    
    # 헤더
    msg_lines.append(f"📆 *광운대 학사일정* ({today.strftime('%m/%d')})")
    
    # 오늘 일정 출력
    if today_events:
        msg_lines.append("\n🔔 *오늘의 일정*")
        for title in today_events:
            msg_lines.append(f"• {title}")
    
    # 다가오는 일정 출력 (최대 2개)
    if upcoming_events:
        msg_lines.append("\n⏳ *다가오는 일정*")
        for item in upcoming_events[:2]: 
            msg_lines.append(f"• D-{item['d_day']} {item['title']} ({item['date']})")

    final_msg = "\n".join(msg_lines)
    print(final_msg)
    
    send_telegram(final_msg)

if __name__ == "__main__":
    run()
