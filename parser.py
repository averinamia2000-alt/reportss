import re
from datetime import date
from projects import PROJECTS

DATE_RE = re.compile(r"(?P<d1>\d{1,2})[./](?P<m1>\d{1,2})(?:[./](?P<y1>\d{2,4}))?\s*[-–—]\s*(?P<d2>\d{1,2})[./](?P<m2>\d{1,2})(?:[./](?P<y2>\d{2,4}))?")

def norm(s: str) -> str:
    return re.sub(r"\s+", " ", s.lower().replace("_", " ")).strip()

def detect_project(text: str | None):
    if not text: return None
    head = norm(text[:220])
    candidates=[]
    for p in PROJECTS:
        for a in p["aliases"]:
            pos=head.find(norm(a))
            if pos >= 0:
                candidates.append((pos, -len(a), p["name"]))
    return sorted(candidates)[0][2] if candidates else None

def parse_period(text: str | None, received: date):
    if not text: return (None, None)
    m=DATE_RE.search(text)
    if not m: return (None, None)
    y1=m.group("y1"); y2=m.group("y2")
    year2=int(y2) if y2 else received.year
    if year2 < 100: year2 += 2000
    year1=int(y1) if y1 else year2
    if year1 < 100: year1 += 2000
    try:
        return date(year1,int(m.group("m1")),int(m.group("d1"))), date(year2,int(m.group("m2")),int(m.group("d2")))
    except ValueError:
        return (None,None)
