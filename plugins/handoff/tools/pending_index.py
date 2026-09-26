#!/usr/bin/env python3
"""
pending_index.py — 為交接語擱置檔 pending.md 產生／重建可跳轉索引

用途：pending.md 累積數十則交接語後，靠滑動找項目成本很高。
      本工具掃描全部 `## [YYYY-MM-DD HH:MM] 標題` 條目，
      在檔頭產生一段 Obsidian wikilink 索引，點擊即跳到該段落。

設計要點：
- 冪等：重複執行只會取代既有索引區塊，不會疊加。索引區塊以 HTML 註解標記界定。
- 就地更新非重寫：只替換索引區塊，其餘位元組原樣保留（呼應 pending.md 的 append-only 精神）。
- 連結格式用 Obsidian wikilink `[[#標題]]`（同檔內跳轉）。
  標題含單個 `[` `]` 不影響解析（wikilink 只在 `]]` 斷開），已對現有條目驗證。
- 狀態欄一併讀出，讓索引本身就能看出哪些是「前置條件未成熟」而不必點進去。

用法：
    python3 pending_index.py                    # 用 $PENDING_FILE，或 cwd 下的 _harness/handoffs/pending.md
    python3 pending_index.py --path <檔案>       # 指定其他檔案
    python3 pending_index.py --check            # 只檢查索引是否為最新，不寫入（exit 1 表示過期）

依 handoff skill Step 5.6 於每次寫入交接語後呼叫（亦供 pending-review skill 使用）。
"""

import argparse
import datetime as dt
import json
import os
import re
import sys
from pathlib import Path


def _default_path():
    """解析擱置檔位置。

    回傳 (路徑, 是否為使用者明示)。環境變數算明示——使用者刻意設過，
    不該被護欄擋；只有落到 cwd 相對推斷才是「猜的」。

    優先序：$PENDING_FILE → $CLAUDE_DATA_ROOT/_harness/handoffs/pending.md
    → 相對於工作目錄的 _harness/handoffs/pending.md。

    為何不寫死任何 vault 名稱：本工具隨 plugin 散佈，別人的 vault 不叫「資料」。
    找不到時寧可報錯，也不要猜——猜錯會靜默寫到錯的地方。
    用 --path 明確指定，或設 $PENDING_FILE 環境變數。
    """
    env = os.environ.get("PENDING_FILE")
    if env:
        return Path(env).expanduser(), True
    root = os.environ.get("CLAUDE_DATA_ROOT")
    if root:
        return Path(root).expanduser() / "_harness/handoffs/pending.md", True
    # 沒有任何設定時不猜測 vault 名稱——猜錯會靜默寫到不存在的路徑，
    # 或更糟，寫進另一個同名目錄。回傳 cwd 下的相對位置，讓 main() 給出可行動的錯誤。
    return Path("_harness/handoffs/pending.md"), False


DEFAULT_PATH, DEFAULT_PATH_IS_EXPLICIT = _default_path()

BEGIN = "<!-- INDEX:BEGIN 由 pending_index.py 自動產生，勿手動編輯此區塊 -->"
END = "<!-- INDEX:END -->"

# 只認前綴，不認整行：BEGIN 註解的尾綴（工具名／說明文字）改過幾次，
# 若用整字串比對，舊區塊會找不到而被當成「沒有索引」→ 插入第二個索引區塊。
# 2026-09-03 實測踩到：工具從 Tools/ 移進 plugin 後尾綴由「Tools/pending_index.py」
# 改為「pending_index.py」，整字串比對即回報索引過期。
BEGIN_PREFIX = "<!-- INDEX:BEGIN"


def _find_block(text):
    """回傳既有索引區塊的 (start, end)；找不到回 None。"""
    start = text.find(BEGIN_PREFIX)
    if start == -1:
        return None
    end = text.find(END, start)
    if end == -1:
        return None
    return start, end + len(END)

# 條目標題：## 專案名稱
# 2026-09-03 起時間移入表格的 `| 建立 |` 欄位，標題不再含 [日期] 前綴。
# 檔頭的結構性標題（怎麼用／生命週期／維護規則／索引）不是條目，以 SKIP_HEADINGS 排除。
ENTRY_RE = re.compile(r"^## (.+)$", re.MULTILINE)

SKIP_HEADINGS = ("怎麼用", "生命週期", "維護規則", "索引")


def _is_entry(title, body, before_index=False):
    """條目的判準：位在索引區塊之後，且該段落含 `### 交接語` 區塊。

    位置優先於標題比對。檔頭的結構性段落（怎麼用／生命週期／維護規則）一律排在
    索引標記之前，條目一律在其後，所以「是否在索引之前」是語言無關的判準。

    2026-09-04：原本只靠 SKIP_HEADINGS 這份寫死的中文標題清單，
    英文（或任何非中文）骨架一旦在說明段裡示範 `### 交接語`，那段就會被當成
    真條目算進索引——實測英文骨架多出一則 `[[#How to use]]`。這對要把 plugin
    給別人用的情境是硬傷，故改為位置判準，標題清單僅作為同語言時的額外保險。
    """
    if before_index:
        return False
    if any(title.startswith(s) for s in SKIP_HEADINGS):
        return False
    return "### 交接語" in body


# 主題分群：依工作區路徑與標題關鍵字判斷。
# 先比對 keywords（標題語義優先），再比對 workspace 前綴。
# 主題分群規則預設為空——關鍵字必然是「某個人的專案名」，寫死在工具裡等於
# 只對原作者有用（2026-09-04 外部化前確實如此，12 組全是原作者的專案）。
# 使用者把自己的規則放在擱置檔同層的 `_topics.json`，格式見 load_topics()。
# 沒有該檔時所有條目歸入「其他」，索引仍可正常運作，只是不分主題。
TOPICS = []


def load_topics(pending_path):
    """從擱置檔同層的 `_topics.json` 載入主題分群規則。

    格式（三者皆為字串陣列，keywords 比對標題、prefixes 比對工作區路徑）：

        [
          {"name": "課程與成績", "keywords": ["成績更正", "課程重構"],
           "prefixes": ["About Course/"]},
          {"name": "工具維護", "keywords": ["工具"], "prefixes": ["Tools/"]}
        ]

    檔案不存在就回傳空清單（全部歸「其他」）；格式錯誤只警告不中斷——
    分群只是索引的可讀性加值，不該讓整個交接流程失敗。
    """
    cfg = Path(pending_path).parent / "_topics.json"
    if not cfg.is_file():
        return []
    try:
        raw = json.loads(cfg.read_text(encoding="utf-8"))
        out = []
        for item in raw:
            out.append((item["name"],
                        list(item.get("keywords", [])),
                        list(item.get("prefixes", []))))
        return out
    except (json.JSONDecodeError, KeyError, TypeError) as exc:
        print(f"警告：{cfg} 格式有誤（{exc}），本次不分主題", file=sys.stderr)
        return []



def _topic(title, workspace, topics=None):
    topics = TOPICS if topics is None else topics
    low = title.lower()
    for name, keywords, prefixes in topics:
        if any(k.lower() in low for k in keywords):
            return name
    for name, keywords, prefixes in topics:
        if any(pref in workspace for pref in prefixes):
            return name
    return "其他"


def _blocked_reason(status, prereq):
    """判斷是否卡住，回傳阻塞原因（未卡住回 None）。"""
    if "前置" in status or "未成熟" in status:
        return prereq or status
    if not prereq:
        return None
    # 前置欄寫「無」開頭視為未卡住
    if prereq.startswith("無"):
        return None
    return prereq


FENCE_RE = re.compile(r"^(```+|~~~+).*?^\1[ \t]*$", re.M | re.S)


def mask_fences(text):
    """把 code fence 內容換成等長空白，位移不變、內容不再參與比對。

    為何需要：交接語本身常引用 Markdown（例如一則「關於 pending.md 格式」的交接語，
    內文就含 `## 標題` 與 `### 交接語`）。直接對原文跑 ENTRY_RE，fence 內的 `## ` 會
    被當成真條目切出來，索引因而長出鬼條目；apply_backlinks 更會把 `[[#索引|↑ 回索引]]`
    寫進 fence 內部，違反 SKILL.md「交接語必須與 Step 5 印出的逐字相同」的硬規則
    ——使用者複製到的交接語會多一行 wikilink。2026-09-04 實測確認兩者皆會發生。

    用等長空白取代而非刪除，是為了讓 match 的位移仍可直接套用回原文。
    """
    def blank(m):
        return re.sub(r"[^\n]", " ", m.group(0))
    return FENCE_RE.sub(blank, text)


DATE_RE = re.compile(r"(\d{4})-(\d{2})(?:-(\d{2}))?")
DEADLINE_RE = re.compile(r"(?:(\d{4})[-/])?(\d{1,2})[/-](\d{1,2})")

# 「下一步」欄的三個值，順序即索引分組順序。值固定，方便日後用程式計數
# （2026-09-26 立案，老師的困難多在起頭：先列出不必老師動手就能開始的）。
NEXT_GROUPS = (
    ("AI", "AI 可直接推進"),
    ("老師", "老師決定或親手做"),
    ("外部", "等外部條件"),
)
NEXT_UNSET = "未填"

# 事情日期超過這個天數、又沒有期限，索引標「久放」，作為去留候選。
# 60 天與 pending-review skill、someday.md 的判準一致。
STALE_DAYS = 60

TODAY = dt.date.today()


def _to_date(m):
    """DATE_RE 的 match 轉 date；只有年月（如 `2026-06`）時取該月 1 日，僅供排序。"""
    return dt.date(int(m.group(1)), int(m.group(2)), int(m.group(3) or 1))


def _dates(created):
    """從 `| 建立 |` 取 (事情日期, 登載日期)，各為 (date, 顯示字串)，取不到為 (None, "")。

    一般條目兩者相同：交接當下寫入。舊條目寫成 `2026-08-26 → 提列 2026-08-31`，
    前者是工作停下的日期，後者是放進本檔的日期（2026-08-31 一次性搬遷）。
    老師要能分別依兩者排序，看出「這件事多久沒動」與「何時放上來」（2026-09-26）。
    """
    created = created or ""
    found = list(DATE_RE.finditer(created))
    if not found:
        return (None, ""), (None, "")
    event = (_to_date(found[0]), found[0].group(0))
    reg = event
    k = created.find("提列")
    if k != -1:
        after = [m for m in found if m.start() > k]
        if after:
            reg = (_to_date(after[0]), after[0].group(0))
    return event, reg


def _deadline_date(deadline, ref):
    """把期限欄第一個日期解析成 date；解析不了回 None。

    期限欄是自由文字（如 `9/14 前（因某事 9/15 到期）`），取第一個日期。
    沒寫年份時用建立日期的年份；若因此比建立日期早半年以上，視為跨年。
    2026-09-26 前用字串排序，`10/10` 會排在 `9/07` 之前。
    """
    m = DEADLINE_RE.search(deadline or "")
    if not m:
        return None
    year = int(m.group(1)) if m.group(1) else (ref.year if ref else TODAY.year)
    try:
        out = dt.date(year, int(m.group(2)), int(m.group(3)))
    except ValueError:
        return None
    if not m.group(1) and ref and out < ref - dt.timedelta(days=180):
        out = out.replace(year=year + 1)
    return out


def _next(cell):
    """`| 下一步 |` 欄取第一個詞比對三個固定值；其餘一律算未填。"""
    v = (cell or "").strip()
    for key, _label in NEXT_GROUPS:
        if v.startswith(key):
            return key
    return NEXT_UNSET


def extract_entries(text, topics=None):
    """回傳 entry dict 清單，依文件出現順序。"""
    entries = []
    scan = mask_fences(text)
    # 索引區塊的位置：在它之前的 `## ` 標題都是檔頭結構，不是條目
    # 尚無索引區塊（首次建檔）時用 -1，等同「沒有任何標題在索引之前」，
    # 所有含 `### 交接語` 的段落照常計為條目。
    index_pos = scan.find(BEGIN_PREFIX)
    matches = list(ENTRY_RE.finditer(scan))
    for i, m in enumerate(matches):
        title = m.group(1).strip()
        start = m.end()
        end = matches[i + 1].start() if i + 1 < len(matches) else len(text)
        body = text[start:end]

        if not _is_entry(title, body, before_index=(m.start() < index_pos)):
            continue

        date = _cell(body, "建立") or ""
        status = _cell(body, "狀態") or ""
        workspace = _cell(body, "工作區") or ""
        prereq = _cell(body, "前置") or ""
        deadline = _cell(body, "期限")
        (event, event_s), (reg, reg_s) = _dates(date)
        entries.append({
            "title": title,
            "date": date,
            "doc": _cell(body, "交接文件") or "",
            "status": status,
            "deadline": deadline,
            "deadline_date": _deadline_date(deadline, reg),
            "event": event, "event_s": event_s,
            "reg": reg, "reg_s": reg_s,
            "next": _next(_cell(body, "下一步")),
            "workspace": workspace,
            "prereq": prereq,
            "link": _cell(body, "連動") or "",
            "topic": _topic(title, workspace, topics),
            "blocked": _blocked_reason(status, prereq),
        })
    return entries


def _cell(body, label):
    """從 `| 標籤 | 值 |` 表格列取值，取不到回傳 None。"""
    m = re.search(rf"^\|\s*{re.escape(label)}\s*\|\s*(.+?)\s*\|\s*$", body, re.MULTILINE)
    return m.group(1).strip() if m else None


def _overdue(e):
    return bool(e["deadline_date"] and e["deadline_date"] < TODAY)


def _stale(e):
    return bool(not e["deadline"] and e["event"]
                and (TODAY - e["event"]).days > STALE_DAYS)


def _unlocks(e, entries):
    """做完 e 會解鎖哪些則：對方的前置欄含 `[[#e 的標題]]`，或含 e 標題前 24 字。

    2026-09-26 前只比對標題前 24 字，而前置欄多半用簡稱（如「上一則」），
    實測 49 則裡一條鏈都沒抓到。`_format.md` 改為引用他則時寫 `[[#標題]]`，
    精確且在 Obsidian 可點；前 24 字比對保留給舊寫法。
    """
    key = f"[[#{e['title']}]]"
    return [o for o in entries
            if o is not e and o["blocked"]
            and (key in o["blocked"] or e["title"][:24] in o["blocked"])]


def _shorten(reason, limit=58):
    """截斷阻塞原因，但不切斷 wikilink——切在 `[[` 與 `]]` 之間會讓後面整段變成壞連結。"""
    reason = reason.replace("**", "").strip()
    if len(reason) <= limit:
        return reason
    cut = reason[:limit]
    if cut.count("[[") > cut.count("]]"):
        end = reason.find("]]", limit)
        cut = reason[:end + 2] if end != -1 else cut[:cut.rfind("[[")]
    return cut.rstrip() + "…"


def build_index(entries):
    """產生索引 markdown 區塊。

    四段結構，依「打開檔案時想知道什麼」排序：
      1. 有期限 —— 依日期排序，已過的標出來
      2. 依下一步 —— AI 可直接推進／老師決定或親手做／等外部條件，主題降為行尾標籤
      3. 卡住的 —— 有明確阻塞，看了不必再判斷一次
      4. 依時間 —— 可收合的兩份清單：依登載日期、依事情日期

    標籤（期限已過、久放）依執行當天計算，跨日後 --check 可能回報過期，重跑即可。
    2026-09-26 改版（3.3.0）：原「依主題」分組改為「依下一步」。
    """
    lines = [BEGIN, "", "## 索引", ""]

    blocked = [e for e in entries if e["blocked"]]
    overdue = [e for e in entries if _overdue(e)]
    stale = [e for e in entries if _stale(e)]
    review = {e["title"] for e in overdue + stale}
    counts = {k: sum(1 for e in entries if e["next"] == k) for k, _ in NEXT_GROUPS}
    unset = sum(1 for e in entries if e["next"] == NEXT_UNSET)

    head = f"共 {len(entries)} 則｜下一步：" + "、".join(f"{k} {counts[k]}" for k, _ in NEXT_GROUPS)
    if unset:
        head += f"、{NEXT_UNSET} {unset}"
    head += f"｜卡住 {len(blocked)}"
    if review:
        head += f"｜待確認去留 {len(review)} 則（期限已過 {len(overdue)}、久放 {len(stale)}）"
    lines += [head + "。點標題跳到該則。", ""]

    def _doc_link(e):
        """交接文件的 Obsidian 連結。

        老師的實際動線是「在索引看到一則 → 想知道它在講什麼 → 要開交接文件」，
        原本得先跳到該則、再從表格裡把路徑複製出來。這裡直接給一個可點的
        `[文件]`，省掉中間兩步。
        `| 交接文件 |` 欄的值形如 `` `~/資料/.../Handoff_X.md` ``，
        取檔名（去掉 .md）當 wikilink 目標——vault 內檔名唯一，Obsidian 解得到。
        """
        cell = e.get("doc", "").strip()
        if not cell or cell in ("無", "-"):
            return ""
        # 取第一個反引號包住的路徑。該欄位可能含多個路徑與括號註解，例如
        # `| 交接文件 | `A.md`（銜接 `B.md`） |`——直接 strip 反引號會把整串
        # 連註解一起當成檔名，產出 `[[B.md`）|文件]]` 這種壞連結（2026-09-04 實測）。
        m = re.search(r"`([^`]+)`", cell)
        raw = m.group(1) if m else cell
        name = raw.rsplit("/", 1)[-1].strip()
        if name.endswith(".md"):
            name = name[:-3]
        if not name:
            return ""
        # 只在檔案真的存在時才給連結。實測 2026-09-04：33 則裡有 9 則的
        # `| 交接文件 |` 指向已不存在的路徑（檔案被搬動或更名，欄位沒跟著改）。
        # 若照樣輸出，索引會多出 9 個點了打不開的死連結——那比沒有連結更糟，
        # 使用者會以為是 Obsidian 壞了。找不到就靜靜省略。
        base = Path(raw.replace("~", str(Path.home()))) if raw.startswith("~") else None
        if base is None or not base.is_file():
            return ""
        return f" · [[{name}|文件]]"

    def link(e):
        return f"[[#{e['title']}]]{_doc_link(e)}"

    def tags(e, with_topic=True, with_deadline=True):
        t = [e["topic"]] if with_topic else []
        if with_deadline and e["deadline"]:
            t.append(f"期限 {e['deadline']}" + ("（已過）" if _overdue(e) else ""))
        if e["blocked"]:
            t.append("卡住")
        n = len(_unlocks(e, entries))
        if n:
            t.append(f"做完會解鎖 {n} 則")
        if _stale(e):
            t.append("久放")
        if e["reg_s"]:
            t.append(f"登載 {e['reg_s']}")
        return "｜".join(t)

    far = dt.date.max

    # ── 1. 有期限 ──
    dated = sorted([e for e in entries if e["deadline"]],
                   key=lambda e: e["deadline_date"] or far)
    if dated:
        lines += ["### 有期限", ""]
        for e in dated:
            lines.append(f"- {link(e)} — 期限 {e['deadline']}"
                         + ("（已過）" if _overdue(e) else "")
                         + f"｜{tags(e, with_deadline=False)}")
        lines.append("")

    # ── 2. 依下一步 ──
    # 組內：有期限的依日期在前，其餘新登載的在前
    pos = {id(e): i for i, e in enumerate(entries)}

    def in_group(e):
        return (e["deadline_date"] or far, -(e["reg"] or dt.date.min).toordinal(), -pos[id(e)])
    lines += ["### 依下一步", ""]
    groups = list(NEXT_GROUPS) + ([(NEXT_UNSET, NEXT_UNSET)] if unset else [])
    for key, label in groups:
        group = sorted([e for e in entries if e["next"] == key], key=in_group)
        if not group:
            continue
        lines += [f"**{label}**（{len(group)}）", ""]
        for e in group:
            lines.append(f"- {link(e)} — {tags(e)}")
        lines.append("")

    # ── 3. 卡住的 ──
    if blocked:
        lines += ["### 卡住（有明確阻塞，不必再判斷一次）", ""]
        for e in blocked:
            lines.append(f"- {link(e)}")
            lines.append(f"  - 等：{_shorten(e['blocked'])}")
        lines.append("")

    # ── 4. 依時間（Obsidian 可收合 callout，預設收合，不拉長索引） ──
    lines += ["### 依時間", ""]
    for label, key, other, other_label in (
            ("依登載日期", "reg", "event_s", "事情"),
            ("依事情日期", "event", "reg_s", "登載")):
        # 同日以檔內位置決勝：新條目附加在檔尾，越後面越新
        ordered = [e for _, e in sorted(enumerate(entries),
                                        key=lambda p: (p[1][key] or dt.date.min, p[0]),
                                        reverse=True)]
        lines.append(f"> [!note]- {label}（新→舊，{len(ordered)} 則）")
        for e in ordered:
            main_s = e["reg_s"] if key == "reg" else e["event_s"]
            main_label = "登載" if key == "reg" else "事情"
            extra = f"｜{other_label} {e[other]}" if e[other] and e[other] != main_s else ""
            lines.append(f"> - [[#{e['title']}]] — {main_label} {main_s or '未記'}{extra}｜{e['topic']}")
        lines.append("")

    lines.append(END)
    return "\n".join(lines)


def apply_index(text, index_block):
    """把索引寫進文件：取代既有區塊，或插在第一則條目之前。"""
    found = _find_block(text)
    if found:
        start, end = found
        return text[:start] + index_block + text[end:]

    # 首次插入：放在第一個條目標題之前
    m = ENTRY_RE.search(text)
    if not m:
        # 沒有任何條目，附到檔尾
        return text.rstrip("\n") + "\n\n" + index_block + "\n"

    # 往前找該條目前最近的分隔線，索引插在分隔線之後
    head = text[: m.start()]
    sep = head.rfind("\n---\n")
    insert_at = sep + len("\n---\n") if sep != -1 else m.start()
    return text[:insert_at] + "\n" + index_block + "\n\n" + text[insert_at:]


BACKLINK = "[[#索引|↑ 回索引]]"


def apply_backlinks(text):
    """每則結尾補一個回索引連結，讓老師看完不必往上滑。

    冪等：已有的不重複加；位置固定在該則的分隔線之前。
    """
    split_at = text.index(END) + len(END)
    head, body = text[:split_at], text[split_at:]

    import re as _re
    # 依「遮蔽後」的文字找條目邊界，再用同一組位移切原文。
    # 直接對原文 split 會把交接語 fence 內的 `## 標題` 當成條目起點，
    # 於是回索引連結被插進 fence 內部，污染使用者複製到的交接語。
    scan = mask_fences(body)
    bounds = [(m.start(), m.end()) for m in _re.finditer(r"(?m)^## .+$", scan)]
    if not bounds:
        return head + body
    parts = [body[: bounds[0][0]]]
    for k, (s, e) in enumerate(bounds):
        nxt = bounds[k + 1][0] if k + 1 < len(bounds) else len(body)
        parts.append(body[s:e])       # 標題行
        parts.append(body[e:nxt])     # 該則內容
    out = [parts[0]]
    for i in range(1, len(parts), 2):
        title, seg = parts[i], parts[i + 1]
        if "### 交接語" not in mask_fences(seg):
            out += [title, seg]
            continue
        # 先移除既有的回索引連結（連同前後空行），避免重複堆疊與空行累積
        seg = _re.sub(r"\n+" + _re.escape(BACKLINK) + r"\n*", "\n", seg)
        lines = seg.rstrip("\n").split("\n")
        # 尾端若有 --- 分隔線，連結插在它前面；沒有（最後一則）就接在內容後
        pos = None
        for j in range(len(lines) - 1, -1, -1):
            if lines[j].strip() == "---":
                pos = j
                break
        if pos is None:
            lines += ["", BACKLINK]
        else:
            # 去掉分隔線前多餘空行，統一為一行空白
            while pos > 0 and lines[pos - 1].strip() == "":
                lines.pop(pos - 1)
                pos -= 1
            lines[pos:pos] = ["", BACKLINK, ""]
        out += [title, "\n".join(lines) + "\n"]
    return head + "".join(out)


def audit(text, entries):
    """不變式稽核：檢查索引輸出「對不對」，而非「重跑是否一致」。

    為何需要這支（2026-09-04 立案）：`--check` 比對的是「重跑會不會產生相同輸出」，
    也就是工具跟自己比——輸出恆等於自己，所以結構上不可能發現輸出本身是錯的。
    實害：build_index() 曾把「其他」組印兩次（主題迴圈一次、專區一次），
    43 個索引連結對 33 則條目，10 則重複；而 --check 回 exit 0、斷鏈檢查也全過。

    這裡斷言的是關係，不製造任何情境：
      1. 索引收錄的唯一條目數 == 實際條目數（不多不少）
      2. 同一分段內不得重複
      3. 全收錄的分段（「依下一步」各組合計、每份時間序清單）必須剛好涵蓋全部條目
      4. code fence 內不得含回索引連結（違反 SKILL.md 的 verbatim 硬規則）
    """
    import re as _re
    from collections import Counter

    problems = []
    body = text.split(BEGIN_PREFIX)[1].split(END)[0] if BEGIN_PREFIX in text else ""
    link_re = _re.compile(r"^- \[\[#([^\]|]+)")

    def norm(ln):
        # 時間序清單在 callout 內，行首多一個 `> `
        s = ln.strip()
        return s[1:].strip() if s.startswith(">") else s

    linked = [link_re.match(norm(ln)).group(1)
              for ln in body.split("\n") if link_re.match(norm(ln))]
    counts = Counter(linked)
    titles = {e["title"] for e in entries}

    missing = titles - set(counts)
    extra = set(counts) - titles
    if missing:
        problems.append(f"條目未被索引收錄（{len(missing)}）：" + "、".join(sorted(missing)[:5]))
    if extra:
        problems.append(f"索引指向不存在的條目（{len(extra)}）：" + "、".join(sorted(extra)[:5]))

    # 正確的不變式是「同一分段內不得重複」，不是「總次數不超過分段數」。
    # 跨段重列（同時有期限又卡住）合法；同段內出現兩次一定是產生邏輯有錯。
    # 2026-09-04：先前寫成寬鬆上限，導致「其他」組整組重複 2 次時仍判通過——
    # 那正是本稽核要抓的那個 bug，寫鬆了就等於沒寫。
    cur, parent = "（未分段）", "（未分段）"
    seen_in_section = {}
    members = {}          # 全收錄分段 → 標題清單
    for ln in body.split("\n"):
        s = norm(ln)
        if s.startswith("### "):
            cur = parent = s
            continue
        if (s.startswith("**") and s.endswith("）")) or s.startswith("[!"):
            cur = s
            continue
        m = link_re.match(s)
        if not m:
            continue
        key = (cur, m.group(1))
        seen_in_section[key] = seen_in_section.get(key, 0) + 1
        if parent == "### 依下一步":
            members.setdefault(parent, []).append(m.group(1))
        elif cur.startswith("[!"):
            members.setdefault(cur, []).append(m.group(1))
    dup = {k: v for k, v in seen_in_section.items() if v > 1}
    if dup:
        problems.append("同一分段內重複列出（{}）：".format(len(dup)) +
                        "、".join(f"{sec} → {title}×{n}" for (sec, title), n in list(dup.items())[:5]))
    # 舊格式索引沒有這些分段時不檢查（過渡期用新工具稽核舊索引不該誤報）
    for sec, got in members.items():
        if len(got) != len(titles) or set(got) != titles:
            problems.append(f"{sec} 應涵蓋全部 {len(titles)} 則，實際 {len(got)} 則")

    for blk in _re.findall(r"\n```+[^\n]*\n(.*?)\n```+[ \t]*\n", text, _re.S):
        if BACKLINK in blk or "[[#索引" in blk:
            problems.append("code fence 內含回索引連結——交接語已被污染，違反 verbatim 規則")
            break

    if problems:
        for x in problems:
            print(f"稽核失敗：{x}", file=sys.stderr)
        return 1
    print(f"稽核通過（{len(entries)} 則條目、{len(counts)} 則被索引、索引連結 {len(linked)} 行）")
    return 0


def main():
    ap = argparse.ArgumentParser(description="為 pending.md 產生可跳轉索引")
    ap.add_argument("--path", type=Path, default=None,
                    help="目標檔案（未給則依 $PENDING_FILE / $CLAUDE_DATA_ROOT / cwd 推斷）")
    ap.add_argument("--check", action="store_true", help="只檢查是否為最新，不寫入")
    ap.add_argument("--audit", action="store_true",
                    help="不變式稽核：驗索引輸出是否正確（--check 只驗一致性，驗不出這個）")
    args = ap.parse_args()
    # 記住路徑是明確給的還是推斷的——護欄只擋推斷的那種
    # 只有真的帶了 --path 才算明示。環境變數雖是使用者設過的，但它在 shell
    # profile 裡全域生效、使用者當下不會意識到，所以仍要把目標印出來。
    args.path_explicit = args.path is not None
    if args.path is None:
        args.path = DEFAULT_PATH

    if not args.path.exists():
        print(f"找不到檔案：{args.path}\n"
              f"用 --path 指定擱置檔位置，或設環境變數 PENDING_FILE：\n"
              f"  python3 {Path(__file__).name} --path ~/your-vault/_harness/handoffs/pending.md\n"
              f"  export PENDING_FILE=~/your-vault/_harness/handoffs/pending.md",
              file=sys.stderr)
        return 2

    text = args.path.read_text(encoding="utf-8")
    entries = extract_entries(text, load_topics(args.path))
    if not entries:
        print(f"警告：{args.path} 中找不到任何條目。"
              f"條目的判準是「位於 INDEX:BEGIN 之後的 `## 標題`，且該段含 `### 交接語`」——"
              f"若條目應該存在，先檢查有沒有漏掉或拼錯 `### 交接語` 這行。", file=sys.stderr)

    # 誤動生產檔的護欄（2026-09-04 立案，14:xx 改為印出目標）。
    #
    # 情境：$CLAUDE_DATA_ROOT 在原作者機器上由 shell profile 全域設定，於是在
    # 任何目錄下不帶 --path 執行本工具，目標都會解析到那個 vault 的生產擱置檔。
    # 實測在 /private/tmp 下執行、目錄本身是空的，工具卻回報「33 則」——讀寫的是
    # 使用者真正的檔案。測試腳本忘記帶 --path 就會摸到生產資料而毫無提示。
    #
    # 為何不用「路徑是否在 cwd 之下」當判準：實測會擋掉正常使用——使用者從
    # LabHub 等子工作區觸發交接時，cwd 不是 vault 根，護欄會拒絕執行，
    # 那比它要防的問題更糟。
    #
    # 採用的做法：路徑非明確指定時，一律把「實際要動哪個檔」印出來。
    # 不阻擋、不互動（skill 的自動流程不能被問話卡住），但讓誤觸在
    # 輸出上肉眼可見——呼應 <completion_gate> 的設計：讓違規變成產出物上
    # 看得見的缺口，而不是依賴執行者記得檢查。
    if not args.path_explicit:
        print(f"目標（未指定 --path，自動解析）：{args.path}", file=sys.stderr)

    # 第二道：寫入前確認目標「長得像擱置檔」。
    # 印出目標只讓誤觸可見，仍可被忽略；這道是真的擋。判準取檔案內容而非路徑——
    # 一個沒有 INDEX 標記、也沒有任何 `### 交接語` 的檔案不是擱置檔，
    # 對它重建索引只會把它弄壞。--check / --audit 是唯讀，不受此限。
    if not (args.check or args.audit):
        looks_like = (BEGIN_PREFIX in text) or ("### 交接語" in text)
        if not looks_like:
            print(f"拒絕寫入：{args.path} 看起來不是擱置檔"
                  f"（找不到 INDEX 標記，也沒有任何 `### 交接語` 區塊）。\n"
                  f"若這確實是新建的擱置檔，先放進 INDEX 標記再跑一次：\n"
                  f"  <!-- INDEX:BEGIN 由 pending_index.py 自動產生，勿手動編輯此區塊 -->\n"
                  f"  <!-- INDEX:END -->",
                  file=sys.stderr)
            return 2

    index_block = build_index(entries)
    updated = apply_index(text, index_block)

    if args.audit:
        # 驗「檔案裡現在的索引」，不是驗剛重算出來的那份——
        # 對 updated 稽核等於又拿工具跟自己比，正是本函式要避免的錯誤。
        return audit(text, entries)

    if args.check:
        if updated == text:
            print(f"索引為最新（{len(entries)} 則）")
            return 0
        print(f"索引已過期，需重建（{len(entries)} 則）", file=sys.stderr)
        return 1

    if updated == text:
        with_links = apply_backlinks(updated)
        if with_links != text:
            args.path.write_text(with_links, encoding="utf-8")
            print(f"索引未變更，已補回索引連結（{len(entries)} 則）")
        else:
            print(f"索引已是最新，未變更（{len(entries)} 則）")
        return 0

    updated = apply_backlinks(updated)
    args.path.write_text(updated, encoding="utf-8")
    print(f"索引已更新：{args.path}（{len(entries)} 則，含回索引連結）")
    return 0


if __name__ == "__main__":
    sys.exit(main())
