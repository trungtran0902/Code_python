"""Test compare logic: RapidFuzz vs JS levenshtein-based token_set_ratio"""
import sys
import io
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')

from rapidfuzz import fuzz
from unidecode import unidecode


# ===== PYTHON FUNCTIONS (from sosanh_loc_xem_file.py) =====
def normalize_text_py(text):
    if text is None:
        return ""
    text = unidecode(str(text).lower())
    for ch in [",", ".", "-", "/", "\\"]:
        text = text.replace(ch, " ")
    return " ".join(text.split())


# ===== JS FUNCTIONS (reimplemented in Python for comparison) =====
import unicodedata
import re

def normalize_text_js(text):
    if not text:
        return ""
    s = str(text).strip().lower()
    # NFD + remove combining marks
    s = unicodedata.normalize("NFD", s)
    s = re.sub(r'[\u0300-\u036f]', '', s)
    s = s.replace('đ', 'd')
    s = re.sub(r'[,.\-/\\]+', ' ', s)
    return re.sub(r'\s+', ' ', s).strip()


def levenshtein_ratio_js(s1, s2):
    """JS levenshteinRatio reimplemented in Python"""
    if s1 == s2:
        return 1.0
    len1, len2 = len(s1), len(s2)
    if len1 == 0 or len2 == 0:
        return 0
    matrix = [[0] * (len2 + 1) for _ in range(len1 + 1)]
    for i in range(len1 + 1):
        matrix[i][0] = i
    for j in range(len2 + 1):
        matrix[0][j] = j
    for i in range(1, len1 + 1):
        for j in range(1, len2 + 1):
            cost = 0 if s1[i-1] == s2[j-1] else 1
            matrix[i][j] = min(
                matrix[i-1][j] + 1,
                matrix[i][j-1] + 1,
                matrix[i-1][j-1] + cost
            )
    dist = matrix[len1][len2]
    return (len1 + len2 - dist) / (len1 + len2)


def token_set_ratio_js(s1, s2):
    """JS tokenSetRatio reimplemented in Python"""
    if not s1 or not s2:
        return 0
    tokens1 = set(w for w in s1.split(' ') if w)
    tokens2 = set(w for w in s2.split(' ') if w)
    if not tokens1 or not tokens2:
        return 0

    intersect = sorted(x for x in tokens1 if x in tokens2)
    diff1 = sorted(x for x in tokens1 if x not in tokens2)
    diff2 = sorted(x for x in tokens2 if x not in tokens1)

    t0 = ' '.join(intersect)
    t1 = ' '.join(intersect + diff1)
    t2 = ' '.join(intersect + diff2)

    r1 = levenshtein_ratio_js(t0, t1) if t0 else 0
    r2 = levenshtein_ratio_js(t0, t2) if t0 else 0
    r3 = levenshtein_ratio_js(t1, t2)

    return round(max(r1, r2, r3) * 100)


# ===== TEST CASES =====
test_pairs = [
    # (Tên nguồn 1, Tên nguồn 2) - các trường hợp thực tế Foody
    ("Sữa Kem Milkai - 73 Phan Trung", "Sữa Kem Milkai - 73 Phan Trung"),   # identical
    ("Quán Cơm Bình Dân Ba Mươi", "Quán Ăn Bình Dân"),                       # partial match
    ("Pharmacity - 233 Hoàng Bá Bích", "Pharmacy - 233 Hoàng Bá Bích"),       # typo
    ("TONY COFFEE & MORE 2", "Tony Coffee And More"),                          # different
    ("Rêver Drinks - Cà Phê Phin Đậm Đà", "Rever Drinks"),                    # subset
    ("ABC Bakery - 134 Phạm Văn Thuận", "ABC Bakery 134 Pham Van Thuan"),      # same after normalize
    ("Tiệm Trà Laha - 120 Nguyễn Ái Quốc", "Laha Tea - 120 Nguyen Ai Quoc"), # different names
    ("Cha Lợi Dầu Long - Quốc Lộ 1A", "quoc lo 1a long binh"),               # partial address-like
    ("Blue Food & Tea", "Blue Food Tea Nguyen Ai Quoc"),                       # subset with extra
    ("Gà rán và Mỳ Ý - Jollibee", "Jollibee - Pham Van Thuan"),              # partial brand
]

print("=" * 100)
print(f"{'Input s1':<40} {'Input s2':<35} {'Py normalize':<6} {'JS normalize':<6} {'RapidFuzz':<10} {'JS algo':<10} {'Diff':<6}")
print("=" * 100)

for s1, s2 in test_pairs:
    n1_py = normalize_text_py(s1)
    n2_py = normalize_text_py(s2)
    n1_js = normalize_text_js(s1)
    n2_js = normalize_text_js(s2)

    norm_match = "✅" if n1_py == n1_js and n2_py == n2_js else "❌"
    
    score_py = fuzz.token_set_ratio(n1_py, n2_py)
    score_js = token_set_ratio_js(n1_js, n2_js)
    diff = abs(score_py - score_js)
    diff_str = f"{'✅' if diff <= 3 else '⚠️'} {diff}"

    print(f"{s1[:38]:<40} {s2[:33]:<35} {norm_match:<6}  {norm_match:<6}  {score_py:<10} {score_js:<10} {diff_str}")

print("\n" + "=" * 100)
print("Legend: RapidFuzz = fuzz.token_set_ratio (Python), JS algo = levenshtein-based token_set_ratio (JS)")
print("Diff ≤ 3 is acceptable (due to different ratio formula: RapidFuzz uses Indel, JS uses Levenshtein)")
