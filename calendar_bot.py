import os
import time
from datetime import datetime, timedelta
import re
import pytz
from bs4 import BeautifulSoup
import requests

# ▼ 셀레니움 필수 라이브러리 ▼
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

def parse_date(date_str, current_year):
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
    chrome_options = Options()
    chrome_options.add_argument("--headless") 
    chrome_options.add_argument("--no-sandbox")
    chrome_options.add_argument("--disable-dev-shm-usage")
    # PC 화면 크기로 위장 (중요)
    chrome_options.add_argument("--window-size=1920,1080")
    chrome_options.add_argument("user-agent=Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36")
    
    print("🚀 크롬 브라우저 실행 중...")
    driver = webdriver.Chrome(service=Service(ChromeDriverManager().install()), options=chrome_options)
    
    try:
        print(f"📡 접속 중: {TARGET_URL}")
        driver.get(TARGET_URL)
        
        # ✅ [핵심 수정] 박스 자체가 아니라, 박스 안의 '내용물(li 태그)'이 생길 때까지 기다림
        # 이전에는 'schedule-this-yearlist'만 기다려서 빈 박스만 보고 통과했던 것임
        try:
            print("⏳ 데이터 로딩 대기 중 (최대 20초)...")
            WebDriverWait(driver, 20).until(
                EC.presence_of_element_located((By.CSS_SELECTOR, ".schedule-this-yearlist li"))
            )
            print("✨ 연간 리스트 데이터(알맹이) 로딩 완료!")
        except:
            print("⚠️ 데이터 로딩 시간 초과! (하지만 스크롤 후 다시 시도해봅니다)")

        # 안전 장치: 강제 스크롤 + 3초 대기
        driver.execute_script("window.scrollTo(0, document.body.scrollHeight);")
        time.sleep(3)

        # 페이지 소스 가져오기
        html_source = driver.page_source
        soup = BeautifulSoup(html_source, 'html.parser')
        
        # 텍스트 추출
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
            
            # 정규식 패턴 확인 (숫자.숫자)
            match = re.search(r'(\d{2}\.\d{2})', line)
            if match:
                date_match = re.search(r'(\d{2}\.\d{2}\([가-힣]\)(?:\s*~\s*\d{2}\.\d{2}\([가-힣]\))?)', line)
                if date_match:
                    date_part = date_match.group(1)
                    title_part = line.replace(date_part, "").strip()
                    
                    if len(title_part) < 2: continue

                    try:
                        s_date, e_date = parse_date(date_part, current_year)
                        
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
                        
        print(f"✅ 최종 추출된 일정: {found_count}개")
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
