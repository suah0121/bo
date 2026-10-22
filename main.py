import datetime
import pandas as pd
import requests
import streamlit as st
from zoneinfo import ZoneInfo

# -----------------------------------------------------------------------------
# 1. 스트림릿 페이지 설정 및 기본 레이아웃
# -----------------------------------------------------------------------------
st.set_page_config(
    page_title="일별 박스오피스 조회", page_icon="🎬", layout="wide"
)

st.title("🎬 일별 박스오피스 조회")
st.caption(
    "영화관입장권통합전산망(KOBIS) Open API 데이터를 기반으로 제공됩니다."
)

# -----------------------------------------------------------------------------
# 2. 한국 시간(KST) 기준 선택 가능한 날짜 범위 설정 및 달력 UI
# -----------------------------------------------------------------------------
# 배포 서버 시계와 무관하게 한국 시간(KST)을 기준으로 오늘 및 어제 날짜 계산
now_kst = datetime.datetime.now(ZoneInfo("Asia/Seoul")).date()
yesterday = now_kst - datetime.timedelta(days=1)

# 사용자 날짜 선택 (최대 선택 가능 날짜: 어제)
selected_date = st.date_input(
    label="📅 조회할 날짜를 선택하세요 (오늘 날짜는 아직 집계 전입니다)",
    value=yesterday,
    max_value=yesterday,
    min_value=datetime.date(2003, 11, 11),  # KOBIS 데이터 제공 시작일 근처
)

# KOBIS API 전달용 YYYYMMDD 포맷팅
target_dt = selected_date.strftime("%Y%m%d")
formatted_date = selected_date.strftime("%Y년 %m월 %d일")

st.info(f"🔍 **조회 일자:** {formatted_date}")

# -----------------------------------------------------------------------------
# 3. KOBIS API 인증키 확인 (Secrets 사용)
# -----------------------------------------------------------------------------
if "KOBIS_KEY" not in st.secrets:
    st.error("❌ **API 인증키(KOBIS_KEY)가 설정되지 않았습니다.**")
    st.markdown("""
    **해결 방법:**
    1. Streamlit Cloud의 App Settings -> **Secrets** 메뉴로 이동합니다.
    2. 아래와 같이 KOBIS_KEY를 등록해 주세요:
    ```toml
    KOBIS_KEY = "발급받은_KOBIS_API_키"
    ```
    """)
    st.stop()

api_key = st.secrets["KOBIS_KEY"]

# -----------------------------------------------------------------------------
# 4. KOBIS API 데이터 요청
# -----------------------------------------------------------------------------
url = "https://www.kobis.or.kr/kobisopenapi/webservice/rest/boxoffice/searchDailyBoxOfficeList.json"
params = {"key": api_key, "targetDt": target_dt}

try:
    response = requests.get(url, params=params, timeout=10)
    response.raise_for_status()
    data = response.json()
except requests.exceptions.RequestException as e:
    st.error(f"❌ **네트워크 통신 오류가 발생했습니다.** ({e})")
    st.info("💡 잠시 후 다시 시도하거나 네트워크 연결을 확인해 주세요.")
    st.stop()

# -----------------------------------------------------------------------------
# 5. API 응답 에러 및 비어있는 목록 예외 처리
# -----------------------------------------------------------------------------
if "faultInfo" in data:
    fault = data["faultInfo"]
    st.error("❌ **KOBIS API 인증 및 요청 오류가 발생했습니다.**")
    st.warning(f"**오류 메시지:** {fault.get('message', '알 수 없는 오류')}")
    st.markdown("""
    **확인해 보세요:**
    - Secrets에 입력한 `KOBIS_KEY` 값이 정확한지 확인해 주세요.
    - KOBIS 개발자 센터에서 키 발급 상태 및 일일 트래픽 제한을 확인해 주세요.
    """)
    st.stop()

box_office_result = data.get("boxOfficeResult", {})
daily_list = box_office_result.get("dailyBoxOfficeList", [])

# 영화 목록이 없는 경우 문구 표시
if not daily_list:
    st.warning("⚠️ **그날은 아직 집계 전입니다.**")
    st.info("💡 선택하신 날짜의 박스오피스 데이터가 전산망에 등록되지 않았거나 집계 중일 수 있습니다.")
    st.stop()

# -----------------------------------------------------------------------------
# 6. 데이터 전처리 (숫자 변환, 순위 증감 포맷팅, 100만 관객 트로피)
# -----------------------------------------------------------------------------
df = pd.DataFrame(daily_list)

# 문자열 숫자를 정수형으로 변환
numeric_cols = ["rank", "rankInten", "audiCnt", "audiAcc", "scrnCnt", "showCnt"]
for col in numeric_cols:
    if col in df.columns:
        df[col] = pd.to_numeric(df[col], errors="coerce").fillna(0).astype(int)

# 1) 순위 증감(rankInten) 포맷팅 함수 정의
def format_rank_change(row):
    # 신규 진입 영화 처리
    if row.get("rankOldAndNew") == "NEW":
        return "🆕 NEW"
    
    inten = row["rankInten"]
    if inten > 0:
        return f"🔺 {inten}"  # 빨간 위 화살표
    elif inten < 0:
        return f"🔹 {abs(inten)}"  # 파란 아래 화살표
    else:
        return "-"

df["순위변동"] = df.apply(format_rank_change, axis=1)

# 2) 누적관객 100만 명 이상 영화 제목에 트로피 이모지(🏆) 추가
def add_trophy(row):
    movie_name = row["movieNm"]
    if row["audiAcc"] >= 1_000_000:
        return f"{movie_name} 🏆"
    return movie_name

df["표시영화명"] = df.apply(add_trophy, axis=1)

# -----------------------------------------------------------------------------
# 7. 1위 영화 지표 카드 (Metrics)
# -----------------------------------------------------------------------------
top_movie = df.iloc[0]

st.subheader(f"🥇 1위 영화: {top_movie['표시영화명']}")

col1, col2, col3 = st.columns(3)

with col1:
    st.metric(label="일일 관객수", value=f"{top_movie['audiCnt']:,} 명")

with col2:
    st.metric(label="누적 관객수", value=f"{top_movie['audiAcc']:,} 명")

with col3:
    st.metric(label="상영 스크린수", value=f"{top_movie['scrnCnt']:,} 개")

st.divider()

# -----------------------------------------------------------------------------
# 8. 관객수 상위 5편 막대그래프
# -----------------------------------------------------------------------------
st.subheader("📊 관객수 상위 5개 영화")

top5_df = df.head(5).copy()
chart_data = top5_df.set_index("표시영화명")[["audiCnt"]]
chart_data.columns = ["일일 관객수"]
st.bar_chart(chart_data)

st.divider()

# -----------------------------------------------------------------------------
# 9. 전체 박스오피스 순위표 (Table)
# -----------------------------------------------------------------------------
st.subheader("📋 박스오피스 전체 순위")

# 표에 노출할 컬럼 가공 및 배치
display_df = df[
    ["rank", "순위변동", "표시영화명", "openDt", "audiCnt", "audiAcc", "scrnCnt"]
].copy()

display_df.columns = [
    "순위",
    "변동",
    "영화명",
    "개봉일",
    "관객수",
    "누적관객",
    "스크린수",
]

st.dataframe(
    display_df,
    hide_index=True,
    use_container_width=True,
    column_config={
        "순위": st.column_config.NumberColumn("순위", format="%d위"),
        "변동": st.column_config.TextColumn("변동", help="🔺 상승 | 🔹 하강 | - 변동없음 | 🆕 신규"),
        "관객수": st.column_config.NumberColumn("관객수", format="%d 명"),
        "누적관객": st.column_config.NumberColumn("누적관객", format="%d 명"),
        "스크린수": st.column_config.NumberColumn("스크린수", format="%d 개"),
    },
)
