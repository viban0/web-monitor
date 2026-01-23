# 🤖 광운대 알리미 (KW Alert Bot)

> **Serverless Telegram Bot for Kwangwoon University** > 별도의 서버 없이 GitHub Actions만으로 동작하는 광운대학교 공지 & 학식 알림 봇입니다.

[![Python](https://img.shields.io/badge/Python-3.9-3776AB?style=flat-square&logo=python&logoColor=white)](https://www.python.org/)
[![GitHub Actions](https://img.shields.io/badge/GitHub_Actions-Automated-2088FF?style=flat-square&logo=github-actions&logoColor=white)](https://github.com/features/actions)
[![Telegram](https://img.shields.io/badge/Telegram-Bot_API-2CA5E0?style=flat-square&logo=telegram&logoColor=white)](https://core.telegram.org/bots/api)

---

## 📖 소개 (Introduction)

이 저장소는 ** [광운대 알리미 서비스](https://viban0.github.io/kwalertweb/) **의 실제 구동 코드를 담고 있습니다.  
24시간 돌아가는 서버 비용을 절약하기 위해 **Git Scraping** 방식을 사용하여, **GitHub Actions**가 주기적으로 학교 홈페이지를 크롤링하고 텔레그램으로 알림을 전송합니다.

### 🎯 핵심 기능
1. **실시간 공지 모니터링 (`monitor.py`)**
   - 학교 홈페이지(광운광장)의 새 글을 30분마다 감지합니다.
   - 학생과 무관한 공지(예: 교수지원팀)는 자동으로 필터링합니다.
   - 키워드(장학, 학사 등)에 따라 이모지를 자동으로 분류합니다.
2. **기숙사 공지 알림 (`dorm_monitor.py`)**
   - 행복기숙사 홈페이지의 공지사항을 모니터링합니다.
   - JSON API를 분석하여 숨겨진 게시글까지 찾아냅니다.
3. **모닝 브리핑 (`calendar_bot.py`)**
   - 매일 아침, 오늘의 학사일정과 D-Day를 브리핑합니다.
   - 오늘 운영하는 학식(함지마루) 메뉴를 크롤링하여 함께 알려줍니다.

---

## 🛠️ 아키텍처 및 작동 원리 (Architecture)

이 프로젝트는 **Stateful**한 DB 없이 `data.txt` 파일에 마지막으로 보낸 공지의 ID를 기록하여 상태를 관리합니다.

```mermaid
graph LR
    A[GitHub Actions<br>(Cron Schedule)] -->|Trigger| B(Python Scripts)
    B -->|Scrape| C{New Data?}
    C -->|Yes| D[Telegram API Push]
    C -->|Yes| E[Git Commit & Push<br>(Update data.txt)]
    C -->|No| F[Exit]
```
1.Schedule: .github/workflows에 정의된 Cron 스케줄러가 워크플로우를 실행합니다.

2.Scrape & Diff: 파이썬 스크립트가 웹사이트를 크롤링하고, data.txt에 저장된 이전 ID와 비교합니다.

3.Notification: 새로운 ID가 발견되면 텔레그램 메시지를 전송합니다.

4.Save State: 전송 완료된 ID를 data.txt에 덮어쓰고, git commit을 통해 저장소에 업데이트합니다.

⚠️ 주의사항 (Disclaimer)
이 프로젝트는 학습 및 개인적 편의를 위해 제작되었습니다.

학교 홈페이지의 구조가 변경되면 크롤링이 작동하지 않을 수 있습니다.

과도한 요청(Request)을 보내지 않도록 설정되어 있으나, 사용 시 주의가 필요합니다.

<p align="center"> Developed by <a href="https://www.google.com/search?q=https://github.com/viban0"><b>viban0</b></a> </p>
