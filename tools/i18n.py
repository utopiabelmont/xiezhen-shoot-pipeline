"""
i18n.py　页面文字的多语言输出（中文原文 → 英文 / 日文）。

渲染脚本里的文字仍以中文写成。设置环境变量 XIEZHEN_LANG=en 或 ja 后，
make_cards.py 在导入时装上钩子：Pillow 的 text / textlength / textbbox 与 wrap() 先把整段中文
按 locales/<语言>*.json 的对照表换成目标语言，再测量、折行、绘制。对照表的键是原文整句，查不到的保持中文。

  XIEZHEN_LANG=en python tools/make_cards.py --plan ... --images ... --out ...
  XIEZHEN_I18N_COLLECT=strings.txt   中文渲染时把画出的整句原文逐行记下，用来补对照表
  XIEZHEN_I18N_MISSING=missing.txt   译文渲染时把缺译的原文记下

Rendering scripts keep their Chinese source strings. With XIEZHEN_LANG=en|ja the hooks below
translate each whole string through locales/<lang>*.json before it is measured, wrapped and drawn.
"""
from __future__ import annotations

import json
import os
import re
from pathlib import Path

LANG = (os.environ.get("XIEZHEN_LANG") or "zh").strip().lower()
if LANG in ("zh-cn", "cn", "zh_cn"):
    LANG = "zh"
ROOT = Path(__file__).resolve().parents[1]
CJK = re.compile(r"[぀-ヿ㐀-䶿一-鿿！-｠]")

_DICT: dict[str, str] = {}
_OUT: set[str] = set()      # 已是译文的字符串（不再翻译）
_FRAG: set[str] = set()     # wrap() 切出的行（整句已处理过）
_SEEN: set[str] = set()
_COLLECT = os.environ.get("XIEZHEN_I18N_COLLECT")
_SUSPEND = [0]              # wrap() 内部测量半句时不查表、不记录
_MISSING = os.environ.get("XIEZHEN_I18N_MISSING")


def _load():
    if LANG == "zh":
        return
    d = ROOT / "locales"
    for p in sorted(d.glob(f"{LANG}*.json")):
        _DICT.update(json.loads(p.read_text(encoding="utf-8")))
    _OUT.update(_DICT.values())


_load()


def _log(path, s):
    if s in _SEEN:
        return
    _SEEN.add(s)
    with open(path, "a", encoding="utf-8") as fh:
        fh.write(json.dumps(s, ensure_ascii=False) + "\n")


def tr(s):
    """整句查表；多行文字逐行查。中文模式原样返回（可记录）。"""
    if not isinstance(s, str) or not s or not CJK.search(s) or s in _FRAG or s in _OUT:
        return s
    if LANG == "zh":
        if _COLLECT:
            _log(_COLLECT, s)
        return s
    t = _DICT.get(s)
    if t is None and s.strip() != s:
        t2 = _DICT.get(s.strip())
        if t2 is not None:
            t = s[: len(s) - len(s.lstrip())] + t2 + s[len(s.rstrip()):]
    if t is None and "\n" in s:
        parts = [tr(x) for x in s.split("\n")]
        t = "\n".join(parts)
    if t is None:
        if _MISSING:
            _log(_MISSING, s)
        return s
    _OUT.add(t)
    return t


class raw:
    """with raw(): 块内的 Pillow 调用不经过 tr()。"""
    def __enter__(self):
        _SUSPEND[0] += 1

    def __exit__(self, *a):
        _SUSPEND[0] -= 1


def mark_fragments(lines):
    _FRAG.update(x for x in lines if x)
    return lines


def wrap_words(draw, text, f, width):
    """英文按单词折行；过长的单词按字符切开。"""
    out = []
    for para in text.split("\n"):
        words, cur = para.split(" "), ""
        for w in words:
            cand = (cur + " " + w) if cur else w
            if draw.textlength(cand, font=f) <= width or not cur:
                cur = cand
            else:
                out.append(cur); cur = w
            while draw.textlength(cur, font=f) > width and len(cur) > 1:       # 单词本身过长（含换到新行的无空格中文）
                k = len(cur)
                while k > 1 and draw.textlength(cur[:k], font=f) > width:
                    k -= 1
                out.append(cur[:k]); cur = cur[k:]
        out.append(cur)
    return out


def install_pil_hooks():
    """让所有 ImageDraw 的测量与绘制都先经过 tr()。只在非中文时安装。"""
    if LANG == "zh" and not _COLLECT:
        return
    from PIL import ImageDraw
    D = ImageDraw.ImageDraw
    if getattr(D, "_xiezhen_i18n", False):
        return

    def patch(name, pos):
        orig = getattr(D, name)

        def f(self, *args, **kw):
            if _SUSPEND[0]:
                return orig(self, *args, **kw)
            if "text" in kw:
                kw["text"] = tr(kw["text"])
            elif len(args) > pos:
                args = list(args); args[pos] = tr(args[pos]); args = tuple(args)
            return orig(self, *args, **kw)
        setattr(D, name, f)

    patch("text", 1); patch("multiline_text", 1); patch("textbbox", 1); patch("multiline_textbbox", 1)
    patch("textlength", 0)
    D._xiezhen_i18n = True


def html(doc: str) -> str:
    """翻译 HTML 里的文字节点、title/alt/placeholder/aria-label 属性与 <script> 里的引号字符串。"""
    if LANG == "zh" and not _COLLECT:
        return doc
    parts = re.split(r"(<script\b.*?</script>|<style\b.*?</style>)", doc, flags=re.S)
    res = []
    for p in parts:
        if p.startswith("<style"):
            res.append(p)
        elif p.startswith("<script"):
            res.append(re.sub(r"(['\"`])((?:(?!\1)[^\\\n]|\\.)*?)\1",
                              lambda m: m.group(1) + (tr(m.group(2)) if CJK.search(m.group(2)) else m.group(2)) + m.group(1), p))
        else:
            p = re.sub(r'((?:title|alt|placeholder|aria-label)=")([^"]*)(")',
                       lambda m: m.group(1) + _esc(tr(_unesc(m.group(2)))) + m.group(3), p)
            p = re.sub(r">([^<>]+)<", lambda m: ">" + _text_node(m.group(1)) + "<", p)
            res.append(p)
    return "".join(res)


def _unesc(s):
    return s.replace("&quot;", '"').replace("&lt;", "<").replace("&gt;", ">").replace("&amp;", "&")


def _esc(s):
    return s.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;").replace('"', "&quot;")


def _text_node(t):
    if not CJK.search(t):
        return t
    raw = _unesc(t)
    core = raw.strip()
    lead, trail = raw[: len(raw) - len(raw.lstrip())], raw[len(raw.rstrip()):]
    return _esc(lead + tr(core) + trail).replace("&quot;", '"')
