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
    """
    태그에서 가져온 날짜 텍스트(예: "02.02(월) ~ 02.27(금)")를 분석합니다.
    구분자(~, -)가 무엇이든 상관없이 숫자 패턴만 추출합니다.
    """
    # 1. 숫자.숫자 패턴을 모두 찾습니다.
    dates = re.findall(r'(\d{2}\.\d{2})', date_text)
    
    if not dates:
        return None, None
        
    try:
        # 첫 번째 날짜 (시작일)
        start_dt = datetime.strptime(f"{current_year}.{dates[0]}", "%Y.%m.%d").date()
        
        # 날짜가 2개 이상이면 두 번째가 종료일, 1개면 시작일=종료일
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
        
        # 1. [중요] 연간 리스트(li)가 로딩될 때까지 대기
        try:
            WebDriverWait(driver, 20).until(
                EC.presence_of_element_located((By.CSS_SELECTOR, ".schedule-this-yearlist li"))
            )
            print("✨ 데이터 로딩 완료!")
        except:
            print("⚠️ 로딩 시간 초과! (스크롤 후 계속 시도)")

        # 2. 안전하게 데이터 확보를 위한 스크롤
        time.sleep(3)
        driver.execute_script("window.scrollTo(0, document.body.scrollHeight);")
        time.sleep(1)

        html_source = driver.page_source
        soup = BeautifulSoup(html_source, 'html.parser')
        
        events = []
        now = datetime.now()
        current_year = now.year 

        # 3. [핵심] 텍스트가 아닌 'HTML 태그 구조'로 찾기
        # 스크린샷에 나온 구조: li -> strong(날짜), p(제목)
        
        # 타겟 박스 찾기
        target_box = soup.select_one(".schedule-this-yearlist")
        if not target_box:
            print("❌ schedule-this-yearlist 박스를 찾지 못했습니다.")
            # 비상용: 이름 상관없이 li 안에 strong, p가 있는 구조 찾기
            list_items = soup.select("li")
        else:
            list_items = target_box.select("li")
            
        print(f"🔍 발견된 항목(li) 개수: {len(list_items)}개")

        found_count = 0
        for item in list_items:
            try:
                # 태그 직접 찾기
                date_tag = item.select_one("strong")
                title_tag = item.select_one("p")
                
                # 둘 중 하나라도 없으면 우리가 찾는 일정이 아님
                if not date_tag or not title_tag:
                    continue
                    
                date_text = date_tag.get_text(strip=True)
                title_text = title_tag.get_text(strip=True)
                
                # 날짜 파싱
                s_date, e_date = parse_date_str(date_text, current_year)
                
                if s_date and e_date:
                    events.append({
                        "title": title_text,
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
