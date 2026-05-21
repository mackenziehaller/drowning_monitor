"""Google News RSS search using feedparser + trafilatura for full article text."""
import hashlib
import urllib.parse
import urllib.request
from datetime import datetime, timedelta, timezone
from email.utils import parsedate_to_datetime

import feedparser
import trafilatura

from .logger import get_logger, log_search

# ---------------------------------------------------------------------------
# KEYWORD MATCHING
# ---------------------------------------------------------------------------
# Two-tier system:
#   1. STRONG KEYWORDS  — a single phrase that on its own signals a water incident.
#   2. COMPOUND RULES   — (Group A) AND (Group B): one term from each must appear.
#                         Avoids enumerating every exact phrase combination.
#
# To add new coverage:
#   • New single signal  → append to KEYWORDS
#   • New action phrase  → append to the relevant Group A list below
#   • New water body     → append to _WATER_BODIES (shared across rules)
#   • New person/role    → append to _WATER_PEOPLE
# ---------------------------------------------------------------------------

# Shared water-body terms used across multiple compound rules
_WATER_BODIES = [
    "water", "waters",
    "river", "creek", "stream", "waterway", "canal",
    "lake", "dam", "reservoir", "weir", "lagoon",
    "pool", "swimming pool", "aquatic centre", "water park",
    "ocean", "sea", "surf", "swell", "waves",
    "beach", "coast", "coastline", "shoreline",
    "harbour", "harbor", "marina", "port", "bay", "inlet",
    "estuary", "gorge", "waterfall", "swimming hole", "waterhole",
    "billabong", "rockpool", "rock pool",
    "flood", "floodwater", "flood waters", "flash flood", "stormwater",
    "rapids", "current", "channel",
]

# Shared water-activity person types
_WATER_PEOPLE = [
    "swimmer", "swimmers",
    "snorkeller", "snorkeler", "snorkelling", "snorkeling",
    "diver", "divers", "diving", "scuba", "freediver", "spearfisher",
    "fisherman", "fisher", "angler", "rock fisher",
    "kayaker", "kayak", "canoeist", "canoe",
    "surfer", "surfing",
    "paddler", "paddleboarding", "paddleboard",
    "boater", "boating", "boat", "vessel",
    "jetskier", "jet ski", "pwc",
    "rower", "rowing",
    "child", "children", "toddler", "infant", "baby", "kid", "kids",
    "teenager", "teen", "youth",
    "nippers", "nipper",
]

# STRONG keywords — standalone signals, no second word needed
KEYWORDS = [
    # Core drowning terms
    "drown", "drowning", "drowned", "drowns",
    "near-drowning", "near drowning",
    "submerged", "submersion",
    # Rescue organisations & roles
    "surf lifesaving", "surf life saving",
    "lifesaving", "life saving",
    "lifeguard", "life guard",
    "water police",
    "marine area command",
    "marine rescue",
    "swift water rescue",
    "flood rescue",
    "aquatic rescue",
    "rescue helicopter",
    "water rescue",
    # Activities that dominate drowning stats
    "rock fishing",
    "overboard", "man overboard",
    # Medical response at water scenes
    "defibrillator",
    # Missing persons (water-specific)
    "missing swimmer",
    "missing fisherman",
    "missing snorkeller",
    "missing diver",
    # Organisations
    "nippers",
    "swim teacher", "swimming teacher", "swimming instructor",
    "surf patrol", "beach patrol",
    "surf club",
    # Vessels
    "capsized", "capsize",
    # Natural hazards
    "rip current", "riptide", "rip tide",
    "king tide",
    # Other
    "search and rescue",
]

# COMPOUND keyword rules — text must match one term from Group A AND one from Group B
COMPOUND_KEYWORDS = [
    # Rule 1 — "pulled/dragged/recovered/rescued from" + any water body
    (
        ["pulled from", "dragged from", "lifted from", "hauled from",
         "recovered from", "rescued from", "removed from", "retrieved from",
         "pulled out of", "dragged out of", "lifted out of", "hauled out of"],
        _WATER_BODIES,
    ),
    # Rule 2 — "body found / body recovered" + water body
    (
        ["body found", "body recovered", "body retrieved", "body located",
         "remains found", "remains recovered",
         "found in the water", "found in water", "found floating",
         "found face down", "found face-down", "found unresponsive"],
        _WATER_BODIES,
    ),
    # Rule 3 — "swept / washed / fell / jumped" + water context
    (
        ["swept off", "swept into", "swept away",
         "washed off", "washed into", "washed away",
         "fell into", "fell off", "fell overboard", "fallen into", "fallen overboard",
         "jumped in", "jumped into", "jumped off", "jumped from",
         "plunged into", "plunged off"],
        _WATER_BODIES + ["rocks", "cliff", "pier", "jetty", "bridge", "wharf"],
    ),
    # Rule 4 — "missing" + water person/activity
    (
        ["missing"],
        _WATER_PEOPLE,
    ),
    # Rule 5 — search terms + water person or body
    (
        ["search underway", "search continues", "search operation",
         "search and rescue", "searching for", "still searching",
         "divers searching", "police searching", "water police searching",
         "coast guard searching", "helicopter searching"],
        _WATER_PEOPLE + ["body", "man", "woman", "person", "persons", "people"],
    ),
    # Rule 6 — medical emergency + water location
    (
        ["unconscious", "unresponsive", "not breathing", "stopped breathing",
         "cpr", "resuscitation", "resuscitated", "life support",
         "critical condition", "fighting for life", "defibrillator"],
        _WATER_BODIES,
    ),
    # Rule 7 — death / died + water location
    (
        ["died", "death", "fatal", "fatality", "killed", "dead"],
        _WATER_BODIES,
    ),
    # Rule 8 — child / toddler + water body (catches "child dies at pool" even without "drown")
    (
        ["child", "children", "toddler", "infant", "baby", "kid",
         "teenager", "teen", "youth", "nippers", "nipper"],
        _WATER_BODIES,
    ),
    # Rule 9 — flood / fast water + person in danger
    (
        ["flood", "flash flood", "floodwater", "flood waters",
         "rapids", "fast-moving water", "fast flowing"],
        ["trapped", "swept", "missing", "rescued", "dead", "body",
         "victim", "driver", "motorist", "car", "vehicle"],
    ),
    # Rule 10 — water activity + incident/emergency
    (
        ["swimming", "surfing", "snorkelling", "snorkeling", "diving",
         "paddling", "kayaking", "boating", "fishing", "rock fishing"],
        ["incident", "accident", "emergency", "tragedy", "death", "died",
         "fatal", "injured", "critical", "rescued", "missing"],
    ),
]


# ---------------------------------------------------------------------------
# KEYWORD WEIGHTS
# ---------------------------------------------------------------------------
# Each strong keyword has a score. Higher = more confident signal.
# Articles are scored by summing all matched weights.
# Compound rules each have a base weight too.
#
# Tuning guide:
#   10 = unambiguous drowning term (drown, drowned, near-drowning)
#    8 = official response org or role (water police, lifeguard, surf lifesaving)
#    7 = specific incident type (rip current, capsized, overboard, rock fishing)
#    5 = medical response at a scene (cpr, defibrillator, unconscious)
#    3 = supporting signal — needs other words to be meaningful (missing swimmer)
#
# DEFAULT_THRESHOLD: minimum score for an article to pass the filter.
# Lower = more recall (catch more, including noise).
# Higher = more precision (fewer false positives, may miss edge cases).
# Tune this using: python score_tune.py  (once you have a real labelled dataset)
# ---------------------------------------------------------------------------

DEFAULT_THRESHOLD = 5  # start here; tune with score_tune.py once you have real data

KEYWORD_WEIGHTS: dict[str, int] = {
    # Core — unambiguous
    "drown":            10,
    "drowning":         10,
    "drowned":          10,
    "drowns":           10,
    "near-drowning":    10,
    "near drowning":    10,
    "submerged":         8,
    "submersion":        8,
    # Official response orgs/roles — very specific
    "water police":      8,
    "marine area command": 8,
    "marine rescue":     8,
    "surf lifesaving":   8,
    "surf life saving":  8,
    "lifesaving":        7,
    "life saving":       7,
    "lifeguard":         7,
    "life guard":        7,
    "swift water rescue": 8,
    "flood rescue":      8,
    "aquatic rescue":    8,
    "rescue helicopter": 7,
    "water rescue":      7,
    "search and rescue": 6,
    # Incident types
    "rock fishing":      8,
    "overboard":         8,
    "man overboard":     9,
    "capsized":          8,
    "capsize":           8,
    "rip current":       8,
    "riptide":           8,
    "rip tide":          8,
    "king tide":         5,
    # Medical response
    "defibrillator":     7,
    # Missing persons (water-specific combos)
    "missing swimmer":   8,
    "missing fisherman": 8,
    "missing snorkeller": 8,
    "missing diver":     8,
    # Organisations / programs
    "nippers":           6,
    "swim teacher":      5,
    "swimming teacher":  5,
    "swimming instructor": 5,
    "surf patrol":       6,
    "beach patrol":      6,
    "surf club":         4,
}

# Compound rule weights — score added when both Group A and Group B match
COMPOUND_WEIGHTS: list[int] = [
    8,   # Rule 1 — pulled/recovered from + water body   (very specific)
    8,   # Rule 2 — body found + water body              (very specific)
    7,   # Rule 3 — swept/fell/jumped + water            (specific)
    5,   # Rule 4 — missing + water person               (moderate — "missing child" is noisy)
    6,   # Rule 5 — searching for + water person/body    (moderate)
    7,   # Rule 6 — medical emergency + water location   (specific)
    6,   # Rule 7 — died/death/fatal + water location    (moderate — "death at beach" still noisy)
    4,   # Rule 8 — child/toddler + water body           (low — very noisy on its own)
    7,   # Rule 9 — flood/rapids + person in danger      (specific)
    6,   # Rule 10 — water activity + incident/emergency (moderate)
]


def score_text(text: str) -> tuple[int, list[str]]:
    """
    Score a text against all keyword rules.
    Returns (total_score, list_of_match_explanations).

    Score is additive — multiple signals stack.
    Use DEFAULT_THRESHOLD to decide pass/fail.
    Tune threshold with score_tune.py once you have labelled real-world data.
    """
    lower = text.lower()
    total = 0
    reasons = []

    # Tier 1 — strong keywords (additive — multiple matches stack)
    for kw, weight in KEYWORD_WEIGHTS.items():
        if kw in lower:
            total += weight
            reasons.append(f"+{weight} [{kw}]")

    # Tier 2 — compound rules (each rule fires at most once)
    for i, ((group_a, group_b), weight) in enumerate(zip(COMPOUND_KEYWORDS, COMPOUND_WEIGHTS)):
        matched_a = next((a for a in group_a if a in lower), None)
        matched_b = next((b for b in group_b if b in lower), None)
        if matched_a and matched_b:
            total += weight
            reasons.append(f"+{weight} [rule {i+1}: '{matched_a}' + '{matched_b}']")

    return total, reasons


def _has_keyword(text: str, threshold: int = DEFAULT_THRESHOLD) -> bool:
    """Binary pass/fail based on score >= threshold. Keeps existing interface intact."""
    score, _ = score_text(text)
    return score >= threshold

# --- Google News RSS queries ---
# Simple targeted queries outperform complex boolean queries on Google News RSS.
# Subject + verb + location keeps results fresh and relevant.
_GNEWS_QUERIES = [
    # National — person type
    "drowns Australia",
    "drowned Australia",
    "man drowns Australia",
    "man drowned Australia",
    "woman drowns Australia",
    "woman drowned Australia",
    "boy drowns Australia",
    "girl drowns Australia",
    "child drowns Australia",
    "toddler drowns Australia",
    "swimmer drowns Australia",
    # National — incident type
    "body found water Australia",
    "body recovered water Australia",
    "body recovered creek Australia",
    "body recovered beach Australia",
    "body recovered river Australia",
    "body recovered Australia",
    "missing swimmer Australia",
    "water rescue Australia",
    "swift water rescue Australia",
    "flood rescue Australia",
    "rock fishing drowning Australia",
    "boat capsize Australia",
    "capsized Australia",
    # National — response/recovery
    "pulled from water Australia",
    "pulled from river Australia",
    "body pulled from water Australia",
    "water police Australia",
    "surf lifesaving rescue Australia",
    "rescue helicopter water Australia",
    # State-specific — catches regional stories not in national coverage
    "drowning Queensland",
    "drowning NSW",
    "drowning Victoria",
    "drowning Western Australia",
    "drowning Northern Territory",
    "drowning South Australia",
    "drowning Tasmania",
    "drowned Queensland",
    "drowned NSW",
    "drowned Victoria",
    "drowned Western Australia",
    # Location-specific incident types
    "rip current death Australia",
    "flash flood missing Australia",
    "gorge drowning Australia",
    "dam drowning Australia",
    "creek drowning Australia",
]

RSS_QUERY = _GNEWS_QUERIES[0]  # used in log output

GNEWS_FEED_URLS = [
    "https://news.google.com/rss/search?q="
    + urllib.parse.quote(q)
    + "&hl=en-AU&gl=AU&ceid=AU:en"
    for q in _GNEWS_QUERIES
]

# --- Direct RSS feeds from Australian news outlets ---
# These are broad feeds; keyword filtering removes non-drowning articles.
DIRECT_FEED_URLS = [
    "https://www.abc.net.au/news/feed/51120/rss.xml",   # ABC National
    "https://www.abc.net.au/news/feed/45910/rss.xml",   # ABC Top Stories
    "https://www.abc.net.au/news/feed/1300/rss.xml",    # ABC NSW
    "https://www.9news.com.au/rss",                      # 9News Australia
    "https://7news.com.au/feed",                         # 7News Australia
    "http://sls.com.au/feed/",                           # Surf Life Saving Australia
    # Police & emergency services — direct media release feeds
    "https://pfes.nt.gov.au/news.rss",                  # NT Police, Fire & Emergency Services
    "https://www.police.tas.gov.au/feed/",              # Tasmania Police
]

FEED_URLS = GNEWS_FEED_URLS  # backwards compat alias


def _is_dry_run() -> bool:
    import os
    return os.getenv("DRY_RUN", "").lower() in ("1", "true", "yes")


_HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
                  "(KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36",
    "Accept-Language": "en-AU,en;q=0.9",
}


def _resolve_url(google_url: str) -> str:
    """Decode a Google News redirect URL to get the real article URL."""
    try:
        from googlenewsdecoder import new_decoderv1
        result = new_decoderv1(google_url)
        if result.get("status") and result.get("decoded_url"):
            return result["decoded_url"]
    except Exception:
        pass
    return google_url


def _parse_feed_date(entry) -> datetime | None:
    """Parse a feedparser entry's published date into a timezone-aware datetime."""
    raw = getattr(entry, "published", None) or getattr(entry, "updated", None)
    if not raw:
        return None
    try:
        return parsedate_to_datetime(raw)
    except Exception:
        return None





def _uid(date_str: str, location: str) -> str:
    """MD5 of date + location — same incident from different sources → same UID."""
    return hashlib.md5(f"{date_str}_{location}".lower().encode()).hexdigest()


_MOCK_ARTICLES = [
    {
        "title": "[DRY RUN] Man drowns at Bondi Beach, Sydney",
        "url": "https://example.com/bondi-drowning",
        "pub_date": datetime.now(timezone.utc).isoformat(),
        "text": "A man in his 30s drowned at Bondi Beach in Sydney on Monday afternoon. "
                "Emergency services were called at 2pm. The man was pulled from the water "
                "by surf lifesavers but could not be revived. Police have confirmed the death "
                "is not being treated as suspicious.",
        "source": "abc.net.au",
    },
    {
        "title": "[DRY RUN] Child rescued from pool in Brisbane",
        "url": "https://example.com/brisbane-pool-rescue",
        "pub_date": datetime.now(timezone.utc).isoformat(),
        "text": "Queensland paramedics responded to a near-drowning incident at a backyard pool "
                "in Brisbane's north on Monday morning. A 4-year-old girl was pulled from the "
                "pool by a family member and treated by paramedics. The child was taken to "
                "Queensland Children's Hospital in a stable condition.",
        "source": "couriermail.com.au",
    },
]


def fetch_drowning_leads(max_articles: int = 80) -> dict:
    """Fetch Australian drowning news leads from multiple RSS sources.

    Pulls from:
    - Google News RSS (targeted subject+verb+location queries)
    - Direct RSS feeds from ABC, 9News, 7News, SLSA

    For each candidate article within the past 3 days that contains a drowning
    keyword, fetches and cleans the full article text using trafilatura.

    Args:
        max_articles: Maximum number of articles to return after filtering.

    Returns:
        A dict with 'articles' (list of dicts with title, url, pub_date, text, source)
        and 'total' count. Returns mock data if DRY_RUN=true.
    """
    logger = get_logger()

    if _is_dry_run():
        logger.info("DRY RUN — returning mock articles")
        return {"articles": _MOCK_ARTICLES, "total": len(_MOCK_ARTICLES), "dry_run": True}

    cutoff = datetime.now(timezone.utc) - timedelta(days=7)  # 7-day window: Google News RSS pub_dates are unreliable — LLM does actual freshness filtering

    # Fetch all feeds — Google News queries + direct outlet feeds
    all_entries = []
    total_raw = 0
    for feed_url in GNEWS_FEED_URLS + DIRECT_FEED_URLS:
        try:
            feed = feedparser.parse(feed_url)
            all_entries.extend(feed.entries)
            total_raw += len(feed.entries)
        except Exception as e:
            logger.error(f"RSS fetch failed ({feed_url[:60]}): {e}")

    if not all_entries:
        return {"articles": [], "total": 0, "error": "all RSS feeds failed"}

    articles = []
    filtered = []

    # --- Pass 1: title-only pre-filter (covers ALL entries, no scraping) ---
    # This avoids the [:max_articles * N] cap that previously cut off articles
    # buried below today's flood of irrelevant posts from broad direct feeds.
    seen_links = set()
    candidates = []
    for entry in all_entries:
        link = getattr(entry, "link", "") or ""
        if not link or link in seen_links:
            filtered.append(("duplicate-link", entry.title[:60], link))
            continue
        seen_links.add(link)

        pub_date = _parse_feed_date(entry)
        if pub_date and pub_date < cutoff:
            filtered.append(("pubDate-too-old", entry.title[:60], link))
            continue

        # Pass 1 uses a LOW threshold (score >= 1) — any single signal in the
        # title OR blurb is enough to proceed to scraping. Short titles don't
        # have enough words to reach threshold=5 on their own, so we'd drop
        # real incidents. Full text gets the normal threshold in Pass 2.
        blurb = getattr(entry, "summary", "") or ""
        title_score, _ = score_text(entry.title + " " + blurb)
        if title_score < 1:
            filtered.append(("no-keyword-match-title", entry.title[:60], link))
            continue

        candidates.append(entry)

    # Sort candidates newest-first before scraping
    def _sort_key(e):
        d = _parse_feed_date(e)
        return d if d else datetime.min.replace(tzinfo=timezone.utc)

    candidates.sort(key=_sort_key, reverse=True)

    # --- Pass 2: resolve URL, scrape text, deduplicate by real URL ---
    import requests
    seen_urls = set()
    for entry in candidates:
        if len(articles) >= max_articles:
            break

        pub_date = _parse_feed_date(entry)
        real_url = _resolve_url(entry.link)

        if real_url in seen_urls:
            filtered.append(("duplicate-url", entry.title[:60], real_url))
            continue

        # Scrape full article text via requests + trafilatura
        try:
            r = requests.get(real_url, headers=_HEADERS, timeout=10)
            text = trafilatura.extract(r.text) if r.status_code == 200 else None
        except Exception:
            text = None

        # Always mark URL seen after first attempt so later duplicates are skipped
        seen_urls.add(real_url)

        if not text:
            # Fall back to the RSS blurb when the full article can't be scraped
            # (paywall, JS-rendered page, timeout, etc.). The blurb is usually
            # enough for the LLM to extract the key facts.
            blurb = getattr(entry, "summary", "") or ""
            if blurb:
                text = blurb
                filtered.append(("no-text-used-blurb", entry.title[:60], real_url))
            else:
                filtered.append(("no-text", entry.title[:60], real_url))
                continue

        # Pass 2: full text + title combined score must reach DEFAULT_THRESHOLD.
        # Combine both so a weak title + strong article body still passes.
        combined = entry.title + " " + text
        full_score, _ = score_text(combined)
        if full_score < DEFAULT_THRESHOLD:
            filtered.append(("no-keyword-match", entry.title[:60], real_url))
            continue

        source = getattr(entry, "source", {})
        source_name = source.get("title", "") if isinstance(source, dict) else ""

        articles.append({
            "title": entry.title,
            "url": real_url,
            "pub_date": pub_date.isoformat() if pub_date else "unknown",
            "text": text[:5000],  # 5K chars — date/location often appear mid-article, 2K was too short
            "source": source_name,
        })

    log_search(logger, RSS_QUERY, total_raw, len(articles), filtered)
    return {"articles": articles, "total": len(articles)}
