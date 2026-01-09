import os
import requests
from datetime import datetime, timedelta, date
import pytz

# ▼ 설정 ▼
ICS_FILE = "calendar.ics"  # 업로드한 달력 파일 이름
TOKEN = os.environ.get('TELEGRAM_TOKEN')
CHAT_ID = os.environ.get('TELEGRAM_CHAT_ID')

def parse_date(date_str):
    """ICS 날짜 형식(YYYYMMDD)을 파이썬 날짜로 변환"""
    return datetime.strptime(date_str, "%Y%m%d").date()

def get_events():
    """ICS 파일을 직접 읽어서 일정 파싱"""
    events = []
    
    with open(ICS_FILE, 'r', encoding='utf-8') as f:
        lines = f.readlines()
        
    current_event = {}
    for line in lines:
        line = line.strip()
        
        if line.startswith("BEGIN:VEVENT"):
            current_event = {}
        elif line.startswith("DTSTART;VALUE=DATE:"):
            current_event['start'] = parse_date(line.split(":")[1])
        elif line.startswith("DTEND;VALUE=DATE:"):
            # 종료일은 보통 하루 뒤로 표기되므로 하루를 뺌 (당일치기는 시작=종료-1)
            end_date = parse_date(line.split(":")[1])
            current_event['end'] = end_date - timedelta(days=1)
        elif line.startswith("SUMMARY:"):
            current_event['title'] = line.split(":", 1)[1]
        elif line.startswith("END:VEVENT"):
            if 'start' in current_event and 'title' in current_event:
                # 종료일이 없으면 시작일과 같게 설정
                if 'end' not in current_event:
                    current_event['end'] = current_event['start']
                events.append(current_event)
                
    # 날짜순 정렬
    events.sort(key=lambda x: x['start'])
    return events

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
    # 한국 시간 기준 오늘 날짜 구하기
    kst = pytz.timezone('Asia/Seoul')
    today = datetime.now(kst).date()
    
    print(f"📅 기준 날짜: {today}")
    
    events = get_events()
    
    # 1. 오늘 일정 찾기
    today_events = []
    # 2. 다가오는 일정 찾기 (오늘 이후)
    upcoming_events = []
    
    for event in events:
        # 오늘 일정: 시작일 <= 오늘 <= 종료일
        if event['start'] <= today <= event['end']:
            today_events.append(event['title'])
        
        # 다가오는 일정: 시작일 > 오늘 (최대 3개만)
        if event['start'] > today:
            d_day = (event['start'] - today).days
            # 너무 먼 미래(60일 이후)는 패스
            if d_day <= 60:
                upcoming_events.append({
                    "title": event['title'],
                    "d_day": d_day,
                    "date": event['start'].strftime("%m/%d")
                })

    # 보낼 내용이 없으면 종료
    if not today_events and not upcoming_events:
        print("보낼 일정이 없습니다.")
        return

    # 메시지 작성
    msg_lines = []
    
    # 헤더
    msg_lines.append(f"📆 *광운대 학사일정 브리핑* ({today.strftime('%m/%d')})")
    msg_lines.append("────────────────")
    
    # 오늘 일정 출력
    if today_events:
        msg_lines.append("🔔 *오늘의 일정*")
        for title in today_events:
            msg_lines.append(f"• {title}")
        msg_lines.append("") # 빈 줄
    
    # 다가오는 일정 출력 (상위 3개)
    if upcoming_events:
        msg_lines.append("⏳ *다가오는 일정*")
        for item in upcoming_events[:3]: # 3개만 자르기
            msg_lines.append(f"• D-{item['d_day']} {item['title']} ({item['date']})")

    final_msg = "\n".join(msg_lines)
    print(final_msg)
    
    # 텔레그램 전송
    send_telegram(final_msg)

if __name__ == "__main__":
    run()
