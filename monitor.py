import os
import requests
from bs4 import BeautifulSoup
import urllib3

# SSL 인증서 경고 무시
urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

# ▼ 설정 ▼
TARGET_URL = "https://www.kw.ac.kr/ko/life/notice.jsp"
TOKEN = os.environ.get('TELEGRAM_TOKEN')
CHAT_ID = os.environ.get('TELEGRAM_CHAT_ID')

def send_telegram(msg):
    if TOKEN and CHAT_ID:
        try:
            url = f"https://api.telegram.org/bot{TOKEN}/sendMessage"
            requests.get(url, params={"chat_id": CHAT_ID, "text": msg})
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
        
        # [핵심 변경] class가 'top-notice'인 li 태그만 콕 집어서 가져오기
        # 일반 게시물은 아예 가져오지도 않습니다.
        items = soup.select(".board-list-box ul li.top-notice")
        
        if not items:
            print("정보: 현재 고정 공지(top-notice)가 하나도 없습니다.")
            # 고정 공지가 없으면 그냥 빈 리스트로 처리해서 저장된 파일도 비워버림 (정상 작동)

        current_fixed_posts = [] # 이번에 발견한 고정 공지들
        new_posts_to_notify = []

        print(f"🔍 발견된 고정 공지: {len(items)}개")

        for item in items:
            # 제목과 링크 추출
            a_tag = item.select_one("div.board-text > a")
            if a_tag:
                title = " ".join(a_tag.get_text().split())
                link = a_tag.get('href')
                full_link = f"https://www.kw.ac.kr{link}" if link else TARGET_URL
                
                # 지문 생성 (제목|링크)
                fingerprint = f"{title}|{full_link}"
                current_fixed_posts.append(fingerprint)
                
                # 로그 출력 (확인용)
                print(f"  📌 {title[:20]}...")

        # 2. 이전 데이터 불러오기
        old_posts = []
        if os.path.exists("data.txt"):
            with open("data.txt", "r", encoding="utf-8") as f:
                old_posts = [line.strip() for line in f.readlines()]

        # 3. 비교 로직
        if old_posts:
            for post in current_fixed_posts:
                if post not in old_posts:
                    title, link = post.split("|")
                    new_posts_to_notify.append((title, link))
        else:
            # 파일이 없으면 첫 실행이므로 알림 안 보내고 저장만 함 (알림 폭탄 방지)
            print("🚀 첫 실행입니다. 현재 공지들을 기준점으로 잡습니다.")

        # 4. 알림 전송
        if new_posts_to_notify:
            print(f"✨ 총 {len(new_posts_to_notify)}개의 새 고정 공지 발견!")
            for title, link in new_posts_to_notify:
                msg = f"🔔[새로운 공지]\n\n 제목: {title}\n\n🔗 링크: {link}"
                send_telegram(msg)
        else:
            print("변경 사항 없음")

        # 5. 저장 (현재 존재하는 top-notice만 저장)
        # 고정이 풀려서 일반 글이 된 녀석은 여기서 자연스럽게 삭제됨
        with open("data.txt", "w", encoding="utf-8") as f:
            for post in current_fixed_posts:
                f.write(post + "\n")

    except Exception as e:
        print(f"❌ 오류 발생: {e}")
        exit(1)

if __name__ == "__main__":
    run()
