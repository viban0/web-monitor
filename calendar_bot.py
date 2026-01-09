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
    날짜 문자열 파싱 (예: 02.02(월) ~ 02.27(금))
    """
    clean_str = re.sub(r'\([가-힣]\)', '', date_str) # 요일 제거
    
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
        response.encoding = 'utf-8' 
        soup = BeautifulSoup(response.text, 'html.parser')
        
        events = []
        now = datetime.now()
        current_year = now.year 

        print(f"📡 페이지 접속 상태: {response.status_code}")
        
        # ▼ [수정] 사용자님이 지정한 정확한 클래스 이름으로 타겟팅
        # class="schedule-list-box schedule-this-yearlist"
        target_box = soup.select_one("div.schedule-list-box.schedule-this-yearlist")
        
        if not target_box:
            print("⚠️ 'schedule-this-yearlist' 박스를 찾지 못했습니다. (클래스명 변경 가능성)")
            # 혹시 몰라 비상용으로 조금 더 넓은 범위인 schedule-list-box 시도
            target_box = soup.select_one("div.schedule-list-box")

        if not target_box:
            print("❌ 학사일정 박스 자체를 찾을 수 없습니다.")
            return []

        # 타겟 박스 안의 모든 li 태그만 가져오기 (메뉴바 제외됨)
        list_items = target_box.select("li")
        print(f"🔍 학사일정 박스 안의 항목 수: {len(list_items)}개")
        
        count = 0
        for item in list_items:
            # 박스 안의 텍스트를 가져옴
            full_text = item.get_text(" ", strip=True)
            
            # strong 태그(보통 날짜)가 있는지 확인하거나, 정규식으로 날짜 패턴 검색
            # 패턴: 숫자.숫자(요일)
            match = re.search(r'(\d{2}\.\d{2}\([가-힣]\)(?:\s*~\s*\d{2}\.\d{2}\([가-힣]\))?)', full_text)
            
            if match:
                date_part = match.group(1)
                title_part = full_text.replace(date_part, "").strip()
                
                if len(title_part) < 2: continue

                try:
                    s_date, e_date = parse_date(date_part, current_year)
                    events.append({
                        "title": title_part,
                        "start": s_date,
                        "end": e_date
                    })
                    count += 1
                except Exception:
                    continue
        
        print(f"✅ 추출된 학사일정: {count}개")
        events.sort(key=lambda x: x['start'])
        return events

    except Exception as e:
        print(f"❌ 오류 발생: {e}")
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
        print("❌ 일정을 가져오지 못했습니다.")
        return

    today_events = []
    upcoming_events = []
    
    for event in events:
        if event['start'] <= today <= event['end']:
            today_events.append(event['title'])
        
        if event['start'] > today:
            d_day = (event['start'] - today).days
            if d_day <= 60:
                upcoming_events.append({
                    "title": event['title'],
                    "d_day": d_day,
                    "date": event['start'].strftime("%m/%d")
                })

    if not today_events and not upcoming_events:
        print("📭 전송할 내용이 없습니다 (날짜 조건 불일치).")
        return

    msg_lines = []
    msg_lines.append(f"📆 *광운대 학사일정* ({today.strftime('%m/%d')})")
    
    if today_events:
        msg_lines.append("\n🔔 *오늘의 일정*")
        for title in today_events:
            msg_lines.append(f"• {title}")
    
    if upcoming_events:
        msg_lines.append("\n⏳ *다가오는 일정*")
        for item in upcoming_events[:2]: 
            msg_lines.append(f"• D-{item['d_day']} {item['title']} ({item['date']})")

    final_msg = "\n".join(msg_lines)
    print("메시지 미리보기:")
    print(final_msg)
    
    send_telegram(final_msg)

if __name__ == "__main__":
    run()
