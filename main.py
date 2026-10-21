import datetime
import pandas as pd
import requests
import streamlit as st
from zoneinfo import ZoneInfo

# -----------------------------------------------------------------------------
# 1. 스트림릿 페이지 설정 및 기본 레이아웃
# -----------------------------------------------------------------------------
st.set_page_config(
    page_title="어제 박스오피스 순위", page_icon="🎬", layout="wide"
)

st.title("🎬 어제 일별 박스오피스")
st.caption(
    "영화관입장권통합전산망(KOBIS) Open API 데이터를 기반으로 제공됩니다."
)

# -----------------------------------------------------------------------------
# 2. 한국 시간(KST) 기준 '어제' 날짜 자동 계산
# -----------------------------------------------------------------------------
# 배포 서버(Streamlit Cloud)의 시계가 UTC(세계 표준시)일 수 있으므로
# 명시적으로 'Asia/Seoul' 타임존을 지정하여 한국 시간 기준 어제 날짜를 구합니다.
now_kst = datetime.datetime.now(ZoneInfo("Asia/Seoul"))
yesterday = now_kst - datetime.timedelta(days=1)
target_dt = yesterday.strftime("%Y%m%d")  # YYYYMMDD 형식으로 변환
formatted_date = yesterday.strftime("%Y년 %m월 %d일")

st.info(f"📅 **조회 일자:** {formatted_date} (한국 시간 기준)")

# -----------------------------------------------------------------------------
# 3. KOBIS API 인증키 확인 (Secrets 사용)
# -----------------------------------------------------------------------------
# Streamlit Cloud의 Secrets Vault에서 KOBIS_KEY를 불러옵니다.
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
    st.stop()  # 키가 없으면 아래 코드 실행 중단

api_key = st.secrets["KOBIS_KEY"]

# -----------------------------------------------------------------------------
# 4. KOBIS API 데이터 요청
# -----------------------------------------------------------------------------
url = "https://www.kobis.or.kr/kobisopenapi/webservice/rest/boxoffice/searchDailyBoxOfficeList.json"
params = {"key": api_key, "targetDt": target_dt}

try:
    response = requests.get(url, params=params, timeout=10)
    # HTTP 상태 코드가 200(성공)이 아닌 경우 예외 발생
    response.raise_for_status()
    data = response.json()
except requests.exceptions.RequestException as e:
    st.error(f"❌ **네트워크 통신 오류가 발생했습니다.** ({e})")
    st.info("💡 잠시 후 다시 시도하거나 네트워크 연결을 확인해 주세요.")
    st.stop()

# -----------------------------------------------------------------------------
# 5. API 응답 에러 및 예외 처리
# -----------------------------------------------------------------------------
# KOBIS API는 인증키 오류 시에도 HTTP 200을 반환하며, 'faultInfo' 객체를 포함합니다.
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

# 정상 응답 구조 확인 및 데이터 추출
box_office_result = data.get("boxOfficeResult", {})
daily_list = box_office_result.get("dailyBoxOfficeList", [])

if not daily_list:
    st.warning(
        "⚠️ **어제 날짜의 박스오피스 데이터가 존재하지 않거나 집계 중입니다.**"
    )
    st.info("💡 KOBIS 전산망의 일별 집계 갱신 시점에 따라 일시적으로 데이터가 비어있을 수 있습니다.")
    st.stop()

# -----------------------------------------------------------------------------
# 6. 데이터 전처리 (문자열 -> 숫자 변환)
# -----------------------------------------------------------------------------
df = pd.DataFrame(daily_list)

# KOBIS API는 모든 숫자 데이터(순위, 관객수 등)를 문자열 형태로 반환하므로 숫자 타입으로 변환합니다.
numeric_cols = ["rank", "audiCnt", "audiAcc", "scrnCnt", "showCnt"]
for col in numeric_cols:
    if col in df.columns:
        df[col] = pd.to_numeric(df[col], errors="coerce").fillna(0)

# -----------------------------------------------------------------------------
# 7. 1위 영화 지표 카드 (Metrics)
# -----------------------------------------------------------------------------
top_movie = df.iloc[0]

st.subheader(f"🥇 1위 영화: {top_movie['movieNm']}")

col1, col2, col3 = st.columns(3)

with col1:
    # 당일 관객수
    st.metric(label="일일 관객수", value=f"{top_movie['audiCnt']:,} 명")

with col2:
    # 누적 관객수
    st.metric(label="누적 관객수", value=f"{top_movie['audiAcc']:,} 명")

with col3:
    # 스크린수
    st.metric(label="상영 스크린수", value=f"{top_movie['scrnCnt']:,} 개")

st.divider()

# -----------------------------------------------------------------------------
# 8. 관객수 상위 5편 막대그래프
# -----------------------------------------------------------------------------
st.subheader("📊 관객수 상위 5개 영화")

# 상위 5개 추출 후 그래프 시각화를 위해 정렬 (위에서부터 1위가 오도록 차트 데이터 정렬)
top5_df = df.head(5).copy()

# Streamlit 기본 막대그래프 활용
chart_data = top5_df.set_index("movieNm")[["audiCnt"]]
chart_data.columns = ["일일 관객수"]
st.bar_chart(chart_data)

st.divider()

# -----------------------------------------------------------------------------
# 9. 전체 박스오피스 순위표 (Table)
# -----------------------------------------------------------------------------
st.subheader("📋 박스오피스 전체 순위")

# 화면에 표시할 컬럼선택 및 이름 변경
display_df = df[
    ["rank", "movieNm", "openDt", "audiCnt", "audiAcc", "scrnCnt"]
].copy()
display_df.columns = [
    "순위",
    "영화명",
    "개봉일",
    "관객수",
    "누적관객",
    "스크린수",
]

# 테이블 형태로 표시 (천 단위 쉼표 포맷 적용)
st.dataframe(
    display_df,
    hide_index=True,
    use_container_width=True,
    column_config={
        "순위": st.column_config.NumberColumn("순위", format="%d위"),
        "관객수": st.column_config.NumberColumn("관객수", format="%d 명"),
        "누적관객": st.column_config.NumberColumn(
            "누적관객", format="%d 명"
        ),
        "스크린수": st.column_config.NumberColumn(
            "스크린수", format="%d 개"
        ),
    },
)
