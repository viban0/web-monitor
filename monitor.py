import os
import requests
from bs4 import BeautifulSoup
import urllib3

# 보안 경고 무시
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
        
        # 1. 사이트에 제대로 들어갔는지 확인 (페이지 제목 출력)
        soup = BeautifulSoup(response.text, 'html.parser')
        print(f"페이지 제목: {soup.title.string if soup.title else '제목 없음'}")

        # 2. 게시글 목록 전체 가져오기 (훨씬 단순한 선택자 사용)
        # 복잡한 필터 없이 일단 'tr(한 줄)'을 다 가져옵니다.
        rows = soup.select(".board-list-box tbody tr")
        
        latest_title = None
        latest_link = None

        print(f"발견된 게시글 수: {len(rows)}개")

        # 3. 하나씩 검사해서 [필독]이 아닌 첫 번째 글 찾기
        for row in rows:
            # 만약 class에 'notice'가 들어있으면(=필독 공지면) 건너뛰기
            if "notice" in row.get("class", []):
                continue
            
            # 제목이 있는 칸(td.title-comm) 찾기
            title_tag = row.select_one(".title-comm a")
            if title_tag:
                latest_title = title_tag.get_text(strip=True)
                href = title_tag.get('href')
                latest_link = f"https://www.kw.ac.kr{href}" if href else TARGET_URL
                break # 찾았으면 반복 종료!

        if not latest_title:
            print("❌ 오류: 일반 게시글을 찾지 못했습니다. (HTML 구조가 다를 수 있음)")
            # 디버깅을 위해 HTML 일부를 출력해봅니다 (로그 확인용)
            print("HTML 덤프:", soup.select_one(".board-list-box"))
            return

        print(f"✅ 추출된 최신글: {latest_title}")

        # 4. 저장 및 비교
        last_title = "NONE"
        if os.path.exists("data.txt"):
            with open("data.txt", "r", encoding="utf-8") as f:
                last_title = f.read().strip()

        if last_title != latest_title:
            print("✨ 새로운 공지 발견!")
            msg = f"📢 [광운대 공지]\n{latest_title}\n\n{latest_link}"
            send_telegram(msg)
            
            with open("data.txt", "w", encoding="utf-8") as f:
                f.write(latest_title)
        else:
            print("변경 사항 없음")

    except Exception as e:
        print(f"❌ 치명적 오류: {e}")
        exit(1)

if __name__ == "__main__":
    run()
