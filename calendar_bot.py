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

def parse_date_str(date_str, current_year):
    """ '02.02(월)' 형태의 문자열을 파이썬 날짜 객체로 변환 """
    clean_str = re.sub(r'\([가-힣]\)', '', date_str).strip() # (월) 제거
    try:
        return datetime.strptime(f"{current_year}.{clean_str}", "%Y.%m.%d").date()
    except ValueError:
        return None

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
            print("✨ 데이터 로딩 감지됨!")
        except:
            print("⚠️ 대기 시간 초과, 스크롤 후 진행")

        time.sleep(3)
        driver.execute_script("window.scrollTo(0, document.body.scrollHeight);")
        time.sleep(1)

        html_source = driver.page_source
        soup = BeautifulSoup(html_source, 'html.parser')
        
        for script in soup(["script", "style"]):
            script.decompose()

        # 텍스트 라인 추출
        all_lines = [line.strip() for line in soup.get_text(separator="\n", strip=True).splitlines() if line.strip()]
        print(f"🔍 읽어온 유효 텍스트 라인 수: {len(all_lines)}줄")
        
        events = []
        now = datetime.now()
        current_year = now.year 
        found_count = 0
        
        i = 0
        while i < len(all_lines):
            line = all_lines[i]
            
            # ▼▼▼ [핵심 수정] 구분자(~) 무시하고 날짜 알맹이만 추출 ▼▼▼
            # 정규식: 숫자.숫자(요일) 패턴을 모두 찾습니다.
            dates_found = re.findall(r'\d{2}\.\d{2}\([가-힣]\)', line)
            
            if dates_found:
                # 1. 날짜 해석
                if len(dates_found) == 2:
                    # 날짜가 2개면 범위 (시작 ~ 끝)
                    s_date = parse_date_str(dates_found[0], current_year)
                    e_date = parse_date_str(dates_found[1], current_year)
                elif len(dates_found) == 1:
                    # 날짜가 1개면 하루 (시작 == 끝)
                    s_date = parse_date_str(dates_found[0], current_year)
                    e_date = s_date
                else:
                    i += 1
                    continue

                if not s_date or not e_date:
                    i += 1
                    continue
                
                # 2. 제목 찾기
                # 해당 줄에서 날짜 텍스트를 모두 지워보고, 남는 게 제목인지 확인
                temp_line = line
                for d in dates_found:
                    temp_line = temp_line.replace(d, "")
                
                # 특수문자(~, -)와 공백 제거
                title_part = re.sub(r'[~\-–\s]', '', temp_line).strip()
                
                # 만약 남은 글자가 별로 없다면(제목이 아랫줄에 있다는 뜻), 아랫줄을 제목으로 가져옴
                final_title = ""
                if len(title_part) < 2:
                    if i + 1 < len(all_lines):
                        next_line = all_lines[i+1]
                        # 다음 줄이 또 날짜가 아니어야 제목으로 인정
                        if not re.search(r'\d{2}\.\d{2}', next_line):
                            final_title = next_line.strip()
                            i += 1 # 다음 줄 썼으니 건너뜀
                else:
                    # 같은 줄에 제목이 있었던 경우 (원래 줄에서 날짜만 뺀 나머지)
                    # 여기서는 clean하게 다시 원본 line에서 날짜 부분만 replace
                    final_title = line
                    for d in dates_found:
                         final_title = final_title.replace(d, "")
                    final_title = re.sub(r'^[~\-–\s]+', '', final_title).strip() # 앞쪽 특수문자 제거

                # 제목 유효성 최종 체크
                if final_title and len(final_title) > 1:
                    # 중복 방지
                    is_duplicate = False
                    for e in events:
                        if e['title'] == final_title and e['start'] == s_date:
                            is_duplicate = True
                            break
                    
                    if not is_duplicate:
                        events.append({
                            "title": final_title,
                            "start": s_date,
                            "end": e_date
                        })
                        found_count += 1
            
            i += 1
            
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
