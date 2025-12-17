##月ごとの勤務時間＆給与 ・日付クリックでその日の詳細表示 ・カレンダー内ツールチップ情報

import streamlit as st
import pandas as pd
from datetime import datetime, date, time, timedelta
import calendar
import os
import base64
import json

st.set_page_config(page_title="シフト(給料)管理アプリ", layout="wide")
st.title("シフト(給料)管理")

DATA_FILE = "shifts_data.csv"
SETTINGS_FILE = "settings.json"


### 勤務先ごとの設定マスタ
WORKPLACE_SETTINGS = {
    "すたば": {
        "default_wage": 1310,
        "wage_history": [
            {"from": "2024-01-01", "wage": 1310},
            # {"from": "2025-04-01", "wage": 1350}, みたいに増やせる
        ],
        "pre_minutes": 10,
        "post_minutes": 5,
        "break_rules": [
            {"min_hours": 4, "break_minutes": 15},
            {"min_hours": 6, "break_minutes": 45},
            {"min_hours": 8, "break_minutes": 60},
        ],
        "night_start": 22,
        "night_end": 1,
        "night_rate": 1.25,
        "early_start": 5,
        "early_end": 7,
        "early_bonus_per_hour": 160,  # 早朝手当は+160円/h固定
        "busy_bonus_per_hour": 100,   # 繁忙期のときの +円/h
    },
    "駿台": {
        "default_wage": 1350,
        "wage_history": [
            {"from": "2024-01-01", "wage": 1350},
        ],
        "pre_minutes": 0,
        "post_minutes": 0,
        "break_rules": [
            {"min_hours": 6, "break_minutes": 45},
        ],
        "night_start": 23,
        "night_end": 1,
        "night_rate": 1,
        "early_start": 5,
        "early_end": 6,
        "early_bonus_per_hour": 0,
        "busy_bonus_per_hour": 0,
    },
    "C": {
        "default_wage": 1100,
        "wage_history": [
            {"from": "2024-01-01", "wage": 1100},
        ],
        "pre_minutes": 0,
        "post_minutes": 0,
        "break_rules": [
            {"min_hours": 5, "break_minutes": 30},
            {"min_hours": 8, "break_minutes": 60},
        ],
        "night_start": 22,
        "night_end": 5,
        "night_rate": 1.25,
        "early_start": 5,
        "early_end": 8,
        "early_bonus_per_hour": 0,
        "busy_bonus_per_hour": 0,
    },
    "D": {
        "default_wage": 1100,
        "wage_history": [
            {"from": "2024-01-01", "wage": 1100},
        ],
        "pre_minutes": 0,
        "post_minutes": 0,
        "break_rules": [],
        "night_start": 22,
        "night_end": 5,
        "night_rate": 1.25,
        "early_start": 5,
        "early_end": 8,
        "early_bonus_per_hour": 0,
        "busy_bonus_per_hour": 0,
    },
}


# よく使う勤務パターン（必要に応じて自分の勤務実態に合わせて書き換えてください）
SHIFT_PATTERNS = {
    "すたば 早番": {
        "workplace": "すたば",
        "start": time(6, 0),
        "end": time(10, 0),
        "wage": 1310,
        "manual_break_min": 0,
        "transport": 0,
    },
    "すたば 遅番": {
        "workplace": "すたば",
        "start": time(18, 0),
        "end": time(23, 0),
        "wage": 1310,
        "manual_break_min": 0,
        "transport": 0,
    },
    "駿台 夜": {
        "workplace": "駿台",
        "start": time(17, 0),
        "end": time(21, 30),
        "wage": 1350,
        "manual_break_min": 0,
        "transport": 0,
    },
}


def get_default_wage_for_date(workplace: str, shift_date: date) -> int:
    """
    勤務先と日付から、その日に適用されるデフォルト時給を返す。
    WORKPLACE_SETTINGS の wage_history に複数エントリを追加すると、
    時給改定に対応できる。
    """
    settings = WORKPLACE_SETTINGS.get(workplace, {})
    history = settings.get("wage_history")

    if history:
        # from 日付が古い順に並べて、「その日以前で一番新しいもの」を採用
        history_sorted = sorted(history, key=lambda h: h["from"])
        chosen_wage = None
        for h in history_sorted:
            from_date = datetime.strptime(h["from"], "%Y-%m-%d").date()
            if shift_date >= from_date:
                chosen_wage = h["wage"]
        if chosen_wage is not None:
            return int(chosen_wage)

    # 履歴がなければ従来どおり default_wage を返す
    return int(settings.get("default_wage", 1100))


# バイト先ごとの行の色(見た目)
WORKPLACE_COLORS = {
    "すたば": "lightgreen",
    "駿台": "lightcyan",
    "C": "lightcoral",
    "D": "lightyellow",
}


def color_by_workplace(row):
    wp = str(row.get("workplace", "")).strip()
    color = WORKPLACE_COLORS.get(wp, "white")
    return [f"background-color: {color}"] * len(row)


### データの保存・読み込み
def save_shifts():
    """セッション内のシフトをCSVに自動保存"""
    if "shifts" not in st.session_state:
        return
    df_save = pd.DataFrame(st.session_state["shifts"])
    if not df_save.empty and "date" in df_save.columns:
        df_save["date"] = pd.to_datetime(df_save["date"]).dt.strftime("%Y-%m-%d")
    df_save.to_csv(DATA_FILE, index=False)


def load_shifts():
    """起動時にCSVがあれば読み込む(空ファイルは無視)"""
    if os.path.exists(DATA_FILE):
        # ファイルサイズが0のときは中身なしとして無視
        if os.path.getsize(DATA_FILE) == 0:
            st.session_state["shifts"] = []
            return

        try:
            df_loaded = pd.read_csv(DATA_FILE)
        except pd.errors.EmptyDataError:
            st.session_state["shifts"] = []
            return

        if "date" in df_loaded.columns:
            df_loaded["date"] = pd.to_datetime(df_loaded["date"]).dt.date
        st.session_state["shifts"] = df_loaded.to_dict(orient="records")
    else:
        st.session_state["shifts"] = []


def save_settings(limit_income, fiscal_start):
    settings = {
        "limit_income": limit_income,
        "fiscal_start": fiscal_start.strftime("%Y-%m-%d"),
    }
    with open(SETTINGS_FILE, "w") as f:
        json.dump(settings, f)


def load_settings():
    if not os.path.exists(SETTINGS_FILE):
        return None
    with open(SETTINGS_FILE, "r") as f:
        settings = json.load(f)
    settings["fiscal_start"] = date.fromisoformat(settings["fiscal_start"])
    return settings


# シフト削除・複製関数
def DelAte(orig_index: int):
    """シフトを1件削除して即反映する関数(DelAteボタン用)"""
    if "shifts" not in st.session_state:
        return
    if 0 <= orig_index < len(st.session_state["shifts"]):
        st.session_state["shifts"].pop(orig_index)
        save_shifts()
        st.success("シフトを削除しました。")
        st.rerun()


def duplicate_shift(orig_index: int, new_date: date):
    """シフトを日付だけ変えて複製して即再描画"""
    if "shifts" not in st.session_state:
        return
    if 0 <= orig_index < len(st.session_state["shifts"]):
        new_item = st.session_state["shifts"][orig_index].copy()
        new_item["date"] = new_date
        st.session_state["shifts"].append(new_item)
        save_shifts()
        st.success(f"{new_date} にシフトを複製しました。")
        st.rerun()


### 休憩時間の自動計算
def get_auto_break_minutes(total_hours, workplace):
    settings = WORKPLACE_SETTINGS.get(workplace)
    if not settings:
        return 0
    rules = settings.get("break_rules", [])
    break_min = 0
    for rule in sorted(rules, key=lambda r: r["min_hours"]):
        if total_hours >= rule["min_hours"]:
            break_min = rule["break_minutes"]
    return break_min


### 深夜・早朝の時間数を計算
def _range_intersection_hours(a_start, a_end, b_start, b_end):
    start = max(a_start, b_start)
    end = min(a_end, b_end)
    if start >= end:
        return 0.0
    return (end - start).total_seconds() / 3600


def _hours_in_window_non_crossing(start_dt, end_dt, window_start_hour, window_end_hour):
    """日付をまたがない時間帯(例:5〜8時など)の重なり時間を計算"""
    total = 0.0
    day = start_dt.date()
    last_day = end_dt.date()
    while day <= last_day:
        w_start = datetime.combine(day, time(window_start_hour, 0))
        w_end = datetime.combine(day, time(window_end_hour, 0))
        total += _range_intersection_hours(start_dt, end_dt, w_start, w_end)
        day += timedelta(days=1)
    return total


def _hours_in_window_crossing(start_dt, end_dt, window_start_hour, window_end_hour):
    """深夜のような「22〜5時」みたいに日付をまたぐ窓"""
    total = 0.0
    day = start_dt.date()
    last_day = end_dt.date()
    while day <= last_day:
        # 当日window_start〜24:00
        w1_start = datetime.combine(day, time(window_start_hour, 0))
        w1_end = datetime.combine(day, time(23, 59, 59, 999999))
        total += _range_intersection_hours(start_dt, end_dt, w1_start, w1_end)

        # 翌日0:00〜window_end
        next_day = day + timedelta(days=1)
        w2_start = datetime.combine(next_day, time(0, 0))
        w2_end = datetime.combine(next_day, time(window_end_hour, 0))
        total += _range_intersection_hours(start_dt, end_dt, w2_start, w2_end)

        day += timedelta(days=1)
    return total


def calc_night_early_hours(start_dt, end_dt, workplace):
    settings = WORKPLACE_SETTINGS.get(workplace)
    if not settings:
        return 0.0, 0.0

    night_start = settings.get("night_start", 22)
    night_end = settings.get("night_end", 5)
    early_start = settings.get("early_start", 5)
    early_end = settings.get("early_end", 8)

    # 深夜
    if night_start > night_end:
        night_hours = _hours_in_window_crossing(start_dt, end_dt, night_start, night_end)
    else:
        night_hours = _hours_in_window_non_crossing(start_dt, end_dt, night_start, night_end)

    # 早朝
    if early_start < early_end:
        early_hours = _hours_in_window_non_crossing(start_dt, end_dt, early_start, early_end)
    else:
        early_hours = _hours_in_window_crossing(start_dt, end_dt, early_start, early_end)

    return night_hours, early_hours


### 初期データ・設定読み込み
if "shifts" not in st.session_state:
    load_shifts()

loaded_settings = load_settings()
if loaded_settings:
    default_limit = loaded_settings["limit_income"]
    default_fiscal = loaded_settings["fiscal_start"]
else:
    default_limit = 1030000
    default_fiscal = date(date.today().year, 1, 1)


# サイドバー：ページ切り替え＆設定
st.sidebar.header("表示 / 設定")

page = st.sidebar.radio(
    "表示ページを選択",
    ["カレンダー", "シフト一覧"],
    index=0,
)

limit_income = st.sidebar.number_input(
    "扶養の上限金額（円）", min_value=0, value=default_limit, step=10000
)

fiscal_start = st.sidebar.date_input(
    "集計開始日（年度のスタート）", value=default_fiscal
)


# カレンダー背景用画像アップロード
bg_file = st.sidebar.file_uploader("カレンダー背景画像（任意）", type=["png", "jpg", "jpeg"])
if bg_file is not None:
    st.session_state["bg_file_bytes"] = bg_file.getvalue()
    st.session_state["bg_file_mime"] = bg_file.type


# 画像がセッションにあれば、背景として反映
if "bg_file_bytes" in st.session_state:
    fake_file = st.session_state["bg_file_bytes"]
    mime = st.session_state.get("bg_file_mime", "image/png")  # デフォルトはpng
    encoded = base64.b64encode(fake_file).decode()
    page_bg_img = f"""
    <style>
    /* 背景画像（画面の外側に出すイメージ） */
    [data-testid="stAppViewContainer"] {{
        background-image:
            linear-gradient(rgba(0, 0, 0, 0.1), rgba(0, 0, 0, 0.1)),
            url("data:{mime};base64,{encoded}");
        background-size: cover;
        background-position: center;
    }}

    /* ヘッダーとサイドバーは白っぽく */
    [data-testid="stHeader"] {{
        background: rgba(255, 255, 255, 0.9);
    }}
    [data-testid="stSidebar"] {{
        background: rgba(255, 255, 255, 0.95);
    }}

    /* 真ん中のコンテンツ部分(block-container)を少し透けた白にする */
    [data-testid="stAppViewContainer"] .block-container {{
        background-color: rgba(255, 255, 255, 0.6) !important;
        color: #111 !important;
        padding-top: 1.0rem;
        padding-bottom: 2.0rem;
        border-radius: 0px;
    }}

    /* シフト入力フォーム周りを白いカード背景で包む */
    .shift-card {{
        background: rgba(255, 255, 255, 0.7);
        padding: 1rem 1.2rem;
        border-radius: 16px;
        box-shadow: 0 4px 18px rgba(0,0,0,0.18);
        margin-bottom: 2rem;
    }}

    /* 入力欄の文字を濃くして見やすく */
    label, input, select, textarea {{
        color: #000 !important;
    }}

    /* Streamlit の input 背景を少し白く */
    .stTextInput > div > div > input,
    .stNumberInput > div > input,
    .stDateInput > div > input,
    .stTimeInput > div > input {{
        background-color: rgba(255,255,255,0.98) !important;
        color: #000 !important;
    }}
    </style>
    """
    st.markdown(page_bg_img, unsafe_allow_html=True)


# シフト入力フォーム(全ページ共通)
st.subheader("シフト入力")
st.markdown('<div class="shift-card">', unsafe_allow_html=True)
with st.form("shift_form", clear_on_submit=True):
    # 勤務パターン選択
    pattern_names = ["（パターンを使わない）"] + list(SHIFT_PATTERNS.keys())
    selected_pattern = st.selectbox("勤務パターン（任意）", pattern_names)

    # 日付を先に決める（時給改定に使う）
    shift_date = st.date_input("日付", value=date.today())

    # パターンに応じてデフォルト値を決める
    pattern = SHIFT_PATTERNS.get(selected_pattern) if selected_pattern != "（パターンを使わない）" else None

    if pattern is not None:
        default_workplace = pattern.get("workplace", "すたば")
        default_start = pattern.get("start", time(18, 0))
        default_end = pattern.get("end", time(23, 0))
        pattern_wage = pattern.get("wage")
        default_manual_break = pattern.get("manual_break_min", 0)
        default_transport = pattern.get("transport", 0)
    else:
        default_workplace = "すたば"
        default_start = time(18, 0)
        default_end = time(23, 0)
        pattern_wage = None
        default_manual_break = 0
        default_transport = 0

    col1, col2 = st.columns(2)
    with col1:
        workplace = st.text_input(
            "バイト先(例：すたば / 駿台 / C / D)",
            value=default_workplace,
        )
        start_time = st.time_input("開始時刻", value=default_start)
    with col2:
        # 時給のデフォルト値：パターン優先、なければ履歴から自動計算
        if pattern_wage is not None:
            default_wage = pattern_wage
        else:
            default_wage = get_default_wage_for_date(workplace, shift_date)

        wage = st.number_input(
            "時給（円）",
            min_value=0,
            value=default_wage,
            step=10,
        )

        manual_break_min = st.number_input(
            "休憩(分) (0なら勤務先のルールから自動計算)",
            min_value=0,
            value=default_manual_break,
            step=5,
        )

        is_busy = st.checkbox("繁忙期（手当適用）", value=False)

        transport = st.number_input(
            "交通費（円）",
            min_value=0,
            value=default_transport,
            step=10,
        )

        end_time = st.time_input("終了時刻", value=default_end)

    submitted = st.form_submit_button("このシフトを追加")
    if submitted:
        start_dt = datetime.combine(shift_date, start_time)
        end_dt = datetime.combine(shift_date, end_time)

        settings_wp = WORKPLACE_SETTINGS.get(workplace, {})
        pre_min = settings_wp.get("pre_minutes", 0)
        post_min = settings_wp.get("post_minutes", 0)

        start_dt_for_pay = start_dt - timedelta(minutes=pre_min)
        end_dt_for_pay = end_dt + timedelta(minutes=post_min)

        total_hours = (end_dt_for_pay - start_dt_for_pay).total_seconds() / 3600

        if total_hours <= 0:
            st.error("終了時刻が開始時刻より前になっていませんか？")
        else:
            if manual_break_min > 0:
                break_minutes = manual_break_min
            else:
                break_minutes = get_auto_break_minutes(total_hours, workplace)

            paid_hours = total_hours - break_minutes / 60.0
            if paid_hours < 0:
                paid_hours = 0

            night_hours, early_hours = calc_night_early_hours(
                start_dt_for_pay, end_dt_for_pay, workplace
            )

            night_rate = settings_wp.get("night_rate", 1.0)
            early_bonus_per_hour = settings_wp.get("early_bonus_per_hour", 0.0)
            busy_bonus_per_hour = settings_wp.get("busy_bonus_per_hour", 0.0)

            base_pay = paid_hours * wage
            night_bonus = night_hours * wage * max(night_rate - 1.0, 0)
            early_bonus = early_hours * early_bonus_per_hour

            if is_busy:
                busy_bonus = paid_hours * busy_bonus_per_hour
            else:
                busy_bonus = 0.0

            pay = int(round(base_pay + night_bonus + early_bonus + busy_bonus))

            if "shifts" not in st.session_state:
                st.session_state["shifts"] = []

            st.session_state["shifts"].append(
                {
                    "workplace": workplace,
                    "date": shift_date,
                    "start": start_time.strftime("%H:%M"),
                    "end": end_time.strftime("%H:%M"),
                    "pre_min": pre_min,
                    "post_min": post_min,
                    "total_hours_raw": round(total_hours, 2),
                    "break_min": break_minutes,
                    "work_hours": round(paid_hours, 2),
                    "night_hours": round(night_hours, 2),
                    "early_hours": round(early_hours, 2),
                    "wage": wage,
                    "transport": int(transport),
                    "base_pay": int(round(base_pay)),
                    "night_bonus": int(round(night_bonus)),
                    "early_bonus": int(round(early_bonus)),
                    "is_busy": is_busy,
                    "busy_bonus": int(round(busy_bonus)),
                    "pay": pay,
                }
            )
            save_shifts()
            st.success("シフトを追加しました！")
st.markdown('</div>', unsafe_allow_html=True)


# シフトがない場合
if "shifts" not in st.session_state or len(st.session_state["shifts"]) == 0:
    st.info("まだシフトがありません。上のフォームから追加してください。")
    save_settings(limit_income, fiscal_start)
    st.stop()


# ここからはシフトがある前提
df = pd.DataFrame(st.session_state["shifts"])
df["date"] = pd.to_datetime(df["date"])

# 欠損カラム対策（古いCSVなどでも動くように）
if "work_hours" not in df.columns:
    df["work_hours"] = 0.0
df["work_hours"] = df["work_hours"].fillna(0.0)

if "transport" not in df.columns:
    df["transport"] = 0
df["transport"] = df["transport"].fillna(0).astype(int)

if "busy_bonus" not in df.columns:
    df["busy_bonus"] = 0
df["busy_bonus"] = df["busy_bonus"].fillna(0).astype(int)

df_period = df[df["date"] >= pd.to_datetime(fiscal_start)]

total_income = df_period["pay"].sum()
by_workplace = df_period.groupby("workplace")["pay"].sum().reset_index()

df_period["year_month"] = df_period["date"].dt.to_period("M").astype(str)
by_month = (
    df_period
    .groupby("year_month")
    .agg(
        total_pay=("pay", "sum"),
        total_hours=("work_hours", "sum"),
    )
    .reset_index()
    .sort_values("year_month")
)
by_month["total_hours"] = by_month["total_hours"].round(2)
by_month = by_month.rename(
    columns={
        "year_month": "年月",
        "total_pay": "給与合計(円)",
        "total_hours": "勤務時間合計(h)",
    }
)


### ページ1：カレンダー表示(Main)
if page == "カレンダー":
    st.subheader("🗓 カレンダー表示(Main)")

    default_date = date.today()
    selected_date = st.date_input("表示する月を選択", value=default_date, key="cal_month")
    y = selected_date.year
    m = selected_date.month

    st.markdown(f"### {y}年 {m}月 のシフト")

    # この月のデータを抽出
    target_period = f"{y}-{m:02d}"
    df_month = df[df["date"].dt.to_period("M").astype(str) == target_period]

    # カレンダー構造
    cal = calendar.Calendar(firstweekday=0)
    weeks = cal.monthdatescalendar(y, m)

    # カレンダー表示用テーブルデータ（HTML＋ツールチップ）
    table_data = []
    for week in weeks:
        row = []
        for d in week:
            if d.month != m:
                row.append("")
                continue

            day_shifts = df_month[df_month["date"].dt.date == d]
            if day_shifts.empty:
                cell = f"{d.day}"
            else:
                total_pay = int(day_shifts["pay"].sum())
                total_hours = float(day_shifts["work_hours"].sum())
                wp_list = sorted(day_shifts["workplace"].unique())
                wp_str = ", ".join(wp_list)

                # ツールチップ（title）用テキスト
                tooltip_text = (
                    f"{d.strftime('%Y-%m-%d')}&#10;"
                    f"勤務時間: {total_hours:.2f}h&#10;"
                    f"給与: {total_pay:,}円"
                )
                display_str = f"{d.day}<br>{total_pay:,}円<br>{wp_str}"
                cell = f'<span title="{tooltip_text}">{display_str}</span>'
            row.append(cell)
        table_data.append(row)

    cal_df = pd.DataFrame(
        table_data,
        columns=["月", "火", "水", "木", "金", "土", "日"],
    )

    def highlight_calendar(val):
        if isinstance(val, str) and "円" in val:
            return "background-color: rgba(255, 243, 205, 0.95); color: #000;"
        return "background-color: rgba(255, 255, 255, 0.95); color: #000;"

    st.markdown(
        """
        <style>
        .calendar-card {
            background: rgba(255, 255, 255, 0.98);
            padding: 1rem 1.2rem;
            border-radius: 16px;
            box-shadow: 0 4px 15px rgba(0,0,0,0.18);
        }
        </style>
        """,
        unsafe_allow_html=True,
    )

    st.markdown('<div class="calendar-card">', unsafe_allow_html=True)
    cal_styler = cal_df.style.map(highlight_calendar)
    st.markdown(cal_styler.to_html(), unsafe_allow_html=True)
    st.markdown('</div>', unsafe_allow_html=True)

    month_total = int(df_month["pay"].sum()) if not df_month.empty else 0
    month_hours = float(df_month["work_hours"].sum()) if not df_month.empty else 0.0
    st.markdown(
        f"#### {y}年{m}月の合計：**{month_total:,} 円 / {month_hours:.2f} h**"
    )

    # 日付クリックでその日の詳細表示（ボタン式カレンダー）
    st.markdown("#### 日別のシフト詳細（下の日付ボタンをクリック）")

    detail_date = st.session_state.get("detail_date")

    for week in weeks:
        cols = st.columns(7)
        for col, d in zip(cols, week):
            with col:
                if d.month != m:
                    st.write(" ")
                else:
                    day_shifts = df_month[df_month["date"].dt.date == d]
                    if day_shifts.empty:
                        label = f"{d.day}"
                    else:
                        total_pay = int(day_shifts["pay"].sum())
                        label = f"{d.day}\n{total_pay:,}円"
                    if st.button(label, key=f"detail_btn_{d.isoformat()}"):
                        st.session_state["detail_date"] = d
                        detail_date = d

    if detail_date is not None and detail_date.year == y and detail_date.month == m:
        day_shifts = df_month[df_month["date"].dt.date == detail_date]
        st.markdown(f"##### {detail_date} のシフト一覧")
        if day_shifts.empty:
            st.info("この日にはシフトはありません。")
        else:
            # 表示したい列だけ抜き出し
            show_cols = [
                "date",
                "workplace",
                "start",
                "end",
                "work_hours",
                "wage",
                "pay",
                "transport",
                "busy_bonus",
            ]
            show_cols = [c for c in show_cols if c in day_shifts.columns]
            st.table(day_shifts[show_cols])


# ページ2:シフト一覧(表＋扶養チェック＋削除&複製)
elif page == "シフト一覧":
    st.subheader("シフト一覧（テーブル表示）")

    df_sorted = df.sort_values("date")
    styled_df = df_sorted.style.apply(color_by_workplace, axis=1)
    st.dataframe(styled_df, width=True)

    st.markdown("### シフトの削除・複製")

    df_ops = df.sort_values("date").reset_index()  # 'index'に元の位置

    for _, row in df_ops.iterrows():
        orig_idx = int(row["index"])

        with st.container():
            cols = st.columns([5, 3, 1, 1])

            with cols[0]:
                st.write(
                    f"**{row['date'].date()}** "
                    f"{row['start']} - {row['end']}  "
                    f"（{row['workplace']} / {row['work_hours']}h / {row['pay']}円 / 交通費{row['transport']}円）"
                )

            with cols[1]:
                new_date = st.date_input(
                    "複製先の日付",
                    value=row["date"].date(),
                    key=f"copy_date_{orig_idx}",
                )

            with cols[2]:
                if st.button("Duplicate", key=f"copy_btn_{orig_idx}"):
                    duplicate_shift(orig_idx, new_date)

            with cols[3]:
                if st.button("DelAte", key=f"delete_btn_{orig_idx}"):
                    DelAte(orig_idx)

    # 扶養チェック表示
    st.subheader("扶養チェック")

    remaining = limit_income - total_income
    col_a, col_b = st.columns(2)
    with col_a:
        st.metric("現在の年間合計（期間内）", f"{total_income:,} 円")
    with col_b:
        if remaining >= 0:
            st.metric("扶養上限までの残り", f"{remaining:,} 円")
        else:
            st.metric("扶養上限超過分", f"{-remaining:,} 円")

    if remaining < 0:
        st.error("扶養の上限を超えています。シフト調整を検討してください。")
    elif remaining < 100000:
        st.warning("扶養の上限まであと10万円未満です。注意してください。")
    else:
        st.success("まだ扶養の上限には余裕があります。")

    st.subheader("バイト先ごとの年間合計（期間内）")
    st.table(by_workplace)

    st.subheader("月ごとの勤務時間＆給料合計（期間内）")
    st.table(by_month)

    # 交通費と繁忙期手当の集計
    total_transport = int(df_period["transport"].sum())
    total_busy_bonus = int(df_period["busy_bonus"].sum())

    st.subheader("交通費・繁忙期手当の集計（期間内）")
    col_t1, col_t2, col_t3 = st.columns(3)
    with col_t1:
        st.metric("交通費合計", f"{total_transport:,} 円")
    with col_t2:
        st.metric("繁忙期手当合計", f"{total_busy_bonus:,} 円")
    with col_t3:
        st.metric("給与＋交通費", f"{int(total_income + total_transport):,} 円")

    csv = df.to_csv(index=False).encode("utf-8-sig")
    st.download_button(
        "シフトデータをCSVでダウンロード",
        csv,
        "shifts.csv",
        "text/csv",
    )

    st.subheader("CSVからシフトを読み込む（任意）")
    uploaded = st.file_uploader("shifts.csv を選択", type="csv")
    if uploaded is not None:
        df_uploaded = pd.read_csv(uploaded)
        if "date" in df_uploaded.columns:
            df_uploaded["date"] = pd.to_datetime(df_uploaded["date"]).dt.date
        st.session_state["shifts"] = df_uploaded.to_dict(orient="records")
        save_shifts()
        st.success("CSVを読み込みました！ 画面を少しスクロールして確認してください。")


# 最後に設定を保存
save_settings(limit_income, fiscal_start)


### End of shift_app.py
