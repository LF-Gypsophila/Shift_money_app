/* Shift (salary) manager - Offline PWA (vanilla JS)
   Data is stored on-device using IndexedDB.
*/

const THEME_OPTIONS = ["シンプルホワイト", "スタバグリーン", "ネイビーダーク", "パステルピンク"];

const DEFAULT_WORKPLACE_SETTINGS = {
  "すたば": {
    "default_wage": 1310,
    "default_transport": 640,
    "wage_history": [
      {"from": "2024-12-12", "wage": 1200},
      {"from": "2025-04-01", "wage": 1220},
      {"from": "2025-10-01", "wage": 1310}
    ],
    "pre_minutes": 10,
    "post_minutes": 5,
    "break_rules": [
      {"min_hours": 4, "break_minutes": 15},
      {"min_hours": 6, "break_minutes": 45},
      {"min_hours": 8, "break_minutes": 60}
    ],
    "night_start": 22,
    "night_end": 1,
    "night_rate": 1.25,
    "early_start": 5,
    "early_end": 7,
    "early_bonus_per_hour": 160,
    "busy_bonus_per_hour": 200
  },
  "駿台": {
    "default_wage": 1350,
    "default_transport": 0,
    "wage_history": [
      {"from": "2024-04-24", "wage": 1200},
      {"from": "2025-04-01", "wage": 1350}
    ],
    "pre_minutes": 0,
    "post_minutes": 0,
    "break_rules": [{"min_hours": 6, "break_minutes": 45}],
    "night_start": 23,
    "night_end": 1,
    "night_rate": 1,
    "early_start": 5,
    "early_end": 6,
    "early_bonus_per_hour": 0,
    "busy_bonus_per_hour": 0
  },
  "C": {
    "default_wage": 1100,
    "default_transport": 0,
    "wage_history": [{"from": "2024-01-01", "wage": 1100}],
    "pre_minutes": 0,
    "post_minutes": 0,
    "break_rules": [
      {"min_hours": 5, "break_minutes": 30},
      {"min_hours": 8, "break_minutes": 60}
    ],
    "night_start": 22,
    "night_end": 5,
    "night_rate": 1.25,
    "early_start": 5,
    "early_end": 8,
    "early_bonus_per_hour": 0,
    "busy_bonus_per_hour": 0
  },
  "D": {
    "default_wage": 1100,
    "default_transport": 0,
    "wage_history": [{"from": "2024-01-01", "wage": 1100}],
    "pre_minutes": 0,
    "post_minutes": 0,
    "break_rules": [],
    "night_start": 22,
    "night_end": 5,
    "night_rate": 1.25,
    "early_start": 5,
    "early_end": 8,
    "early_bonus_per_hour": 0,
    "busy_bonus_per_hour": 0
  }
};

const DEFAULT_SHIFT_PATTERNS = {
  "すたば:15-CL": {"workplace":"すたば","start":"15:00","end":"22:30","wage":1310,"manual_break_min":45,"transport":640},
  "すたば:18-CL": {"workplace":"すたば","start":"18:00","end":"22:30","wage":1310,"manual_break_min":15,"transport":640},
  "駿台:CL業務": {"workplace":"駿台","start":"18:00","end":"22:00","wage":1350,"manual_break_min":0,"transport":0}
};

const WORKPLACE_COLORS = {
  "すたば": "rgba(144, 238, 144, 0.35)",
  "駿台": "rgba(224, 255, 255, 0.55)",
  "C": "rgba(240, 128, 128, 0.35)",
  "D": "rgba(255, 255, 224, 0.75)"
};

const DB_NAME = "shift_app_db";
const DB_VERSION = 1;
const STORE = "kv";
const STATE_KEY = "state";

/* ---------- IndexedDB (simple KV) ---------- */
function openDB() {
  return new Promise((resolve, reject) => {
    const req = indexedDB.open(DB_NAME, DB_VERSION);
    req.onupgradeneeded = () => {
      const db = req.result;
      if (!db.objectStoreNames.contains(STORE)) db.createObjectStore(STORE);
    };
    req.onsuccess = () => resolve(req.result);
    req.onerror = () => reject(req.error);
  });
}
async function idbGet(key) {
  const db = await openDB();
  return new Promise((resolve, reject) => {
    const tx = db.transaction(STORE, "readonly");
    const store = tx.objectStore(STORE);
    const req = store.get(key);
    req.onsuccess = () => resolve(req.result);
    req.onerror = () => reject(req.error);
  });
}
async function idbSet(key, val) {
  const db = await openDB();
  return new Promise((resolve, reject) => {
    const tx = db.transaction(STORE, "readwrite");
    const store = tx.objectStore(STORE);
    const req = store.put(val, key);
    req.onsuccess = () => resolve();
    req.onerror = () => reject(req.error);
  });
}

/* ---------- Date/time helpers (local time) ---------- */
function pad2(n){ return String(n).padStart(2,"0"); }
function dateToISO(d){
  return `${d.getFullYear()}-${pad2(d.getMonth()+1)}-${pad2(d.getDate())}`;
}
function isoToDate(iso){
  const [y,m,d] = iso.split("-").map(Number);
  return new Date(y, m-1, d, 0,0,0,0);
}
function hmToParts(hm){
  const [h,m] = hm.split(":").map(Number);
  return {h, m};
}
function combineDateTime(dateISO, timeHM){
  const d = isoToDate(dateISO);
  const {h,m} = hmToParts(timeHM);
  d.setHours(h, m, 0, 0);
  return d;
}
function minutesBetween(a,b){
  return (b.getTime() - a.getTime())/60000;
}
function hoursBetween(a,b){
  return (b.getTime() - a.getTime())/3600000;
}
function addMinutes(dt, mins){
  const d = new Date(dt.getTime());
  d.setMinutes(d.getMinutes()+mins);
  return d;
}
function startOfDay(dt){
  const d = new Date(dt.getTime());
  d.setHours(0,0,0,0);
  return d;
}
function sameDay(a,b){
  return a.getFullYear()===b.getFullYear() && a.getMonth()===b.getMonth() && a.getDate()===b.getDate();
}

/* ---------- Japanese holidays (approx) ---------- */
/* Equinox approx formulas commonly used for 1980-2099. */
function vernalEquinoxDay(y){
  // 1980-2099
  return Math.floor(20.8431 + 0.242194*(y-1980) - Math.floor((y-1980)/4));
}
function autumnEquinoxDay(y){
  // 1980-2099
  return Math.floor(23.2488 + 0.242194*(y-1980) - Math.floor((y-1980)/4));
}
function nthWeekdayOfMonth(y, mIndex, weekday, n){
  // weekday: 0=Sun ... 6=Sat
  const first = new Date(y, mIndex, 1);
  const firstW = first.getDay();
  const diff = (weekday - firstW + 7) % 7;
  const day = 1 + diff + (n-1)*7;
  return new Date(y, mIndex, day);
}
const holidayCache = new Map(); // year -> Map(iso->name)
function buildHolidayMap(year){
  if (holidayCache.has(year)) return holidayCache.get(year);

  const m = new Map();
  const add = (d, name) => m.set(dateToISO(d), name);

  // Fixed / Happy Monday system (current standard rules)
  add(new Date(year,0,1), "元日");
  add(nthWeekdayOfMonth(year,0,1,2), "成人の日");            // 2nd Monday Jan
  add(new Date(year,1,11), "建国記念の日");
  add(new Date(year,1,23), "天皇誕生日");
  add(new Date(year,2,vernalEquinoxDay(year)), "春分の日");
  add(new Date(year,3,29), "昭和の日");
  add(new Date(year,4,3), "憲法記念日");
  add(new Date(year,4,4), "みどりの日");
  add(new Date(year,4,5), "こどもの日");
  add(nthWeekdayOfMonth(year,6,1,3), "海の日");             // 3rd Monday Jul
  add(new Date(year,7,11), "山の日");
  add(nthWeekdayOfMonth(year,8,1,3), "敬老の日");           // 3rd Monday Sep
  add(new Date(year,8,autumnEquinoxDay(year)), "秋分の日");
  add(nthWeekdayOfMonth(year,9,1,2), "スポーツの日");       // 2nd Monday Oct
  add(new Date(year,10,3), "文化の日");
  add(new Date(year,10,23), "勤労感謝の日");

  // --- One-off holiday moves (Tokyo Olympics etc.) ---
  // 2020: Marine Day 7/23, Sports Day 7/24, Mountain Day 8/10
  // 2021: Marine Day 7/22, Sports Day 7/23, Mountain Day 8/8 (Substitute 8/9)
  // 2019: No Emperor's Birthday (transition year)
  if (year === 2019){
    m.delete(`${year}-02-23`);
  }
  if (year === 2020){
    // Remove standard dates
    m.delete(dateToISO(nthWeekdayOfMonth(year,6,1,3))); // usual Marine Day
    m.delete(dateToISO(nthWeekdayOfMonth(year,9,1,2))); // usual Sports Day (Oct)
    m.delete(`${year}-08-11`); // usual Mountain Day
    // Add moved dates
    add(new Date(year,6,23), "海の日");
    add(new Date(year,6,24), "スポーツの日");
    add(new Date(year,7,10), "山の日");
  }
  if (year === 2021){
    m.delete(dateToISO(nthWeekdayOfMonth(year,6,1,3))); // usual Marine Day
    m.delete(dateToISO(nthWeekdayOfMonth(year,9,1,2))); // usual Sports Day (Oct)
    m.delete(`${year}-08-11`); // usual Mountain Day
    add(new Date(year,6,22), "海の日");
    add(new Date(year,6,23), "スポーツの日");
    add(new Date(year,7,8), "山の日"); // substitute handled later
  }

  // Substitute holidays: if a holiday is on Sunday, the next non-holiday weekday becomes substitute.
  // (This behavior matches modern rules; older historical differences are not handled.)
  const entries = Array.from(m.keys()).sort();
  for (const iso of entries){
    const d = isoToDate(iso);
    if (d.getDay() === 0){ // Sunday
      let sub = new Date(d.getTime());
      sub.setDate(sub.getDate()+1);
      while (m.has(dateToISO(sub))) sub.setDate(sub.getDate()+1);
      add(sub, "振替休日");
    }
  }

  // Citizen's holiday: a weekday between two holidays becomes a holiday.
  // We'll scan the year days.
  const start = new Date(year,0,1);
  const end = new Date(year,11,31);
  for (let d=new Date(start); d<=end; d.setDate(d.getDate()+1)){
    const iso = dateToISO(d);
    if (m.has(iso)) continue;
    const dow = d.getDay();
    if (dow === 0 || dow === 6) continue; // weekday only
    const prev = new Date(d.getTime()); prev.setDate(prev.getDate()-1);
    const next = new Date(d.getTime()); next.setDate(next.getDate()+1);
    if (m.has(dateToISO(prev)) && m.has(dateToISO(next))){
      add(new Date(d.getTime()), "国民の休日");
    }
  }

  holidayCache.set(year, m);
  return m;
}
function isHoliday(dateObj){
  const year = dateObj.getFullYear();
  const map = buildHolidayMap(year);
  return map.has(dateToISO(dateObj));
}

/* ---------- Business logic (ported from shift_app_8.py) ---------- */
function getWorkplaceSettings(wp){
  return state.workplaceSettings[wp] || {};
}
function getDefaultWageForDate(workplace, shiftDateISO){
  const shiftDate = isoToDate(shiftDateISO);
  const settings = getWorkplaceSettings(workplace);
  const history = settings.wage_history;
  if (Array.isArray(history) && history.length){
    const sorted = [...history].sort((a,b)=> String(a.from).localeCompare(String(b.from)));
    let chosen = null;
    for (const h of sorted){
      if (!h || !h.from) continue;
      const fromD = isoToDate(h.from);
      if (shiftDate >= fromD) chosen = h.wage;
    }
    if (chosen !== null && chosen !== undefined) return parseInt(chosen,10);
  }
  const dw = settings.default_wage;
  return (dw!==undefined && dw!==null) ? parseInt(dw,10) : 1100;
}
function getDefaultTransportForWorkplace(workplace){
  const settings = getWorkplaceSettings(workplace);
  const dt = settings.default_transport;
  return (dt!==undefined && dt!==null) ? parseInt(dt,10) : 0;
}
function getAutoBreakMinutes(totalHours, workplace){
  const settings = getWorkplaceSettings(workplace);
  const rules = settings.break_rules || [];
  let b = 0;
  const sorted = [...rules].sort((a,b)=> (a.min_hours||0)-(b.min_hours||0));
  for (const rule of sorted){
    if (totalHours >= (rule.min_hours||0)) b = rule.break_minutes||0;
  }
  return parseInt(b,10) || 0;
}

function intersectionHours(aStart,aEnd,bStart,bEnd){
  const s = new Date(Math.max(aStart.getTime(), bStart.getTime()));
  const e = new Date(Math.min(aEnd.getTime(), bEnd.getTime()));
  if (s >= e) return 0;
  return hoursBetween(s,e);
}
function hoursInWindow(startDt, endDt, windowStartHour, windowEndHour){
  let total = 0;
  let day = startOfDay(startDt);
  const last = startOfDay(endDt);
  while (day <= last){
    let wStart = new Date(day.getTime());
    wStart.setHours(windowStartHour,0,0,0);
    let wEnd;
    if (windowStartHour < windowEndHour){
      wEnd = new Date(day.getTime());
      wEnd.setHours(windowEndHour,0,0,0);
    } else {
      wEnd = new Date(day.getTime());
      wEnd.setDate(wEnd.getDate()+1);
      wEnd.setHours(windowEndHour,0,0,0);
    }
    total += intersectionHours(startDt,endDt,wStart,wEnd);
    day.setDate(day.getDate()+1);
  }
  return total;
}
function calcNightEarlyHours(startDt, endDt, workplace){
  const settings = getWorkplaceSettings(workplace);
  const night_start = parseInt(settings.night_start ?? 22,10);
  const night_end = parseInt(settings.night_end ?? 5,10);
  const early_start = parseInt(settings.early_start ?? 5,10);
  const early_end = parseInt(settings.early_end ?? 8,10);

  const nightHours = hoursInWindow(startDt,endDt,night_start,night_end);
  const earlyHours = hoursInWindow(startDt,endDt,early_start,early_end);
  return {nightHours, earlyHours};
}
function calcPayForShift(shift){
  const wp = String(shift.workplace||"");
  const settings = getWorkplaceSettings(wp);
  const workHours = Number(shift.work_hours||0);
  const nightHours = Number(shift.night_hours||0);
  const earlyHours = Number(shift.early_hours||0);
  const wage = parseInt(shift.wage||0,10);
  const isBusy = !!shift.is_busy;

  const nightRate = Number(settings.night_rate ?? 1.0);
  const earlyBonusPerHour = Number(settings.early_bonus_per_hour ?? 0);
  const busyBonusPerHour = Number(settings.busy_bonus_per_hour ?? 0);

  const basePay = workHours*wage;
  const nightBonus = nightHours*wage*Math.max(nightRate-1.0,0);
  const earlyBonus = earlyHours*earlyBonusPerHour;
  const busyBonus = isBusy ? workHours*busyBonusPerHour : 0;
  const pay = Math.round(basePay + nightBonus + earlyBonus + busyBonus);

  shift.base_pay = Math.round(basePay);
  shift.night_bonus = Math.round(nightBonus);
  shift.early_bonus = Math.round(earlyBonus);
  shift.busy_bonus = Math.round(busyBonus);
  shift.pay = pay;
  return shift;
}

/* ---------- State ---------- */
function deepClone(x){ return JSON.parse(JSON.stringify(x)); }
function todayISO(){ return dateToISO(new Date()); }
function defaultFiscalStartISO(){
  const now = new Date();
  return `${now.getFullYear()}-01-01`;
}
function makeDefaultState(){
  return {
    version: 1,
    settings: {
      theme_name: THEME_OPTIONS[0],
      limit_income: 1030000,
      fiscal_start: defaultFiscalStartISO()
    },
    bg: { dataUrl: null, mime: null },
    workplaceSettings: deepClone(DEFAULT_WORKPLACE_SETTINGS),
    shiftPatterns: deepClone(DEFAULT_SHIFT_PATTERNS),
    shifts: []
  };
}
let state = makeDefaultState();

async function loadState(){
  const saved = await idbGet(STATE_KEY);
  if (saved && typeof saved === "object"){
    // Merge carefully to allow future schema changes
    state = makeDefaultState();
    if (saved.settings) state.settings = {...state.settings, ...saved.settings};
    if (saved.bg) state.bg = {...state.bg, ...saved.bg};
    if (saved.workplaceSettings) state.workplaceSettings = {...state.workplaceSettings, ...saved.workplaceSettings};
    if (saved.shiftPatterns) state.shiftPatterns = {...state.shiftPatterns, ...saved.shiftPatterns};
    if (Array.isArray(saved.shifts)) state.shifts = saved.shifts.map(s=>({...s, id: s.id || crypto.randomUUID()}));
  } else {
    state = makeDefaultState();
  }
}
async function saveState(){
  await idbSet(STATE_KEY, state);
}

/* ---------- UI ---------- */
const $ = (id) => document.getElementById(id);

function setBodyBackground(){
  const theme = state.settings.theme_name || THEME_OPTIONS[0];
  const bg = state.bg?.dataUrl;

  // default
  document.body.style.backgroundImage = "";
  document.body.style.background = "";

  if (bg){
    document.body.style.backgroundImage = `linear-gradient(rgba(0,0,0,0.10), rgba(0,0,0,0.10)), url("${bg}")`;
    document.body.style.backgroundSize = "cover";
    document.body.style.backgroundPosition = "center";
  } else {
    if (theme === "スタバグリーン"){
      document.body.style.background = "linear-gradient(135deg, #dfe7e1, #9ad0b1)";
    } else if (theme === "ネイビーダーク"){
      document.body.style.background = "linear-gradient(135deg, #1f2937, #111827)";
      document.documentElement.style.setProperty("--text", "#f5f5f5");
      document.documentElement.style.setProperty("--muted", "rgba(255,255,255,0.7)");
      document.documentElement.style.setProperty("--card", "rgba(17,24,39,0.55)");
      document.documentElement.style.setProperty("--border", "rgba(255,255,255,0.12)");
    } else if (theme === "パステルピンク"){
      document.body.style.background = "linear-gradient(135deg, #ffe4ec, #ffd1dc)";
    } else {
      document.body.style.background = "#f5f5f5";
    }
  }

  // reset dark theme vars if not navy
  if (theme !== "ネイビーダーク"){
    document.documentElement.style.setProperty("--text", "#111");
    document.documentElement.style.setProperty("--muted", "#666");
    document.documentElement.style.setProperty("--card", "rgba(255,255,255,0.85)");
    document.documentElement.style.setProperty("--border", "rgba(0,0,0,0.12)");
  }
}

function renderThemeSelect(){
  const sel = $("themeSelect");
  sel.innerHTML = "";
  for (const t of THEME_OPTIONS){
    const opt = document.createElement("option");
    opt.value = t;
    opt.textContent = t;
    sel.appendChild(opt);
  }
  sel.value = state.settings.theme_name || THEME_OPTIONS[0];
}

function renderPatternSelect(){
  const sel = $("patternSelect");
  sel.innerHTML = "";
  const opt0 = document.createElement("option");
  opt0.value = "";
  opt0.textContent = "（パターンを使わない）";
  sel.appendChild(opt0);
  for (const name of Object.keys(state.shiftPatterns)){
    const opt = document.createElement("option");
    opt.value = name;
    opt.textContent = name;
    sel.appendChild(opt);
  }
}

function fillShiftFormFromPattern(patternName){
  const dateISO = $("shiftDate").value || todayISO();
  const workplaceInput = $("workplace");
  const startInput = $("startTime");
  const endInput = $("endTime");
  const wageInput = $("wage");
  const breakInput = $("manualBreak");
  const transportInput = $("transport");

  const p = patternName ? state.shiftPatterns[patternName] : null;
  if (p){
    workplaceInput.value = p.workplace || "すたば";
    startInput.value = p.start || "18:00";
    endInput.value = p.end || "23:00";
    breakInput.value = String(p.manual_break_min ?? 0);
    const wage = (p.wage !== null && p.wage !== undefined) ? parseInt(p.wage,10) : getDefaultWageForDate(workplaceInput.value, dateISO);
    wageInput.value = String(wage);
    const tr = (p.transport !== null && p.transport !== undefined) ? parseInt(p.transport,10) : getDefaultTransportForWorkplace(workplaceInput.value);
    transportInput.value = String(tr);
  } else {
    // no pattern: keep current times, but refresh defaults
    const wp = workplaceInput.value || "すたば";
    wageInput.value = String(getDefaultWageForDate(wp, dateISO));
    transportInput.value = String(getDefaultTransportForWorkplace(wp));
  }
}

function renderSettings(){
  renderThemeSelect();
  $("limitIncome").value = String(state.settings.limit_income ?? 1030000);
  $("fiscalStart").value = String(state.settings.fiscal_start ?? defaultFiscalStartISO());
  setBodyBackground();
}

function setMessage(el, text, kind=""){
  el.textContent = text;
  el.dataset.kind = kind;
  if (kind === "error") el.style.color = "var(--danger)";
  else if (kind === "ok") el.style.color = "var(--ok)";
  else if (kind === "warn") el.style.color = "var(--warn)";
  else el.style.color = "var(--muted)";
}

function addShift(){
  const msg = $("addShiftMsg");
  setMessage(msg, "");

  const shiftDateISO = $("shiftDate").value;
  const workplace = $("workplace").value.trim() || "すたば";
  const startHM = $("startTime").value;
  const endHM = $("endTime").value;
  const wage = parseInt($("wage").value || "0",10);
  const manualBreak = parseInt($("manualBreak").value || "0",10);
  const isBusy = $("isBusy").checked;
  const transport = parseInt($("transport").value || "0",10);
  const memo = $("memo").value || "";

  if (!shiftDateISO || !startHM || !endHM){
    setMessage(msg, "日付・開始・終了を入力してください。", "error");
    return;
  }

  const startDt = combineDateTime(shiftDateISO, startHM);
  const endDt = combineDateTime(shiftDateISO, endHM);

  if (endDt <= startDt){
    setMessage(msg, "終了時刻が開始時刻より前になっていませんか？（このアプリは日跨ぎ勤務には未対応です）", "error");
    return;
  }

  const wpSettings = getWorkplaceSettings(workplace);
  const preMin = parseInt(wpSettings.pre_minutes ?? 0,10);
  const postMin = parseInt(wpSettings.post_minutes ?? 0,10);

  const startDtForPay = addMinutes(startDt, -preMin);
  const endDtForPay = addMinutes(endDt, postMin);

  const totalHours = hoursBetween(startDtForPay, endDtForPay);
  if (totalHours <= 0){
    setMessage(msg, "時間の計算で不整合が出ました。入力を確認してください。", "error");
    return;
  }

  const breakMinutes = manualBreak > 0 ? manualBreak : getAutoBreakMinutes(totalHours, workplace);
  let paidHours = totalHours - breakMinutes/60;
  if (paidHours < 0) paidHours = 0;

  const {nightHours, earlyHours} = calcNightEarlyHours(startDtForPay, endDtForPay, workplace);

  const shift = {
    id: crypto.randomUUID(),
    workplace,
    date: shiftDateISO,
    start: startHM,
    end: endHM,
    pre_min: preMin,
    post_min: postMin,
    total_hours_raw: Math.round(totalHours*100)/100,
    break_min: breakMinutes,
    work_hours: Math.round(paidHours*100)/100,
    night_hours: Math.round(nightHours*100)/100,
    early_hours: Math.round(earlyHours*100)/100,
    wage: wage,
    transport: transport,
    is_busy: isBusy,
    memo: memo
  };
  calcPayForShift(shift);

  state.shifts.push(shift);
  saveState().then(() => {
    setMessage(msg, "シフトを追加しました！", "ok");
    //入力欄リセット
    $("manualBreak").value = "";
    $("transport").value = "";
    $("isBusy").checked = false;
    $("memo").value = "";
    renderAll();
  }).catch(() => setMessage(msg, "保存に失敗しました。", "error"));
}

/* ---------- Derived data ---------- */
function getShiftsSortedByDateAsc(shifts){
  return [...shifts].sort((a,b)=> (a.date||"").localeCompare(b.date||"") || (a.start||"").localeCompare(b.start||""));
}
function toPeriodYearMonth(dateISO){
  return dateISO.slice(0,7); // YYYY-MM
}

function computePeriodShifts(){
  const fiscal = state.settings.fiscal_start || defaultFiscalStartISO();
  return state.shifts.filter(s => (s.date||"") >= fiscal);
}
function sum(arr, fn){
  return arr.reduce((acc,x)=> acc + (fn?fn(x):x), 0);
}
function groupSumBy(shifts, keyFn, valFn){
  const m = new Map();
  for (const s of shifts){
    const k = keyFn(s);
    const v = valFn(s);
    m.set(k, (m.get(k)||0) + v);
  }
  return m;
}
function groupAggByMonth(shifts){
  const m = new Map(); // ym -> {pay,hours}
  for (const s of shifts){
    const ym = toPeriodYearMonth(s.date);
    if (!m.has(ym)) m.set(ym, {pay:0, hours:0});
    const o = m.get(ym);
    o.pay += (s.pay||0);
    o.hours += Number(s.work_hours||0);
  }
  const rows = Array.from(m.entries())
    .sort((a,b)=> a[0].localeCompare(b[0]))
    .map(([ym,o]) => ({ "年月": ym, "給与合計(円)": o.pay, "勤務時間合計(h)": Math.round(o.hours*100)/100 }));
  return rows;
}

/* ---------- Calendar ---------- */
function monthWeeksMondayFirst(year, monthIndex){
  // monthIndex: 0-11
  const first = new Date(year, monthIndex, 1);
  const last = new Date(year, monthIndex+1, 0);
  // Monday=1
  const firstDow = first.getDay(); // Sun=0..Sat=6
  const offset = (firstDow + 6) % 7; // days since Monday
  const start = new Date(first.getTime());
  start.setDate(first.getDate() - offset);

  const weeks = [];
  let cur = new Date(start.getTime());
  while (cur <= last || cur.getDay() !== 1){ // ensure at least covers month
    const week = [];
    for (let i=0;i<7;i++){
      week.push(new Date(cur.getTime()));
      cur.setDate(cur.getDate()+1);
    }
    weeks.push(week);
    // stop if we've passed last day and are at Monday of next week
    if (cur > last && cur.getDay() === 1) break;
  }
  return weeks;
}
function renderCalendar(){
  const wrap = $("calendarWrap");
  const calMonth = $("calMonth").value; // YYYY-MM
  if (!calMonth){
    const now = new Date();
    $("calMonth").value = `${now.getFullYear()}-${pad2(now.getMonth()+1)}`;
  }
  const [yStr,mStr] = $("calMonth").value.split("-");
  const y = parseInt(yStr,10);
  const m = parseInt(mStr,10);
  const monthIndex = m-1;

  const weeks = monthWeeksMondayFirst(y, monthIndex);
  const monthISO = `${y}-${pad2(m)}`;

  const monthShifts = state.shifts.filter(s => (s.date||"").slice(0,7) === monthISO);
  const byDay = groupSumBy(monthShifts, s=>s.date, s=>s.pay||0);
  const byDayHours = groupSumBy(monthShifts, s=>s.date, s=>Number(s.work_hours||0));
  const byDayWps = new Map();
  for (const s of monthShifts){
    const k = s.date;
    if (!byDayWps.has(k)) byDayWps.set(k, new Set());
    byDayWps.get(k).add(s.workplace||"");
  }

  let html = `<table class="calendar"><thead><tr>
    <th>月</th><th>火</th><th>水</th><th>木</th><th>金</th><th>土</th><th>日</th>
  </tr></thead><tbody>`;
  for (const week of weeks){
    html += "<tr>";
    for (let col=0; col<7; col++){
      const d = week[col];
      const iso = dateToISO(d);
      const out = (d.getMonth() !== monthIndex);
      const pay = byDay.get(iso)||0;
      const hours = byDayHours.get(iso)||0;
      const wps = byDayWps.get(iso) ? Array.from(byDayWps.get(iso)).sort() : [];
      const isSun = d.getDay() === 0;
      const holiday = isHoliday(d);
      const has = pay>0;
      const cls = [
        out ? "out" : "",
        (!out && isSun) ? "sun" : "",
        (!out && !isSun && holiday) ? "holiday" : "",
        (!out && has) ? "has" : ""
      ].filter(Boolean).join(" ");
      const title = !out && has ? `${iso}\n勤務時間: ${hours.toFixed(2)}h\n給与: ${pay.toLocaleString()}円` : iso;
      const inner = out ? "" : `
        <div class="day">${d.getDate()}</div>
        ${has ? `<div class="sub">${pay.toLocaleString()}円</div><div class="sub">${wps.join(", ")}</div>` : ``}
      `;
      html += `<td class="${cls}" data-date="${iso}" title="${escapeHtml(title)}">${inner}</td>`;
    }
    html += "</tr>";
  }
  html += "</tbody></table>";
  wrap.innerHTML = html;

  // Summary
  const monthTotal = sum(monthShifts, s=>s.pay||0);
  const monthHours = sum(monthShifts, s=>Number(s.work_hours||0));
  $("monthSummary").textContent = `${y}年${m}月の合計：${monthTotal.toLocaleString()} 円 / ${monthHours.toFixed(2)} h`;

  // Cell click
  wrap.querySelectorAll("td[data-date]").forEach(td=>{
    td.addEventListener("click", () => {
      const iso = td.getAttribute("data-date");
      if (!iso) return;
      // ignore out-of-month clicks
      const d = isoToDate(iso);
      if (d.getMonth() !== monthIndex) return;
      renderDayDetail(iso);
    });
  });

  // show last selected if still in month
  const last = state.ui?.detailDate;
  if (last && last.startsWith(monthISO)) renderDayDetail(last);
  else $("dayDetail").textContent = "";
}
function renderDayDetail(dateISO){
  state.ui = state.ui || {};
  state.ui.detailDate = dateISO;
  const dayShifts = getShiftsSortedByDateAsc(state.shifts.filter(s=>s.date===dateISO));
  if (!dayShifts.length){
    $("dayDetail").textContent = `${dateISO}：この日にはシフトはありません。`;
    return;
  }
  const cols = ["date","workplace","start","end","work_hours","wage","pay","transport","busy_bonus","memo"];
  const rows = dayShifts.map(s => {
    const r = {};
    for (const c of cols){
      r[c] = (s[c] ?? "");
    }
    return r;
  });
  $("dayDetail").innerHTML = renderTable(cols, rows, {title:`${dateISO} のシフト一覧`});
}
function escapeHtml(s){
  return String(s).replace(/[&<>"']/g, c => ({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));
}

/* ---------- Shift list page ---------- */
function uniqueWorkplaces(){
  const set = new Set();
  for (const s of state.shifts) if (s.workplace) set.add(s.workplace);
  // include master workplaces too
  for (const wp of Object.keys(state.workplaceSettings)) set.add(wp);
  return Array.from(set).sort();
}

function renderFilterControls(){
  const wps = uniqueWorkplaces();
  const sel = $("filterWorkplaces");
  sel.innerHTML = "";
  for (const wp of wps){
    const opt = document.createElement("option");
    opt.value = wp;
    opt.textContent = wp;
    opt.selected = true;
    sel.appendChild(opt);
  }
  // date range defaults based on data
  if (state.shifts.length){
    const min = state.shifts.map(s=>s.date).sort()[0];
    const max = state.shifts.map(s=>s.date).sort().slice(-1)[0];
    $("filterStart").value = min;
    $("filterEnd").value = max;
  } else {
    $("filterStart").value = state.settings.fiscal_start || defaultFiscalStartISO();
    $("filterEnd").value = todayISO();
  }
}

function getSelectedValues(selectEl){
  return Array.from(selectEl.selectedOptions).map(o=>o.value);
}

function applyFilterAndRender(){
  const selectedWps = getSelectedValues($("filterWorkplaces"));
  const startISO = $("filterStart").value;
  const endISO = $("filterEnd").value;
  const sortOpt = $("sortOption").value;

  let shifts = [...state.shifts];
  if (startISO) shifts = shifts.filter(s => (s.date||"") >= startISO);
  if (endISO) shifts = shifts.filter(s => (s.date||"") <= endISO);
  if (selectedWps.length) shifts = shifts.filter(s => selectedWps.includes(s.workplace));

  // sort
  const by = {
    "日付昇順": (a,b)=> (a.date||"").localeCompare(b.date||"") || (a.start||"").localeCompare(b.start||""),
    "日付降順": (a,b)=> (b.date||"").localeCompare(a.date||"") || (b.start||"").localeCompare(a.start||""),
    "勤務時間（長い順）": (a,b)=> Number(b.work_hours||0)-Number(a.work_hours||0),
    "勤務時間（短い順）": (a,b)=> Number(a.work_hours||0)-Number(b.work_hours||0),
    "給料（高い順）": (a,b)=> Number(b.pay||0)-Number(a.pay||0),
    "給料（低い順）": (a,b)=> Number(a.pay||0)-Number(b.pay||0),
  }[sortOpt] || ((a,b)=> (a.date||"").localeCompare(b.date||""));

  shifts.sort(by);

  renderShiftTable(shifts);
  renderAggregates();
  renderDataIssues();
}

function renderShiftTable(shifts){
  const wrap = $("shiftTableWrap");
  if (!shifts.length){
    wrap.innerHTML = `<div class="detail">この条件に一致するシフトはありません。</div>`;
    return;
  }

  // Table with operations
  let html = `<table><thead><tr>
    <th></th>
    <th>日付</th>
    <th>勤務先</th>
    <th>開始</th>
    <th>終了</th>
    <th>勤務(h)</th>
    <th>時給</th>
    <th>給料</th>
    <th>交通費</th>
    <th>繁忙期</th>
    <th>メモ</th>
    <th>複製先</th>
    <th>操作</th>
  </tr></thead><tbody>`;

  for (const s of shifts){
    const bg = WORKPLACE_COLORS[s.workplace] || "transparent";
    html += `<tr data-id="${s.id}" style="background:${bg}">
      <td><input type="checkbox" class="rowCheck"></td>
      <td>${escapeHtml(s.date||"")}</td>
      <td>${escapeHtml(s.workplace||"")}</td>
      <td>${escapeHtml(s.start||"")}</td>
      <td>${escapeHtml(s.end||"")}</td>
      <td>${Number(s.work_hours||0).toFixed(2)}</td>
      <td>${(s.wage||0).toLocaleString()}</td>
      <td>${(s.pay||0).toLocaleString()}</td>
      <td>${(s.transport||0).toLocaleString()}</td>
      <td>${s.is_busy ? "✓" : ""}</td>
      <td>${escapeHtml(s.memo||"")}</td>
      <td><input type="date" class="dupDate" value="${escapeHtml(s.date||"")}"></td>
      <td>
        <button class="btn btn--secondary btnDup" type="button">Duplicate</button>
        <button class="btn btn--danger btnDel" type="button">DelAte</button>
      </td>
    </tr>`;
  }
  html += `</tbody></table>`;
  wrap.innerHTML = html;

  // bind buttons
  wrap.querySelectorAll("tr[data-id]").forEach(tr=>{
    const id = tr.getAttribute("data-id");
    tr.querySelector(".btnDel").addEventListener("click", async () => {
      state.shifts = state.shifts.filter(x=>x.id!==id);
      await saveState();
      renderAll();
    });
    tr.querySelector(".btnDup").addEventListener("click", async () => {
      const dateISO = tr.querySelector(".dupDate").value;
      const orig = state.shifts.find(x=>x.id===id);
      if (!orig || !dateISO) return;
      const copy = {...orig, id: crypto.randomUUID(), date: dateISO};
      state.shifts.push(copy);
      await saveState();
      renderAll();
    });
  });
}

function getCheckedShiftIds(){
  const wrap = $("shiftTableWrap");
  const ids = [];
  wrap.querySelectorAll("tr[data-id]").forEach(tr=>{
    const checked = tr.querySelector(".rowCheck")?.checked;
    if (checked) ids.push(tr.getAttribute("data-id"));
  });
  return ids.filter(Boolean);
}

async function bulkDelete(){
  const ids = getCheckedShiftIds();
  const msg = $("csvMsg");
  if (!ids.length){
    setMessage(msg, "削除する行が選択されていません。", "warn");
    return;
  }
  state.shifts = state.shifts.filter(s=> !ids.includes(s.id));
  await saveState();
  setMessage(msg, `${ids.length}件のシフトを削除しました。`, "ok");
  renderAll();
}

async function bulkEdit(){
  const ids = getCheckedShiftIds();
  const msg = $("csvMsg");
  if (!ids.length){
    setMessage(msg, "編集する行が選択されていません。", "warn");
    return;
  }
  const newWp = $("bulkWorkplace").value.trim();
  const newWage = parseInt($("bulkWage").value || "0",10);
  const newMemo = $("bulkMemo").value;

  for (const s of state.shifts){
    if (!ids.includes(s.id)) continue;
    if (newWp) s.workplace = newWp;
    if (newWage > 0) s.wage = newWage;
    if (newMemo) s.memo = newMemo;
    calcPayForShift(s);
  }
  await saveState();
  setMessage(msg, `${ids.length}件のシフトを更新しました。`, "ok");
  renderAll();
}

function renderAggregates(){
  const period = computePeriodShifts();
  const totalIncome = sum(period, s=>s.pay||0);
  const limit = Number(state.settings.limit_income ?? 1030000);
  const remaining = limit - totalIncome;

  //扶養チェック
  const check = $("supportCheck");
  check.innerHTML = `
    <div class="card-inner"><div class="small">現在の年間合計（期間内）</div><div class="summary">${totalIncome.toLocaleString()} 円</div></div>
    <div class="card-inner"><div class="small">${remaining>=0 ? "扶養上限までの残り" : "扶養上限超過分"}</div>
      <div class="summary">${Math.abs(remaining).toLocaleString()} 円</div>
      <div class="small">${
        remaining<0 ? "扶養の上限を超えています。シフト調整を検討してください。"
        : (remaining<100000 ? "扶養の上限まであと10万円未満です。注意してください。" : "まだ扶養の上限には余裕があります。")
      }</div>
    </div>`;

  // by workplace
  const byWp = groupSumBy(period, s=>s.workplace||"", s=>s.pay||0);
  const wpRows = Array.from(byWp.entries()).sort((a,b)=> a[0].localeCompare(b[0]))
    .map(([wp,val]) => ({workplace: wp, pay: val}));
  $("byWorkplace").innerHTML = renderTable(["workplace","pay"], wpRows, {headerMap:{"workplace":"バイト先","pay":"給与合計(円)"}});

  // by month
  $("byMonth").innerHTML = renderTable(Object.keys(groupAggByMonth(period)[0]||{"年月":""}), groupAggByMonth(period));

  // transport + busy bonus
  const totalTransport = sum(period, s=>Number(s.transport||0));
  const totalBusy = sum(period, s=>Number(s.busy_bonus||0));
  $("bonusSummary").innerHTML = `
    <div class="card-inner"><div class="small">交通費合計</div><div class="summary">${totalTransport.toLocaleString()} 円</div></div>
    <div class="card-inner"><div class="small">繁忙期手当合計</div><div class="summary">${totalBusy.toLocaleString()} 円</div></div>
    <div class="card-inner"><div class="small">給与＋交通費</div><div class="summary">${(totalIncome+totalTransport).toLocaleString()} 円</div></div>
  `;
}

function renderDataIssues(){
  const issues = [];

  // 1) end <= start
  for (const s of state.shifts){
    try{
      const startDt = combineDateTime(s.date, s.start);
      const endDt = combineDateTime(s.date, s.end);
      if (endDt <= startDt){
        issues.push(`${s.date} ${s.workplace}: 終了時刻が開始時刻以前になっています（${s.start}〜${s.end}）`);
      }
    }catch(_){}
  }

  // 2) overlap on same day + workplace
  const groups = new Map(); // key: date|wp -> list of intervals
  for (const s of state.shifts){
    const key = `${s.date}||${s.workplace}`;
    if (!groups.has(key)) groups.set(key, []);
    try{
      const sdt = combineDateTime(s.date, s.start);
      const edt = combineDateTime(s.date, s.end);
      groups.get(key).push({sdt, edt, start:s.start, end:s.end});
    }catch(_){}
  }
  for (const [key, arr] of groups.entries()){
    arr.sort((a,b)=> a.sdt - b.sdt);
    for (let i=0;i<arr.length-1;i++){
      const a = arr[i], b = arr[i+1];
      if (b.sdt < a.edt){
        const [d, wp] = key.split("||");
        issues.push(`${d} ${wp}: ${a.start}〜${a.end} と ${b.start}〜${b.end} のシフトが重複しています`);
      }
    }
  }

  // 3) wage<=0, work_hours<0, pay<0
  for (const s of state.shifts){
    if ((s.wage||0) <= 0) issues.push(`${s.date} ${s.workplace}: 時給が0以下になっています`);
    if (Number(s.work_hours||0) < 0) issues.push(`${s.date} ${s.workplace}: 勤務時間が負の値になっています`);
    if (Number(s.pay||0) < 0) issues.push(`${s.date} ${s.workplace}: 給与が負の値になっています`);
  }

  const wrap = $("dataIssues");
  if (!issues.length){
    wrap.textContent = "明らかな不整合は見つかりませんでした。";
  } else {
    wrap.textContent = `データにいくつか気になる点があります（${issues.length}件）:\n` + issues.map(x=>"・"+x).join("\n");
  }
}

function renderTable(columns, rows, opts={}){
  const headerMap = opts.headerMap || {};
  const title = opts.title ? `<div class="small" style="padding:8px 8px 0;">${escapeHtml(opts.title)}</div>` : "";
  if (!rows || !rows.length){
    return `<div class="detail">（データなし）</div>`;
  }
  const cols = columns && columns.length ? columns : Object.keys(rows[0]);
  let html = `${title}<table><thead><tr>`;
  for (const c of cols){
    html += `<th>${escapeHtml(headerMap[c] || c)}</th>`;
  }
  html += `</tr></thead><tbody>`;
  for (const r of rows){
    html += `<tr>`;
    for (const c of cols){
      const v = r[c];
      html += `<td>${escapeHtml(v===undefined||v===null ? "" : String(v))}</td>`;
    }
    html += `</tr>`;
  }
  html += `</tbody></table>`;
  return html;
}

/* ---------- Workplace settings page ---------- */
function renderWorkplaceSettingsPage(){
  const wrap = $("workplaceSettingsWrap");
  const keys = Object.keys(state.workplaceSettings).sort();
  const wpOptions = keys;

  let html = "";
  for (const wp of keys){
    const s = state.workplaceSettings[wp] || {};
    html += `<details class="card-inner" style="margin:10px 0;">
      <summary><strong>${escapeHtml(wp)}</strong> の設定</summary>
      <div class="grid2" style="margin-top:10px;">
        ${numField(`${wp} の基本時給`, `wp_${wp}_default_wage`, s.default_wage ?? 1100, 0, 10)}
        ${numField(`${wp} の基本交通費（往復）`, `wp_${wp}_default_transport`, s.default_transport ?? 0, 0, 10)}
        ${numField("前後の付け時間（前, 分）", `wp_${wp}_pre_minutes`, s.pre_minutes ?? 0, 0, 1)}
        ${numField("前後の付け時間（後, 分）", `wp_${wp}_post_minutes`, s.post_minutes ?? 0, 0, 1)}
        ${numField("深夜時間帯の開始時刻（時）", `wp_${wp}_night_start`, s.night_start ?? 22, 0, 1, 23)}
        ${numField("深夜時間帯の終了時刻（時）", `wp_${wp}_night_end`, s.night_end ?? 5, 0, 1, 23)}
        ${numField("深夜割増率（例: 1.25）", `wp_${wp}_night_rate`, s.night_rate ?? 1.25, 0, 0.05, null, true)}
        ${numField("早朝手当の開始時刻（時）", `wp_${wp}_early_start`, s.early_start ?? 5, 0, 1, 23)}
        ${numField("早朝手当の終了時刻（時）", `wp_${wp}_early_end`, s.early_end ?? 8, 0, 1, 23)}
        ${numField("早朝手当（円/h）", `wp_${wp}_early_bonus_per_hour`, s.early_bonus_per_hour ?? 0, 0, 10)}
        ${numField("繁忙期手当（円/h）", `wp_${wp}_busy_bonus_per_hour`, s.busy_bonus_per_hour ?? 0, 0, 10)}
      </div>
    </details>`;
  }
  wrap.innerHTML = html;

  // bind inputs
  for (const wp of keys){
    bindWpNumber(wp, "default_wage");
    bindWpNumber(wp, "default_transport");
    bindWpNumber(wp, "pre_minutes");
    bindWpNumber(wp, "post_minutes");
    bindWpNumber(wp, "night_start");
    bindWpNumber(wp, "night_end");
    bindWpNumber(wp, "night_rate", true);
    bindWpNumber(wp, "early_start");
    bindWpNumber(wp, "early_end");
    bindWpNumber(wp, "early_bonus_per_hour", true);
    bindWpNumber(wp, "busy_bonus_per_hour", true);
  }

  // new pattern workplace options
  const newWpSel = $("newPatternWp");
  newWpSel.innerHTML = "";
  for (const wp of wpOptions){
    const opt = document.createElement("option");
    opt.value = wp;
    opt.textContent = wp;
    newWpSel.appendChild(opt);
  }
}

function numField(label, id, value, min, step, max=null, float=false){
  const maxAttr = (max===null || max===undefined) ? "" : `max="${max}"`;
  const type = "number";
  const val = (value===undefined||value===null) ? "" : value;
  const st = float ? `step="${step}"` : `step="${step}"`;
  return `<label class="field"><span>${escapeHtml(label)}</span>
    <input id="${escapeHtml(id)}" type="${type}" min="${min}" ${maxAttr} ${st} value="${escapeHtml(val)}"></label>`;
}
function bindWpNumber(wp, field, allowFloat=false){
  const id = `wp_${wp}_${field}`;
  const el = $(id);
  if (!el) return;
  el.addEventListener("change", async () => {
    const raw = el.value;
    const v = allowFloat ? Number(raw) : parseInt(raw||"0",10);
    state.workplaceSettings[wp][field] = allowFloat ? v : (isNaN(v)?0:v);
    // pay recalculation is NOT automatic for all shifts here (same as streamlit; it recalcs on edit operations).
    await saveState();
    // update defaults if current form workplace matches
    fillShiftFormFromPattern($("patternSelect").value);
  });
}

/* ---------- Shift pattern settings ---------- */
function renderPatternSettings(){
  const wrap = $("patternSettingsWrap");
  const names = Object.keys(state.shiftPatterns).sort();
  const wps = Object.keys(state.workplaceSettings).sort();
  let html = "";

  for (const name of names){
    const p = state.shiftPatterns[name];
    html += `<details class="card-inner" style="margin:10px 0;">
      <summary>${escapeHtml(name)}</summary>
      <div class="grid3" style="margin-top:10px;">
        <label class="field"><span>勤務先</span>
          <select id="pt_${escapeId(name)}_wp">
            ${wps.map(wp=>`<option value="${escapeHtml(wp)}" ${wp===p.workplace?"selected":""}>${escapeHtml(wp)}</option>`).join("")}
          </select>
        </label>
        <label class="field"><span>開始時刻</span><input id="pt_${escapeId(name)}_start" type="time" value="${escapeHtml(p.start||"18:00")}"></label>
        <label class="field"><span>終了時刻</span><input id="pt_${escapeId(name)}_end" type="time" value="${escapeHtml(p.end||"22:00")}"></label>
        <label class="field"><span>時給（0で勤務先デフォルト）</span><input id="pt_${escapeId(name)}_wage" type="number" min="0" step="10" value="${escapeHtml(p.wage||0)}"></label>
        <label class="field"><span>手動休憩（分）</span><input id="pt_${escapeId(name)}_break" type="number" min="0" step="5" value="${escapeHtml(p.manual_break_min||0)}"></label>
        <label class="field"><span>交通費</span><input id="pt_${escapeId(name)}_transport" type="number" min="0" step="10" value="${escapeHtml(p.transport||0)}"></label>
      </div>
      <div class="row">
        <button class="btn btn--danger" type="button" data-del="${escapeHtml(name)}">このパターンを削除</button>
      </div>
    </details>`;
  }
  wrap.innerHTML = html;

  // bind
  for (const name of names){
    const eid = escapeId(name);
    const wpEl = $(`pt_${eid}_wp`);
    const sEl = $(`pt_${eid}_start`);
    const eEl = $(`pt_${eid}_end`);
    const wEl = $(`pt_${eid}_wage`);
    const bEl = $(`pt_${eid}_break`);
    const tEl = $(`pt_${eid}_transport`);
    const upd = async () => {
      const p = state.shiftPatterns[name];
      p.workplace = wpEl.value;
      p.start = sEl.value;
      p.end = eEl.value;
      const w = parseInt(wEl.value||"0",10);
      p.wage = w>0 ? w : null;
      p.manual_break_min = parseInt(bEl.value||"0",10);
      p.transport = parseInt(tEl.value||"0",10);
      await saveState();
      renderPatternSelect();
    };
    [wpEl,sEl,eEl,wEl,bEl,tEl].forEach(el => el.addEventListener("change", upd));
  }
  wrap.querySelectorAll("button[data-del]").forEach(btn=>{
    btn.addEventListener("click", async ()=>{
      const name = btn.getAttribute("data-del");
      delete state.shiftPatterns[name];
      await saveState();
      renderPatternSelect();
      renderPatternSettings();
      setMessage($("patternMsg"), "勤務パターンを削除しました。", "ok");
    });
  });
}

function escapeId(s){
  return btoa(unescape(encodeURIComponent(s))).replace(/=+/g,"").replace(/[+/]/g,"_");
}

/* ---------- CSV import/export ---------- */
const CSV_COLUMNS = [
  "date","workplace","start","end","pre_min","post_min","total_hours_raw","break_min","work_hours",
  "night_hours","early_hours","wage","transport","is_busy","memo","base_pay","night_bonus","early_bonus","busy_bonus","pay"
];

function csvEscapeCell(v){
  const s = (v===undefined||v===null) ? "" : String(v);
  if (/[",\n\r]/.test(s)) return `"${s.replace(/"/g,'""')}"`;
  return s;
}
function toCSV(rows){
  const lines = [];
  lines.push(CSV_COLUMNS.join(","));
  for (const r of rows){
    const line = CSV_COLUMNS.map(c=> csvEscapeCell(r[c])).join(",");
    lines.push(line);
  }
  return lines.join("\r\n");
}
function downloadText(filename, text, mime){
  const blob = new Blob([text], {type: mime});
  const url = URL.createObjectURL(blob);
  const a = document.createElement("a");
  a.href = url;
  a.download = filename;
  document.body.appendChild(a);
  a.click();
  a.remove();
  URL.revokeObjectURL(url);
}
function exportCSV(){
  const rows = state.shifts.map(s=>{
    const r = {};
    for (const c of CSV_COLUMNS) r[c] = (s[c] ?? "");
    return r;
  });
  // UTF-8 with BOM like the original "utf-8-sig"
  const bom = "\uFEFF";
  downloadText("shifts.csv", bom + toCSV(rows), "text/csv;charset=utf-8");
}
function parseCSV(text){
  // Very small CSV parser (handles quoted cells).
  const rows = [];
  let i=0, field="", row=[];
  const pushField=()=>{ row.push(field); field=""; };
  const pushRow=()=>{ rows.push(row); row=[]; };
  let inQuotes=false;

  while (i<text.length){
    const c = text[i];
    if (inQuotes){
      if (c === '"'){
        if (text[i+1] === '"'){ field+='"'; i+=2; continue; }
        inQuotes=false; i++; continue;
      }
      field += c; i++; continue;
    } else {
      if (c === '"'){ inQuotes=true; i++; continue; }
      if (c === ','){ pushField(); i++; continue; }
      if (c === '\n'){
        pushField(); pushRow(); i++; 
        if (text[i]==='\r') i++;
        continue;
      }
      if (c === '\r'){
        pushField(); pushRow(); i++;
        if (text[i]==='\n') i++;
        continue;
      }
      field += c; i++; continue;
    }
  }
  pushField();
  if (row.length>1 || row[0]!=="" ) pushRow();
  return rows;
}
async function importCSVFile(file){
  const msg = $("csvMsg");
  const text = await file.text();
  const cleaned = text.replace(/^\uFEFF/, ""); // remove BOM
  const rows = parseCSV(cleaned);
  if (!rows.length){ setMessage(msg, "CSVが空です。", "error"); return; }
  const header = rows[0].map(h=>h.trim());
  const idx = {};
  header.forEach((h, i)=> idx[h]=i);

  if (!idx.date || idx.date===undefined){ /* ok */ }
  // Build shifts
  const shifts = [];
  for (let r=1; r<rows.length; r++){
    const cells = rows[r];
    const get = (col) => {
      const j = idx[col];
      return (j===undefined) ? "" : (cells[j] ?? "");
    };
    const date = get("date") || get("Date") || "";
    if (!date || !/^\d{4}-\d{2}-\d{2}/.test(date)) continue;
    const shift = {
      id: crypto.randomUUID(),
      date: date.slice(0,10),
      workplace: get("workplace"),
      start: get("start"),
      end: get("end"),
      pre_min: parseInt(get("pre_min")||"0",10),
      post_min: parseInt(get("post_min")||"0",10),
      total_hours_raw: Number(get("total_hours_raw")||"0"),
      break_min: parseInt(get("break_min")||"0",10),
      work_hours: Number(get("work_hours")||"0"),
      night_hours: Number(get("night_hours")||"0"),
      early_hours: Number(get("early_hours")||"0"),
      wage: parseInt(get("wage")||"0",10),
      transport: parseInt(get("transport")||"0",10),
      is_busy: String(get("is_busy")).toLowerCase()==="true" || get("is_busy")==="1" || get("is_busy")==="✓",
      memo: get("memo") || ""
    };
    calcPayForShift(shift);
    shifts.push(shift);
  }
  state.shifts = shifts;
  await saveState();
  setMessage(msg, `CSVを読み込みました！（${shifts.length}件）`, "ok");
  renderAll();
}

/* ---------- Navigation / init ---------- */
function showPage(name){
  const pages = {
    "calendar": $("pageCalendar"),
    "list": $("pageList"),
    "workplace": $("pageWorkplace")
  };
  for (const [k, el] of Object.entries(pages)){
    el.hidden = (k !== name);
  }
  document.querySelectorAll(".tab").forEach(btn=>{
    const selected = btn.dataset.page === name;
    btn.setAttribute("aria-selected", selected ? "true":"false");
  });

  // page-specific renders
  if (name === "calendar") renderCalendar();
  if (name === "list") applyFilterAndRender();
  if (name === "workplace") { renderWorkplaceSettingsPage(); renderPatternSettings(); }
}

function renderAll(){
  renderSettings();
  renderPatternSelect();

  // shift form defaults
  if (!$("shiftDate").value) $("shiftDate").value = todayISO();
  fillShiftFormFromPattern($("patternSelect").value);

  // page
  const page = state.ui?.page || "calendar";
  showPage(page);
}

function bindEvents(){
  // Tabs
  document.querySelectorAll(".tab").forEach(btn=>{
    btn.addEventListener("click", () => {
      const page = btn.dataset.page;
      state.ui = state.ui || {};
      state.ui.page = page;
      saveState().catch(()=>{});
      showPage(page);
    });
  });

  // Settings
  $("themeSelect").addEventListener("change", async (e) => {
    state.settings.theme_name = e.target.value;
    setBodyBackground();
    await saveState();
  });
  $("limitIncome").addEventListener("change", async (e) => {
    state.settings.limit_income = parseInt(e.target.value||"0",10);
    await saveState();
    renderAggregates();
  });
  $("fiscalStart").addEventListener("change", async (e) => {
    state.settings.fiscal_start = e.target.value;
    await saveState();
    renderAll();
  });

  $("bgFile").addEventListener("change", async (e) => {
    const file = e.target.files?.[0];
    if (!file) return;
    const reader = new FileReader();
    reader.onload = async () => {
      state.bg = { dataUrl: reader.result, mime: file.type };
      setBodyBackground();
      await saveState();
    };
    reader.readAsDataURL(file);
  });

  $("clearBgBtn").addEventListener("click", async () => {
    state.bg = { dataUrl: null, mime: null };
    setBodyBackground();
    await saveState();
  });

  // Shift form
  $("patternSelect").addEventListener("change", (e)=> fillShiftFormFromPattern(e.target.value));
  $("shiftDate").addEventListener("change", ()=> fillShiftFormFromPattern($("patternSelect").value));
  $("workplace").addEventListener("change", ()=> fillShiftFormFromPattern($("patternSelect").value));

  $("addShiftBtn").addEventListener("click", addShift);

  // Calendar month change
  $("calMonth").addEventListener("change", renderCalendar);

  // List page
  $("applyFilterBtn").addEventListener("click", applyFilterAndRender);
  $("bulkDeleteBtn").addEventListener("click", bulkDelete);
  $("bulkApplyBtn").addEventListener("click", bulkEdit);
  $("exportCsvBtn").addEventListener("click", exportCSV);
  $("importCsvFile").addEventListener("change", async (e)=>{
    const file = e.target.files?.[0];
    if (!file) return;
    await importCSVFile(file);
    e.target.value = "";
  });

  // Add new pattern
  $("addPatternBtn").addEventListener("click", async ()=>{
    const msg = $("patternMsg");
    setMessage(msg, "");
    const name = $("newPatternName").value.trim();
    if (!name){ setMessage(msg, "パターン名を入力してください。", "warn"); return; }
    if (state.shiftPatterns[name]){ setMessage(msg, "同じ名前のパターンが既に存在します。", "warn"); return; }
    state.shiftPatterns[name] = {
      workplace: $("newPatternWp").value,
      start: $("newPatternStart").value,
      end: $("newPatternEnd").value,
      wage: parseInt($("newPatternWage").value||"0",10),
      manual_break_min: parseInt($("newPatternBreak").value||"0",10),
      transport: parseInt($("newPatternTransport").value||"0",10),
    };
    await saveState();
    renderPatternSelect();
    renderPatternSettings();
    setMessage(msg, `勤務パターン「${name}」を追加しました。`, "ok");
  });
}

async function init(){
  // Service Worker (offline)
  if ("serviceWorker" in navigator){
    window.addEventListener("load", () => {
      navigator.serviceWorker.register("./sw.js").catch(()=>{});
    });
  }

  await loadState();
  bindEvents();
  renderSettings();
  renderPatternSelect();
  renderFilterControls();

  // defaults
  $("shiftDate").value = todayISO();
  const now = new Date();
  $("calMonth").value = `${now.getFullYear()}-${pad2(now.getMonth()+1)}`;

  renderAll();
}

document.addEventListener("DOMContentLoaded", init);
