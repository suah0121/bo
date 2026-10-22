import datetime
import pandas as pd
import requests
import streamlit as st
from zoneinfo import ZoneInfo

# -----------------------------------------------------------------------------
# 1. 페이지 초기화 및 커스텀 CSS 스타일링
# -----------------------------------------------------------------------------
st.set_page_config(
    page_title="일별 박스오피스 & 영화 리뷰",
    page_icon="🎬",
    layout="wide",
    initial_sidebar_state="expanded"
)

# Custom CSS
st.markdown("""
<style>
    /* 메인 배경 및 폰트 설정 */
    .main {
        background-color: #f8f9fa;
    }
    
    /* 헤더 스타일링 */
    .header-banner {
        background: linear-gradient(135deg, #1e1e2f 0%, #2a2a40 100%);
        color: white;
        padding: 1.8rem 2rem;
        border-radius: 16px;
        box-shadow: 0 10px 25px rgba(0,0,0,0.1);
        margin-bottom: 1.5rem;
    }
    .header-banner h1 {
        margin: 0;
        font-weight: 800;
        letter-spacing: -0.5px;
        color: #ffffff;
    }
    .header-banner p {
        margin-top: 0.5rem;
        color: #a0a5ba;
        font-size: 0.95rem;
    }

    /* 카드 콘테이너 스타일 */
    .custom-card {
        background: white;
        padding: 1.5rem;
        border-radius: 14px;
        border: 1px solid #e9ecef;
        box-shadow: 0 4px 12px rgba(0, 0, 0, 0.03);
        margin-bottom: 1rem;
    }

    /* 1위 영화 하이라이트 카드 */
    .top-movie-card {
        background: linear-gradient(135deg, #ffffff 0%, #fffbf0 100%);
        border: 1.5px solid #ffe082;
        padding: 1.5rem;
        border-radius: 16px;
        box-shadow: 0 6px 18px rgba(255, 193, 7, 0.12);
    }
    
    /* 뱃지 스타일링 */
    .badge-up {
        background-color: #ffebee;
        color: #d32f2f;
        padding: 4px 10px;
        border-radius: 20px;
        font-weight: bold;
        font-size: 0.85rem;
    }
    .badge-down {
        background-color: #e3f2fd;
        color: #1976d2;
        padding: 4px 10px;
        border-radius: 20px;
        font-weight: bold;
        font-size: 0.85rem;
    }
    .badge-same {
        background-color: #f5f5f5;
        color: #616161;
        padding: 4px 10px;
        border-radius: 20px;
        font-size: 0.85rem;
    }
    .badge-new {
        background-color: #e8f5e9;
        color: #2e7d32;
        padding: 4px 10px;
        border-radius: 20px;
        font-weight: bold;
        font-size: 0.85rem;
    }
</style>
""", unsafe_allow_html=True)

# -----------------------------------------------------------------------------
# 2. 헤더 섹션
# -----------------------------------------------------------------------------
st.markdown("""
<div class="header-banner">
    <h1>🎬 일별 박스오피스 인사이트</h1>
    <p>KOBIS 영화관입장권통합전산망 실시간 데이터를 바탕으로 순위, 관객 수 및 영화 상세 리뷰를 제공합니다.</p>
</div>
""", unsafe_allow_html=True)

# -----------------------------------------------------------------------------
# 3. 날짜 선택 파트
# -----------------------------------------------------------------------------
now_kst = datetime.datetime.now(ZoneInfo("Asia/Seoul")).date()
yesterday = now_kst - datetime.timedelta(days=1)

col_date1, col_date2 = st.columns([1, 3])

with col_date1:
    selected_date = st.date_input(
        label="📅 조회 날짜 선택",
        value=yesterday,
        max_value=yesterday,
        min_value=datetime.date(2003, 11, 11),
    )

target_dt = selected_date.strftime("%Y%m%d")
formatted_date = selected_date.strftime("%Y년 %m월 %d일")

with col_date2:
    st.write("") # 수평 맞춤용 여백
    st.info(f"💡 현재 **{formatted_date}** 기준 박스오피스를 조회 중입니다. (당일 관객수는 익일 집계됩니다)")

# -----------------------------------------------------------------------------
# 4. KOBIS API 키 검증
# -----------------------------------------------------------------------------
if "KOBIS_KEY" not in st.secrets:
    st.error("❌ **API 인증키(KOBIS_KEY)가 설정되지 않았습니다.**")
    st.markdown("""
    **Secrets 설정 방법:**
    Streamlit Cloud의 App Settings -> **Secrets** 메뉴에 아래 키를 추가해주세요.
    ```toml
    KOBIS_KEY = "발급받은_KOBIS_API_키"
    ```
    """)
    st.stop()

api_key = st.secrets["KOBIS_KEY"]

# -----------------------------------------------------------------------------
# 5. API 데이터 호출 함수
# -----------------------------------------------------------------------------
@st.cache_data(ttl=3600)
def fetch_box_office(date_str, key):
    url = "https://www.kobis.or.kr/kobisopenapi/webservice/rest/boxoffice/searchDailyBoxOfficeList.json"
    params = {"key": key, "targetDt": date_str}
    try:
        res = requests.get(url, params=params, timeout=10)
        res.raise_for_status()
        return res.json()
    except Exception as e:
        return {"error": str(e)}

@st.cache_data(ttl=86400)
def fetch_movie_detail(movie_cd, key):
    url = "https://www.kobis.or.kr/kobisopenapi/webservice/rest/movie/searchMovieInfo.json"
    params = {"key": key, "movieCd": movie_cd}
    try:
        res = requests.get(url, params=params, timeout=10)
        res.raise_for_status()
        data = res.json()
        return data.get("movieInfoResult", {}).get("movieInfo", {})
    except Exception:
        return {}

data = fetch_box_office(target_dt, api_key)

if "error" in data or "faultInfo" in data:
    st.error("❌ KOBIS API 연결 중 오류가 발생했습니다.")
    if "faultInfo" in data:
        st.warning(f"사유: {data['faultInfo'].get('message', '인증 키 오류')}")
    st.stop()

daily_list = data.get("boxOfficeResult", {}).get("dailyBoxOfficeList", [])

if not daily_list:
    st.warning("⚠️ **선택하신 날짜는 아직 집계 전이거나 데이터가 존재하지 않습니다.**")
    st.stop()

# -----------------------------------------------------------------------------
# 6. 데이터 가공
# -----------------------------------------------------------------------------
df = pd.DataFrame(daily_list)

numeric_cols = ["rank", "rankInten", "audiCnt", "audiAcc", "scrnCnt", "showCnt"]
for col in numeric_cols:
    if col in df.columns:
        df[col] = pd.to_numeric(df[col], errors="coerce").fillna(0).astype(int)

def format_rank_change(row):
    if row.get("rankOldAndNew") == "NEW":
        return "🆕 NEW"
    inten = row["rankInten"]
    if inten > 0:
        return f"🔺 {inten}"
    elif inten < 0:
        return f"🔹 {abs(inten)}"
    else:
        return "-"

df["순위변동"] = df.apply(format_rank_change, axis=1)

def add_trophy(row):
    movie_name = row["movieNm"]
    if row["audiAcc"] >= 1_000_000:
        return f"{movie_name} 🏆"
    return movie_name

df["표시영화명"] = df.apply(add_trophy, axis=1)

# -----------------------------------------------------------------------------
# 7. 1위 영화 하이라이트 UI 카드
# -----------------------------------------------------------------------------
top_movie = df.iloc[0]

st.markdown(f"""
<div class="top-movie-card">
    <h3 style="margin-top:0; color: #b78103; font-weight: 700;">🥇 오늘의 박스오피스 1위</h3>
    <h2 style="margin-bottom: 1rem; color: #111;">{top_movie['표시영화명']}</h2>
</div>
""", unsafe_allow_html=True)

# 1위 지표 Metrics
col_m1, col_m2, col_m3 = st.columns(3)
with col_m1:
    st.metric(label="일일 관객수", value=f"{top_movie['audiCnt']:,} 명")
with col_m2:
    st.metric(label="누적 관객수", value=f"{top_movie['audiAcc']:,} 명")
with col_m3:
    st.metric(label="스크린 수", value=f"{top_movie['scrnCnt']:,} 개")

st.markdown("---")

# -----------------------------------------------------------------------------
# 8. 탭 구성 (박스오피스 순위표 & 시각화 차트)
# -----------------------------------------------------------------------------
tab1, tab2 = st.tabs(["📋 전체 박스오피스 순위", "📊 관객수 비교 차트"])

with tab1:
    st.caption("💡 **표에서 행을 선택하면 하단에 선택된 영화의 상세 정보와 리뷰가 연동됩니다.**")
    
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

    event = st.dataframe(
        display_df,
        hide_index=True,
        use_container_width=True,
        selection_mode="single-row",
        on_select="rerun",
        column_config={
            "순위": st.column_config.NumberColumn("순위", format="%d위"),
            "변동": st.column_config.TextColumn("변동"),
            "관객수": st.column_config.NumberColumn("관객수", format="%d 명"),
            "누적관객": st.column_config.NumberColumn("누적관객", format="%d 명"),
            "스크린수": st.column_config.NumberColumn("스크린수", format="%d 개"),
        },
    )

with tab2:
    st.subheader("TOP 5 영화 일일 관객수 비교")
    top5_df = df.head(5).copy()
    chart_data = top5_df.set_index("표시영화명")[["audiCnt"]]
    chart_data.columns = ["일일 관객수"]
    st.bar_chart(chart_data, color="#3f51b5")

# -----------------------------------------------------------------------------
# 9. 선택 영화 상세 카드 및 평점 UI
# -----------------------------------------------------------------------------
