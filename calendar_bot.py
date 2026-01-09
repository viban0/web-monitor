import os
import time
from datetime import datetime, timedelta
import re
import pytz
from bs4 import BeautifulSoup
import requests

# ▼ 셀레니움 관련 기능 불러오기 ▼
from selenium import webdriver
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.chrome.service import Service
from webdriver_manager.chrome import ChromeDriverManager
from selenium.webdriver.common.by import By

# ▼ 설정 ▼
TARGET_URL = "https://www.kw.ac.kr/ko/life/bachelor_calendar.jsp"
TOKEN = os.environ.get('TELEGRAM_TOKEN')
CHAT_ID = os.environ.get('TELEGRAM_CHAT_ID')

def parse_date(date_str, current_year):
    # 괄호/요일 제거 및 공백 정리
    clean_str = re.sub(r'\([가-힣]\)', '', date_str).strip()
    
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

def get_calendar_with_selenium():
    # 1. 가짜 브라우저(Headless Chrome) 설정
    chrome_options = Options()
    chrome_options.add_argument("--headless")  # 화면 없이 실행 (서버용)
    chrome_options.add_argument("--no-sandbox")
    chrome_options.add_argument("--disable-dev-shm-usage")
    
    # 2. 브라우저 실행
    print("🚀 크롬 브라우저를 실행합니다...")
    driver = webdriver.Chrome(service=Service(ChromeDriverManager().install()), options=chrome_options)
    
    try:
        # 3. 페이지 접속
        print(f"📡 접속 중: {TARGET_URL}")
        driver.get(TARGET_URL)
        
        # 4. 자바스크립트 로딩 대기 (3초)
        # 사이트가 느리면 숫자를 늘려야 함 (최대 10초 추천)
        time.sleep(3)
        
        # 5. 로딩된 페이지의 '소스 코드'를 가져옴 (이제 내용은 채워져 있음!)
        html_source = driver.page_source
        soup = BeautifulSoup(html_source, 'html.parser')
        
        # --- 여기서부터는 아까 했던 '무조건 탐색' 로직과 동일 ---
        
        # 스크립트 제거
        for script in soup(["script", "style"]):
            script.decompose()

        all_lines = soup.get_text(separator="\n", strip=True).splitlines()
        print(f"🔍 읽어온 텍스트 라인 수: {len(all_lines)}줄")
        
        events = []
        now = datetime.now()
        current_year = now.year 
        found_count = 0
        
        for line in all_lines:
            line = line.strip()
            if not line: continue
            
            # 날짜 패턴 찾기 (숫자.숫자)
            match = re.search(r'(\d{2}\.\d{2})', line)
            if match:
                # 정밀 패턴 확인 (요일 포함)
                date_match = re.search(r'(\d{2}\.\d{2}\([가-힣]\)(?:\s*~\s*\d{2}\.\d{2}\([가-힣]\))?)', line)
                if date_match:
                    date_part = date_match.group(1)
                    title_part = line.replace(date_part, "").strip()
                    
                    if len(title_part) < 2: continue

                    try:
                        s_date, e_date = parse_date(date_part, current_year)
                        
                        # 중복 제거
                        is_duplicate = False
                        for e in events:
                            if e['title'] == title_part and e['start'] == s_date:
                                is_duplicate = True
                                break
                        
                        if not is_duplicate:
                            events.append({
                                "title": title_part,
                                "start": s_date,
                                "end": e_date
                            })
                            found_count += 1
                    except Exception:
                        continue
                        
        print(f"✅ 셀레니움으로 찾은 일정: {found_count}개")
        events.sort(key=lambda x: x['start'])
        return events

    except Exception as e:
        print(f"❌ 브라우저 에러: {e}")
        return []
    finally:
        # 6. 브라우저 종료 (중요)
        driver.quit()
        print("👋 브라우저 종료")

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
    
    # 함수 이름 변경됨: get_calendar_events -> get_calendar_with_selenium
    events = get_calendar_with_selenium()
    
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
