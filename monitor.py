import os
import requests
from bs4 import BeautifulSoup
import urllib3

# SSL 인증서 경고 무시 (학교 사이트 접속 시 필요할 수 함)
urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

# ▼ 설정 ▼
TARGET_URL = "https://www.kw.ac.kr/ko/life/notice.jsp"
TOKEN = os.environ.get('TELEGRAM_TOKEN')
CHAT_ID = os.environ.get('TELEGRAM_CHAT_ID')

def send_telegram(title, link):
    if TOKEN and CHAT_ID:
        try:
            # 1. 제목에 대괄호 [ ]가 있으면 마크다운 링크가 깨질 수 있어서 소괄호 ( )로 변경
            safe_title = title.replace("[", "(").replace("]", ")")
            
            # 2. 마크다운 형식으로 메시지 생성: [제목](링크) -> 링크 길이를 숨김
            msg = f"[{safe_title}]({link})"
            
            url = f"https://api.telegram.org/bot{TOKEN}/sendMessage"
            payload = {
                "chat_id": CHAT_ID,
                "text": msg,
                "parse_mode": "Markdown" # <--- 핵심: 마크다운 모드 사용
            }
            requests.post(url, data=payload)
        except Exception as e:
            print(f"텔레그램 전송 실패: {e}")

def run():
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) Chrome/91.0.4472.124 Safari/537.36"
    }

    try:
        print(f"접속 시도: {TARGET_URL}")
        response = requests.get(TARGET_URL, headers=headers, verify=False, timeout=30)
        soup = BeautifulSoup(response.text, 'html.parser')
        
        # 1. 게시글 목록 가져오기 (상단 50개만 스캔)
        # 기존의 .top-notice 제한을 풀고 전체 리스트(.board-list-box ul li)를 가져옵니다.
        items = soup.select(".board-list-box ul li")[:50]
        
        current_new_posts = [] # "신규게시글" 딱지가 붙은 글들만 저장할 리스트

        print(f"🔍 스크랩한 게시글 수: {len(items)}개 (상위 50개 중)")

        for item in items:
            # ★ 핵심 로직: 텍스트에 "신규게시글"이 포함되지 않았으면 건너뜀
            if "신규게시글" not in item.get_text():
                continue

            # 제목과 링크 추출
            a_tag = item.select_one("div.board-text > a")
            if a_tag:
                # 1) 원본 텍스트 가져오기 (불필요한 공백 제거)
                raw_title = " ".join(a_tag.get_text().split())
                
                # 2) "신규게시글" 및 "Attachment" 같은 지저분한 글자 제거
                clean_title = raw_title.replace("신규게시글", "").replace("Attachment", "").strip()
                
                # 3) 링크 추출 (상대경로면 도메인 붙이기)
                link = a_tag.get('href')
                full_link = f"https://www.kw.ac.kr{link}" if link else TARGET_URL
                
                # 4) 저장 및 비교용 식별자 생성 (제목|링크)
                fingerprint = f"{clean_title}|{full_link}"
                current_new_posts.append(fingerprint)

        # 2. 이전 데이터(data.txt) 불러오기
        old_posts = []
        if os.path.exists("data.txt"):
            with open("data.txt", "r", encoding="utf-8") as f:
                old_posts = [line.strip() for line in f.readlines()]

        # 3. 비교 및 알림 전송
        new_alerts_count = 0
        
        # data.txt가 아예 없으면 첫 실행이므로 알림을 보내지 않고 기준점만 잡음
        if not old_posts:
            print("🚀 첫 실행(또는 파일 없음): 현재 발견된 신규 게시글을 저장만 합니다.")
        else:
            for post in current_new_posts:
                if post not in old_posts:
                    title, link = post.split("|")
                    print(f"🚀 새 공지 발견: {title}")
                    send_telegram(title, link)
                    new_alerts_count += 1

        if new_alerts_count == 0 and old_posts:
            print("✅ 변경 사항 없음")

        # 4. 파일 저장 (현재 "신규게시글" 목록으로 덮어쓰기)
        # 이렇게 하면 '신규' 딱지가 떼어진 글은 다음 비교 대상에서 자연스럽게 사라짐
        with open("data.txt", "w", encoding="utf-8") as f:
            for post in current_new_posts:
                f.write(post + "\n")
        print("💾 data.txt 업데이트 완료")

    except Exception as e:
        print(f"❌ 오류 발생: {e}")
        # 오류가 나더라도 다음 실행을 위해 스크립트를 종료
        exit(1)

if __name__ == "__main__":
    run()
