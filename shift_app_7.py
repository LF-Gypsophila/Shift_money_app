## 休日・祝日判定＆色付け + 勤務パターン（SHIFT_PATTERNS）の画面編集
## ComentOut


1
import streamlit as st #WebアプリフレームワークStreamlitをインポート
import pandas as pd #データ処理用のpandasをインポート
from datetime import datetime, date, time, timedelta #日付・時刻関連クラスをインポート
import calendar #カレンダー生成用モジュール
import os #ファイル存在チェックなどに利用
import base64 #画像などをBase64エンコード/デコードするため
import json #設定の保存・読み込みに利用
from typing import Dict, Any, Optional #型ヒント用（辞書型などに使う）
import jpholiday #日本の祝日判定用ライブラリ

st.set_page_config(page_title="シフト(給料)管理アプリ", layout="wide") #ページタイトルとレイアウトを設定
st.title("シフト(給料)管理") #アプリ上部のタイトル表示

DATA_FILE = "shifts_data.csv" #シフト情報を保存するCSVファイル名
SETTINGS_FILE = "settings.json" #設定情報を保存するJSONファイル名


### 勤務先ごとの設定マスタ
WORKPLACE_SETTINGS = { #各バイト先ごとのルールやデフォルト時給などを定義
    "すたば": { #バイト先「すたば」の設定
        "default_wage": 1310, #デフォルト時給
        "wage_history": [ #時給改定の履歴（開始日と時給）
            {"from": "2024-12-12", "wage": 1200},
            {"from": "2025-04-01", "wage": 1220},
            {"from": "2025-10-01", "wage": 1310},
        ],
        "pre_minutes": 10, #給与計算上、開始前に自動でプラスされる分数
        "post_minutes": 5, #給与計算上、終了後に自動でプラスされる分数
        "break_rules": [ #勤務時間に応じた休憩時間の自動付与ルール
            {"min_hours": 4, "break_minutes": 15},
            {"min_hours": 6, "break_minutes": 45},
            {"min_hours": 8, "break_minutes": 60},
        ],
        "night_start": 22, #深夜時間帯の開始時刻（時）
        "night_end": 1, #深夜時間帯の終了時刻（時）
        "night_rate": 1.25, #深夜割増率（1.25倍など）
        "early_start": 5, #早朝手当の開始時刻（時）
        "early_end": 7, #早朝手当の終了時刻（時）
        "early_bonus_per_hour": 160, #早朝手当（円/時間）
        "busy_bonus_per_hour": 200,  #繁忙期手当（円/時間）
    },
    "駿台": { #バイト先「駿台」の設定
        "default_wage": 1350,
        "wage_history": [
            {"from": "2024-04-24", "wage": 1200},
            {"from": "2025-04-01", "wage": 1350},
        ],
        "pre_minutes": 0,
        "post_minutes": 0,
        "break_rules": [
            {"min_hours": 6, "break_minutes": 45},
        ],
        "night_start": 23,
        "night_end": 1,
        "night_rate": 1, #深夜割増なし
        "early_start": 5,
        "early_end": 6,
        "early_bonus_per_hour": 0, #早朝手当なし
        "busy_bonus_per_hour": 0, #繁忙期手当なし
    },
    "C": { #バイト先「C」の設定
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
    "D": { #バイト先「D」の設定
        "default_wage": 1100,
        "wage_history": [
            {"from": "2024-01-01", "wage": 1100},
        ],
        "pre_minutes": 0,
        "post_minutes": 0,
        "break_rules": [], #特に休憩ルールなし
        "night_start": 22,
        "night_end": 5,
        "night_rate": 1.25,
        "early_start": 5,
        "early_end": 8,
        "early_bonus_per_hour": 0,
        "busy_bonus_per_hour": 0,
    },
}

#背景テーマのプリセット
THEME_OPTIONS = ["シンプルホワイト", "スタバグリーン", "ネイビーダーク", "パステルピンク"] #背景テーマの選択肢

#よく使う勤務パターン
SHIFT_PATTERNS = { #フォームで選べる「勤務パターン」プリセット
    "すたば:15-CL": {
        "workplace": "すたば",
        "start": time(15, 0), #15:00開始
        "end": time(22, 30), #22:30終了
        "wage": 1310,
        "manual_break_min": 45,
        "transport": 640,
    },
    "すたば:18-CL": {
        "workplace": "すたば",
        "start": time(18, 0),
        "end": time(22, 30),
        "wage": 1310,
        "manual_break_min": 15,
        "transport": 640,
    },
    "駿台:CL業務": {
        "workplace": "駿台",
        "start": time(18, 0),
        "end": time(22, 00),
        "wage": 1350,
        "manual_break_min": 0,
        "transport": 0,
    },
}

# === 勤務パターン設定：JSON保存用の変換関数 ===
def serialize_shift_patterns_for_settings(
    patterns: Dict[str, Dict[str, Any]]
) -> Dict[str, Any]:
    """SHIFT_PATTERNS を settings.json に保存できる形に変換"""
    result: Dict[str, Any] = {}
    for name, p in patterns.items():
        start_val = p.get("start")
        end_val = p.get("end")
        result[name] = {
            "workplace": p.get("workplace", ""),
            "start": start_val.strftime("%H:%M") if isinstance(start_val, time) else start_val,
            "end": end_val.strftime("%H:%M") if isinstance(end_val, time) else end_val,
            "wage": p.get("wage"),
            "manual_break_min": int(p.get("manual_break_min", 0)),
            "transport": int(p.get("transport", 0)),
        }
    return result


def load_shift_patterns_from_settings(
    data: Dict[str, Any]
) -> Dict[str, Dict[str, Any]]:
    """settings.json に保存したパターン情報を SHIFT_PATTERNS 形式に戻す"""
    loaded: Dict[str, Dict[str, Any]] = {}
    for name, p in data.items():
        start_str = p.get("start")
        end_str = p.get("end")
        start_obj = (
            datetime.strptime(start_str, "%H:%M").time()
            if isinstance(start_str, str) and start_str
            else time(0, 0)
        )
        end_obj = (
            datetime.strptime(end_str, "%H:%M").time()
            if isinstance(end_str, str) and end_str
            else time(0, 0)
        )
        loaded[name] = {
            "workplace": p.get("workplace", ""),
            "start": start_obj,
            "end": end_obj,
            "wage": p.get("wage"),
            "manual_break_min": int(p.get("manual_break_min", 0)),
            "transport": int(p.get("transport", 0)),
        }
    return loaded

def get_default_wage_for_date(workplace: str, shift_date: date) -> int:
    """
    勤務先と日付から、その日に適用されるデフォルト時給を返す。
    時給履歴（wage_history）があれば、開始日以降の最新レコードを使う。
    """
    settings = WORKPLACE_SETTINGS.get(workplace, {}) #指定の勤務先設定を取得（なければ空dict）
    history = settings.get("wage_history") #時給履歴を取得

    if history: #履歴があれば、日付に応じて選ぶ
        history_sorted = sorted(history, key=lambda h: h["from"]) #from日付でソート
        chosen_wage = None #適用される時給
        for h in history_sorted: #古い順に確認
            from_date = datetime.strptime(h["from"], "%Y-%m-%d").date() #"YYYY-MM-DD" を date型に
            if shift_date >= from_date: #シフト日が開始日以降なら候補
                chosen_wage = h["wage"]
        if chosen_wage is not None: #適用時給が見つかったら返す
            return int(chosen_wage)

    return int(settings.get("default_wage", 1100)) #見つからなければ default_wage か 1100を返す


# バイト先ごとの行の色(見た目)
WORKPLACE_COLORS = { #DataFrame表示時の行背景色設定
    "すたば": "lightgreen",
    "駿台": "lightcyan",
    "C": "lightcoral",
    "D": "lightyellow",
}


def color_by_workplace(row): #DataFrame Styler用のカラー関数
    wp = str(row.get("workplace", "")).strip() #行の勤務先名を取得
    color = WORKPLACE_COLORS.get(wp, "white") #対応する色を取得（なければ白）
    return [f"background-color: {color}"] * len(row) #行の全列に同じ背景色を適用


### データの保存・読み込み
def save_shifts() -> None:
    """セッション内のシフトをCSVに自動保存"""
    if "shifts" not in st.session_state: #シフトがなければ何もしない
        return
    df_save = pd.DataFrame(st.session_state["shifts"]) #シフトリストをDataFrameに変換
    if not df_save.empty and "date" in df_save.columns: #date列がある場合
        df_save["date"] = pd.to_datetime(df_save["date"]).dt.strftime("%Y-%m-%d") #日付を文字列に変換
    df_save.to_csv(DATA_FILE, index=False) #CSVとして保存（インデックス列は保存しない）


def save_settings(
    limit_income: int,
    fiscal_start: date,
    theme_name: Optional[str] = None,
    workplace_settings: Optional[Dict[str, Any]] = None,
) -> None:
    """設定＋背景画像も JSON に保存"""
    settings: Dict[str, Any] = { #保存する設定の辞書を作成
        "limit_income": limit_income, #扶養の上限金額
        "fiscal_start": fiscal_start.strftime("%Y-%m-%d"), #集計開始日を文字列に
    }
    if theme_name is not None: #テーマ名が指定されていれば保存
        settings["theme_name"] = theme_name

    if workplace_settings is not None: #勤務先設定が指定されていれば保存
        settings["workplace_settings"] = workplace_settings
        
    try:
        settings["shift_patterns"] = serialize_shift_patterns_for_settings(
            SHIFT_PATTERNS
        ) #勤務パターン設定を保存形式に変換して保存
    except Exception: #NameError? など万一のエラーに備える
        pass #万一エラーが出てもアプリが止まらないようにする

   #背景画像（あれば）も保存
    if "bg_file_bytes" in st.session_state: #セッションに背景画像があれば
        try:
            settings["bg_image_b64"] = base64.b64encode(
                st.session_state["bg_file_bytes"]
            ).decode() #画像バイト列をBase64文字列に
            settings["bg_image_mime"] = st.session_state.get(
                "bg_file_mime", "image/png"
            ) #MIMEタイプも保存
        except Exception:
            pass #万一エラーが出てもアプリが止まらないようにする

    with open(SETTINGS_FILE, "w") as f: #JSONファイルとして保存
        json.dump(settings, f)


def load_shifts() -> None:
    """起動時にCSVがあれば読み込む(空ファイルは無視)"""
    if os.path.exists(DATA_FILE): #CSVファイルが存在するかチェック
        if os.path.getsize(DATA_FILE) == 0: #ファイルサイズが0なら中身なし
            st.session_state["shifts"] = [] #空リストとして初期化
            return

        try:
            df_loaded = pd.read_csv(DATA_FILE) #CSVを読み込み
        except pd.errors.EmptyDataError: #形式的には存在するが中身が空の場合
            st.session_state["shifts"] = []
            return

        if "date" in df_loaded.columns: #date列がある場合
            df_loaded["date"] = pd.to_datetime(df_loaded["date"]).dt.date #date列をdate型に変換
        st.session_state["shifts"] = df_loaded.to_dict(orient="records") #レコードのリストに変換して保存
    else:
        st.session_state["shifts"] = [] #ファイルがなければ空リストで初期化


def load_settings() -> Optional[Dict[str, Any]]:
    """設定ファイル(JSON)の読み込み＋テーマ＆背景画像＆勤務先設定の復元"""
    global WORKPLACE_SETTINGS, SHIFT_PATTERNS #グローバルな勤務先設定を更新するためglobal宣言

    if not os.path.exists(SETTINGS_FILE): #設定ファイルがない場合
        return None
    with open(SETTINGS_FILE, "r") as f: #JSONファイルを読み込み
        settings = json.load(f)

   #年度開始
    if "fiscal_start" in settings: #fiscal_startが含まれていればdate型に変換
        settings["fiscal_start"] = date.fromisoformat(settings["fiscal_start"])

   #勤務先設定をマスタにマージ
    ws = settings.get("workplace_settings") #JSON中の勤務先設定を取得
    if isinstance(ws, dict): #辞書として存在すれば
        for name, cfg in ws.items(): #各勤務先ごとの設定を
            if name in WORKPLACE_SETTINGS: #すでにある勤務先は上書きマージ
                WORKPLACE_SETTINGS[name].update(cfg)
            else: #新しい勤務先はそのまま追加
                WORKPLACE_SETTINGS[name] = cfg
    sp = settings.get("shift_patterns") #JSON中の勤務パターン設定を取得
    if isinstance(sp, dict): #辞書として存在すれば
        loaded_patterns = load_shift_patterns_from_settings(sp) #形式を変換して読み込み
        SHIFT_PATTERNS.update(loaded_patterns) #既存のパターンにマージ

   #テーマをセッションに反映
    theme_name = settings.get("theme_name") #設定からテーマ名取得
    if theme_name and "theme" not in st.session_state:
        st.session_state["theme"] = theme_name #セッションのテーマにセット

   #背景画像をセッションに復元
    bg_b64 = settings.get("bg_image_b64") #Base64文字列の背景画像
    if bg_b64:
        try:
            st.session_state["bg_file_bytes"] = base64.b64decode(bg_b64) #バイト列に戻す
            st.session_state["bg_file_mime"] = settings.get(
                "bg_image_mime", "image/png"
            ) #MIMEタイプも復元
        except Exception:
            pass #失敗してもアプリが落ちないようにする

    return settings #読み込んだ設定を返す


# シフト削除・複製関数
def DelAte(orig_index: int) -> None:
    """シフトを1件削除して即反映する関数(DelAteボタン用)"""
    if "shifts" not in st.session_state: #シフトがなければ何もしない
        return
    if 0 <= orig_index < len(st.session_state["shifts"]): #インデックスの範囲チェック
        st.session_state["shifts"].pop(orig_index) #指定インデックスのシフトを削除
        save_shifts() #CSVに保存
        st.success("シフトを削除しました。") #成功メッセージ
        st.rerun() #Streamlitアプリを再実行（画面更新）


def duplicate_shift(orig_index: int, new_date: date) -> None:
    """シフトを日付だけ変えて複製して即再描画"""
    if "shifts" not in st.session_state:
        return
    if 0 <= orig_index < len(st.session_state["shifts"]):
        new_item = st.session_state["shifts"][orig_index].copy() #元のシフトをコピー
        new_item["date"] = new_date #日付だけ新しい日付に変更
        st.session_state["shifts"].append(new_item) #シフトリストに追加
        save_shifts() #CSVに保存
        st.success(f"{new_date} にシフトを複製しました。") #メッセージ表示
        st.rerun() #再描画


### 休憩時間の自動計算
def get_auto_break_minutes(total_hours: float, workplace: str) -> int:
    """勤務時間と勤務先に応じて、自動で休憩時間（分）を計算"""
    settings = WORKPLACE_SETTINGS.get(workplace) #勤務先設定を取得
    if not settings: #なければ休憩0
        return 0
    rules = settings.get("break_rules", []) #休憩ルールリスト
    break_min = 0 #デフォルトは0分
    for rule in sorted(rules, key=lambda r: r["min_hours"]): #必要時間が小さい順にソート
        if total_hours >= rule["min_hours"]: #条件を満たすごとに休憩時間を更新
            break_min = rule["break_minutes"]
    return break_min #最も大きな条件を満たした休憩時間を返す


### 深夜・早朝の時間数を計算
def _range_intersection_hours(
    a_start: datetime, a_end: datetime, b_start: datetime, b_end: datetime
) -> float:
    """2つの時間帯[a_start, a_end], [b_start, b_end]の重なり時間（時間）を計算"""
    start = max(a_start, b_start) #重なり開始時刻
    end = min(a_end, b_end) #重なり終了時刻
    if start >= end: #重なりがない場合
        return 0.0
    return (end - start).total_seconds() / 3600 #差を秒で計算し、時間に変換


def _hours_in_window_non_crossing(
    start_dt: datetime, end_dt: datetime, window_start_hour: int, window_end_hour: int
) -> float:
    """日付をまたがない時間帯(例:5〜8時など)の重なり時間を計算"""
    total = 0.0 #合計時間
    day = start_dt.date() #開始日
    last_day = end_dt.date() #終了日
    while day <= last_day: #開始日から終了日までループ
        w_start = datetime.combine(day, time(window_start_hour, 0)) #当日の窓開始時刻
        w_end = datetime.combine(day, time(window_end_hour, 0)) #当日の窓終了時刻
        total += _range_intersection_hours(start_dt, end_dt, w_start, w_end) #重なり時間を加算
        day += timedelta(days=1) #日付を1日進める
    return total #合計時間を返す


def _hours_in_window_crossing(
    start_dt: datetime, end_dt: datetime, window_start_hour: int, window_end_hour: int
) -> float:
    """深夜のような「22〜5時」みたいに日付をまたぐ窓の重なり時間を計算"""
    total = 0.0 #合計時間
    day = start_dt.date() #開始日
    last_day = end_dt.date() #終了日
    while day <= last_day: #開始日から終了日まで
       #当日window_start〜24:00
        w1_start = datetime.combine(day, time(window_start_hour, 0)) #当日深夜開始
        w1_end = datetime.combine(day, time(23, 59, 59, 999999)) #当日末（ほぼ24時）
        total += _range_intersection_hours(start_dt, end_dt, w1_start, w1_end) #重なり時間加算

       #翌日0:00〜window_end
        next_day = day + timedelta(days=1) #翌日
        w2_start = datetime.combine(next_day, time(0, 0)) #0:00
        w2_end = datetime.combine(next_day, time(window_end_hour, 0)) #窓終了時刻
        total += _range_intersection_hours(start_dt, end_dt, w2_start, w2_end) #重なり時間加算

        day += timedelta(days=1) #日付を1日進める
    return total #合計時間を返す


def calc_night_early_hours(
    start_dt: datetime, end_dt: datetime, workplace: str
) -> tuple[float, float]:
    """指定の勤務先設定に基づいて、深夜時間・早朝時間（時間数）を返す"""
    settings = WORKPLACE_SETTINGS.get(workplace) #勤務先設定取得
    if not settings:
        return 0.0, 0.0

    night_start = settings.get("night_start", 22) #深夜開始時刻
    night_end = settings.get("night_end", 5) #深夜終了時刻
    early_start = settings.get("early_start", 5) #早朝開始時刻
    early_end = settings.get("early_end", 8) #早朝終了時刻

   #深夜時間の計算
    if night_start > night_end: #例: 22〜5時のように日付をまたぐ場合
        night_hours = _hours_in_window_crossing(start_dt, end_dt, night_start, night_end)
    else: #日付をまたがない場合
        night_hours = _hours_in_window_non_crossing(start_dt, end_dt, night_start, night_end)

   #早朝時間の計算
    if early_start < early_end: #例: 5〜8時のように日付をまたがない場合
        early_hours = _hours_in_window_non_crossing(start_dt, end_dt, early_start, early_end)
    else: #日付をまたぐ場合
        early_hours = _hours_in_window_crossing(start_dt, end_dt, early_start, early_end)

    return night_hours, early_hours #(深夜時間, 早朝時間) を返す


### 1レコード分の給与計算を行う共通関数（型ヒント付き）
def calc_pay_for_shift(shift: Dict[str, Any]) -> Dict[str, Any]:
    """
    1件分のシフト情報から、給与関連の項目を計算して埋める。

    必要な入力:
        shift["workplace"] : str
        shift["work_hours"]: float
        shift["night_hours"]: float
        shift["early_hours"]: float
        shift["wage"]      : int
        shift["is_busy"]   : bool

    追加・更新される出力:
        shift["base_pay"]   : int
        shift["night_bonus"]: int
        shift["early_bonus"]: int
        shift["busy_bonus"] : int
        shift["pay"]        : int
    """
    workplace = str(shift.get("workplace", "")) #勤務先名を取得
    settings_wp = WORKPLACE_SETTINGS.get(workplace, {}) #勤務先設定を取得（なければ空dict）

    work_hours = float(shift.get("work_hours", 0.0)) #実働時間（休憩控除後）を取得
    night_hours = float(shift.get("night_hours", 0.0)) #深夜労働時間
    early_hours = float(shift.get("early_hours", 0.0)) #早朝労働時間
    wage = int(shift.get("wage", 0)) #時給
    is_busy = bool(shift.get("is_busy", False)) #繁忙期フラグ

    night_rate = settings_wp.get("night_rate", 1.0) #深夜割増率
    early_bonus_per_hour = settings_wp.get("early_bonus_per_hour", 0.0) #早朝手当（円/h）
    busy_bonus_per_hour = settings_wp.get("busy_bonus_per_hour", 0.0) #繁忙期手当（円/h）

    base_pay = work_hours * wage #基本給 = 実働時間 × 時給
    night_bonus = night_hours * wage * max(night_rate - 1.0, 0) #深夜割増分
    early_bonus = early_hours * early_bonus_per_hour #早朝手当
    busy_bonus = work_hours * busy_bonus_per_hour if is_busy else 0.0 #繁忙期手当（繁忙期のみ）
    pay = int(round(base_pay + night_bonus + early_bonus + busy_bonus)) #合計支給額

    shift["base_pay"] = int(round(base_pay)) #基本給（整数）
    shift["night_bonus"] = int(round(night_bonus)) #深夜手当
    shift["early_bonus"] = int(round(early_bonus)) #早朝手当
    shift["busy_bonus"] = int(round(busy_bonus)) #繁忙期手当
    shift["pay"] = pay #合計給料

    return shift #結果を含んだシフトdictを返す


### 初期データ・設定読み込み
if "shifts" not in st.session_state: #初回アクセス時など、セッションにシフトがない場合
    load_shifts() #CSVから読み込む

loaded_settings = load_settings() #設定ファイル(JSON)の読み込み
if loaded_settings:
    default_limit = loaded_settings.get("limit_income", 1030000) #扶養上限のデフォルト
    default_fiscal = loaded_settings.get("fiscal_start", date(date.today().year, 1, 1)) #集計開始日
    default_theme = loaded_settings.get("theme_name", THEME_OPTIONS[0]) #テーマ
else:
    default_limit = 1030000 #デフォルト扶養上限
    default_fiscal = date(date.today().year, 1, 1) #当年1月1日
    default_theme = THEME_OPTIONS[0] #テーマ初期値

if "theme" not in st.session_state: #セッションにテーマがまだない場合
    st.session_state["theme"] = default_theme #デフォルトテーマをセット


# サイドバー：ページ切り替え＆設定
st.sidebar.header("表示 / 設定") #サイドバーのヘッダー表示

page = st.sidebar.radio(
    "表示ページを選択",
    ["カレンダー", "シフト一覧", "勤務先設定"], #ページの選択肢
    index=0, #初期選択は「カレンダー」
)

# 背景テーマ選択
theme_index = (
    THEME_OPTIONS.index(st.session_state["theme"])
    if st.session_state["theme"] in THEME_OPTIONS
    else 0
) #現在のテーマのインデックスを取得
theme_name = st.sidebar.selectbox("背景テーマ", THEME_OPTIONS, index=theme_index) #テーマ選択
st.session_state["theme"] = theme_name #セッションのテーマを更新

limit_income = st.sidebar.number_input(
    "扶養の上限金額（円）", min_value=0, value=default_limit, step=10000 #扶養上限の入力
)

fiscal_start = st.sidebar.date_input(
    "集計開始日（年度のスタート）", value=default_fiscal #集計開始日の入力
)


# カレンダー背景用画像アップロード
bg_file = st.sidebar.file_uploader("カレンダー背景画像（任意）", type=["png", "jpg", "jpeg"]) #背景画像のアップロード
if bg_file is not None: #ファイルがアップロードされた場合
    st.session_state["bg_file_bytes"] = bg_file.getvalue() #バイト列としてセッションに保存
    st.session_state["bg_file_mime"] = bg_file.type #MIMEタイプを保存

# テーマ or 背景画像に応じたCSSを生成
bg_bytes = st.session_state.get("bg_file_bytes") #セッションから背景画像バイト列取得
bg_mime = st.session_state.get("bg_file_mime", "image/png") #MIMEタイプ（なければPNG）

if bg_bytes: #画像がある場合
    encoded = base64.b64encode(bg_bytes).decode() #Base64文字列に変換
    bg_style = f"""
        background-image:
            linear-gradient(rgba(0, 0, 0, 0.1), rgba(0, 0, 0, 0.1)),
            url("data:{bg_mime};base64,{encoded}");
        background-size: cover;
        background-position: center;
    """ #背景画像を画面全体に表示するCSS
else: #画像がない場合はテーマごとのグラデーション背景
    if theme_name == "スタバグリーン":
        bg_style = "background: linear-gradient(135deg, #dfe7e1, #9ad0b1);" #緑系グラデーション
    elif theme_name == "ネイビーダーク":
        bg_style = "background: linear-gradient(135deg, #1f2937, #111827);" #ダークネイビー
    elif theme_name == "パステルピンク":
        bg_style = "background: linear-gradient(135deg, #ffe4ec, #ffd1dc);" #パステルピンク
    else:
        bg_style = "background-color: #f5f5f5;" #シンプルな薄いグレー背景

page_bg_css = f"""
<style>
[data-testid="stAppViewContainer"] {{
    {bg_style}
}}

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
""" #ページ全体の見た目を整えるCSS
st.markdown(page_bg_css, unsafe_allow_html=True) #CSSをHTMLとして適用


# シフト入力フォーム(カレンダー / シフト一覧ページ共通)
if page in ("カレンダー", "シフト一覧"): #カレンダーとシフト一覧の両ページで入力フォームを表示
    st.subheader("シフト入力") #セクションタイトル
    st.markdown('<div class="shift-card">', unsafe_allow_html=True) #カード風の枠開始
    with st.form("shift_form", clear_on_submit=True): #フォーム（送信後はクリア）
       #勤務パターン選択
        pattern_names = ["（パターンを使わない）"] + list(SHIFT_PATTERNS.keys()) #パターンの選択肢リスト
        selected_pattern = st.selectbox("勤務パターン（任意）", pattern_names) #パターン選択

       #日付を先に決める（時給改定に使う）
        shift_date = st.date_input("日付", value=date.today(), key="shift_date") #シフト日付の入力

       #パターンに応じてデフォルト値を決める
        pattern = SHIFT_PATTERNS.get(selected_pattern) if selected_pattern != "（パターンを使わない）" else None #選択パターン取得

        if pattern is not None: #パターンが選ばれている場合
            default_workplace = pattern.get("workplace", "すたば") #パターンから勤務先
            default_start = pattern.get("start", time(18, 0)) #パターンから開始時刻
            default_end = pattern.get("end", time(23, 0)) #パターンから終了時刻
            pattern_wage = pattern.get("wage") #パターンの時給
            default_manual_break = pattern.get("manual_break_min", 0) #パターンの休憩
            default_transport = pattern.get("transport", 0) #パターンの交通費
        else: #パターン未使用時のデフォルト
            default_workplace = "すたば"
            default_start = time(18, 0)
            default_end = time(23, 0)
            pattern_wage = None
            default_manual_break = 0
            default_transport = 0

        col1, col2 = st.columns(2) #入力欄を2列に分割
        with col1:
            workplace = st.text_input(
                "バイト先(例：すたば / 駿台 / C / D)",
                value=default_workplace,
            ) #勤務先名の入力
            start_time = st.time_input("開始時刻", value=default_start) #開始時刻の入力
        with col2:
           #時給のデフォルト値：パターン優先、なければ履歴から自動計算
            if pattern_wage is not None: #パターンに時給が指定されていればそれを使用
                default_wage = pattern_wage
            else: #それ以外は日付に応じたdefault_wage
                default_wage = get_default_wage_for_date(workplace, shift_date)

            wage = st.number_input(
                "時給（円）",
                min_value=0,
                value=default_wage,
                step=10,
            ) #時給入力

            manual_break_min = st.number_input(
                "休憩(分) (0なら勤務先のルールから自動計算)",
                min_value=0,
                value=default_manual_break,
                step=5,
            ) #休憩時間の手動指定

            is_busy = st.checkbox("繁忙期（手当適用）", value=False) #繁忙期フラグ

            transport = st.number_input(
                "交通費（円）",
                min_value=0,
                value=default_transport,
                step=10,
            ) #交通費入力

            end_time = st.time_input("終了時刻", value=default_end) #終了時刻の入力

       #メモ欄
        memo = st.text_input("メモ（任意）", "") #メモテキスト入力

        submitted = st.form_submit_button("このシフトを追加") #フォーム送信ボタン
        if submitted: #ボタンが押されたら
            start_dt = datetime.combine(shift_date, start_time) #日付と開始時刻からdatetimeを生成
            end_dt = datetime.combine(shift_date, end_time) #日付と終了時刻からdatetimeを生成

            settings_wp = WORKPLACE_SETTINGS.get(workplace, {}) #勤務先設定を取得
            pre_min = settings_wp.get("pre_minutes", 0) #開始前の付け時間
            post_min = settings_wp.get("post_minutes", 0) #終了後の付け時間

            start_dt_for_pay = start_dt - timedelta(minutes=pre_min) #給与計算上の開始時刻
            end_dt_for_pay = end_dt + timedelta(minutes=post_min) #給与計算上の終了時刻

            total_hours = (end_dt_for_pay - start_dt_for_pay).total_seconds() / 3600 #合計時間（付け時間込み）

            if total_hours <= 0: #終了が開始より早い or 同じ場合はエラー
                st.error("終了時刻が開始時刻より前になっていませんか？")
            else:
                if manual_break_min > 0: #休憩が手動入力されている場合
                    break_minutes = manual_break_min
                else: #自動計算
                    break_minutes = get_auto_break_minutes(total_hours, workplace)

                paid_hours = total_hours - break_minutes / 60.0 #実働時間 = 合計時間 − 休憩時間
                if paid_hours < 0: #念のため0未満にならないように
                    paid_hours = 0

                night_hours, early_hours = calc_night_early_hours(
                    start_dt_for_pay, end_dt_for_pay, workplace
                ) #深夜・早朝時間を計算

                if "shifts" not in st.session_state: #セッションにシフトリストがなければ初期化
                    st.session_state["shifts"] = []

               #ここで1レコード分を組み立て → calc_pay_for_shift で給与計算
                shift_record: Dict[str, Any] = { #シフト1件分の辞書を作成
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
                    "is_busy": is_busy,
                    "memo": memo,
                }
                shift_record = calc_pay_for_shift(shift_record) #共通関数で給与関連を計算

                st.session_state["shifts"].append(shift_record) #シフトリストに追加
                save_shifts() #CSVへ保存
                st.success("シフトを追加しました！") #成功メッセージ
    st.markdown('</div>', unsafe_allow_html=True) #カード枠の終了


# シフトがない場合
if "shifts" not in st.session_state or len(st.session_state["shifts"]) == 0: #シフトが一件もない場合
    st.info("まだシフトがありません。上のフォームから追加してください。") #メッセージ表示
    save_settings(limit_income, fiscal_start, theme_name, WORKPLACE_SETTINGS) #設定保存
    raise SystemExit #以降の処理を中断して終了


# ここからはシフトがある前提
df = pd.DataFrame(st.session_state["shifts"]) #シフトリストをDataFrameに変換
df["date"] = pd.to_datetime(df["date"]) #date列をdatetime型に変換

# 欠損カラム対策（古いCSVなどでも動くように）
if "work_hours" not in df.columns: #work_hours列がない場合
    df["work_hours"] = 0.0
df["work_hours"] = df["work_hours"].fillna(0.0) #NaNは0に置き換え

if "transport" not in df.columns: #transport列がない場合
    df["transport"] = 0
df["transport"] = df["transport"].fillna(0).astype(int) #NaNを0にしintへ

if "busy_bonus" not in df.columns: #busy_bonus列がない場合
    df["busy_bonus"] = 0
df["busy_bonus"] = df["busy_bonus"].fillna(0).astype(int)

if "memo" not in df.columns: #memo列がない場合
    df["memo"] = ""
df["memo"] = df["memo"].fillna("") #NaNを空文字に

df_period = df[df["date"] >= pd.to_datetime(fiscal_start)] #集計開始日以降のデータだけ抽出

total_income = df_period["pay"].sum() #期間内の支給合計
by_workplace = df_period.groupby("workplace")["pay"].sum().reset_index() #勤務先ごとの合計支給額

df_period["year_month"] = df_period["date"].dt.to_period("M").astype(str) #年月（YYYY-MM形式）の列を追加
by_month = (
    df_period
    .groupby("year_month")
    .agg(
        total_pay=("pay", "sum"),
        total_hours=("work_hours", "sum"),
    )
    .reset_index()
    .sort_values("year_month")
) #月ごとの給与合計と勤務時間合計を集計
by_month["total_hours"] = by_month["total_hours"].round(2) #勤務時間を小数2桁に丸める
by_month = by_month.rename(
    columns={
        "year_month": "年月",
        "total_pay": "給与合計(円)",
        "total_hours": "勤務時間合計(h)",
    }
) #列名を日本語に変更


### ページ1：カレンダー表示(Main)
if page == "カレンダー": #カレンダーページ
    st.subheader("🗓 カレンダー表示(Main)") #セクションタイトル

    default_date = date.today() #デフォルトの日付は今日
    selected_date = st.date_input("表示する月を選択", value=default_date, key="cal_month") #表示対象の月を選択
    y = selected_date.year #年
    m = selected_date.month #月

    st.markdown(f"### {y}年 {m}月 のシフト") #見出し表示

   #この月のデータを抽出
    target_period = f"{y}-{m:02d}" #"YYYY-MM"形式の文字列
    df_month = df[df["date"].dt.to_period("M").astype(str) == target_period] #指定年月に属する行のみ抽出

   #カレンダー構造
    cal = calendar.Calendar(firstweekday=0) #月曜始まりのカレンダー（0=月曜）
    weeks = cal.monthdatescalendar(y, m) #表示対象月の「週ごとの日付リスト」を取得

   #カレンダー表示用テーブルデータ（HTML＋ツールチップ）
    table_data = [] #カレンダー用テーブルのデータ
    for week in weeks: #各週について
        row = [] #1週間分の行
        for d in week: #週の各日付について
            if d.month != m: #前後の月の日付の場合は空欄
                row.append("")
                continue

            day_shifts = df_month[df_month["date"].dt.date == d] #その日のシフトを抽出
            if day_shifts.empty: #シフトがない場合
                cell = f"{d.day}" #日付のみ
            else: #シフトがある場合
                total_pay = int(day_shifts["pay"].sum()) #その日の支給額合計
                total_hours = float(day_shifts["work_hours"].sum()) #その日の勤務時間合計
                wp_list = sorted(day_shifts["workplace"].unique()) #勤務先名の一覧
                wp_str = ", ".join(wp_list) #勤務先名をカンマ区切り文字列に

               #ツールチップ（title）用テキスト（改行は&#10;）
                tooltip_text = (
                    f"{d.strftime('%Y-%m-%d')}&#10;"
                    f"勤務時間: {total_hours:.2f}h&#10;"
                    f"給与: {total_pay:,}円"
                )
                display_str = f"{d.day}<br>{total_pay:,}円<br>{wp_str}" #セルに表示するHTML文字列
                cell = f'<span title="{tooltip_text}">{display_str}</span>' #title属性でツールチップ
            row.append(cell) #行にセルを追加
        table_data.append(row) #テーブルデータに行を追加

        cal_df = pd.DataFrame(
        table_data,
        columns=["月", "火", "水", "木", "金", "土", "日"],
    )  # カレンダーのテーブルとしてDataFrame化

    # --- 日曜 / 祝日 / シフト有りセルのスタイルを作る ---
    # cal_df と同じ形の「CSS文字列」のDataFrameを用意
    style_df = pd.DataFrame(
        "",
        index=cal_df.index,
        columns=cal_df.columns,
    )

    for row_idx, week in enumerate(weeks):
        for col_idx, d in enumerate(week):
            # 前後の月の日付の場合はグレー背景
            if d.month != m:
                style = "background-color: rgba(245, 245, 245, 0.9); color: #999;"
            else:
                # 基本は白背景
                style = "background-color: rgba(255, 255, 255, 0.95); color: #000;"

                # Pythonの weekday(): 月=0, …, 日=6
                # → 日曜日は濃いめの赤背景＋赤文字
                if d.weekday() == 6:
                    style = "background-color: rgba(255, 230, 230, 0.95); color: #c00;"
                # 日曜以外の祝日は薄い赤背景＋赤文字
                elif jpholiday.is_holiday(d):
                    style = "background-color: rgba(255, 240, 240, 0.95); color: #c00;"

                # このセルにシフトが入っているかどうか（表示文字列に「円」が含まれる）
                cell_val = cal_df.iloc[row_idx, col_idx]
                if isinstance(cell_val, str) and "円" in cell_val:
                    # 背景色は上の（日曜 / 祝日 / 通常）のまま、
                    # 枠線＋太字で「シフトあり」を強調
                    style += " font-weight: 600; border: 1px solid rgba(255, 200, 0, 0.9);"

            style_df.iloc[row_idx, col_idx] = style

    def highlight_calendar(_df: pd.DataFrame) -> pd.DataFrame:
        """cal_df と同じ形の CSS DataFrame を返す"""
        return style_df

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
    # ★ axis=None で「テーブル全体」に対して style_df を返す関数を適用
    cal_styler = cal_df.style.apply(highlight_calendar, axis=None)
    st.markdown(cal_styler.to_html(), unsafe_allow_html=True)
    st.markdown('</div>', unsafe_allow_html=True)


    month_total = int(df_month["pay"].sum()) if not df_month.empty else 0 #月合計支給額
    month_hours = float(df_month["work_hours"].sum()) if not df_month.empty else 0.0 #月合計勤務時間
    st.markdown(
        f"#### {y}年{m}月の合計：**{month_total:,} 円 / {month_hours:.2f} h**"
    ) #月合計の表示

   #日付クリックでその日の詳細表示（ボタン式カレンダー）
    st.markdown("#### 日別のシフト詳細（下の日付ボタンをクリック）") #説明文

    detail_date = st.session_state.get("detail_date") #直近でクリックされた日付をセッションから取得

    for week in weeks: #週ごとにボタンを並べる
        cols = st.columns(7) #7列（曜日分）を用意
        for col, d in zip(cols, week):
            with col:
                if d.month != m: #他の月の日付は空白
                    st.write(" ")
                else:
                    day_shifts = df_month[df_month["date"].dt.date == d] #当日のシフト
                    if day_shifts.empty:
                        label = f"{d.day}" #シフトなしは日付のみ
                    else:
                        total_pay = int(day_shifts["pay"].sum()) #その日合計の給料
                        label = f"{d.day}\n{total_pay:,}円" #ボタンラベルに給料も表示
                    if st.button(label, key=f"detail_btn_{d.isoformat()}"): #日付ボタン
                        st.session_state["detail_date"] = d #セッションに保存
                        detail_date = d #ローカル変数も更新

    if detail_date is not None and detail_date.year == y and detail_date.month == m: #同じ月の詳細のみ表示
        day_shifts = df_month[df_month["date"].dt.date == detail_date] #詳細対象日のシフト
        st.markdown(f"##### {detail_date} のシフト一覧") #見出し
        if day_shifts.empty:
            st.info("この日にはシフトはありません。") #シフトなしの場合
        else:
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
                "memo",
            ] #表示したい列
            show_cols = [c for c in show_cols if c in day_shifts.columns] #存在する列だけに絞る
            st.table(day_shifts[show_cols]) #テーブル表示


# ページ2:シフト一覧(表＋扶養チェック＋削除&複製＋一括操作＋データチェック)
elif page == "シフト一覧":
    st.subheader("シフト一覧（テーブル表示）") #セクションタイトル

   #絞り込み・並び替え UI
    st.markdown("### 絞り込み・並び替え") #絞り込みセクション見出し
    workplaces = sorted(df["workplace"].dropna().unique().tolist()) #勤務先のユニーク一覧
    selected_workplaces = st.multiselect(
        "バイト先フィルタ", workplaces, default=workplaces
    ) #勤務先でフィルタするマルチセレクト

    min_date = df["date"].min().date() #シフトの最小日付
    max_date = df["date"].max().date() #シフトの最大日付
    col_f1, col_f2, col_f3 = st.columns(3) #日付範囲＆並び替えの3列
    with col_f1:
        filter_start = st.date_input(
            "開始日フィルタ", value=min_date, min_value=min_date, max_value=max_date, key="filter_start"
        ) #フィルタ用開始日
    with col_f2:
        filter_end = st.date_input(
            "終了日フィルタ", value=max_date, min_value=min_date, max_value=max_date, key="filter_end"
        ) #フィルタ用終了日
    with col_f3:
        sort_option = st.selectbox(
            "並び替え",
            [
                "日付昇順",
                "日付降順",
                "勤務時間（長い順）",
                "勤務時間（短い順）",
                "給料（高い順）",
                "給料（低い順）",
            ],
        ) #並び替え条件の選択

    df_filtered = df.copy() #フィルタリング用にコピー
    df_filtered = df_filtered[
        (df_filtered["date"].dt.date >= filter_start)
        & (df_filtered["date"].dt.date <= filter_end)
    ] #日付範囲でのフィルタ
    if selected_workplaces: #勤務先フィルタがある場合
        df_filtered = df_filtered[df_filtered["workplace"].isin(selected_workplaces)]

   #並び替え
    if sort_option == "日付昇順":
        df_sorted = df_filtered.sort_values("date", ascending=True)
    elif sort_option == "日付降順":
        df_sorted = df_filtered.sort_values("date", ascending=False)
    elif sort_option == "勤務時間（長い順）":
        df_sorted = df_filtered.sort_values("work_hours", ascending=False)
    elif sort_option == "勤務時間（短い順）":
        df_sorted = df_filtered.sort_values("work_hours", ascending=True)
    elif sort_option == "給料（高い順）":
        df_sorted = df_filtered.sort_values("pay", ascending=False)
    elif sort_option == "給料（低い順）":
        df_sorted = df_filtered.sort_values("pay", ascending=True)
    else:
        df_sorted = df_filtered.sort_values("date", ascending=True) #デフォルトは日付昇順

    if df_sorted.empty: #フィルタ結果が空の場合
        st.info("この条件に一致するシフトはありません。")
    else:
        styled_df = df_sorted.style.apply(color_by_workplace, axis=1) #行ごとに勤務先カラーを適用
        st.dataframe(styled_df, width=True) #ソート・フィルタ後のDataFrame表示

    st.markdown("### シフトの削除・複製・一括操作") #操作セクション見出し

    df_ops = df_sorted.reset_index() if not df_sorted.empty else pd.DataFrame() #元インデックスを保持したDataFrame
    selected_indices: list[int] = [] #一括操作対象として選択されたインデックスリスト

    for _, row in df_ops.iterrows(): #表示されている各シフト行について
        orig_idx = int(row["index"]) #元のインデックス（st.session_state["shifts"] 上の位置）

        with st.container(): #1行分のUIコンテナ
            cols = st.columns([0.5, 4.5, 3, 1, 1]) #チェックボックス/情報/複製日付/duplicateボタン/deleteボタン

            with cols[0]:
                checked = st.checkbox("", key=f"select_{orig_idx}") #一括操作用チェックボックス
                if checked:
                    selected_indices.append(orig_idx) #チェックされたインデックスを保存

            with cols[1]:
                memo_str = f" / メモ: {row['memo']}" if row.get("memo") else "" #メモがあれば表示用文字列を作る
                st.write(
                    f"**{row['date'].date()}** "
                    f"{row['start']} - {row['end']}  "
                    f"（{row['workplace']} / {row['work_hours']}h / {row['pay']}円 / 交通費{row['transport']}円{memo_str}）"
                ) #シフト概要表示

            with cols[2]:
                new_date = st.date_input(
                    "複製先の日付",
                    value=row["date"].date(),
                    key=f"copy_date_{orig_idx}",
                ) #複製先の日付入力

            with cols[3]:
                if st.button("Duplicate", key=f"copy_btn_{orig_idx}"): #複製ボタン
                    duplicate_shift(orig_idx, new_date) #シフトを複製

            with cols[4]:
                if st.button("DelAte", key=f"delete_btn_{orig_idx}"): #削除ボタン
                    DelAte(orig_idx) #シフトを削除

   #一括削除・一括編集
    st.markdown("#### 一括削除・一括編集") #一括操作セクション見出し

    col_bulk1, col_bulk2 = st.columns(2) #一括削除と一括編集を2列に分ける
    with col_bulk1:
        if st.button("選択したシフトを削除"): #一括削除ボタン
            if not selected_indices: #一つも選択されていない場合
                st.info("削除する行が選択されていません。")
            else:
                st.session_state["shifts"] = [
                    s for i, s in enumerate(st.session_state["shifts"]) if i not in selected_indices
                ] #選択されていないレコードだけ残す
                save_shifts() #CSV保存
                st.success(f"{len(selected_indices)}件のシフトを削除しました。") #成功メッセージ
                st.rerun() #再描画

    with col_bulk2:
        with st.expander("選択したシフトを一括編集（バイト先・時給・メモ）"): #一括編集の詳細設定
            new_workplace = st.text_input("新しいバイト先（空欄なら変更しない）", "") #変更後の勤務先
            new_wage = st.number_input(
                "新しい時給（0なら変更しない）", min_value=0, value=0, step=10
            ) #変更後の時給
            new_memo = st.text_input("新しいメモ（空欄なら変更しない）", "") #変更後のメモ

            if st.button("一括編集を適用"): #一括編集実行ボタン
                if not selected_indices:
                    st.info("編集する行が選択されていません。")
                else:
                    for idx in selected_indices: #選択された全レコードに対して
                        if 0 <= idx < len(st.session_state["shifts"]):
                            shift = st.session_state["shifts"][idx] #対象シフトを取得
                            if new_workplace: #勤務先の変更指定があれば上書き
                                shift["workplace"] = new_workplace
                            if new_wage > 0: #時給の変更指定があれば上書き
                                shift["wage"] = int(new_wage)
                            if new_memo: #メモの変更指定があれば上書き
                                shift["memo"] = new_memo
                           #給与関連を再計算（共通関数を利用）
                            calc_pay_for_shift(shift)

                    save_shifts() #変更内容を保存
                    st.success(f"{len(selected_indices)}件のシフトを更新しました。") #成功メッセージ
                    st.rerun() #再描画

   #扶養チェック表示
    st.subheader("扶養チェック") #扶養チェックセクション

    remaining = limit_income - total_income #扶養上限までの残額
    col_a, col_b = st.columns(2) #メトリクスを2列に配置
    with col_a:
        st.metric("現在の年間合計（期間内）", f"{total_income:,} 円") #現在の合計所得
    with col_b:
        if remaining >= 0:
            st.metric("扶養上限までの残り", f"{remaining:,} 円") #残り余裕
        else:
            st.metric("扶養上限超過分", f"{-remaining:,} 円") #超過額

    if remaining < 0:
        st.error("扶養の上限を超えています。シフト調整を検討してください。") #扶養超過の警告
    elif remaining < 100000:
        st.warning("扶養の上限まであと10万円未満です。注意してください。") #10万円未満の注意
    else:
        st.success("まだ扶養の上限には余裕があります。") #余裕ありメッセージ

    st.subheader("バイト先ごとの年間合計（期間内）") #勤務先別合計セクション
    st.table(by_workplace) #勤務先別の支給合計をテーブル表示

    st.subheader("月ごとの勤務時間＆給料合計（期間内）") #月別合計セクション
    st.table(by_month) #月別集計をテーブル表示

   #交通費と繁忙期手当の集計
    total_transport = int(df_period["transport"].sum()) #期間内交通費合計
    total_busy_bonus = int(df_period["busy_bonus"].sum()) #期間内繁忙期手当合計

    st.subheader("交通費・繁忙期手当の集計（期間内）") #交通費・手当の集計セクション
    col_t1, col_t2, col_t3 = st.columns(3) #3つのメトリクス表示
    with col_t1:
        st.metric("交通費合計", f"{total_transport:,} 円") #交通費合計
    with col_t2:
        st.metric("繁忙期手当合計", f"{total_busy_bonus:,} 円") #繁忙期手当合計
    with col_t3:
        st.metric("給与＋交通費", f"{int(total_income + total_transport):,} 円") #給与＋交通費の合計

   #データチェック（品質管理）
    st.subheader("データチェック（品質管理）") #データチェックセクション
    issues: list[str] = [] #問題点メッセージのリスト

   #1) 終了時刻が開始時刻より前・同じ
    for _, row in df.iterrows():
        try:
            d = row["date"].date() #日付
            start_t = datetime.strptime(row["start"], "%H:%M").time() #開始時刻
            end_t = datetime.strptime(row["end"], "%H:%M").time() #終了時刻
            start_dt = datetime.combine(d, start_t) #開始datetime
            end_dt = datetime.combine(d, end_t) #終了datetime
            if end_dt <= start_dt: #終了が開始以前なら問題
                issues.append(
                    f"{d} {row['workplace']}: 終了時刻が開始時刻以前になっています（{row['start']}〜{row['end']}）"
                )
        except Exception:
            continue #パースに失敗した場合はスキップ

   #2) 同じ日・同じ勤務先で時間帯が重複
    for (d, wp), group in df.groupby([df["date"].dt.date, "workplace"]): #日付と勤務先でグルーピング
        intervals = [] #(開始datetime, 終了datetime, 開始文字列, 終了文字列) のリスト
        for _, r in group.iterrows():
            try:
                s_t = datetime.strptime(r["start"], "%H:%M").time()
                e_t = datetime.strptime(r["end"], "%H:%M").time()
                s_dt = datetime.combine(d, s_t)
                e_dt = datetime.combine(d, e_t)
                intervals.append((s_dt, e_dt, r["start"], r["end"]))
            except Exception:
                continue
        intervals.sort(key=lambda x: x[0]) #開始時間でソート
        for j in range(len(intervals) - 1):
            s1, e1, s1_str, e1_str = intervals[j]
            s2, e2, s2_str, e2_str = intervals[j + 1]
            if s2 < e1: #後のシフト開始が前のシフト終了より早ければ重複
                issues.append(
                    f"{d} {wp}: {s1_str}〜{e1_str} と {s2_str}〜{e2_str} のシフトが重複しています"
                )

   #3) 時給や勤務時間が0・負の値
    for _, row in df.iterrows():
        if row["wage"] <= 0: #時給が0以下
            issues.append(f"{row['date'].date()} {row['workplace']}: 時給が0以下になっています")
        if row["work_hours"] < 0: #勤務時間が負
            issues.append(f"{row['date'].date()} {row['workplace']}: 勤務時間が負の値になっています")
        if row["pay"] < 0: #給与が負
            issues.append(f"{row['date'].date()} {row['workplace']}: 給与が負の値になっています")

    if not issues: #問題が一つもなければ
        st.success("明らかな不整合は見つかりませんでした。")
    else: #問題があれば一覧表示
        st.warning(f"データにいくつか気になる点があります（{len(issues)}件）:")
        for msg in issues:
            st.write("・" + msg)

    csv = df.to_csv(index=False).encode("utf-8-sig") #DataFrameをCSV文字列にしてUTF-8(BOM付き)にエンコード
    st.download_button(
        "シフトデータをCSVでダウンロード",
        csv,
        "shifts.csv",
        "text/csv",
    ) #CSVダウンロードボタン

    st.subheader("CSVからシフトを読み込む（任意）") #CSV読み込みセクション
    uploaded = st.file_uploader("shifts.csv を選択", type="csv") #CSVファイルアップロード
    if uploaded is not None:
        df_uploaded = pd.read_csv(uploaded) #アップロードCSVを読み込む
        if "date" in df_uploaded.columns:
            df_uploaded["date"] = pd.to_datetime(df_uploaded["date"]).dt.date #date列をdate型に変換
        st.session_state["shifts"] = df_uploaded.to_dict(orient="records") #セッションに反映
        save_shifts() #CSVファイルとして保存
        st.success("CSVを読み込みました！ 画面を少しスクロールして確認してください。") #成功メッセージ


# ページ3：勤務先設定
elif page == "勤務先設定":
    st.subheader("勤務先ごとの設定（時給・時間帯など）") #勤務先設定のページタイトル
    st.info("各バイト先の設定を編集できます。変更後は下部の「勤務先設定を保存」ボタンを押してください。") #説明文

    for wp_name in sorted(WORKPLACE_SETTINGS.keys()): #勤務先ごとに設定フォームを表示
        settings_wp = WORKPLACE_SETTINGS[wp_name] #勤務先設定
        with st.expander(f"{wp_name} の設定", expanded=False): #折りたたみの枠
            col1, col2 = st.columns(2) #左右2列に分けて入力

            with col1:
                default_wage = st.number_input(
                    f"{wp_name} の基本時給",
                    min_value=0,
                    value=int(settings_wp.get("default_wage", 1100)),
                    step=10,
                    key=f"{wp_name}_default_wage",
                ) #基本時給入力
                pre_minutes = st.number_input(
                    "前後の付け時間（前, 分）",
                    min_value=0,
                    value=int(settings_wp.get("pre_minutes", 0)),
                    step=1,
                    key=f"{wp_name}_pre_minutes",
                ) #開始前付け時間
                post_minutes = st.number_input(
                    "前後の付け時間（後, 分）",
                    min_value=0,
                    value=int(settings_wp.get("post_minutes", 0)),
                    step=1,
                    key=f"{wp_name}_post_minutes",
                ) #終了後付け時間
                night_start = st.number_input(
                    "深夜時間帯の開始時刻（時）",
                    min_value=0,
                    max_value=23,
                    value=int(settings_wp.get("night_start", 22)),
                    step=1,
                    key=f"{wp_name}_night_start",
                ) #深夜開始時刻
                night_end = st.number_input(
                    "深夜時間帯の終了時刻（時）",
                    min_value=0,
                    max_value=23,
                    value=int(settings_wp.get("night_end", 5)),
                    step=1,
                    key=f"{wp_name}_night_end",
                ) #深夜終了時刻
                night_rate = st.number_input(
                    "深夜割増率（例: 1.25）",
                    min_value=0.0,
                    value=float(settings_wp.get("night_rate", 1.25)),
                    step=0.05,
                    format="%.2f",
                    key=f"{wp_name}_night_rate",
                ) #深夜割増率

            with col2:
                early_start = st.number_input(
                    "早朝手当の開始時刻（時）",
                    min_value=0,
                    max_value=23,
                    value=int(settings_wp.get("early_start", 5)),
                    step=1,
                    key=f"{wp_name}_early_start",
                ) #早朝開始時刻
                early_end = st.number_input(
                    "早朝手当の終了時刻（時）",
                    min_value=0,
                    max_value=23,
                    value=int(settings_wp.get("early_end", 8)),
                    step=1,
                    key=f"{wp_name}_early_end",
                ) #早朝終了時刻
                early_bonus_per_hour = st.number_input(
                    "早朝手当（円/h）",
                    min_value=0.0,
                    value=float(settings_wp.get("early_bonus_per_hour", 0.0)),
                    step=10.0,
                    key=f"{wp_name}_early_bonus",
                ) #早朝手当（円/時間）
                busy_bonus_per_hour = st.number_input(
                    "繁忙期手当（円/h）",
                    min_value=0.0,
                    value=float(settings_wp.get("busy_bonus_per_hour", 0.0)),
                    step=10.0,
                    key=f"{wp_name}_busy_bonus",
                ) #繁忙期手当（円/時間）

           #入力値を即マスタに反映
            settings_wp["default_wage"] = int(default_wage)
            settings_wp["pre_minutes"] = int(pre_minutes)
            settings_wp["post_minutes"] = int(post_minutes)
            settings_wp["night_start"] = int(night_start)
            settings_wp["night_end"] = int(night_end)
            settings_wp["night_rate"] = float(night_rate)
            settings_wp["early_start"] = int(early_start)
            settings_wp["early_end"] = int(early_end)
            settings_wp["early_bonus_per_hour"] = float(early_bonus_per_hour)
            settings_wp["busy_bonus_per_hour"] = float(busy_bonus_per_hour)
    
        # --- 勤務パターン設定 -------------------------------------------------
    st.subheader("勤務パターン設定")
    st.caption("シフト入力画面の「勤務パターン（任意）」で選べるプリセットを編集できます。")

    pattern_names = sorted(SHIFT_PATTERNS.keys())
    for pname in pattern_names:
        pattern = SHIFT_PATTERNS[pname]
        with st.expander(pname, expanded=False):
            col1, col2, col3 = st.columns(3)

            # 勤務先
            with col1:
                wp_options = list(WORKPLACE_SETTINGS.keys())
                current_wp = pattern.get("workplace", wp_options[0] if wp_options else "")
                if current_wp not in wp_options and wp_options:
                    current_wp = wp_options[0]
                workplace = st.selectbox(
                    "勤務先",
                    wp_options,
                    index=wp_options.index(current_wp) if wp_options else 0,
                    key=f"{pname}_wp",
                )

            # 開始・終了時刻
            with col2:
                start_default = pattern.get("start", time(18, 0))
                end_default = pattern.get("end", time(22, 0))
                start_t = st.time_input(
                    "開始時刻",
                    value=start_default,
                    key=f"{pname}_start",
                )
                end_t = st.time_input(
                    "終了時刻",
                    value=end_default,
                    key=f"{pname}_end",
                )

            # 時給・休憩・交通費
            with col3:
                wage_default = pattern.get("wage")
                wage_value = st.number_input(
                    "時給（0で勤務先デフォルト）",
                    min_value=0,
                    value=int(wage_default) if isinstance(wage_default, (int, float)) else 0,
                    step=10,
                    key=f"{pname}_wage",
                )
                break_min = st.number_input(
                    "手動休憩（分）",
                    min_value=0,
                    value=int(pattern.get("manual_break_min", 0)),
                    step=5,
                    key=f"{pname}_break",
                )
                transport = st.number_input(
                    "交通費",
                    min_value=0,
                    value=int(pattern.get("transport", 0)),
                    step=10,
                    key=f"{pname}_transport",
                )

            # 入力値を即 SHIFT_PATTERNS に反映
            SHIFT_PATTERNS[pname]["workplace"] = workplace
            SHIFT_PATTERNS[pname]["start"] = start_t
            SHIFT_PATTERNS[pname]["end"] = end_t
            SHIFT_PATTERNS[pname]["wage"] = int(wage_value) if wage_value > 0 else None
            SHIFT_PATTERNS[pname]["manual_break_min"] = int(break_min)
            SHIFT_PATTERNS[pname]["transport"] = int(transport)

            # 削除ボタン
            if st.button("このパターンを削除", key=f"{pname}_delete"):
                deleted = st.session_state.get("delete_patterns", [])
                deleted.append(pname)
                st.session_state["delete_patterns"] = deleted

    # 削除指定されたパターンをまとめて削除
    deleted = st.session_state.get("delete_patterns", [])
    if deleted:
        for pname in deleted:
            SHIFT_PATTERNS.pop(pname, None)
        st.session_state["delete_patterns"] = []
        st.success("選択した勤務パターンを削除しました。")

    st.markdown("---")
    st.markdown("##### 新しい勤務パターンを追加")

    new_name = st.text_input("パターン名（例：すたば:18-CL2）", key="new_pattern_name")

    col_n1, col_n2, col_n3 = st.columns(3)
    with col_n1:
        wp_options = list(WORKPLACE_SETTINGS.keys())
        new_wp = st.selectbox(
            "勤務先",
            wp_options,
            index=0 if wp_options else 0,
            key="new_pattern_wp",
        )
    with col_n2:
        new_start = st.time_input("開始時刻", value=time(18, 0), key="new_pattern_start")
        new_end = st.time_input("終了時刻", value=time(22, 0), key="new_pattern_end")
    with col_n3:
        new_wage = st.number_input(
            "時給",
            min_value=0,
            value=1100,
            step=10,
            key="new_pattern_wage",
        )
        new_break = st.number_input(
            "手動休憩（分）",
            min_value=0,
            value=0,
            step=5,
            key="new_pattern_break",
        )
        new_transport = st.number_input(
            "交通費",
            min_value=0,
            value=0,
            step=10,
            key="new_pattern_transport",
        )

    if st.button("パターンを追加", key="add_pattern"):
        if not new_name.strip():
            st.warning("パターン名を入力してください。")
        elif new_name in SHIFT_PATTERNS:
            st.warning("同じ名前のパターンが既に存在します。")
        else:
            SHIFT_PATTERNS[new_name] = {
                "workplace": new_wp,
                "start": new_start,
                "end": new_end,
                "wage": int(new_wage),
                "manual_break_min": int(new_break),
                "transport": int(new_transport),
            }
            st.success(f"勤務パターン「{new_name}」を追加しました。")

    if st.button("勤務先設定を保存"): #勤務先設定の保存ボタン
        save_settings(limit_income, fiscal_start, theme_name, WORKPLACE_SETTINGS) #JSONに保存
        st.success("勤務先設定を保存しました。") #成功メッセージ


# 最後に設定を保存（テーマ＆背景＆勤務先設定込み）
save_settings(limit_income, fiscal_start, theme_name, WORKPLACE_SETTINGS) #毎回最後に設定を保存

### End of File ###