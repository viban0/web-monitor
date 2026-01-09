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
        response.encoding = 'utf-8' 
        soup = BeautifulSoup(response.text, 'html.parser')
        
        events = []
        now = datetime.now()
        current_year = now.year 

        print(f"📡 페이지 접속 상태: {response.status_code}")
        
        # ▼ [핵심 수정] 구체적인 이름 대신, 공통된 이름 'schedule-list-box'를 가진 모든 박스를 찾습니다.
        # (월별 보기 박스, 연간 보기 박스 등이 다 잡힙니다)
        all_boxes = soup.select("div.schedule-list-box")
        
        print(f"🔍 발견된 스케줄 박스 개수: {len(all_boxes)}개")
        
        found_count = 0
        
        # 발견된 모든 박스를 하나씩 뜯어봅니다.
        for i, box in enumerate(all_boxes):
            list_items = box.select("li")
            print(f"  ▶ [Box {i+1}] 내부 리스트 아이템 수: {len(list_items)}개")
            
            for item in list_items:
                # 텍스트 전체 가져오기
                full_text = item.get_text(" ", strip=True)
                
                # 디버깅용: 텍스트가 어떻게 생겼는지 확인
                # print(f"    - 읽은 텍스트: {full_text}")
                
                # 날짜 패턴 찾기 (숫자.숫자 형태)
                # 정규식을 좀 더 유연하게 (괄호나 띄어쓰기 변수 고려)
                match = re.search(r'(\d{2}\.\d{2})', full_text)
                
                if match:
                    # 정확한 날짜 구간 추출을 위해 다시 정규식 적용
                    # 예: 02.02(월) ~ 02.27(금)
                    full_date_match = re.search(r'(\d{2}\.\d{2}\([가-힣]\)(?:\s*~\s*\d{2}\.\d{2}\([가-힣]\))?)', full_text)
                    
                    if full_date_match:
                        date_part = full_date_match.group(1)
                        title_part = full_text.replace(date_part, "").strip()
                        
                        # 제목이 너무 짧으면 패스
                        if len(title_part) < 2: continue

                        try:
                            s_date, e_date = parse_date(date_part, current_year)
                            events.append({
                                "title": title_part,
                                "start": s_date,
                                "end": e_date
                            })
                            found_count += 1
                        except Exception:
                            continue

        print(f"✅ 최종 추출된 학사일정: {found_count}개")
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
