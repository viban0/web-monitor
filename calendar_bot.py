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

def get_calendar_debug():
    chrome_options = Options()
    chrome_options.add_argument("--headless") 
    chrome_options.add_argument("--no-sandbox")
    chrome_options.add_argument("--disable-dev-shm-usage")
    chrome_options.add_argument("--window-size=1920,1080")
    chrome_options.add_argument("user-agent=Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36")
    
    print("🚀 [디버그 모드] 크롬 브라우저 실행 중...")
    driver = webdriver.Chrome(service=Service(ChromeDriverManager().install()), options=chrome_options)
    
    try:
        print(f"📡 접속 중: {TARGET_URL}")
        driver.get(TARGET_URL)
        
        # 로딩 대기
        try:
            WebDriverWait(driver, 20).until(
                EC.presence_of_element_located((By.CSS_SELECTOR, ".schedule-this-yearlist li"))
            )
            print("✨ 데이터 로딩 감지됨!")
        except:
            print("⚠️ 대기 시간 초과")

        time.sleep(3)
        driver.execute_script("window.scrollTo(0, document.body.scrollHeight);")
        time.sleep(1)

        html_source = driver.page_source
        soup = BeautifulSoup(html_source, 'html.parser')
        
        for script in soup(["script", "style"]):
            script.decompose()

        # 텍스트 라인 추출
        all_lines = [line.strip() for line in soup.get_text(separator="\n", strip=True).splitlines() if line.strip()]
        print(f"🔍 전체 텍스트 라인 수: {len(all_lines)}줄")
        print("-" * 60)
        
        found_any_date = False
        
        for i, line in enumerate(all_lines):
            # ▼▼▼ [디버깅 핵심] 아주 단순한 패턴(숫자.숫자)만 있으면 무조건 출력 ▼▼▼
            # 봇이 점(.)을 인식하는지, 숫자를 인식하는지 확인
            simple_match = re.search(r'(\d{2}).(\d{2})', line)
            
            if simple_match:
                found_any_date = True
                print(f"👉 [Line {i}] 날짜 후보 발견!")
                print(f"   원본 텍스트: '{line}'")
                print(f"   RAW 데이터 : {repr(line)}") # 눈에 안 보이는 특수문자 확인용
                
                # 1단계: 단순 패턴(00.00) 매칭 확인
                # 점(.)이 특수문자일 수도 있으므로 . 대신 모든 문자(.)로 매칭한 결과 확인
                print(f"   1차 매칭(00.00): {simple_match.group(0)}")
                
                # 2단계: 우리가 쓰던 엄격한 패턴(00.00(요일)) 테스트
                strict_match = re.search(r'\d{2}\.\d{2}\([가-힣]\)', line)
                if strict_match:
                    print(f"   2차 매칭(엄격) : 성공 ✅ ({strict_match.group(0)})")
                else:
                    print(f"   2차 매칭(엄격) : 실패 ❌ (괄호나 요일, 점이 다를 수 있음)")
                    
                print("-" * 60)
                
        if not found_any_date:
            print("❌ '숫자.숫자' 형태가 단 한 번도 발견되지 않았습니다.")
            print("   -> 숫자가 이미지가 아니거나, 인코딩이 완전히 깨졌을 가능성이 큽니다.")

        return []

    except Exception as e:
        print(f"❌ 에러: {e}")
        return []
    finally:
        driver.quit()

def run():
    # 디버깅만 실행하고 알림은 보내지 않음
    get_calendar_debug()

if __name__ == "__main__":
    run()
