import os
import requests
from bs4 import BeautifulSoup
import urllib3

# 보안 경고 무시 설정 (학교 사이트 접속 시 SSL 에러 방지)
urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

# ▼▼▼ 설정 ▼▼▼
TARGET_URL = "https://www.kw.ac.kr/ko/life/notice.jsp"
TOKEN = os.environ.get('TELEGRAM_TOKEN')
CHAT_ID = os.environ.get('TELEGRAM_CHAT_ID')

def send_telegram(msg):
    if TOKEN and CHAT_ID:
        url = f"https://api.telegram.org/bot{TOKEN}/sendMessage"
        try:
            requests.get(url, params={"chat_id": CHAT_ID, "text": msg})
        except Exception as e:
            print(f"텔레그램 전송 실패: {e}")

def run():
    # 사람인 척하는 헤더 (필수)
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36"
    }

    try:
        print(f"접속 시도: {TARGET_URL}")
        # verify=False로 설정하여 SSL 인증서 문제 우회
        response = requests.get(TARGET_URL, headers=headers, verify=False, timeout=30)
        response.raise_for_status() # 접속 실패시 에러 발생시킴
        
        # HTML 분석 (BeautifulSoup)
        soup = BeautifulSoup(response.text, 'html.parser')
        
        # 공지사항 리스트에서 [필독]이 아닌 일반 게시글 찾기
        # 'notice' 클래스가 없는 tr 태그 중 첫 번째 것을 찾음
        latest_post = soup.select_one(".board-list-box tbody tr:not(.notice) .title-comm a")
        
        if not latest_post:
            print("게시글을 찾을 수 없습니다. 선택자(Selector)를 확인하세요.")
            return

        # 제목과 링크 추출
        current_title = latest_post.get_text(strip=True)
        link_suffix = latest_post.get('href')
        full_link = f"https://www.kw.ac.kr{link_suffix}" if link_suffix else TARGET_URL
        
        print(f"가져온 최신글: {current_title}")

        # 파일 저장 및 비교 로직
        last_title = "NONE"
        if os.path.exists("data.txt"):
            with open("data.txt", "r", encoding="utf-8") as f:
                last_title = f.read().strip()

        if last_title != current_title:
            print("✨ 새로운 공지 발견!")
            msg = f"📢 [광운대 공지]\n{current_title}\n\n{full_link}"
            send_telegram(msg)
            
            with open("data.txt", "w", encoding="utf-8") as f:
                f.write(current_title)
        else:
            print("변경 사항 없음")

    except Exception as e:
        print(f"❌ 오류 발생: {e}")
        send_telegram(f"봇 오류 발생: {e}")
        exit(1) # 강제로 오류 처리

if __name__ == "__main__":
    run()
