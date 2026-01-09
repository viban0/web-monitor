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
    """ '02.02(월) ~ 02.27(금)' 텍스트에서 날짜 추출 """
    # 숫자.숫자 패턴 찾기 (02.02)
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
    # PC 화면 크기 설정 (중요)
    chrome_options.add_argument("--window-size=1920,1080")
    chrome_options.add_argument("user-agent=Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36")
    
    print("🚀 크롬 브라우저 실행 중...")
    driver = webdriver.Chrome(service=Service(ChromeDriverManager().install()), options=chrome_options)
    
    try:
        print(f"📡 접속 중: {TARGET_URL}")
        driver.get(TARGET_URL)
        
        # 1. 데이터가 로딩될 때까지 확실하게 대기
        # 'li' 태그 안에 'strong'이 있는 요소가 나타날 때까지 기다림
        try:
            WebDriverWait(driver, 20).until(
                EC.presence_of_element_located((By.CSS_SELECTOR, "li strong"))
            )
            print("✨ 데이터 로딩 감지됨!")
        except:
            print("⚠️ 로딩 대기 시간 초과 (스크롤 후 탐색 시도)")

        time.sleep(3)
        driver.execute_script("window.scrollTo(0, document.body.scrollHeight);")
        time.sleep(1)

        html_source = driver.page_source
        soup = BeautifulSoup(html_source, 'html.parser')
        
        events = []
        now = datetime.now()
        current_year = now.year 

        # ▼▼▼ [핵심 전략] 모든 리스트(li)를 다 뒤져서 '구조'가 맞는 것만 골라냄 ▼▼▼
        # 특정 클래스(schedule-this-yearlist)를 찾지 않고, 페이지 내 모든 li를 검사합니다.
        all_list_items = soup.find_all("li")
        print(f"🔍 페이지 내 전체 리스트(li) 개수: {len(all_list_items)}개")
        
        found_count = 0
        for item in all_list_items:
            # 1. <strong> 태그(날짜)가 있는가?
            date_tag = item.find("strong")
            if not date_tag:
                continue
            
            # 2. <p> 태그(제목)가 있는가?
            title_tag = item.find("p")
            if not title_tag:
                continue
                
            # 3. 텍스트 추출
            date_text = date_tag.get_text(strip=True)
            title_text = title_tag.get_text(strip=True)
            
            # 4. 날짜 형식이 맞는지 검증 (엉뚱한 strong 태그 걸러내기)
            # 예: "02.02(월)" 형식이 포함되어 있어야 함
            if not re.search(r'\d{2}\.\d{2}', date_text):
                continue
                
            # 5. 데이터 파싱
            s_date, e_date = parse_date_str(date_text, current_year)
            
            if s_date and e_date:
                # 중복 방지
                is_duplicate = False
                for e in events:
                    if e['title'] == title_text and e['start'] == s_date:
                        is_duplicate = True
                        break
                
                if not is_duplicate:
                    events.append({
                        "title": title_text,
                        "start": s_date,
                        "end": e_date
                    })
                    found_count += 1

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
