import re


STATUS_SUCCESS = "success"
STATUS_FAIL = "fail"
STATUS_PARTIAL = "partial"
STATUS_EMPTY = "empty"
STATUS_ANOMALY = "anomaly"


AA3_TO_1 = {
    "Ala": "A",
    "Arg": "R",
    "Asn": "N",
    "Asp": "D",
    "Cys": "C",
    "Gln": "Q",
    "Glu": "E",
    "Gly": "G",
    "His": "H",
    "Ile": "I",
    "Leu": "L",
    "Lys": "K",
    "Met": "M",
    "Phe": "F",
    "Pro": "P",
    "Ser": "S",
    "Thr": "T",
    "Trp": "W",
    "Tyr": "Y",
    "Val": "V",
    "Ter": "*",
    "Stop": "*",
}


PH_PATTERNS = [
    re.compile(r"\bpH\s*(\d{1,2}(?:\.\d+)?)\s*(?:-|~|to)\s*(\d{1,2}(?:\.\d+)?)\b", re.I),
    re.compile(r"\bpH\s*(?:=|of|at)?\s*(\d{1,2}(?:\.\d+)?)\b", re.I),
]

TEMP_C_UNIT = r"(?:[\u00B0\u00BA]\s*C|\u2103|degrees?\s*C(?:elsius)?|Celsius)(?=$|[\s,;.)])"
TEMP_K_UNIT = r"(?:K|kelvin)(?=$|[\s,;.)])"
TEMP_C_RANGE_PATTERN = re.compile(
    rf"(?<![A-Za-z0-9])(-?\d+(?:\.\d+)?)\s*(?:-|~|to)\s*(-?\d+(?:\.\d+)?)\s*{TEMP_C_UNIT}",
    re.I,
)
TEMP_C_SINGLE_PATTERN = re.compile(rf"(?<![A-Za-z0-9])(-?\d+(?:\.\d+)?)\s*{TEMP_C_UNIT}", re.I)
TEMP_K_RANGE_PATTERN = re.compile(
    rf"(?<![A-Za-z0-9])(\d+(?:\.\d+)?)\s*(?:-|~|to)\s*(\d+(?:\.\d+)?)\s*{TEMP_K_UNIT}",
    re.I,
)
TEMP_K_SINGLE_PATTERN = re.compile(rf"(?<![A-Za-z0-9])(\d+(?:\.\d+)?)\s*{TEMP_K_UNIT}", re.I)
TEMP_K_CONTEXT_PATTERN = re.compile(
    r"\b(?:"
    r"at|around|about|approximately|approx\.?|"
    r"between|from|over|under|near|below|above|"
    r"temperature|temperatures|temp\.?|"
    r"incubat(?:ed|ion)|assay(?:ed)?|measured|performed|"
    r"reaction|growth|optimal|stability|activity|observed|recorded"
    r")\b",
    re.I,
)

ION_PATTERN = re.compile(
    r"\b("
    r"CaCl2|MgCl2|MnCl2|ZnCl2|NaCl|KCl|LiCl|NH4Cl|"
    r"Fe2\+|Fe3\+|Mn2\+|Mg2\+|Ca2\+|Zn2\+|Cu2\+|Co2\+|Ni2\+|Na\+|K\+|Li\+|NH4\+|Cl-|"
    r"[A-Z][a-z]?\d*[+-]"
    r")\b"
)

MUTATION_1LETTER = re.compile(r"\b([A-Z*])(\d+)([A-Z*])\b")
MUTATION_3LETTER = re.compile(
    r"\b(" + "|".join(AA3_TO_1.keys()) + r")(\d+)(" + "|".join(AA3_TO_1.keys()) + r")\b",
    re.I,
)
MUTATION_PAREN_3LETTER = re.compile(
    r"\b([A-Z*])(\d+)\((" + "|".join(AA3_TO_1.keys()) + r")\)\d*\b",
    re.I,
)
INSERTION_PATTERN = re.compile(
    r"\b(?:ins(?=[\s:\-]*[A-Za-z0-9])|insert(?:ion)?(?=[\s:\-]+[A-Za-z0-9]))[:\s-]*([A-Za-z0-9_+\-]+)\b",
    re.I,
)
POINT_INSERTION_PATTERN = re.compile(
    r"\b([A-Z])(\d+)Ins([A-Z]|Ala|Arg|Asn|Asp|Cys|Gln|Glu|Gly|His|Ile|Leu|Lys|Met|Phe|Pro|Ser|Thr|Trp|Tyr|Val)\b",
    re.I,
)
DELETION_PATTERN = re.compile(r"\b(?:del|deletion)(?:[:\s-]+)([A-Za-z][A-Za-z0-9_+\-]*\d+[A-Za-z0-9_+\-]*|\d+[A-Za-z0-9_+\-]*)\b", re.I)
STOP_TOKEN_PATTERN = re.compile(
    r"\b(([A-Z]|Ala|Arg|Asn|Asp|Cys|Gln|Glu|Gly|His|Ile|Leu|Lys|Met|Phe|Pro|Ser|Thr|Trp|Tyr|Val)\d+(?:Stop|Ter|\*))\b",
    re.I,
)
NONCANONICAL_MUTATION_PATTERN = re.compile(r"\b([A-Za-z][A-Za-z0-9-]*?)(([A-Z])(\d{3,5}))\b")
NONCANONICAL_MUTATION_DASH_PATTERN = re.compile(r"\b([A-Za-z][A-Za-z0-9]*)([A-Z])-(\d{3,5})\b")
MUTATION_KEYWORDS = re.compile(
    r"\b(mutant|mutation|variant|substitution|replacement|deletion|insertion|truncation|stop)\b",
    re.I,
)
WILD_KEYWORDS = re.compile(r"\b(wild[\s-]?type|wild type|wt)\b", re.I)
UNPARSED_MUTANT_HINT = re.compile(
    r"\b(mutant enzyme|mutated enzyme|enzyme variant|mutant|truncated|truncation|lacking\s+\d+|c-terminal\s+\d+\s+residues|n-terminal\s+\d+\s+amino\s+acid\s+truncated)\b",
    re.I,
)

PH_ABSENCE_PATTERNS = [
    re.compile(r"\bpH\s+(?:not\s+specified|not\s+reported|not\s+available|unknown)\b", re.I),
    re.compile(r"\bno\s+pH\s+(?:given|reported|specified|available)\b", re.I),
]

TEMP_ABSENCE_PATTERNS = [
    re.compile(r"\btemperature\s+(?:not\s+specified|not\s+reported|not\s+available|unknown)\b", re.I),
    re.compile(r"\bno\s+temperature\s+(?:given|reported|specified|available)\b", re.I),
]

ION_ABSENCE_PATTERNS = [
    re.compile(r"\b(?:no|without)\s+(?:metal\s+)?ions?\b", re.I),
    re.compile(r"\bcofactor\s+(?:not\s+specified|not\s+reported|unknown)\b", re.I),
]

TEXT_REPLACEMENTS = {
    "｡紊": "°C",
    "掳C": "°C",
    "潞C": "°C",
}


def normalize_space(text):
    value = str(text or "")
    for source, target in TEXT_REPLACEMENTS.items():
        value = value.replace(source, target)
    return re.sub(r"\s+", " ", value).strip()


def _dedupe_keep_order(values):
    return list(dict.fromkeys(v for v in values if v))


def _kelvin_match_has_context(text, match):
    start, end = match.span()
    window = text[max(0, start - 24) : min(len(text), end + 24)]
    return bool(TEMP_K_CONTEXT_PATTERN.search(window))


def parse_temperature(text):
    text = normalize_space(text)
    if not text:
        return "", STATUS_EMPTY
    if any(pattern.search(text) for pattern in TEMP_ABSENCE_PATTERNS):
        return "", STATUS_EMPTY

    matches = []
    range_spans = []

    for match in TEMP_C_RANGE_PATTERN.finditer(text):
        matches.append(match.group(0).strip())
        range_spans.append(match.span())

    for match in TEMP_K_RANGE_PATTERN.finditer(text):
        if not _kelvin_match_has_context(text, match):
            continue
        matches.append(match.group(0).strip())
        range_spans.append(match.span())

    def _covered(span):
        return any(span[0] >= start and span[1] <= end for start, end in range_spans)

    for match in TEMP_C_SINGLE_PATTERN.finditer(text):
        if _covered(match.span()):
            continue
        matches.append(match.group(0).strip())

    for match in TEMP_K_SINGLE_PATTERN.finditer(text):
        if _covered(match.span()) or not _kelvin_match_has_context(text, match):
            continue
        matches.append(match.group(0).strip())

    matches = _dedupe_keep_order(matches)
    if matches:
        return " | ".join(matches), STATUS_SUCCESS

    if re.search(rf"({TEMP_C_UNIT}|{TEMP_K_UNIT})", text, re.I):
        return "", STATUS_FAIL

    return "", STATUS_EMPTY


def parse_temperature_value(text):
    text = normalize_space(text)
    if not text or text in {"-", "--", "NA", "N/A", "null"}:
        return "", STATUS_EMPTY
    if re.fullmatch(r"-?\d+(?:\.\d+)?", text):
        return text, STATUS_SUCCESS
    return parse_temperature(text)


def parse_ph(text):
    text = normalize_space(text)
    if not text:
        return "", STATUS_EMPTY
    if any(pattern.search(text) for pattern in PH_ABSENCE_PATTERNS):
        return "", STATUS_EMPTY

    matches = []
    for pattern in PH_PATTERNS:
        for match in pattern.finditer(text):
            raw = match.group(0).strip()
            numbers = [float(x) for x in re.findall(r"\d+(?:\.\d+)?", raw)]
            if not numbers:
                continue
            if any(x < 0 or x > 14 for x in numbers):
                return "", STATUS_ANOMALY
            matches.append(raw)

    matches = _dedupe_keep_order(matches)
    if matches:
        return " | ".join(matches), STATUS_SUCCESS

    if re.search(r"\bpH\b", text, re.I):
        return "", STATUS_FAIL

    return "", STATUS_EMPTY


def parse_ph_value(text):
    text = normalize_space(text)
    if not text or text in {"-", "--", "NA", "N/A", "null"}:
        return "", STATUS_EMPTY
    if re.fullmatch(r"\d{1,2}(?:\.\d+)?", text):
        value = float(text)
        if value < 0 or value > 14:
            return text, STATUS_ANOMALY
        return text, STATUS_SUCCESS
    return parse_ph(text)


def parse_ions(text):
    text = normalize_space(text)
    if not text:
        return "", STATUS_EMPTY
    if any(pattern.search(text) for pattern in ION_ABSENCE_PATTERNS):
        return "", STATUS_EMPTY

    matches = _dedupe_keep_order(m.group(1) for m in ION_PATTERN.finditer(text))
    if matches:
        return " | ".join(matches), STATUS_SUCCESS

    if re.search(r"\b(ion|ions|metal|cofactor|salt)\b", text, re.I):
        return "", STATUS_FAIL

    return "", STATUS_EMPTY


def parse_ions_value(text):
    text = normalize_space(text)
    if not text or text in {"-", "--", "NA", "N/A", "null"}:
        return "", STATUS_EMPTY

    matches = _dedupe_keep_order(m.group(1) for m in ION_PATTERN.finditer(text))
    if matches:
        return " | ".join(matches), STATUS_SUCCESS

    if any(token in text for token in ["+", "Cl", "Br", "Na", "K", "Mg", "Mn", "Zn", "Ca", "Fe", "Cu", "Co", "Ni"]):
        return "", STATUS_FAIL

    return "", STATUS_EMPTY


def _normalize_3letter_mutation(match):
    src = AA3_TO_1[match.group(1).title()]
    pos = match.group(2)
    dst = AA3_TO_1[match.group(3).title()]
    return f"{src}{pos}{dst}"


def _normalize_paren_3letter_mutation(match):
    src = match.group(1)
    pos = match.group(2)
    dst = AA3_TO_1[match.group(3).title()]
    return f"{src}{pos}{dst}"


def _normalize_stop_token(raw_token):
    raw = normalize_space(raw_token)
    return f"{raw} [stop]"


def _normalize_insertion_mutation(match):
    src = match.group(1).upper()
    pos = match.group(2)
    dst = match.group(3)
    if len(dst) > 1:
        dst = AA3_TO_1[dst.title()]
    else:
        dst = dst.upper()
    return f"{src}{pos}ins{dst} [insertion]"


def _normalize_noncanonical_mutation(match):
    prefix = match.group(1)
    residue = match.group(3).upper()
    pos = match.group(4)
    return f"{prefix}:{pos}{residue} [noncanonical]"


def _normalize_noncanonical_dash_mutation(match):
    prefix = match.group(1)
    residue = match.group(2).upper()
    pos = match.group(3)
    return f"{prefix}:{pos}{residue} [noncanonical]"


def parse_mutation_and_type(text):
    text = normalize_space(text)
    if not text:
        return "ambiguous", "", "", STATUS_EMPTY

    raw_mutations = []
    normalized_mutations = []

    for match in MUTATION_1LETTER.finditer(text):
        token = match.group(0)
        raw_mutations.append(token)
        normalized_mutations.append(token)

    for match in MUTATION_3LETTER.finditer(text):
        raw_mutations.append(match.group(0))
        normalized_mutations.append(_normalize_3letter_mutation(match))

    for match in MUTATION_PAREN_3LETTER.finditer(text):
        raw_mutations.append(match.group(0))
        normalized_mutations.append(_normalize_paren_3letter_mutation(match))

    for match in STOP_TOKEN_PATTERN.finditer(text):
        raw_mutations.append(match.group(1))
        normalized_mutations.append(_normalize_stop_token(match.group(1)))

    for match in POINT_INSERTION_PATTERN.finditer(text):
        raw_mutations.append(match.group(0))
        normalized_mutations.append(_normalize_insertion_mutation(match))

    for match in INSERTION_PATTERN.finditer(text):
        token = match.group(1)
        if token and token.lower() != "ertion" and "ins" not in token.lower():
            raw_mutations.append(f"ins:{token}")
            normalized_mutations.append(f"ins:{token} [insertion]")

    for match in DELETION_PATTERN.finditer(text):
        token = match.group(1)
        raw_mutations.append(f"del:{token}")
        normalized_mutations.append(f"del:{token} [deletion]")

    if not normalized_mutations:
        for match in NONCANONICAL_MUTATION_DASH_PATTERN.finditer(text):
            token = match.group(0)
            if any(token == existing for existing in raw_mutations):
                continue
            if "mutant" in text.lower() or "variant" in text.lower() or "mutation" in text.lower():
                raw_mutations.append(token)
                normalized_mutations.append(_normalize_noncanonical_dash_mutation(match))

    if not normalized_mutations:
        for match in NONCANONICAL_MUTATION_PATTERN.finditer(text):
            token = match.group(0)
            upper_token = token.upper()
            if upper_token in {"STOP", "TER"}:
                continue
            if MUTATION_1LETTER.fullmatch(token):
                continue
            if POINT_INSERTION_PATTERN.fullmatch(token):
                continue
            if any(token == existing for existing in raw_mutations):
                continue
            if "mutant" in text.lower() or "variant" in text.lower() or "mutation" in text.lower():
                raw_mutations.append(token)
                normalized_mutations.append(_normalize_noncanonical_mutation(match))

    raw_mutations = _dedupe_keep_order(raw_mutations)
    normalized_mutations = _dedupe_keep_order(normalized_mutations)

    if normalized_mutations:
        return "mutant", " | ".join(raw_mutations), " | ".join(normalized_mutations), STATUS_SUCCESS

    if UNPARSED_MUTANT_HINT.search(text) or MUTATION_KEYWORDS.search(text):
        return "mutant", "", "", STATUS_FAIL

    if WILD_KEYWORDS.search(text):
        return "wild", "", "", STATUS_EMPTY

    return "ambiguous", "", "", STATUS_EMPTY


def combine_parse_status(*statuses):
    statuses = [s for s in statuses if s]
    if not statuses:
        return STATUS_EMPTY
    if STATUS_ANOMALY in statuses:
        return STATUS_ANOMALY
    if all(s == STATUS_EMPTY for s in statuses):
        return STATUS_EMPTY
    if all(s == STATUS_SUCCESS for s in statuses):
        return STATUS_SUCCESS
    if any(s == STATUS_SUCCESS for s in statuses) and any(s in {STATUS_EMPTY, STATUS_FAIL} for s in statuses):
        return STATUS_PARTIAL
    if STATUS_FAIL in statuses and any(s == STATUS_EMPTY for s in statuses):
        return STATUS_PARTIAL
    if STATUS_FAIL in statuses and all(s in {STATUS_FAIL, STATUS_EMPTY} for s in statuses):
        return STATUS_FAIL
    if all(s in {STATUS_SUCCESS, STATUS_EMPTY} for s in statuses):
        return STATUS_PARTIAL if STATUS_EMPTY in statuses else STATUS_SUCCESS
    if STATUS_FAIL in statuses:
        return STATUS_PARTIAL
    return STATUS_PARTIAL
