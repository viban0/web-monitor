import os
import requests
from bs4 import BeautifulSoup
from datetime import datetime, timedelta
import re
import pytz
import urllib3

# SSL 경고 무시
urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

# ▼ 설정 ▼
TARGET_URL = "https://www.kw.ac.kr/ko/life/bachelor_calendar.jsp"
TOKEN = os.environ.get('TELEGRAM_TOKEN')
CHAT_ID = os.environ.get('TELEGRAM_CHAT_ID')

def parse_date_range(date_str, current_year):
    """
    '02.02(월) ~ 02.27(금)' 또는 '02.20(금)' 형태의 문자열을 파싱
    """
    # 괄호와 요일 제거 (02.02 ~ 02.27)
    clean_str = re.sub(r'\([가-힣]\)', '', date_str)
    
    # 시작일과 종료일 분리
    if "~" in clean_str:
        start_str, end_str = clean_str.split("~")
    else:
        start_str = clean_str
        end_str = clean_str
        
    start_str = start_str.strip()
    end_str = end_str.strip()
    
    # 날짜 객체로 변환
    start_date = datetime.strptime(f"{current_year}.{start_str}", "%Y.%m.%d").date()
    end_date = datetime.strptime(f"{current_year}.{end_str}", "%Y.%m.%d").date()
    
    return start_date, end_date

def get_calendar_events():
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) Chrome/91.0.4472.124 Safari/537.36"
    }
    
    try:
        response = requests.get(TARGET_URL, headers=headers, verify=False, timeout=30)
        soup = BeautifulSoup(response.text, 'html.parser')
        
        events = []
        
        # 현재 연도 가져오기 (페이지 상단의 2026.01 등에서 추출하거나 현재 연도 사용)
        # 보통 학사일정은 '올해' 기준이므로 시스템 연도를 쓰되, 1,2월은 학기 고려 필요.
        # 여기서는 단순하게 현재 시스템 연도를 기준으로 잡고 크롤링합니다.
        now = datetime.now()
        current_year = now.year 

        # 광운대 학사일정 리스트 구조 크롤링
        # (웹페이지 구조: <dl> <dt>날짜</dt> <dd>내용</dd> </dl> 형태가 반복됨)
        # 스크린샷의 리스트 형태를 기반으로 추출
        
        # 특정 월/일정 리스트 박스 찾기
        schedule_list = soup.select("div.bachelor_sch_list ul li")
        
        if not schedule_list:
             # 만약 li 구조가 아니라면 테이블이나 dl 구조일 수 있음 (일반적인 대학 사이트 패턴 시도)
             schedule_list = soup.select(".sche-list li, .list-box li")

        # 만약 위 selector로 안 잡히면 광운대 페이지 특성상 텍스트 기반으로 찾음
        if not schedule_list:
            # 전체 텍스트에서 날짜 패턴이 있는 행을 찾음
            pass 

        # 광운대 실제 페이지 구조에 맞춘 파싱 (tbody tr 등)
        rows = soup.select("table tbody tr") # 테이블 형태일 가능성 대비
        
        # ⚠️ 중요: 광운대 학사일정 페이지는 보통 '연간 일정'이 텍스트로 쭉 나열된 형태가 많습니다.
        # 스크린샷을 보면 날짜(왼쪽) - 내용(오른쪽) 구조입니다.
        
        # class="txt-box"나 반복되는 패턴을 찾습니다.
        # 여기서는 가장 범용적인 '모든 텍스트'에서 날짜 패턴을 찾는 방식으로 구현합니다.
        # (페이지 구조가 바뀌어도 잘 작동하도록)
        
        content_div = soup.select_one("div.bachelor_sch") # 학사일정 메인 div
        if not content_div:
            content_div = soup # 전체에서 찾기

        # 텍스트 라인별로 분석
        text_lines = content_div.get_text("\n").split("\n")
        
        for line in text_lines:
            line = line.strip()
            if not line: continue
            
            # 정규식으로 '00.00(요일)' 패턴이 있는지 확인
            # 예: 02.02(월) ~ 02.27(금)   2026학년도...
            match = re.search(r'(\d{2}\.\d{2}\([가-힣]\)(?:\s*~\s*\d{2}\.\d{2}\([가-힣]\))?)', line)
            
            if match:
                date_part = match.group(1)
                title_part = line.replace(date_part, "").strip()
                
                # 내용이 너무 짧거나(단순 월 표시) 없으면 스킵
                if len(title_part) < 2: 
                    continue
                    
                try:
                    s_date, e_date = parse_date_range(date_part, current_year)
                    
                    # 1,2월 일정은 학사일정상 '내년'으로 넘어가는 경우가 있음.
                    # 현재가 11,12월인데 일정이 1,2월이면 내년으로 처리하는 로직은 생략(단순화)
                    # 필요시 추가 가능
                    
                    events.append({
                        "title": title_part,
                        "start": s_date,
                        "end": e_date
                    })
                except:
                    continue

        # 날짜순 정렬
        events.sort(key=lambda x: x['start'])
        return events

    except Exception as e:
        print(f"크롤링 에러: {e}")
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
        print("일정을 가져오지 못했습니다.")
        return

    today_events = []
    upcoming_events = []
    
    for event in events:
        # 오늘 일정
        if event['start'] <= today <= event['end']:
            today_events.append(event['title'])
        
        # 다가오는 일정 (오늘보다 시작일이 큼)
        if event['start'] > today:
            d_day = (event['start'] - today).days
            if d_day <= 30: # 30일 이내 일정만
                upcoming_events.append({
                    "title": event['title'],
                    "d_day": d_day,
                    "date": event['start'].strftime("%m/%d")
                })

    # 보낼 내용 없으면 종료
    if not today_events and not upcoming_events:
        return

    # 메시지 작성
    msg_lines = []
    
    # 1. 헤더 (구분선 제거됨)
    msg_lines.append(f"📆 *광운대 학사일정* ({today.strftime('%m/%d')})")
    
    # 2. 오늘 일정
    if today_events:
        msg_lines.append("\n🔔 *오늘의 일정*")
        for title in today_events:
            msg_lines.append(f"• {title}")
    
    # 3. 다가오는 일정 (최대 2개)
    if upcoming_events:
        msg_lines.append("\n⏳ *다가오는 일정*")
        # [:2]로 2개만 자름
        for item in upcoming_events[:2]: 
            msg_lines.append(f"• D-{item['d_day']} {item['title']} ({item['date']})")

    final_msg = "\n".join(msg_lines)
    print(final_msg)
    
    send_telegram(final_msg)

if __name__ == "__main__":
    run()
