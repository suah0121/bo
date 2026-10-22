import datetime
import urllib.parse
import pandas as pd
import requests
import streamlit as st
from zoneinfo import ZoneInfo

# -----------------------------------------------------------------------------
# 1. 페이지 설정 및 커스텀 CSS 적용
# -----------------------------------------------------------------------------
st.set_page_config(
    page_title="박스오피스 대시보드",
    page_icon="🎬",
    layout="wide",
    initial_sidebar_state="collapsed",
)

st.markdown(
    """
<style>
    @import url('https://cdn.jsdelivr.net/gh/orioncactus/pretendard/dist/web/static/pretendard.css');
    * { font-family: 'Pretendard', sans-serif; }
    
    /* 앱 전체 배경 및 여백 */
    .stApp {
        background-color: #0f172a;
        color: #f8fafc;
    }
    
    /* 헤더 배너 */
    .hero-banner {
        background: linear-gradient(135deg, #1e1b4b 0%, #312e81 50%, #4338ca 100%);
        border: 1px solid rgba(255, 255, 255, 0.1);
        padding: 2rem;
        border-radius: 20px;
        box-shadow: 0 20px 25px -5px rgba(0, 0, 0, 0.5);
        margin-bottom: 2rem;
    }
    .hero-title {
        font-size: 2.2rem;
        font-weight: 800;
        color: #ffffff;
        margin: 0;
    }
    .hero-sub {
        color: #c7d2fe;
        font-size: 1rem;
        margin-top: 0.5rem;
    }

    /* 카드 UI */
    .glass-card {
        background: #1e293b;
        border: 1px solid #334155;
        border-radius: 16px;
        padding: 1.5rem;
        margin-bottom: 1rem;
        box-shadow: 0 10px 15px -3px rgba(0, 0, 0, 0.3);
    }
    
    /* 1위 강조 카드 */
    .top1-card {
        background: linear-gradient(135deg, #312e81 0%, #1e1b4b 100%);
        border: 2px solid #818cf8;
        border-radius: 20px;
        padding: 1.8rem;
        box-shadow: 0 0 25px rgba(99, 102, 241, 0.25);
    }

    /* 지표 카드 내 텍스트 */
    .stat-label {
        font-size: 0.875rem;
        color: #94a3b8;
        font-weight: 600;
    }
    .stat-value {
        font-size: 1.5rem;
        font-weight: 700;
        color: #f8fafc;
        margin-top: 0.25rem;
    }

    /* 외부 링크 버튼 */
    .portal-link-btn {
        display: inline-block;
        background-color: #3b82f6;
        color: white !important;
        padding: 0.6rem 1.2rem;
        border-radius: 10px;
        text-decoration: none;
        font-weight: 600;
        font-size: 0.9rem;
        margin-right: 0.5rem;
        margin-top: 0.5rem;
        transition: all 0.2s;
    }
    .portal-link-btn:hover {
        background-color: #2563eb;
        transform: translateY(-2px);
    }
</style>
""",
    unsafe_allow_html=True,
)

# -----------------------------------------------------------------------------
# 2. 헤더 섹션
# -----------------------------------------------------------------------------
st.markdown(
    """
<div class="hero-banner">
    <div class="hero-title">🎬 KOBIS 일별 박스오피스</div>
    <div class="hero-sub">영화관입장권통합전산망 데이터를 기반으로 실시간 순위 및 상세 분석 정보를 제공합니다.</div>
</div>
""",
    unsafe_allow_html=True,
)

# -----------------------------------------------------------------------------
# 3. 날짜 선택 파트 (KST 기준)
# -----------------------------------------------------------------------------
now_kst = datetime.datetime.now(ZoneInfo("Asia/Seoul")).date()
yesterday = now_kst - datetime.timedelta(days=1)

col_d1, col_d2 = st.columns([1, 2])

with col_d1:
    selected_date = st.date_input(
        label="📅 조회 날짜 선택",
        value=yesterday,
        max_value=yesterday,
        min_value=datetime.date(2003, 11, 11),
    )

target_dt = selected_date.strftime("%Y%m%d")
formatted_date = selected_date.strftime("%Y년 %m월 %d일")

with col_d2:
    st.write("")
    st.caption(f"💡 현재 **{formatted_date}** 기준 박스오피스 데이터를 확인하고 계십니다.")

# -----------------------------------------------------------------------------
# 4. KOBIS API 키 확인
# -----------------------------------------------------------------------------
if "KOBIS_KEY" not in st.secrets:
    st.error("❌ **API 인증키(KOBIS_KEY)가 설정되지 않았습니다.**")
    st.info("Streamlit Cloud 설정 메뉴의 Secrets 란에 KOBIS_KEY를 입력해 주세요.")
    st.stop()

api_key = st.secrets["KOBIS_KEY"]


# -----------------------------------------------------------------------------
# 5. API 호출 및 캐싱
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
    st.error("❌ API 데이터 요청 중 문제가 발생했습니다.")
    st.stop()

daily_list = data.get("boxOfficeResult", {}).get("dailyBoxOfficeList", [])

if not daily_list:
    st.warning("⚠️ **선택하신 날짜는 아직 집계 전이거나 데이터가 비어있습니다.**")
    st.stop()

# -----------------------------------------------------------------------------
# 6. 데이터 전처리
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
# 7. 오늘의 1위 영화 하이라이트
# -----------------------------------------------------------------------------
top_movie = df.iloc[0]

st.markdown(
    f"""
<div class="top1-card">
    <div style="color: #fbbf24; font-weight: 700; font-size: 0.9rem; margin-bottom: 0.3rem;">🥇 BOX OFFICE NO.1</div>
    <div style="font-size: 1.8rem; font-weight: 800; color: #ffffff;">{top_movie['표시영화명']}</div>
    <div style="color: #94a3b8; font-size: 0.9rem; margin-top: 0.3rem;">개봉일: {top_movie['openDt']}</div>
</div>
""",
    unsafe_allow_html=True,
)

m1, m2, m3 = st.columns(3)
with m1:
    st.markdown(
        f"""<div class="glass-card"><div class="stat-label">일일 관객수</div><div class="stat-value">{top_movie['audiCnt']:,} 명</div></div>""",
        unsafe_allow_html=True,
    )
with m2:
    st.markdown(
        f"""<div class="glass-card"><div class="stat-label">누적 관객수</div><div class="stat-value">{top_movie['audiAcc']:,} 명</div></div>""",
        unsafe_allow_html=True,
    )
with m3:
    st.markdown(
        f"""<div class="glass-card"><div class="stat-label">상영 스크린수</div><div class="stat-value">{top_movie['scrnCnt']:,} 개</div></div>""",
        unsafe_allow_html=True,
    )

st.markdown("---")

# -----------------------------------------------------------------------------
# 8. 탭 구성 (순위표 / 관객수 비교 차트)
# -----------------------------------------------------------------------------
tab1, tab2 = st.tabs(["📋 순위 전체보기", "📊 TOP 5 관객수 그래프"])

with tab1:
    st.caption(
        "👇 **목록에서 영화를 클릭하면 하단에서 감독, 출연진 및 포털 검색 링크를 확인할 수 있습니다.**"
    )

    display_df = df[
        [
            "rank",
            "순위변동",
            "표시영화명",
            "openDt",
            "audiCnt",
            "audiAcc",
            "scrnCnt",
        ]
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
            "누적관객": st.column_config.NumberColumn(
                "누적관객", format="%d 명"
            ),
            "스크린수": st.column_config.NumberColumn(
                "스크린수", format="%d 개"
            ),
        },
    )

with tab2:
    top5_df = df.head(5).copy()
    chart_data = top5_df.set_index("표시영화명")[["audiCnt"]]
    chart_data.columns = ["일일 관객수"]
    st.bar_chart(chart_data)

# -----------------------------------------------------------------------------
# 9. 선택 영화 상세 정보 및 줄거리/포스터 안내 카드
# -----------------------------------------------------------------------------
selected_rows = (
    event.selection.rows if event and hasattr(event, "selection") else []
)
selected_index = selected_rows[0] if selected_rows else 0
selected_movie = df.iloc[selected_index]
movie_code = selected_movie.get("movieCd", "")

movie_detail = fetch_movie_detail(movie_code, api_key) if movie_code else {}

directors = (
    ", ".join([d.get("peopleNm", "") for d in movie_detail.get("directors", [])])
    or "정보 없음"
)
actors = (
    ", ".join([a.get("peopleNm", "") for a in movie_detail.get("actors", [])[:5]])
    or "정보 없음"
)
genres = (
    ", ".join([g.get("genreNm", "") for g in movie_detail.get("genres", [])])
    or "정보 없음"
)
show_tm = movie_detail.get("showTm", "-")
audits = (
    movie_detail.get("audits", [{}])[0].get("watchGradeNm", "정보 없음")
    if movie_detail.get("audits")
    else "정보 없음"
)

# 포털 검색 URL 생성 (KOBIS OpenAPI에는 줄거리 및 포스터 이미지가 제공되지 않음)
encoded_title = urllib.parse.quote(selected_movie["movieNm"])
naver_search_url = f"https://search.naver.com/search.naver?query=영화+{encoded_title}"
daum_search_url = f"https://search.daum.net/search?w=tot&q=영화+{encoded_title}"

st.markdown("---")
st.subheader(f"🔍 선택된 영화 상세: {selected_movie['movieNm']}")

col_info, col_link = st.columns([1.5, 1])

with col_info:
    st.markdown(
        f"""
    <div class="glass-card">
        <h4 style="margin-top:0; color:#818cf8;">📌 영화 상세 스펙 (KOBIS 연동)</h4>
        <table style="width:100%; color:#cbd5e1; font-size:0.95rem; line-height:2;">
            <tr><td style="width:30%; color:#94a3b8;"><b>개봉일</b></td><td>{selected_movie['openDt']}</td></tr>
            <tr><td style="color:#94a3b8;"><b>장르</b></td><td>{genres}</td></tr>
            <tr><td style="color:#94a3b8;"><b>상영시간</b></td><td>{show_tm}분</td></tr>
            <tr><td style="color:#94a3b8;"><b>관람등급</b></td><td>{audits}</td></tr>
            <tr><td style="color:#94a3b8;"><b>감독</b></td><td>{directors}</td></tr>
            <tr><td style="color:#94a3b8;"><b>주연 배우</b></td><td>{actors}</td></tr>
            <tr><td style="color:#94a3b8;"><b>누적 관객수</b></td><td>{selected_movie['audiAcc']:,} 명</td></tr>
        </table>
    </div>
    """,
        unsafe_allow_html=True,
    )

with col_link:
    st.markdown(
        f"""
    <div class="glass-card">
        <h4 style="margin-top:0; color:#818cf8;">📖 줄거리 및 포스터 보기</h4>
        <p style="color:#94a3b8; font-size:0.9rem; line-height:1.6;">
            KOBIS 공식 API 규정상 줄거리 및 이미지 포스터는 데이터로 제공되지 않습니다.<br>
            아래 버튼을 누르면 해당 영화의 <b>공식 줄거리·포스터·실관람객 평점</b>을 즉시 확인할 수 있습니다.
        </p>
        <div style="margin-top:1rem;">
            <a href="{naver_search_url}" target="_blank" class="portal-link-btn">네이버 영화 정보 ↗</a>
            <a href="{daum_search_url}" target="_blank" class="portal-link-btn" style="background-color:#ea580c;">다음 영화 정보 ↗</a>
        </div>
    </div>
    """,
        unsafe_allow_html=True,
    )
