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
    # 괄호 및 불필요한 공백 제거
    clean_str = re.sub(r'\([가-힣]\)', '', date_str).strip()
    
    if "~" in clean_str:
        start_str, end_str = clean_str.split("~")
    else:
        start_str = clean_str
        end_str = clean_str
        
    start_str = start_str.strip()
    end_str = end_str.strip()
    
    try:
        start_date = datetime.strptime(f"{current_year}.{start_str}", "%Y.%m.%d").date()
        end_date = datetime.strptime(f"{current_year}.{end_str}", "%Y.%m.%d").date()
        return start_date, end_date
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
        
        # 1. '연간 리스트(li)'가 로딩될 때까지 대기
        try:
            print("⏳ 데이터 로딩 대기 중...")
            WebDriverWait(driver, 20).until(
                # schedule-this-yearlist 안의 li 태그가 생길 때까지 기다림
                EC.presence_of_element_located((By.CSS_SELECTOR, ".schedule-this-yearlist li"))
            )
            print("✨ 데이터 로딩 완료!")
        except:
            print("⚠️ 대기 시간 초과! (스크롤 후 계속 진행)")

        # 2. 확실한 로딩을 위해 스크롤 및 대기
        driver.execute_script("window.scrollTo(0, document.body.scrollHeight);")
        time.sleep(3)

        # 3. HTML 파싱 시작
        html_source = driver.page_source
        soup = BeautifulSoup(html_source, 'html.parser')
        
        events = []
        now = datetime.now()
        current_year = now.year 
        
        # ▼▼▼ [핵심 변경] 텍스트가 아닌 '구조(li)'를 찾습니다 ▼▼▼
        # 우리가 찾는 그 리스트 박스
        target_box = soup.select_one(".schedule-this-yearlist")
        
        if not target_box:
            # 혹시 클래스명이 다를 경우를 대비해 schedule-list-box 전체에서 찾기
            list_items = soup.select(".schedule-list-box li")
        else:
            list_items = target_box.select("li")
            
        print(f"🔍 발견된 일정 항목(li) 개수: {len(list_items)}개")

        count = 0
        for item in list_items:
            # 하나의 li 안에 날짜와 제목이 다 들어있습니다.
            # 예: <li> <strong>날짜</strong> <p>제목</p> </li>
            
            # 텍스트 추출 (태그 무시하고 공백으로 연결)
            full_text = item.get_text(" ", strip=True)
            
            # 날짜 패턴 찾기 (숫자.숫자)
            # 예: 02.02(월) ~ 02.27(금)
            date_match = re.search(r'(\d{2}\.\d{2}\([가-힣]\)(?:\s*~\s*\d{2}\.\d{2}\([가-힣]\))?)', full_text)
            
            if date_match:
                date_part = date_match.group(1)
                # 전체 텍스트에서 날짜 부분을 지우면 나머지가 제목!
                title_part = full_text.replace(date_part, "").strip()
                
                if len(title_part) < 2: continue

                s_date, e_date = parse_date(date_part, current_year)
                
                if s_date and e_date:
                    # 중복 방지
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
                        count += 1
                        
        print(f"✅ 최종 추출된 일정: {count}개")
        events.sort(key=lambda x: x['start'])
        return events

    except Exception as e:
        print(f"❌ 오류 발생: {e}")
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
