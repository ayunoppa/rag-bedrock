import re
from typing import List

# 日本語を含む素朴な文分割（句点を優先）
_SPLIT_PAT = re.compile(r'(?<=。)\s*|(?<=！)\s*|(?<=！)\s*|(?<=？)\s*')

def split_into_chunks(text: str, max_chars: int = 800) -> List[str]:
    """
    日本語向けの簡易チャンク分割。
    - 句点「。！？」「改行」で分割し、max_chars を超えないようマージ
    """
    if not text:
        return []
    # まずは行区切り → 文区切り
    lines = []
    for line in text.splitlines():
        line = line.strip()
        if not line:
            continue
        parts = [p for p in _SPLIT_PAT.split(line) if p]
        lines.extend(parts)

    chunks = []
    buf = ""
    for sent in lines:
        # 余裕があれば結合、なければフラッシュ
        if len(buf) + len(sent) + 1 <= max_chars:
            buf = f"{buf}{sent}".strip()
        else:
            if buf:
                chunks.append(buf)
            buf = sent
    if buf:
        chunks.append(buf)
    return chunks

