"""Standalone verification of competition scout deterministic extraction."""
from app.tools.competitor_scout import (
    _extract_prices,
    _extract_keywords,
    CompetitorScout,
    CompetitionScanResult,
    CompetitorProfile,
    FEATURE_KEYWORDS,
    POSITIVE_WORDS,
    NEGATIVE_WORDS,
    is_competition_task,
    extract_named_competitors,
)

text = (
    "Pricing starts at $25/month per user. Also $99 / year plans. "
    "Free trial available. Great dashboard with analytics and automation, "
    "very intuitive and easy. Some say it is expensive and slow at times."
)

prices = _extract_prices(text)
print("PRICES:", prices)
assert "$25/month" in prices, "expected $25/month captured"
assert any("99" in p for p in prices), "expected $99 captured"
assert "free trial" in prices, "expected free trial captured"
assert not any("free free" in p for p in prices), "no duplicated free prefix"

feats = _extract_keywords(text, FEATURE_KEYWORDS, 6)
print("FEATURES:", feats)
assert "analytics" in feats and "automation" in feats

strengths = _extract_keywords(text, POSITIVE_WORDS, 4)
print("STRENGTHS:", strengths)
assert "intuitive" in strengths

weaknesses = _extract_keywords(text, NEGATIVE_WORDS, 4)
print("WEAKNESSES:", weaknesses)
assert "expensive" in weaknesses

profile = CompetitorProfile(
    name="HubSpot",
    website="hubspot.com",
    pricing=["$25/month", "free trial"],
    features=["analytics", "automation"],
    strengths=["intuitive"],
    weaknesses=["expensive"],
    sources=[{"url": "https://hubspot.com/pricing", "title": "Pricing"}],
    sites_checked=6,
)
result = CompetitionScanResult(user_input="x", competitors=[profile])
matrix = CompetitorScout._build_matrix(result)
print("MATRIX:")
print(matrix)
assert "$25/month" in matrix, "dollar amount must survive into the matrix"

# detection + name extraction sanity
assert is_competition_task("do a competitor analysis vs HubSpot")
assert not is_competition_task("write me a poem about cats")
own, names = extract_named_competitors(
    "Compare my CRM SalesFlow vs HubSpot and Zoho CRM"
)
print("OWN:", own, "| COMPETITORS:", names)
assert "HubSpot" in names and "Zoho CRM" in names

print("ALL_SCOUT_CHECKS_PASSED")
