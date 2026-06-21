"""
app/services/matching_service.py

Phase 7 — Teammate compatibility scoring.

Score breakdown (0-100):
  50 pts — Complementary skills  (skills the other has that you don't)
  30 pts — Shared interests       (Jaccard similarity of interest sets)
  20 pts — Same graduation year   (binary)

No ML, no embeddings — pure set arithmetic. Fast and explainable.
"""


def compute_match_score(current_user: dict, other_user: dict) -> tuple[int, str]:
    """
    Return (score, reason) for how well other_user complements current_user.

    score  — integer 0-100
    reason — short human-readable explanation shown on the Matches page
    """
    cp = current_user.get("profile") or {}
    op = other_user.get("profile")   or {}

    # Normalise to lowercase sets for comparison
    c_skills    = {s.lower() for s in cp.get("skills", [])}
    o_skills    = {s.lower() for s in op.get("skills", [])}
    c_interests = {i.lower() for i in cp.get("interests", [])}
    o_interests = {i.lower() for i in op.get("interests", [])}

    # Keep original-case maps so we can display canonical names in the reason
    o_skill_map    = {s.lower(): s for s in op.get("skills", [])}
    o_interest_map = {i.lower(): i for i in op.get("interests", [])}

    reasons: list[str] = []

    # ── 1. Complementary skills (50 pts) ────────────────────────────────────
    # Skills the other person has that the current user does NOT have.
    # Ratio = unique_to_other / total_other  →  scaled to 50.
    unique_to_other = o_skills - c_skills
    if o_skills:
        skill_score = int((len(unique_to_other) / len(o_skills)) * 50)
    else:
        skill_score = 0

    if unique_to_other:
        samples = [o_skill_map.get(s, s.title()) for s in list(unique_to_other)[:2]]
        reasons.append(f"Brings {' and '.join(samples)}")

    # ── 2. Shared interests (30 pts) ────────────────────────────────────────
    # Jaccard similarity: |intersection| / |union|  →  scaled to 30.
    union_interests = c_interests | o_interests
    if union_interests:
        shared       = c_interests & o_interests
        interest_score = int((len(shared) / len(union_interests)) * 30)
    else:
        shared         = set()
        interest_score = 0

    if shared:
        samples = [o_interest_map.get(i, i.title()) for i in list(shared)[:2]]
        reasons.append(f"Shares interest in {' and '.join(samples)}")

    # ── 3. Same graduation year (20 pts) ────────────────────────────────────
    c_year = cp.get("year")
    o_year = op.get("year")
    year_score = 20 if (c_year and o_year and c_year == o_year) else 0

    if year_score:
        reasons.append(f"Same year (Year {c_year})")

    total  = min(skill_score + interest_score + year_score, 100)
    reason = ". ".join(reasons) + "." if reasons else "Potential collaboration opportunity."

    return total, reason
