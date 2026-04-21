#!/usr/bin/env python3
"""Fast merge: use pre-verified hunted URLs (no re-test). Match by name to refs."""
import json, sys, re, unicodedata, os

def strip_accents(s):
    return ''.join(c for c in unicodedata.normalize('NFKD', s) if not unicodedata.combining(c))

def norm(s):
    if not s: return ""
    s = strip_accents(s).lower()
    s = re.sub(r'\([^)]*\)', ' ', s)
    s = re.sub(r'\[[^\]]*\]', ' ', s)
    s = re.sub(r'[^\w\s]', ' ', s)
    s = re.sub(r'\b(hd|sd|uhd|fhd|4k|1080p?|720p?|576p?|480p?|360p?|240p?|live|tv|channel|chaine|geo|blocked|east|eastern|west|feed|usa|us|us-|united|states|na|noth|north|america|not 24 7|format mpeg)\b', ' ', s)
    s = re.sub(r'\s+', ' ', s).strip()
    return s

GENERIC = {"tv", "news", "one", "de", "en", "et", "la", "le", "el", "al", "on", "au",
           "la", "el", "i", "ii", "1", "2", "3", "4", "5", "plus", "media", "network", "ent", "hd", "sd"}

def tokens(s):
    return set(t for t in norm(s).split() if t and t not in GENERIC and len(t) >= 2)

def distinctive_tokens(s):
    return [t for t in tokens(s) if len(t) >= 3]

# Country-specific rejection patterns. If the candidate NAME contains any of these substrings
# (case-insensitive), reject the match because it's clearly from the wrong country/region.
REJECT_FOR_REGION = {
    "dz": [
        r'\bfinland\b', r'\bsul\b', r'\bbrazil\b', r'\bbrasil\b', r'\bturkic\b',
        r'\bturkey\b', r'\begypt(?:ian)?\b', r'\bbangla(?:desh)?\b', r'\bcolmar\b',
        r'\blao(?:s)?\b', r'\bphilippines\b', r'\bvietnam\b', r'\bindia\b', r'\bhindi\b',
        r'\brussia\b', r'\bukraine\b', r'\bsudan\b', r'\bburkina\b', r'\beritrea\b',
        r'\biraq\b', r'\biran\b', r'\byemen\b', r'\bsaudi\b', r'\bafghanistan\b',
        r'\bpakistan\b', r'\bnepal\b', r'\bsomalia\b', r'\bniger\b', r'\bmali\b',
        r'\bliberia\b', r'\bguinea\b', r'\bsyria\b', r'\bkenya\b', r'\bethiopia\b',
        r'\bmorocco\b', r'\btunisia\b', r'\bturkish\b', r'\bczech\b', r'\bhungary\b',
        r'\balbania\b', r'\bbulgaria\b', r'\bromania\b', r'\bslovenia\b', r'\bcroatia\b',
        r'\barabia\b', r'\bdubai\b', r'\buae\b', r'\bkuwait\b', r'\bqatar\b', r'\boman\b',
        r'\bCBC\b', r'\b\(us\)\b', r'\bkabc\b', r'\bkcbs\b', r'\bktmc\b',
        r'\bEr TV\b',  # Eritrean
        r'\bFinnish\b', r'\bAfghan\b', r'\bCzech\b',
        r'\bQuran Radio\b',  # Saudi — not Algerian Coran
    ],
    "fr": [
        r'\bfinland\b', r'\busa\b', r'\b\(us\)\b', r'\beastern feed\b',
        r'\blife\s*tv\b',  # generic
        r'\b30a\b',  # 30A Luxe Life (US Florida)
        r'\bBrazil\b', r'\bBrasil\b', r'\bhindi\b', r'\bindia\b',
        r'\bazerbay', r'\brussia(?:n)?\b', r'\brussian\b', r'\bukrain', r'\bshraq',
        r'\bturkic\b', r'\bturkey\b', r'\bgreece\b', r'\bgerman(?:y)?\b',
        r'\bspanish\b', r'\bespanol\b', r'\bgreek\b', r'\bitalian\b', r'\bportugues\b',
        r'\bcambodia\b', r'\bvietnam\b', r'\barabic\b', r'\basharq\b',
        r'\bDrive-in\b', r'\bJunior\b', r'\bEast\b',
        r'\bNovelas\s+Turcas\b', r'\bArte\s+Network\b', r'\bAurora\s+Arte\b',
        r'\bEr TV\b', r'\bNOVELA\b',
    ],
    "us": [
        r'\bfrance\b', r'\bFrench\b', r'\bdeutsch\b', r'\bspanish\b', r'\bitaliano\b',
        r'\bbrasil\b', r'\bportugues\b', r'\bcanal\b(?!\s*\+)',  # canal alone, not canal+
        r'\bturkic\b', r'\bturkey\b', r'\bLao\b', r'\bPhilippines\b',
    ],
}

def region_reject(region, cand_name):
    if not region: return False
    for pat in REJECT_FOR_REGION.get(region, []):
        if re.search(pat, cand_name, re.IGNORECASE):
            return True
    return False

def strict_match(ref_name, cand_name, aliases=None, region=None):
    """Return True if cand plausibly IS ref."""
    if region and region_reject(region, cand_name):
        return False
    aliases = aliases or []
    names = [ref_name] + [a for a in aliases if a]
    cn = norm(cand_name)
    ct = tokens(cand_name)
    for rn in names:
        rnn = norm(rn)
        if not rnn: continue
        if rnn == cn: return True
        # Ref as whole-word substring/phrase of cand
        if re.search(r'(?:^|\s)' + re.escape(rnn) + r'(?:\s|$)', cn):
            return True
        # Token fallback: require ≥2 long distinctive tokens and ALL present in cand.
        # Single-token matches are NOT sufficient (avoids "France 2" → "Radio France Inter")
        dts = distinctive_tokens(rn)
        dts_long = [t for t in dts if len(t) >= 4]
        if len(dts_long) >= 2 and all(t in ct for t in dts_long):
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
    validated_path = sys.argv[1]
    hunted_path = sys.argv[2]
    out_path = sys.argv[3]
    region = sys.argv[4] if len(sys.argv) > 4 else None  # "fr", "dz", "us"

    with open(validated_path) as f:
        data = json.load(f)

    hunted = []
    with open(hunted_path) as f:
        for line in f:
            line = line.strip()
            if not line: continue
            try:
                h = json.loads(line)
                if h.get("_passed") and h.get("url"):
                    hunted.append(h)
            except Exception: pass
    print(f"loaded {len(hunted)} verified hunted entries (region={region})", file=sys.stderr)

    # Also apply region rejection to round-1 winners
    stats = {"hunter_wins": 0, "round1_wins": 0, "none": 0, "round1_rejected_by_region": 0}
    for entry in data:
        ref = entry["ref"]
        ref_name = ref.get("name") or ref.get("branding") or ""
        aliases = list(ref.get("aliases", []) or [])
        if ref.get("branding") and ref.get("branding") != ref_name:
            aliases.append(ref["branding"])

        # Pre-filter existing winner by region rejection
        if entry.get("winner") and region_reject(region, entry["winner"].get("name", "")):
            entry["winner"] = None
            stats["round1_rejected_by_region"] += 1

        matches = []
        for h in hunted:
            if strict_match(ref_name, h["channel"], aliases, region=region):
                matches.append(h)
        # Sort by resolution desc (prefer higher res)
        matches.sort(key=lambda h: -resolution_score(h.get("_resolution", "")))

        if matches:
            h = matches[0]
            entry["winner"] = {
                "name": h["channel"],
                "url": h["url"],
                "source": h.get("source", "hunted"),
                "status": "PASS",
                "codec": h.get("_codec", ""),
                "resolution": h.get("_resolution", ""),
                "score": 1000,
                "tvg_id": "",
                "logo": h.get("logo", ""),
            }
            stats["hunter_wins"] += 1
        elif entry.get("winner"):
            stats["round1_wins"] += 1
        else:
            stats["none"] += 1

    with open(out_path, "w") as f:
        json.dump(data, f, ensure_ascii=False, indent=1)
    print(f"{out_path}: {stats}", file=sys.stderr)

if __name__ == "__main__":
    main()
