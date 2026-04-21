#!/usr/bin/env python3
"""Tighten matcher results: reject winners whose name doesn't contain the ref's distinctive token(s).
Also rank by resolution (prefer higher).
"""
import json, sys, re, unicodedata

def strip_accents(s):
    return ''.join(c for c in unicodedata.normalize('NFKD', s) if not unicodedata.combining(c))

def norm(s):
    if not s: return ""
    s = strip_accents(s).lower()
    s = re.sub(r'\([^)]*\)', ' ', s)
    s = re.sub(r'\[[^\]]*\]', ' ', s)
    s = re.sub(r'[^\w\s]', ' ', s)
    s = re.sub(r'\b(hd|sd|uhd|fhd|4k|1080p?|720p?|576p?|480p?|360p?|240p?|live|tv|channel|chaine|geo|blocked)\b', ' ', s)
    s = re.sub(r'\s+', ' ', s).strip()
    return s

# Tokens that are too generic to be distinctive
GENERIC = {"tv", "news", "one", "de", "en", "et", "la", "le", "el", "al", "on", "au", "de",
           "el", "i", "ii", "1", "2", "3", "4", "5", "plus"}

def distinctive_tokens(name):
    n = norm(name)
    toks = [t for t in n.split() if t and t not in GENERIC and len(t) >= 3]
    return toks

def is_valid_match(ref_name, cand_name, ref_aliases=None):
    """Return True ONLY if cand_name plausibly IS the ref_name channel.
    Much stricter than the matcher: require the ref's distinctive token(s) to actually appear in cand,
    not vice-versa (a substring of ref being inside cand). """
    ref_aliases = ref_aliases or []
    all_ref_names = [ref_name] + list(ref_aliases)
    cand_norm = norm(cand_name)
    cand_toks = set(t for t in cand_norm.split() if len(t) >= 2)

    for rn in all_ref_names:
        if not rn: continue
        rnn = norm(rn)
        if not rnn: continue

        # 1) exact normalized match
        if rnn == cand_norm: return True

        # 2) full ref name is a substring of cand (e.g., "tf1" in "tf1 hd series films")
        # Must require word boundary-ish — i.e. rnn appears as whole token or bordered by space
        if rnn in cand_norm:
            # Check it's not a false substring like "f1" inside "tf1".
            # Require surrounding characters to be whitespace or string-edge.
            import re as _re
            if _re.search(r'(?:^|\s)' + _re.escape(rnn) + r'(?:\s|$)', cand_norm):
                return True

        # 3) distinctive token(s) of ref all present in cand_toks (and at least one is ≥4 chars)
        dts = distinctive_tokens(rn)
        dts_long = [t for t in dts if len(t) >= 4]
        if dts_long and all(t in cand_toks for t in dts_long):
            # Require ALL long distinctive tokens present, and at least one IS long
            return True
        # 4) for multi-token refs, at least N-1 of N distinctive tokens present
        if len(dts) >= 3:
            present = sum(1 for t in dts if t in cand_toks)
            if present >= len(dts) - 1 and present >= 2:
                return True
    return False

def resolution_score(res):
    if not res or "x" not in res: return 0
    try:
        w, h = res.split("x")
        return int(w) * int(h)
    except Exception:
        return 0

def main():
    in_path = sys.argv[1]
    out_path = sys.argv[2]
    strict = sys.argv[3].lower() == "strict" if len(sys.argv) > 3 else False
    with open(in_path) as f:
        data = json.load(f)

    out = []
    stats = {"kept": 0, "rejected": 0, "no_winner": 0, "strict_reject": 0}
    for e in data:
        ref = e["ref"]
        ref_name = ref.get("name") or ref.get("branding") or ""
        ref_aliases = ref.get("aliases", [])
        if ref.get("branding") and ref.get("branding") != ref_name:
            ref_aliases = [ref["branding"]] + list(ref_aliases)

        # Re-pick best winner from tested[] that BOTH passes 5-gate AND matches name
        tested = e.get("tested", [])
        valid_passes = []
        for t in tested:
            if t.get("status") != "PASS": continue
            if is_valid_match(ref_name, t.get("name", ""), ref_aliases):
                valid_passes.append(t)

        # In strict mode, only keep name-validated passes
        # Otherwise, fall back to original winner if any
        if strict:
            # sort by score desc, then resolution desc
            valid_passes.sort(key=lambda t: (-t.get("score", 0), -resolution_score(t.get("resolution", ""))))
            winner = valid_passes[0] if valid_passes else None
            if winner:
                stats["kept"] += 1
            elif e.get("winner"):
                stats["strict_reject"] += 1
                winner = None
            else:
                stats["no_winner"] += 1
                winner = None
        else:
            if valid_passes:
                valid_passes.sort(key=lambda t: (-t.get("score", 0), -resolution_score(t.get("resolution", ""))))
                winner = valid_passes[0]
                stats["kept"] += 1
            elif e.get("winner"):
                winner = e["winner"]
                stats["kept"] += 1
            else:
                winner = None
                stats["no_winner"] += 1

        out.append({**e, "winner": winner, "valid_passes": valid_passes})

    with open(out_path, "w") as f:
        json.dump(out, f, ensure_ascii=False, indent=1)

    print(f"{in_path} -> {out_path}: {stats}", file=sys.stderr)

if __name__ == "__main__":
    main()
