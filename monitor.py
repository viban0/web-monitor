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
# 2. 텔레그램 전송 함수 (구분선 포함)
# ------------------------------------------------------
def send_telegram(title, link, info):
    if TOKEN and CHAT_ID:
        try:
            icon = get_emoji(title)
            safe_title = title.replace("[", "(").replace("]", ")")
            
            # ▼ 메시지 포맷 ▼
            # 💰 제목
            # ────────────────
            # | 작성일 2026-01-07 | 학생복지팀
            # [👉 공지 바로가기]
            
            msg = f"{icon} *{safe_title}*\n" \
                  f"\n" \
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
        
        items = soup.select(".board-list-box ul li")[:50]
        
        current_new_posts = []

        print(f"🔍 스캔 중... ({len(items)}개)")

        for item in items:
            # 1. 신규 게시글 필터링
            if "신규게시글" not in item.get_text():
                continue

            a_tag = item.select_one("div.board-text > a")
            info_tag = item.select_one("p.info") 

            if a_tag:
                # 제목 정리
                raw_title = " ".join(a_tag.get_text().split())
                clean_title = raw_title.replace("신규게시글", "").replace("Attachment", "").strip()
                
                # 링크 정리
                link = a_tag.get('href')
                full_link = f"https://www.kw.ac.kr{link}" if link else TARGET_URL
                
                # ▼ 정보 정리 (수정일 제거 및 포맷팅 로직) ▼
                meta_info = ""
                if info_tag:
                    # 1. 텍스트를 파이프(|) 기준으로 쪼갭니다.
                    raw_text = info_tag.get_text("|", strip=True)
                    parts = raw_text.split("|")
                    
                    clean_parts = []
                    skip_next = False
                    
                    for part in parts:
                        p = part.strip()
                        if not p: continue # 빈칸 제거
                        
                        if "수정일" in p:
                            skip_next = True # 수정일 나오면 다음(날짜)도 스킵 준비
                            continue
                        
                        if skip_next:
                            # 수정일 뒤에 오는 날짜(숫자 포함된 문자열)를 스킵
                            if any(char.isdigit() for char in p):
                                skip_next = False
                                continue
                            else:
                                skip_next = False
                        
                        if "조회" in p: continue
                        
                        clean_parts.append(p)
                    
                    # clean_parts -> ['작성일', '2026-01-07', '학생복지팀'] 상태
                    
                    # 2. '작성일'과 날짜를 한 덩어리로 합치기
                    final_parts = []
                    idx = 0
                    while idx < len(clean_parts):
                        current = clean_parts[idx]
                        if "작성일" in current and idx + 1 < len(clean_parts):
                            final_parts.append(f"{current} {clean_parts[idx+1]}") # "작성일 2026-01-07"
                            idx += 2
                        else:
                            final_parts.append(current)
                            idx += 1
                    
                    # 3. 최종 조립: "| 작성일 2026-01-07 | 학생복지팀"
                    if final_parts:
                        meta_info = "| " + " | ".join(final_parts)

                # 식별자 생성
                fingerprint = f"{clean_title}|{full_link}"
                
                current_new_posts.append({
                    "id": fingerprint,
                    "title": clean_title,
                    "link": full_link,
                    "info": meta_info
                })

        # 3. 데이터 비교 및 전송
        old_posts = []
        if os.path.exists("data.txt"):
            with open("data.txt", "r", encoding="utf-8") as f:
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
