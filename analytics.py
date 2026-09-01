from __future__ import annotations

import re
from dataclasses import dataclass
from datetime import date
from sqlalchemy import delete, select

from db import Session, Report, ReportMetric, ReportInsight
from projects import PROJECTS

# The parser is intentionally deterministic: it never invents a number.
# Real Global reports use several layouts, so parsing is line-oriented rather
# than tied to one exact punctuation/order template.
LABELS = {
    "ggr": "GGR", "deposits": "Депозиты", "withdrawals": "Выводы",
    "withdrawal_rate": "Withdrawal Rate", "fd": "FD", "inout": "InOut",
    "registrations": "Регистрации", "paid_users": "Paid Users", "rd": "RD", "bonus_rate": "Bonus Rate",
}
CORE = ("ggr", "deposits", "fd", "inout")

ALIASES = [
    ("withdrawal_rate", re.compile(r"^(?:withdrawal\s*rate|процент\s+вывода|%\s*выводов?)\b", re.I)),
    ("bonus_rate", re.compile(r"^bonus\s*rate\b", re.I)),
    ("paid_users", re.compile(r"^paid\s*users?\b", re.I)),
    ("registrations", re.compile(r"^(?:регистрации|registrations?)\b", re.I)),
    ("withdrawals", re.compile(r"^(?:выводы|withdrawal\s*sum|withdrawals?)\b", re.I)),
    ("deposits", re.compile(r"^(?:депозиты|deposit\s*sum|deposits?)\b", re.I)),
    ("ggr", re.compile(r"^ggr\b", re.I)),
    ("fd", re.compile(r"^(?:количество\s+)?fd\b", re.I)),
    # Do not let InOut% become the absolute InOut metric.
    ("inout", re.compile(r"^inout(?!\s*%)\b", re.I)),
    ("rd", re.compile(r"^rd\b", re.I)),
]

NUM_RE = re.compile(r"[+−-]?\s*\d[\d\s\u00a0]*(?:[.,]\d+)?")
PCT_RE = re.compile(r"([+−-]?\s*\d+(?:[.,]\d+)?)\s*(п\.?\s*п\.?|%)", re.I)
MONEY_OR_NUM_RE = re.compile(r"\$?\s*(\d[\d\s\u00a0]*(?:[.,]\d+)?)")


def _num(s: str) -> float:
    s = s.replace("−", "-").replace("\u00a0", "").replace(" ", "").replace(",", ".")
    return float(s)


def _clean_line(line: str) -> str:
    # Also makes pasted Markdown test reports behave like Telegram plain text.
    return re.sub(r"[*_`]", "", line).strip(" \t•—")


def _segment_heading(line: str, current: str) -> str:
    low = _clean_line(line).lower()
    if re.search(r"\btraffic\b", low):
        return "traffic"
    if re.search(r"\bpartners?\b|партн[её]р", low):
        return "partners"
    # Typical headings that return from a sub-section to project-level prose.
    if re.search(r"ключевые\s+(?:проблем|метрик)|что\s+(?:сделано|делаем)|фокус|приоритет|планы|реализовано", low):
        return "main"
    return current


def _metric_key_and_rest(line: str):
    clean = _clean_line(line)
    for key, rx in ALIASES:
        m = rx.match(clean)
        if m:
            return key, clean[m.end():].lstrip(" \t:—")
    return None, None


def _extract_change(rest: str):
    matches = list(PCT_RE.finditer(rest))
    if not matches:
        return None, None
    # For lines with previous-period values, the WoW change is usually the last percent.
    m = matches[-1]
    unit = "pp" if "п" in m.group(2).lower() else "pct"
    return _num(m.group(1)), unit


def _extract_value(key: str, rest: str):
    # Change-first layout: "GGR -4.5% ($116 689)".
    first_pct = PCT_RE.search(rest)
    if first_pct and rest[:first_pct.start()].strip(" :—-") == "":
        par = re.search(r"\(\s*\$?\s*(\d[\d\s\u00a0]*(?:[.,]\d+)?)\s*\)", rest[first_pct.end():])
        if par:
            return _num(par.group(1))
        # Trend layout: "FD -15.6% (11 984 → 10 113)" => current is RHS.
        arrow = re.search(r"\(\s*\d[\d\s\u00a0]*(?:[.,]\d+)?\s*[→>]\s*(\d[\d\s\u00a0]*(?:[.,]\d+)?)\s*\)", rest[first_pct.end():])
        if arrow:
            return _num(arrow.group(1))
        return None

    # Normal layout: "$1 619 839 (+46%)" or "57,2% (+5,34%)".
    m = MONEY_OR_NUM_RE.search(rest)
    if not m:
        return None
    return _num(m.group(1))


def extract_metrics(text: str) -> list[dict]:
    found = []
    seen = set()
    segment = "main"
    for raw in text.splitlines():
        segment = _segment_heading(raw, segment)
        key, rest = _metric_key_and_rest(raw)
        if not key:
            # Narrative-only changes such as "GGR снизился на 45,5%".
            clean = _clean_line(raw)
            m = re.match(r"^(GGR|NGR|FD|Депозиты)\s+(?:снизил(?:ся|ись)|упал(?:а|и)?|вырос(?:ла|ли)?)\s+на\s+([\d.,]+)%", clean, re.I)
            if m:
                map_key = {"ggr":"ggr", "fd":"fd", "депозиты":"deposits"}.get(m.group(1).lower())
                if map_key and (map_key, segment) not in seen:
                    sign = -1 if re.search(r"сниз|упал", clean, re.I) else 1
                    found.append({"key": map_key, "value": None, "change": sign * _num(m.group(2)), "change_unit": "pct", "segment": segment})
                    seen.add((map_key, segment))
            continue
        if (key, segment) in seen:
            continue
        value = _extract_value(key, rest)
        change, unit = _extract_change(rest)
        # Withdrawal rate's first percentage is the level, not a WoW change.
        if key == "withdrawal_rate":
            pcts = list(PCT_RE.finditer(rest))
            if pcts:
                value = _num(pcts[0].group(1))
                if len(pcts) >= 2:
                    change = _num(pcts[-1].group(1)); unit = "pp" if "п" in pcts[-1].group(2).lower() else "pct"
                else:
                    change = None; unit = None
        found.append({"key": key, "value": value, "change": change, "change_unit": unit, "segment": segment})
        seen.add((key, segment))
    return found

def extract_insight(text: str) -> dict:
    low = text.lower()
    tags = []
    tag_rules = {
        "VIP": ("vip", "вип"),
        "выводы": ("withdrawal", "вывод"),
        "retention": ("retention", "ретен", "повторн", "paid users", "\brd\b"),
        "платежи": ("payment", "платеж", "psp", "approval rate", "\bar\b"),
        "трафик": ("traffic", "трафик", "партнер", "партнёр", "ftd"),
        "anti-fraud": ("anti-fraud", "антифрод", "анти-фрод", "security"),
        "bonus": ("bonus rate", "бонус", "bonus"),
    }
    for tag, words in tag_rules.items():
        if any(re.search(w, low) for w in words):
            tags.append(tag)

    reason = None
    for pat in (
        r"(?:причин[аы]\s*(?:падения|просадки)?\s*[-—:]\s*)([^\n]{8,240})",
        r"(?:причина\s*:\s*)([^\n]{8,240})",
    ):
        m = re.search(pat, text, re.I)
        if m:
            reason = m.group(1).strip(" .;—-")[:240]
            break

    has_action = bool(re.search(r"что делаем|сделали|исправ|запуска|увелич|уменьш|перезапуст|релиз|план", low))
    management = bool(re.search(r"нужн[оа]\s+(?:решени|помощ|эскалац)|требует\s+(?:решени|внимани)|эскалац", low))
    return {"reason": reason, "has_action": has_action, "management": management, "tags": tags}


def metric_level(key: str, change: float | None, unit: str | None) -> int:
    if change is None:
        return 0
    if key in CORE and unit == "pct":
        if change < -20: return 2
        if change <= -10: return 1
    if key == "withdrawal_rate":
        # A report may state either pp or %. We flag the reported increase conservatively in both cases.
        if change > 10: return 2
        if change >= 5: return 1
    return 0


def project_status(metrics: list, insight: ReportInsight | None = None) -> tuple[int, str]:
    main = [m for m in metrics if m.segment == "main"]
    levels = [(m, metric_level(m.metric_key, m.change_value, m.change_unit)) for m in main]
    critical = [x for x in levels if x[1] == 2]
    down10 = [x for x in levels if x[0].metric_key in CORE and x[0].change_value is not None and x[0].change_value <= -10]
    unexplained30 = [x for x in levels if x[0].metric_key in CORE and x[0].change_value is not None and x[0].change_value < -30]
    if len(critical) >= 2 or len(down10) >= 3 or (unexplained30 and not (insight and insight.reason)):
        return 2, "несколько критических отклонений" if len(critical) >= 2 else "сильное снижение ключевых показателей"
    if critical:
        m = critical[0][0]
        return 2, f"{LABELS[m.metric_key]} {m.change_value:+.1f}%" if m.change_value is not None else LABELS[m.metric_key]
    attention = [x for x in levels if x[1] == 1]
    if attention:
        m = attention[0][0]
        suffix = " п.п." if m.change_unit == "pp" else "%"
        return 1, f"{LABELS[m.metric_key]} {m.change_value:+.1f}{suffix}"
    return 0, "без существенных отклонений"


async def upsert_analysis(report_id: int, text: str, replace: bool = False):
    parsed = extract_metrics(text)
    insight_data = extract_insight(text)
    async with Session() as s:
        if replace:
            await s.execute(delete(ReportMetric).where(ReportMetric.report_id == report_id))
        existing = (await s.execute(select(ReportMetric).where(ReportMetric.report_id == report_id))).scalars().all()
        keys = {(m.metric_key, m.segment) for m in existing}
        for item in parsed:
            k = (item["key"], item["segment"])
            if k in keys:
                continue
            s.add(ReportMetric(report_id=report_id, metric_key=item["key"], segment=item["segment"], value=item["value"], change_value=item["change"], change_unit=item["change_unit"]))
            keys.add(k)
        insight = (await s.execute(select(ReportInsight).where(ReportInsight.report_id == report_id))).scalar_one_or_none()
        if not insight:
            insight = ReportInsight(report_id=report_id)
            s.add(insight)
        if insight_data["reason"] and not insight.reason:
            insight.reason = insight_data["reason"]
        insight.has_action = insight.has_action or insight_data["has_action"]
        insight.management_attention = insight.management_attention or insight_data["management"]
        old = set(filter(None, (insight.tags or "").split(",")))
        insight.tags = ",".join(sorted(old | set(insight_data["tags"])))
        await s.commit()


def fmt_change(m) -> str:
    if m is None or m.change_value is None:
        return "—"
    suffix = " п.п." if m.change_unit == "pp" else "%"
    return f"{m.change_value:+.1f}{suffix}".replace(".", ",")


async def build_digest(period_start: date, period_end: date) -> str:
    async with Session() as s:
        reports = (await s.execute(select(Report).where(Report.report_type == "global", Report.period_start == period_start, Report.period_end == period_end).order_by(Report.received_at.desc()))).scalars().all()
        latest = {}
        for r in reports:
            latest.setdefault(r.project, r)

        rows = []
        tag_counts = {}
        positives = []
        management = []
        trends = []
        counts = [0, 0, 0]

        for p in PROJECTS:
            name = p["name"]
            rep = latest.get(name)
            if not rep:
                rows.append((name, 2, {}, "Global-отчёт не предоставлен"))
                counts[2] += 1
                management.append(f"{name} — Global-отчёт не предоставлен")
                continue
            metrics = (await s.execute(select(ReportMetric).where(ReportMetric.report_id == rep.id))).scalars().all()
            insight = (await s.execute(select(ReportInsight).where(ReportInsight.report_id == rep.id))).scalar_one_or_none()
            main = {m.metric_key: m for m in metrics if m.segment == "main"}
            if len([k for k in CORE if k in main and main[k].change_value is not None]) < 2:
                level, signal = 1, "недостаточно данных для полной оценки"
            else:
                level, signal = project_status(metrics, insight)
            counts[level] += 1
            rows.append((name, level, main, signal))
            if insight:
                for tag in filter(None, (insight.tags or "").split(",")):
                    tag_counts[tag] = tag_counts.get(tag, 0) + 1
                if insight.management_attention and name not in " ".join(management):
                    management.append(f"{name} — отмечена необходимость решения/эскалации")
            if level == 2 and name not in " ".join(management):
                management.append(f"{name} — {signal}")
            ggr = main.get("ggr")
            if ggr and ggr.change_value is not None and ggr.change_value >= 10:
                positives.append((ggr.change_value, f"{name} — GGR {fmt_change(ggr)}"))

            # Consecutive negative GGR/FD trend from stored history.
            hist = (await s.execute(select(Report).where(Report.project == name, Report.report_type == "global", Report.period_end <= period_end).order_by(Report.period_end.desc()).limit(4))).scalars().all()
            for key in ("ggr", "fd"):
                seq = []
                for hr in hist:
                    hm = (await s.execute(select(ReportMetric).where(ReportMetric.report_id == hr.id, ReportMetric.metric_key == key, ReportMetric.segment == "main"))).scalar_one_or_none()
                    if hm and hm.change_value is not None and hm.change_value < 0: seq.append(hm)
                    else: break
                if len(seq) >= 3:
                    trends.append(f"{name} — {LABELS[key]} снижается {len(seq)} недели подряд")

    status_emoji = ["🟢", "🟡", "🔴"]
    lines = [
        "📊 <b>Еженедельная сводка по проектам</b>",
        f"{period_start:%d.%m}–{period_end:%d.%m.%Y}", "",
        f"🟢 {counts[0]} — без существенных отклонений",
        f"🟡 {counts[1]} — требуют внимания",
        f"🔴 {counts[2]} — критическое отклонение / нет отчёта", "",
        "<b>📋 Состояние проектов</b>",
    ]
    for name, level, main, signal in rows:
        vals = " · ".join(f"{LABELS[k]} {fmt_change(main.get(k))}" for k in ("ggr", "deposits", "fd", "inout"))
        lines.append(f"{status_emoji[level]} <b>{name}</b> — {vals}")
        if level > 0:
            lines.append(f"   ↳ {signal}")

    exceptions = [r for r in rows if r[1] > 0]
    if exceptions:
        lines += ["", "<b>🔻 Основные отклонения</b>"]
        for name, level, main, signal in exceptions[:6]:
            lines.append(f"{status_emoji[level]} <b>{name}</b> — {signal}")

    common = sorted(((n, t) for t, n in tag_counts.items() if n >= 2), reverse=True)
    if common:
        lines += ["", "<b>⚠️ Общие сигналы</b>"]
        for n, tag in common[:5]: lines.append(f"• {tag} — {n} проекта")

    if management:
        lines += ["", "<b>🎯 Требует внимания руководства</b>"]
        for i, x in enumerate(management[:5], 1): lines.append(f"{i}. {x}")

    lines += ["", "<b>📈 Позитивные сигналы</b>"]
    if positives:
        for _, x in sorted(positives, reverse=True)[:3]: lines.append(f"• {x}")
    lines.append(f"• {counts[0]} из {len(PROJECTS)} проектов без существенных отклонений")

    if trends:
        lines += ["", "<b>📉 Тренды</b>"] + [f"• {x}" for x in trends[:5]]
    return "\n".join(lines)
