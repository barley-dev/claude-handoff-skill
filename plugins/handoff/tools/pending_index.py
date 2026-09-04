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
        entries.append({
            "title": title,
            "date": date,
            "status": status,
            "deadline": _cell(body, "期限"),
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


def build_index(entries):
    """產生索引 markdown 區塊。

    三段結構，依「打開檔案時想知道什麼」排序：
      1. 現在該做什麼 —— 有期限的、可立刻開工的
      2. 依主題分組 —— 看出哪些工作是同一條線
      3. 卡住的 —— 有明確阻塞，看了不必再判斷一次
    """
    lines = [BEGIN, "", "## 索引", ""]

    blocked = [e for e in entries if e["blocked"]]
    active = [e for e in entries if not e["blocked"]]
    dated = sorted([e for e in active if e["deadline"]], key=lambda e: e["deadline"])

    lines.append(f"共 {len(entries)} 則：可動手 {len(active)}、卡住 {len(blocked)}。點標題跳到該則。")
    lines.append("")

    def link(e):
        return f"[[#{e['title']}]]"

    # ── 1. 現在該做什麼 ──
    if dated:
        lines += ["### 有期限", ""]
        for e in dated:
            unblocks = [o for o in entries if o["blocked"] and e["title"][:24] in o["blocked"]]
            note = f" — 期限 {e['deadline']}"
            if unblocks:
                note += f"；做完會解鎖 {len(unblocks)} 則"
            lines.append(f"- {link(e)}{note}")
        lines.append("")

    # ── 2. 依主題分組 ──
    lines += ["### 依主題", ""]
    by_topic = {}
    for e in entries:
        by_topic.setdefault(e["topic"], []).append(e)
    # 多則的主題優先顯示，「其他」殿後
    def topic_key(item):
        name, group = item
        return (name == "其他", -len(group), name)
    for name, group in sorted(by_topic.items(), key=topic_key):
        # 「其他」一律由下方專區印，這裡跳過。
        # 2026-09-04：原本寫 `len(group) == 1 and name == "其他"`，只擋掉「其他」剛好
        # 1 則的情況；一旦有 2 則以上，主題迴圈印一次、專區又印一次，該組全部重複。
        # 實害：43 個索引連結對 33 則條目，10 則重複。--check 與斷鏈檢查都不會發現，
        # 因為兩者比對的是「重跑是否一致」，不是「輸出是否正確」。
        if name == "其他":
            continue
        lines.append(f"**{name}**（{len(group)}）")
        lines.append("")
        for e in group:
            marks = []
            if e["deadline"]:
                marks.append(f"期限 {e['deadline']}")
            if e["blocked"]:
                marks.append("卡住")
            suffix = f" — {'；'.join(marks)}" if marks else ""
            lines.append(f"- {link(e)}{suffix}")
        lines.append("")

    others = by_topic.get("其他", [])
    if others:
        lines.append(f"**其他**（{len(others)}）")
        lines.append("")
        for e in others:
            suffix = " — 卡住" if e["blocked"] else ""
            lines.append(f"- {link(e)}{suffix}")
        lines.append("")

    # ── 3. 卡住的 ──
    if blocked:
        lines += ["### 卡住（有明確阻塞，不必再判斷一次）", ""]
        for e in blocked:
            reason = e["blocked"]
            reason = reason.replace("**", "").strip()
            if len(reason) > 58:
                reason = reason[:58] + "…"
            lines.append(f"- {link(e)}")
            lines.append(f"  - 等：{reason}")
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
      2. 每則出現次數不超過索引分段數（跨段重列合法，同段重複不合法）
      3. code fence 內不得含回索引連結（違反 SKILL.md 的 verbatim 硬規則）
    """
    import re as _re
    from collections import Counter

    problems = []
    body = text.split(BEGIN_PREFIX)[1].split(END)[0] if BEGIN_PREFIX in text else ""
    linked = [_re.match(r"^- \[\[#([^\]|]+)", ln.strip()).group(1)
              for ln in body.split("\n")
              if _re.match(r"^- \[\[#([^\]|]+)", ln.strip())]
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
    cur = "（未分段）"
    seen_in_section = {}
    for ln in body.split("\n"):
        s = ln.strip()
        if s.startswith("### ") or (s.startswith("**") and s.endswith("）")):
            cur = s
            continue
        m = _re.match(r"^- \[\[#([^\]|]+)", s)
        if not m:
            continue
        key = (cur, m.group(1))
        seen_in_section[key] = seen_in_section.get(key, 0) + 1
    dup = {k: v for k, v in seen_in_section.items() if v > 1}
    if dup:
        problems.append("同一分段內重複列出（{}）：".format(len(dup)) +
                        "、".join(f"{sec} → {title}×{n}" for (sec, title), n in list(dup.items())[:5]))

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
