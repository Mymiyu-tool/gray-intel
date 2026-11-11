#!/usr/bin/env python3
# Description: OSINT search for underground/gray-market topics: expands Chinese and English slang into query variants, queries DuckDuckGo, Bing and Sogou plus forum/code/social site dorks, then dedupes and scores the hits. Standard library only.
# Display name: Gray Intel
# 显示名称：灰产情报检索
# Timeout: 150
# Parameters:
# {"type":"object","properties":{"query":{"type":"string","description":"Topic or keyword, e.g. 中转站 黑幕"},"action":{"type":"string","enum":["search","expand","sites"],"description":"search (default), expand (show slang variants), sites"},"mode":{"type":"string","enum":["all","web","forum","code","social","market","dark"],"description":"Where to search. Default all."},"engine":{"type":"string","enum":["all","ddg","bing","sogou"],"description":"Default all"},"site":{"type":"string","description":"Extra site: filter, e.g. linux.do"},"extra":{"type":"string","description":"Extra terms to append, space separated"},"limit":{"type":"integer","description":"Max results, default 24"},"expand":{"type":"boolean","description":"Auto expand slang, default true"},"format":{"type":"string","enum":["md","json"],"description":"Default md"}},"required":["query"]}
import base64
import concurrent.futures as cf
import html as htmllib
import json
import os
import re
import sys
import time
import urllib.parse as up
import urllib.request as ur

UA = ("Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 "
      "(KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36")

# --- slang dictionary: canonical term -> variants -------------------------
DICT = {
    "中转站": ["中转站", "API中转", "api relay", "relay station", "2api", "one-api", "new-api", "sub2api", "claude relay", "号池", "倍率"],
    "中转": ["中转", "relay", "proxy api", "反向代理", "反代", "转发接口"],
    "降智": ["降智", "掺水", "掺假", "掉包", "偷换模型", "模型替换", "偷token", "虚标", "缩水", "阉割"],
    "掺水": ["掺水", "注水", "掺假", "adulteration", "模型掉包", "token 虚标"],
    "黑幕": ["黑幕", "内幕", "套路", "骗局", "灰产", "黑产", "产业链", "起底", "scam", "fraud"],
    "跑路": ["跑路", "关站", "失联", "余额不退", "月抛站", "exit scam"],
    "数据": ["数据倒卖", "卖数据", "prompt 泄露", "日志留存", "蒸馏", "训练数据", "data resale", "distillation"],
    "号池": ["号池", "账号池", "订阅拆分", "拼车", "共享账号", "account pool", "subscription sharing"],
    "盗刷": ["盗刷", "黑卡", "信用卡盗刷", "拒付", "chargeback", "stolen card"],
    "盗版": ["盗版", "破解", "crack", "keygen", "warez", "patched", "绿色版"],
    "接码": ["接码", "虚拟号码", "短信验证码", "sms code", "otp bypass", "虚拟卡"],
    "洗钱": ["洗钱", "跑分", "USDT 跑分", "mule account", "money laundering", "四件套"],
    "外挂": ["外挂", "辅助", "透视", "自瞄", "内存修改", "cheat", "aimbot", "esp"],
    "社工": ["社工", "社工库", "人肉", "开盒", "doxxing", "osint", "信息贩卖"],
    "验证码": ["验证码", "captcha", "打码平台", "ocr 识别", "captcha solving"],
    "代理": ["代理", "代理池", "proxy pool", "socks5", "住宅ip", "residential proxy"],
    "封号": ["封号", "封禁", "风控", "ban wave", "account suspension", "风控绕过"],
    "claude": ["claude", "claude code", "anthropic", "sonnet", "opus", "haiku"],
    "gpt": ["gpt", "openai", "chatgpt", "codex"],
}

SITES = {
    "forum": ["linux.do", "v2ex.com", "hostloc.com", "nodeloc.com", "52pojie.cn", "tieba.baidu.com", "zhihu.com"],
    "code": ["github.com", "gitee.com", "pypi.org", "npmjs.com"],
    "social": ["t.me", "x.com", "reddit.com", "weibo.com", "xiaohongshu.com"],
    "market": ["taobao.com", "goofish.com", "t.me", "tieba.baidu.com"],
    "dark": ["onion", "tor.taxi", "dread", "darknet", "telegram 群", "暗网"],
}
SITE_WEIGHT = {
    "linux.do": 3, "v2ex.com": 3, "github.com": 3, "zhihu.com": 2, "hostloc.com": 2,
    "nodeloc.com": 2, "52pojie.cn": 2, "t.me": 2, "reddit.com": 2, "huxiu.com": 4,
    "36kr.com": 4, "21jingji.com": 4, "eeo.com.cn": 4, "chinanews.com": 3, "nbd.com.cn": 3,
    "thepaper.cn": 3, "caixin.com": 3, "x.com": 2,
}
NOISE = ("baidu.com/link", "google.com/url", "sogou.com/link", "javascript:")
# SEO / 带货软文的口气，出现越多越不值得看
MARKETING = ("推荐", "怎么选", "排行", "榜单", "测评", "横向对比", "优惠", "注册送", "充值", "官网",
             "首选", "哪家", "选购", "攻略", "一文看懂", "亲测", "避坑指南", "值得", "教程", "指南",
             "实战", "接入", "首充", "折扣", "秒到", "稳定", "低价")
# 实锤口气
SIGNAL = ("黑幕", "内幕", "骗局", "套路", "跑路", "封号", "判刑", "刑事", "被抓", "曝光", "受害者",
          "维权", "退款", "虚标", "偷换", "偷 token", "偷token", "泄露", "卖数据", "倒卖", "起底", "揭"
          , "实测数据", "检测数据", "不通过", "掉包", "掺水", "注水")


def arg_json():
    raw = os.environ.get("MIYU_ARGS_JSON")
    if not raw:
        raw = sys.stdin.read() or "{}"
    try:
        return json.loads(raw)
    except Exception:
        return {}


def fetch(url, timeout=12, tries=2):
    hdr = {"User-Agent": UA, "Accept-Language": "zh-CN,zh;q=0.9,en;q=0.8"}
    last = None
    for i in range(tries):
        try:
            req = ur.Request(url, headers=hdr)
            with ur.urlopen(req, timeout=timeout) as r:
                data = r.read()
            if len(data) < 2000 and i + 1 < tries:
                time.sleep(1.2)
                continue
            for enc in ("utf-8", "gb18030"):
                try:
                    return data.decode(enc)
                except Exception:
                    continue
            return data.decode("utf-8", "ignore")
        except Exception as e:
            last = e
            time.sleep(1.0 + i)
    raise last


def clean(s):
    s = re.sub(r"<script.*?</script>", " ", s, flags=re.S)
    s = re.sub(r"<[^>]+>", "", s)
    s = htmllib.unescape(s)
    return re.sub(r"\s+", " ", s).strip()


def real_url(u):
    u = htmllib.unescape(u)
    if u.startswith("//"):
        u = "https:" + u
    if "duckduckgo.com/l/" in u or "uddg=" in u:
        q = up.parse_qs(up.urlparse(u).query)
        if q.get("uddg"):
            return q["uddg"][0]
    if "bing.com/ck/a" in u:
        q = up.parse_qs(up.urlparse(u).query)
        v = q.get("u", [""])[0]
        if v.startswith("a1"):
            v = v[2:]
            v += "=" * (-len(v) % 4)
            try:
                return base64.urlsafe_b64decode(v).decode("utf-8", "ignore")
            except Exception:
                pass
    return u


# --- engines --------------------------------------------------------------
def ddg(q):
    t = fetch("https://html.duckduckgo.com/html/?q=" + up.quote(q))
    out = []
    for blk in re.split(r'<div class="result results_links', t)[1:]:
        m = re.search(r'class="result__a"[^>]*href="([^"]+)"[^>]*>(.*?)</a>', blk, re.S)
        if not m:
            continue
        sm = re.search(r'class="result__snippet"[^>]*>(.*?)</a>', blk, re.S)
        out.append({"title": clean(m.group(2)), "url": real_url(m.group(1)),
                    "snippet": clean(sm.group(1)) if sm else "", "engine": "ddg"})
    return out


def bing(q):
    t = fetch("https://www.bing.com/search?q=" + up.quote(q) + "&setlang=zh")
    out = []
    for blk in re.split(r'<li class="b_algo"', t)[1:]:
        m = re.search(r'<h2[^>]*>\s*<a[^>]*href="([^"]+)"[^>]*>(.*?)</a>', blk, re.S)
        if not m:
            continue
        sm = re.search(r"<p[^>]*>(.*?)</p>", blk, re.S)
        out.append({"title": clean(m.group(2)), "url": real_url(m.group(1)),
                    "snippet": clean(sm.group(1)) if sm else "", "engine": "bing"})
    return out


def sogou(q):
    t = fetch("https://www.sogou.com/web?query=" + up.quote(q))
    out = []
    for blk in re.split(r'<div class="vrwrap', t)[1:]:
        m = re.search(r"<h3[^>]*>(.*?)</h3>", blk, re.S)
        if not m:
            continue
        a = re.search(r'<a[^>]*href="([^"]+)"', m.group(1))
        if not a:
            continue
        sm = re.search(r'class="(?:text-layout|str_info|space-txt|fz-mid)"[^>]*>(.*?)</(?:div|p)>', blk, re.S)
        u = real_url(a.group(1))
        if u.startswith("/link"):
            u = "https://www.sogou.com" + u
        out.append({"title": clean(m.group(1)), "url": u,
                    "snippet": clean(sm.group(1)) if sm else "", "engine": "sogou"})
    return out


def so360(q):
    t = fetch("https://www.so.com/s?q=" + up.quote(q))
    out = []
    for blk in re.split(r'<li class="res-list', t)[1:]:
        m = re.search(r'<h3[^>]*>(.*?)</h3>', blk, re.S)
        if not m:
            continue
        md = re.search(r'data-mdurl="([^"]+)"', m.group(1))
        hr = re.search(r'href="([^"]+)"', m.group(1))
        if not hr:
            continue
        u = htmllib.unescape(md.group(1)) if md else real_url(hr.group(1))
        sm = re.search(r'class="res-desc"[^>]*>(.*?)</(?:p|div)>', blk, re.S)
        out.append({"title": clean(m.group(1)), "url": u,
                    "snippet": clean(sm.group(1)) if sm else "", "engine": "360"})
    return out


ENGINES = {"ddg": ddg, "bing": bing, "so360": so360, "sogou": sogou}


# --- query planning -------------------------------------------------------
def expand(q):
    found, variants = [], []
    low = q.lower()
    for k, vs in DICT.items():
        if k.lower() in low:
            found.append(k)
    if not found:
        for ch in re.findall(r"[\u4e00-\u9fa5]{2,4}", q):
            for k in DICT:
                if k in ch or ch in k:
                    found.append(k)
    found = list(dict.fromkeys(found))
    variants.append(q)
    for k in found[:2]:
        alt = [v for v in DICT[k] if v.lower() != k.lower()][:3]
        if alt:
            variants.append(q.replace(k, alt[0]) if k in q else q + " " + alt[0])
    if any(w in low for w in ("中转", "relay", "2api", "号池")):
        variants.append(q + " 骗局 套路 产业链")
        variants.append(q + " 数据倒卖 跑路")
    return found, list(dict.fromkeys(variants))[:5]


def domains(mode, site):
    ds = []
    if mode in ("all", "forum"):
        ds += SITES["forum"]
    if mode in ("all", "code"):
        ds += SITES["code"]
    if mode in ("all", "social"):
        ds += SITES["social"]
    if mode in ("all", "market"):
        ds += SITES["market"]
    if mode == "dark":
        ds += SITES["dark"]
    if site:
        ds = [site] + [d for d in ds if d != site]
    return ds


def score(hit, terms):
    s = 0
    title = hit["title"].lower()
    body = hit["snippet"].lower()
    matched = []
    for t in sorted(set(terms), key=len, reverse=True):
        tl = t.lower()
        if any(tl in m and tl != m for m in matched):
            continue
        if tl in title:
            s += 4
            matched.append(tl)
        elif tl in body:
            s += 1
            matched.append(tl)
    host = up.urlparse(hit["url"]).netloc.replace("www.", "")
    path = up.urlparse(hit["url"]).path
    for d, w in SITE_WEIGHT.items():
        if host.endswith(d):
            s += w
    if any(n in hit["url"] for n in NOISE):
        s -= 2
    if len(hit["title"]) < 6:
        s -= 3
    if not hit["snippet"]:
        s -= 1
    if hit.get("engine") == "sogou":
        s -= 2
    if any(x in host for x in ("rank", "zhongzhuan", "helpaio", "aiapirank")):
        s -= 8
    # 落地页广告：首页 + 卖货语气
    if len(path.strip("/")) < 3 and any(w in title for w in ("中转", "api", "claude", "gpt")):
        s -= 6
    blob = title + " " + body
    s -= 3 * sum(1 for w in MARKETING if w.lower() in blob)
    s += 3 * sum(1 for w in SIGNAL if w.lower() in blob)
    return s


def run(args):
    action = args.get("action", "search")
    q = (args.get("query") or "").strip()
    mode = args.get("mode", "all")
    eng = args.get("engine", "all")
    fmt = args.get("format", "md")
    limit = int(args.get("limit") or 24)
    do_expand = args.get("expand", True)

    found, variants = expand(q) if do_expand else ([], [q])
    if args.get("extra"):
        variants = [v + " " + args["extra"] for v in variants] or [q + " " + args["extra"]]

    if action == "expand":
        return {"query": q, "terms": found,
                "variants": {t: DICT[t] for t in found}, "queries": variants}
    if action == "sites":
        return {"sites": SITES, "weights": SITE_WEIGHT}

    ds = domains(mode, args.get("site"))
    use = ["bing", "so360"] if eng == "all" else [eng]
    tasks = []
    for v in variants:
        for e in use:
            tasks.append((e, v))
    # site dorks: the only reliable way past SEO farms
    for d in ds[:3]:
        tasks.append(("bing", f"{q} 跑路 骗局 黑幕 曝光 site:{d}"))
    tasks = tasks[:13]

    hits, errors = [], []
    with cf.ThreadPoolExecutor(max_workers=4) as ex:
        futs = {ex.submit(ENGINES[e], v): (e, v) for e, v in tasks}
        for f in cf.as_completed(futs):
            e, v = futs[f]
            try:
                for h in f.result():
                    h["q"] = v
                    hits.append(h)
            except Exception as ex2:
                errors.append(f"{e}:{type(ex2).__name__}")

    # sogou only as a fallback: its ranking is noisy
    if len(hits) < 6 and eng in ("all", "sogou"):
        with cf.ThreadPoolExecutor(max_workers=2) as ex:
            futs = {ex.submit(sogou, v): v for v in variants[:3]}
            for f in cf.as_completed(futs):
                try:
                    for h in f.result():
                        h["q"] = futs[f]
                        hits.append(h)
                except Exception as ex2:
                    errors.append(f"sogou:{type(ex2).__name__}")

    seen, uniq = set(), []
    for h in hits:
        key = up.urlparse(h["url"]).netloc + up.urlparse(h["url"]).path
        key = re.sub(r"/+$", "", key)
        if key in seen:
            continue
        seen.add(key)
        h["score"] = score(h, found + [q])
        uniq.append(h)
    uniq.sort(key=lambda x: -x["score"])
    uniq = uniq[:limit]

    if fmt == "json":
        return {"query": q, "terms": found, "queries": variants,
                "count": len(uniq), "results": uniq, "errors": sorted(set(errors))}

    lines = [f"# 灰产情报检索：{q}", ""]
    if found:
        lines.append("**命中的黑话词**：" + "、".join(found))
        lines.append("")
    lines.append(f"**检索式**（{len(variants)} 条，{len(uniq)} 条结果）：")
    for v in variants:
        lines.append(f"- `{v}`")
    lines.append("")
    if not uniq:
        lines.append("没有结果。换个词，或调 mode / engine。")
    for i, h in enumerate(uniq, 1):
        host = up.urlparse(h["url"]).netloc.replace("www.", "")
        lines.append(f"{i}. [{h['title'] or host}]({h['url']})  `{host}` · {h['score']}分 · {h['engine']}")
        if h["snippet"]:
            lines.append(f"   > {h['snippet'][:220]}")
    if errors:
        lines.append("")
        lines.append("失败的请求：" + ", ".join(sorted(set(errors))))
    return "\n".join(lines)


if __name__ == "__main__":
    a = arg_json()
    if not (a.get("query") or a.get("action") in ("sites",)):
        print(json.dumps({"error": "query required"}, ensure_ascii=False))
        sys.exit(0)
    r = run(a)
    if isinstance(r, str):
        print(r)
    else:
        print(json.dumps(r, ensure_ascii=False, indent=1))
