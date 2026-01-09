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
    chrome_options.add_argument("--window-size=1920,1080")
    chrome_options.add_argument("user-agent=Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36")
    
    print("🚀 크롬 브라우저 실행 중...")
    driver = webdriver.Chrome(service=Service(ChromeDriverManager().install()), options=chrome_options)
    
    try:
        print(f"📡 접속 중: {TARGET_URL}")
        driver.get(TARGET_URL)
        
        # 1. 페이지 로딩 대기
        try:
            print("⏳ 'schedule-this-yearlist' 박스 대기 중...")
            WebDriverWait(driver, 20).until(
                EC.presence_of_element_located((By.CLASS_NAME, "schedule-this-yearlist"))
            )
            print("✨ 박스 발견!")
        except:
            print("⚠️ 박스 발견 실패 (시간 초과). 스크롤 후 진행합니다.")

        time.sleep(5) # 넉넉하게 5초 대기
        driver.execute_script("window.scrollTo(0, document.body.scrollHeight);")
        time.sleep(2)

        # 2. 소스 가져오기
        html_source = driver.page_source
        soup = BeautifulSoup(html_source, 'html.parser')
        
        # 불필요 태그 제거
        for script in soup(["script", "style"]):
            script.decompose()

        all_lines = soup.get_text(separator="\n", strip=True).splitlines()
        print(f"🔍 읽어온 텍스트 라인 수: {len(all_lines)}줄")
        
        # ▼▼▼ [디버깅 핵심] 읽은 내용을 전부 출력합니다 ▼▼▼
        print("="*50)
        print("📜 봇이 읽은 텍스트 내용 전체 출력 시작")
        print("="*50)
        for i, line in enumerate(all_lines):
            # 내용이 너무 많으면 로그가 잘릴 수 있으므로, 공백이 아닌 줄만 출력
            if line.strip():
                print(f"[Line {i+1}] {line.strip()}")
        print("="*50)
        print("📜 출력 종료")
        print("="*50)
        # ▲▲▲▲▲▲▲▲▲▲▲▲▲▲▲▲▲▲▲▲▲▲▲▲▲▲▲▲▲▲▲▲▲▲▲▲▲
        
        events = []
        now = datetime.now()
        current_year = now.year 
        found_count = 0
        
        for line in all_lines:
            line = line.strip()
            if not line: continue
            
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
                            events.append({"title": title_part, "start": s_date, "end": e_date})
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
