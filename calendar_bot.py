import os
import time
from datetime import datetime
import re
import pytz
from bs4 import BeautifulSoup
import requests

# ▼ 셀레니움 라이브러리 ▼
from selenium import webdriver
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.chrome.service import Service
from webdriver_manager.chrome import ChromeDriverManager
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC

# ▼ 설정 ▼
TARGET_URL = "https://www.kw.ac.kr/ko/life/bachelor_calendar.jsp"
TOKEN = os.environ.get('TELEGRAM_TOKEN')
CHAT_ID = os.environ.get('TELEGRAM_CHAT_ID')

def parse_date_str(date_text, current_year):
    """ 날짜 문자열(02.02 ~ 02.04)을 파싱하여 시작일, 종료일 반환 """
    # 정규식으로 숫자.숫자 패턴만 모두 추출
    dates = re.findall(r'(\d{2}\.\d{2})', date_text)
    
    if not dates:
        return None, None
        
    try:
        start_dt = datetime.strptime(f"{current_year}.{dates[0]}", "%Y.%m.%d").date()
        if len(dates) >= 2:
            end_dt = datetime.strptime(f"{current_year}.{dates[1]}", "%Y.%m.%d").date()
        else:
            end_dt = start_dt
        return start_dt, end_dt
    except ValueError:
        return None, None

def get_calendar_with_selenium():
    chrome_options = Options()
    chrome_options.add_argument("--headless") 
    chrome_options.add_argument("--no-sandbox")
    chrome_options.add_argument("--disable-dev-shm-usage")
    chrome_options.add_argument("--window-size=1920,1080")
    chrome_options.add_argument("user-agent=Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36")
    
    print("🚀 크롬 브라우저 실행 중...")
    driver = webdriver.Chrome(service=Service(ChromeDriverManager().install()), options=chrome_options)
    
    try:
        print(f"📡 접속 중: {TARGET_URL}")
        driver.get(TARGET_URL)
        
        # 1. 로딩 대기
        try:
            WebDriverWait(driver, 20).until(
                EC.presence_of_element_located((By.CSS_SELECTOR, ".schedule-this-yearlist li"))
            )
            print("✨ 데이터 로딩 완료!")
        except:
            print("⚠️ 로딩 시간 초과! (스크롤 후 계속 시도)")

        time.sleep(3)
        driver.execute_script("window.scrollTo(0, document.body.scrollHeight);")
        time.sleep(1)

        html_source = driver.page_source
        soup = BeautifulSoup(html_source, 'html.parser')
        
        # 2. 텍스트 라인 추출 (빈 줄 제거)
        # separator="\n"을 주어 태그가 달라도 줄바꿈이 되도록 함
        all_lines = [line.strip() for line in soup.get_text(separator="\n", strip=True).splitlines() if line.strip()]
        
        print(f"🔍 읽어온 텍스트 라인 수: {len(all_lines)}줄")
        
        events = []
        now = datetime.now()
        current_year = now.year 

        # ▼▼▼ [핵심 로직] 순차적 스캔 (State Machine) ▼▼▼
        pending_date_range = None # 날짜를 기억할 변수
        
        count = 0
        for line in all_lines:
            # 1. 이 줄이 '날짜'인지 확인 (예: 02.02(월) ...)
            # 정규식: 시작(^)이 숫자.숫자 인 경우
            is_date_line = re.match(r'^\d{2}\.\d{2}', line)
            
            if is_date_line:
                # 날짜 줄을 발견하면 파싱해서 '기억'해둡니다.
                s_date, e_date = parse_date_str(line, current_year)
                if s_date and e_date:
                    pending_date_range = (s_date, e_date)
                    # (아직 제목을 못 찾았으니 저장하지 않고 넘어감)
            
            elif pending_date_range:
                # 2. 날짜가 아닌데, '기억된 날짜'가 있다? -> 이게 바로 '제목'이다!
                title = line
                s_date, e_date = pending_date_range
                
                # 제목이 너무 짧거나(단순 기호), 또 다른 날짜 패턴이면 무시
                if len(title) < 2 or re.match(r'^\d{2}\.\d{2}', title):
                    continue

                # 저장
                # 중복 방지
                is_duplicate = False
                for e in events:
                    if e['title'] == title and e['start'] == s_date:
                        is_duplicate = True
                        break
                
                if not is_duplicate:
                    events.append({
                        "title": title,
                        "start": s_date,
                        "end": e_date
                    })
                    count += 1
                
                # 사용했으니 기억 초기화 (다음 날짜를 기다림)
                pending_date_range = None
        
        print(f"✅ 최종 추출된 일정: {count}개")
        events.sort(key=lambda x: x['start'])
        return events

    except Exception as e:
        print(f"❌ 브라우저 에러: {e}")
        return []
    finally:
        driver.quit()

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
        print("📭 전송할 내용이 없습니다.")
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
