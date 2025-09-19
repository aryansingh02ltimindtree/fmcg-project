
import argparse, json, re, random, sys
from typing import Optional, Tuple, List

MONTHS = ["Jan","Feb","Mar","Apr","May","Jun","Jul","Aug","Sep","Oct","Nov","Dec"]

def _pct(x: float) -> float:
    return x*100 if isinstance(x, (int,float)) and abs(x) <= 1.0 else x

def _fmt_pct(x: float) -> str:
    return f"{_pct(x):.1f}%".replace("-0.0%","0.0%")

def _fmt_cr(x: Optional[float]) -> Optional[str]:
    if x is None:
        return None
    return f"₹{float(x):.2f} Cr".replace(".00","")

def _readable_period(period: str) -> str:
    if not isinstance(period, str) or not period.strip():
        return ""
    ytd = "YTD" in period.upper()
    m = re.findall(r"(\d{4})-(\d{2})", period)
    if not m:
        return period
    if len(m) == 1:
        y, mo = m[0]
        s = f"{MONTHS[int(mo)-1]} {y}"
    else:
        (y1, m1), (y2, m2) = m[0], m[-1]
        if y1 == y2:
            s = f"{MONTHS[int(m1)-1]}–{MONTHS[int(m2)-1]} {y1}"
        else:
            s = f"{MONTHS[int(m1)-1]} {y1}–{MONTHS[int(m2)-1]} {y2}"
    return f"{s} (YTD)" if ytd else s

def _growth_words(p: float) -> List[str]:
    # p is percent (8.1), not fraction
    if p >= 15:   return ["surged","jumped","climbed sharply"]
    if p >= 8:    return ["grew","expanded","picked up"]
    if p >= 3:    return ["inched up","ticked up","nudged higher"]
    if p > -3:    return ["was flat","held steady","was unchanged"]
    if p > -8:    return ["softened","eased","dipped"]
    if p > -15:   return ["declined","fell","contracted"]
    return ["contracted","slid","dropped"]

def _share_phrase(share: Optional[float]) -> List[str]:
    if share is None:
        return ["has share"]
    p = _pct(share)
    s = f"{_fmt_pct(p)}"
    if p >= 50: return [f"dominates with {s} share",
                        f"commands {s} share",
                        f"tops the market at {s}"]
    if p >= 35: return [f"leads with {s} share",
                        f"holds {s} share",
                        f"is the front-runner at {s}"]
    if p >= 28: return [f"holds {s} share",
                        f"maintains {s} share"]
    if p >= 22: return [f"has a narrow lead at {s}",
                        f"edges ahead at {s}",
                        f"keeps a slight edge at {s}"]
    return [f"has {s} share"]

def _pair_edge(a_share: Optional[float], b_share: Optional[float]) -> List[str]:
    if a_share is None or b_share is None:
        return ["vs"]
    gap = abs(_pct(a_share) - _pct(b_share))
    if gap < 2:  return ["is neck-and-neck with"]
    if gap < 5:  return ["has a narrow lead over", "edges past"]
    if gap < 10: return ["leads over"]
    return ["is well ahead of"]

def _too_wordy(b: str, max_words=26) -> bool:
    return len(b.replace("•","").split()) > max_words

def _numbers_in_text(b: str):
    # returns (crores, percents)
    import re
    crs = [float(x) for x in re.findall(r"₹\s*([0-9]+(?:\.[0-9]+)?)", b)]
    pcs = [float(x) for x in re.findall(r"([0-9]+(?:\.[0-9]+)?)%", b)]
    return crs, pcs

def _contains_only_source_numbers(b: str, obj: dict) -> bool:
    """
    Tolerant check:
    - Crores: allow ±0.02 Cr tolerance; accept 2 or 3 decimals.
    - Percents: JSON may store fractions (0.081); NLG prints 8.1%.
      We accept if |printed_pct - 100*fraction| <= 0.2
    """
    # 1) Collect candidate crore values from JSON
    crore_fields = []
    for k in ("mat_sales_cr","ytd_sales_cr","mat_cr_a","mat_cr_b","ytd_cr","ytd_cr_a","ytd_cr_b"):
        v = obj.get(k)
        if isinstance(v, (int,float)):
            crore_fields.append(float(v))
    # leaders array
    for ld in obj.get("leaders", []) or []:
        v = ld.get("ytd_cr") or ld.get("mat_cr")
        if isinstance(v, (int,float)):
            crore_fields.append(float(v))

    # 2) Collect candidate percent (as FRACTIONS) and also shares
    frac_fields = []
    for k in obj.keys():
        if "yoy" in k or "share" in k:
            v = obj.get(k)
            if isinstance(v, (int,float)):
                frac_fields.append(float(v))
    # leaders share
    if obj.get("leaders"):
        v = obj["leaders"][0].get("share")
        if isinstance(v, (int,float)):
            frac_fields.append(float(v))

    # 3) Parse numbers from text and compare
    cr_text, pc_text = _numbers_in_text(b)

    # crores check
    for n in cr_text:
        if not any(abs(n - c) <= 0.02 or abs(n - round(c,2)) <= 0.02 or abs(n - round(c,3)) <= 0.02
                   for c in crore_fields):
            return False

    # percent check (printed like 8.1 where JSON may have 0.081)
    for p_print in pc_text:
        if not any(abs(p_print - (f*100.0)) <= 0.2 or abs(p_print - round(f*100.0,1)) <= 0.2
                   for f in frac_fields):
            return False

    return True

def _ctx_phrase(category: str, market: str, variant: int) -> str:
    if category and market:
        return ["The {cat} market in {mkt}",
                "In {mkt} {cat}",
                "Across {mkt}, {cat}"][variant % 3].format(cat=category.lower(), mkt=market)
    if category:
        return ["The {cat} market",
                "In {cat}",
                "Across {cat}"][variant % 3].format(cat=category.lower())
    if market:
        return ["The market in {mkt}",
                "In {mkt}",
                "Across {mkt}"][variant % 3].format(mkt=market)
    return ["The market","In the market","Across the market"][variant % 3]

def nlg_summary_variants(obj: dict, k: int) -> List[List[str]]:
    cat = obj.get("category","")
    mkt = obj.get("market","")
    per = obj.get("period","")
    ytd = obj.get("ytd_sales_cr")
    yoy = obj.get("yoy")
    leaders = obj.get("leaders") or []
    lb = leaders[0]["brand"] if leaders and isinstance(leaders[0], dict) else None
    ls = leaders[0].get("share") if leaders and isinstance(leaders[0], dict) else None
    ly = leaders[0].get("ytd_cr") if leaders and isinstance(leaders[0], dict) else None

    period_str = _readable_period(per)
    p = _pct(yoy) if isinstance(yoy, (int,float)) else None
    verbs = _growth_words(p if p is not None else 0.0)
    ytd_txt = _fmt_cr(ytd)
    yoy_txt = _fmt_pct(p) if p is not None else None
    share_opts = _share_phrase(ls) if ls is not None else ["leads"]
    ly_txt = _fmt_cr(ly)

    out = []
    for i in range(k):
        ctx = _ctx_phrase(cat, mkt, i)
        verb = random.choice(verbs)

        # Two ordering styles
        if random.choice([True, False]):
            parts = [ctx, verb]
            if yoy_txt: parts.append(yoy_txt)
            if ytd_txt: parts += [random.choice(["reaching","to"]), ytd_txt]
        else:
            parts = [ctx]
            if ytd_txt: parts += [random.choice(["reached","totaled"]), ytd_txt]
            if yoy_txt: parts += [random.choice(["up","up by","growing"]), yoy_txt, "YoY"]
            else: parts.append("YoY")

        if period_str: parts.append(period_str)
        b1 = "• " + " ".join([x for x in parts if x]).strip()
        if "YoY YoY" in b1: b1 = b1.replace("YoY YoY","YoY")
        if not b1.endswith("."): b1 += "."

        if lb:
            sp = random.choice(share_opts)
            if ly_txt:
                b2 = f"• {lb} {sp}, contributing {ly_txt}."
            else:
                b2 = f"• {lb} {sp}."
        else:
            b2 = ""

        # compactness & number integrity
        if not _too_wordy(b1) and _contains_only_source_numbers(b1, obj):
            if b2 and not _contains_only_source_numbers(b2, obj):
                b2 = ""
            out.append([b1, b2])
    return out

def nlg_pair_variants(obj: dict, k: int) -> List[List[str]]:
    cat = obj.get("category","")
    mkt = obj.get("market","")
    per = obj.get("period","")
    a, b = obj.get("brand_a",""), obj.get("brand_b","")
    a_cr, b_cr = obj.get("ytd_cr_a"), obj.get("ytd_cr_b")
    a_sh, b_sh = obj.get("share_a"), obj.get("share_b")
    a_y, b_y = obj.get("yoy_a"), obj.get("yoy_b")

    period_str = _readable_period(per)
    edges = _pair_edge(a_sh, b_sh)

    out = []
    for i in range(k):
        ctx = _ctx_phrase(cat, mkt, i)
        lead = random.choice(edges)
        bits = [ctx + ",", f"{a} {lead} {b}:"]
        if a_cr is not None and b_cr is not None:
            bits.append(f"{_fmt_cr(a_cr)} vs {_fmt_cr(b_cr)};")
        if a_sh is not None and b_sh is not None:
            bits.append(f"share {_fmt_pct(a_sh)} vs {_fmt_pct(b_sh)};")
        if a_y is not None and b_y is not None:
            bits.append(f"YoY {_fmt_pct(a_y)} vs {_fmt_pct(b_y)};")
        s = " ".join(bits).rstrip(";")
        s = re.sub(r"\s+"," ", s)
        if period_str: s += f" ({period_str})."
        else: s += "."
        b1 = "• " + s
        if not _too_wordy(b1) and _contains_only_source_numbers(b1, obj):
            out.append([b1])
    return out

def _extract_obj(line_obj: dict) -> Optional[dict]:
    # Supports two schemas
    if "task" in line_obj:
        return line_obj
    if isinstance(line_obj.get("input"), dict) and "task" in line_obj["input"]:
        return line_obj["input"]
    return None

def convert_file(in_path: str, out_path: str, variants: int, variants_ytd: int | None) -> int:

    written = 0
    with open(in_path, "r", encoding="utf-8") as f, open(out_path, "w", encoding="utf-8") as w:
        for line in f:
            line = line.strip()
            if not line:
                continue
            try:
                obj = json.loads(line)
            except json.JSONDecodeError:
                continue
            src = _extract_obj(obj)
            if not isinstance(src, dict):
                continue

            task = (src.get("task") or "").lower()

# decide variants per task (YTD can override)
            k = variants_ytd if (task == "ytd_summary" and variants_ytd) else variants

            if task in ("ytd_summary","mat_summary"):
                variants_list = nlg_summary_variants(src, k=k)
                for b1, b2 in variants_list:
                    if not b1:
                        continue
                    out = b1 if not b2 else (b1 + "\n" + b2)
                    row = {
                        "instruction": "Write exactly 2 short, human-like FMCG bullets from the JSON. Use readable dates. Keep numbers unchanged.\n\nJSON:\n"+json.dumps(src, ensure_ascii=False),
                        "input": "",
                        "output": out
                    }
                    w.write(json.dumps(row, ensure_ascii=False) + "\n")
                    written += 1
            elif task == "brand_pair":
                variants_list = nlg_pair_variants(src, k=variants)  # no YTD override here
                for (b1,) in variants_list:
                    row = {
                        "instruction": "Write exactly 1 short, human-like brand-pair bullet from the JSON. Mention sales (₹ Cr), shares (%), and YoY if present. Use readable dates.\n\nJSON:\n"+json.dumps(src, ensure_ascii=False),
                        "input": "",
                        "output": b1
                    }
                    w.write(json.dumps(row, ensure_ascii=False) + "\n")
                    written += 1
            else:
                continue

    return written

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--in-train", required=True, help="Path to existing train JSONL")
    ap.add_argument("--in-val",   required=True, help="Path to existing val JSONL")
    ap.add_argument("--out-train", required=True, help="Output path for NLG train JSONL")
    ap.add_argument("--out-val",   required=True, help="Output path for NLG val JSONL")
    ap.add_argument("--variants-ytd", type=int, default=None,help="Overrides --variants for ytd_summary only (e.g., 5)")

    ap.add_argument("--variants", type=int, default=3, help="Number of alternate phrasings per example")
    args = ap.parse_args()

    n1 = convert_file(args.in_train, args.out_train, args.variants, args.variants_ytd)
    n2 = convert_file(args.in_val,   args.out_val,   args.variants, args.variants_ytd)


    print(f"Wrote {n1} rows to {args.out_train}")
    print(f"Wrote {n2} rows to {args.out_val}")

if __name__ == "__main__":
    main()
