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

# ------------------------------------------------------
# 1. 키워드별 이모지 매핑 (제목 앞 아이콘)
# ------------------------------------------------------
def get_emoji(title):
    if "장학" in title or "대출" in title:
        return "💰" 
    elif "학사" in title or "수업" in title or "복학" in title:
        return "📅" 
    elif "행사" in title or "축제" in title or "특강" in title:
        return "🎉" 
    elif "채용" in title or "모집" in title or "인턴" in title:
        return "👔" 
    elif "국제" in title or "교환" in title:
        return "✈️" 
    elif "봉사" in title:
        return "❤️" 
    elif "대회" in title or "공모" in title:
        return "🏆" 
    else:
        return "📢" 

# ------------------------------------------------------
# 2. 텔레그램 전송 함수 (구분선 포함 버전)
# ------------------------------------------------------
def send_telegram(title, link, info):
    if TOKEN and CHAT_ID:
        try:
            icon = get_emoji(title)
            safe_title = title.replace("[", "(").replace("]", ")")
            
            # ▼ 변경된 메시지 포맷 (구분선 복구!) ▼
            # 💰 제목
            # ────────────────
            # 2026-01-07 | 학생복지팀
            # [공지 바로가기]
            
            msg = f"{icon} *{safe_title}*\n" \
                  f"────────────────\n" \
                  f"{info}\n" \
                  f"[👉 공지 바로가기]({link})"
            
            url = f"https://api.telegram.org/bot{TOKEN}/sendMessage"
            payload = {
                "chat_id": CHAT_ID,
                "text": msg,
                "parse_mode": "Markdown"
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
        
        # 게시글 목록 가져오기 (상단 50개)
        items = soup.select(".board-list-box ul li")[:50]
        
        current_new_posts = []

        print(f"🔍 스캔 중... ({len(items)}개)")

        for item in items:
            # 1. 신규 게시글 필터링
            if "신규게시글" not in item.get_text():
                continue

            # 2. 정보 추출
            a_tag = item.select_one("div.board-text > a")
            info_tag = item.select_one("p.info") 

            if a_tag:
                # 제목 정리
                raw_title = " ".join(a_tag.get_text().split())
                clean_title = raw_title.replace("신규게시글", "").replace("Attachment", "").strip()
                
                # 링크 정리
                link = a_tag.get('href')
                full_link = f"https://www.kw.ac.kr{link}" if link else TARGET_URL
                
                # 부가 정보 정리 (조회수 제거)
                meta_info = ""
                if info_tag:
                    parts = info_tag.get_text(" ", strip=True).split()
                    filtered_parts = []
                    for part in parts:
                        if "조회" in part: continue
                        if part.isdigit() and len(part) < 6: continue
                        filtered_parts.append(part)
                    meta_info = " | ".join(filtered_parts)

                # 식별자 생성
                fingerprint = f"{clean_title}|{full_link}"
                
                current_new_posts.append({
                    "id": fingerprint,
                    "title": clean_title,
                    "link": full_link,
                    "info": meta_info
                })

        # 3. 데이터 비교 및 알림 전송
        old_posts = []
        if os.path.exists("data.txt"):
            with open("data.txt", "r", encoding="utf-8") as f:
                # 빈 줄 무시하고 읽기
                old_posts = [line.strip() for line in f.readlines() if line.strip()]

        save_data = []
        for post in current_new_posts:
            save_data.append(post["id"])
            
            if not old_posts:
                continue
            
            if post["id"] not in old_posts:
                print(f"🚀 새 공지: {post['title']}")
                send_telegram(post['title'], post['link'], post['info'])

        if not old_posts:
             print("🚀 첫 실행: 기준점 잡기 완료")

        # 4. 파일 저장
        with open("data.txt", "w", encoding="utf-8") as f:
            for pid in save_data:
                f.write(pid + "\n")
        
        print("💾 data.txt 업데이트 완료")

    except Exception as e:
        print(f"❌ 오류 발생: {e}")
        exit(1)

if __name__ == "__main__":
    run()
