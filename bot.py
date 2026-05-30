"""
Twitter Content Bot — MCLB DAO
Positioning: DeFi Liquidity DAO / Professional Treasury & Liquidity Management

Generates two types of drafts per run:
  1. REPLIES      — direct replies to target protocols/operators + DeFi conversations
  2. QUOTE TWEETS — same pool, framed as a QT with MCLB commentary on top

Run: python3 bot.py
Then open the dashboard to review and post.
"""

import asyncio
import json
import os
import random
import re
import time
from pathlib import Path

import anthropic
from dotenv import load_dotenv
from playwright.async_api import async_playwright

load_dotenv(dotenv_path=Path(__file__).parent / ".env", override=True)

# ── Config ─────────────────────────────────────────────────────────────────────

ANTHROPIC_API_KEY  = os.getenv("ANTHROPIC_API_KEY")
MAX_REPLY_DRAFTS = int(os.getenv("MAX_REPLY_DRAFTS", "15"))
MAX_QT_DRAFTS    = int(os.getenv("MAX_QT_DRAFTS", "8"))

DRAFTS_FILE           = Path(__file__).parent / "drafts.json"
SEEN_POSTS_FILE       = Path(__file__).parent / "seen_posts.json"
BROWSER_COOKIES_FILE  = Path(__file__).parent / "browser_cookies.json"
PARTNER_ACCOUNTS_FILE = Path(__file__).parent / "partner_accounts.json"

# ── Identity & voice ───────────────────────────────────────────────────────────

IDENTITY = """
You are MCLB DAO (Millennium Club DAO). A crypto-native investment and liquidity DAO.

WHAT MCLB DAO IS:
An on-chain capital engine built around active treasury deployment, DeFi strategy, and ecosystem growth.
Not a passive investment club. Not a single-purpose protocol.
A DAO that invests, builds, partners, and incubates — creating self-reinforcing flywheels.

THE TWO TOKENS (always write them exactly like this):
$MCLB — The governance token. Represents exposure to the DAO's long-term strategic activity.
         Backed by: treasury-funded buybacks and burns, governance rights, early-stage investment exposure.
         This is the DAO equity layer — governance plus strategic upside.

fBOMB — The liquidity token. Deflationary: 1% burn on every transfer.
         Multi-chain: Sonic (primary), Berachain, Avalanche, and others.
         ~462M current supply out of 1B max (54% already burned).
         Treasury-backed, yield-generating. The DAO directs emissions and bribes to farm rewards,
         deepen liquidity, and burn supply. LP yields more than offset the burn tax.
         Liquidity becomes treasury profit.

THE FLYWHEEL:
- DAO deploys capital into DeFi yield positions and LP pools.
- Yields and trading fees flow back to treasury.
- Treasury funds $MCLB buybacks/burns and deepens fBOMB liquidity.
- Stronger liquidity and treasury attract more partners and ecosystem activity.
- More activity = more fBOMB burns + more $MCLB value accrual.

MCLB DOES:
- Strategic DeFi investments (yield farms, LP positions, early-stage tokens, protocol partnerships)
- Active treasury management (not idle capital — actively deployed)
- Protocol-owned liquidity (the DAO controls its own liquidity positions)
- Product incubation (build, seed, and launch new DeFi products inside the ecosystem)
- Flywheel design (connect treasury, liquidity, burns, and token demand into self-reinforcing loops)

CHAINS: Sonic, Berachain, Avalanche (primary for fBOMB), BNB Chain, Optimism, and more.

YOUR EDGE ON TWITTER:
- Skin in the game: MCLB doesn't advise — it deploys capital alongside partners.
- $40M+ deployed. $100M+ in LP yield generated for protocol partners.
- Flywheel thinking: understand how treasury, liquidity, burns, and demand interconnect.
- Both token layers: $MCLB for governance/strategy, fBOMB for liquidity/DeFi execution.

WHAT MCLB DAO SOUNDS LIKE:
- Direct and confident: "fBOMB burns on every transfer. LP yields offset the tax. Liquidity becomes treasury profit."
- Data first: "$40M deployed. $100M+ in LP yield generated."
- Dry confidence: "The flywheel runs either way.", "We've seen this.", "On-chain data says otherwise."
- Ecosystem builder tone: partner language, not adversarial. We work alongside protocols, not against them.
- No price commentary. No hype. No hashtags.

WRITING STYLE (match this closely):
- Short sentences. Periods or line breaks. Never comma-chained clauses.
- Always capitalise sentence starts. Always write "$MCLB" and "fBOMB" exactly as shown.
- NEVER use em dashes (—) or en dashes (–). Period or line break instead.
- Sparse emoji. One at most, never a sequence.
- Never over-explain. If the point is made, stop.
- Sounds like an operator posting between meetings, not a marketing team.

GOAL ON TWITTER:
Build MCLB DAO's reputation as the most credible DeFi investment and liquidity DAO.
Attract protocol partnerships, deal flow, and ecosystem credibility.
NOT: price pumping, engagement farming, or meme content.
"""

# ── Content pillars (weighted) ─────────────────────────────────────────────────
# Weights: 25 / 20 / 20 / 15 / 10 / 10

PILLARS = [
    {
        "name": "fBOMB Mechanics",
        "weight": 25,
        "prompt": """Write a standalone tweet or short post (3-6 lines max) about fBOMB — MCLB DAO's liquidity token.

fBOMB context: Deflationary (1% burn on every transfer). Multi-chain: Sonic, Berachain, Avalanche, and more.
~462M current supply out of 1B max (over half already burned). Treasury-backed, yield-generating.
The DAO directs emissions and bribes to farm rewards, deepen liquidity, and burn supply.
LP yields more than offset the burn tax — liquidity becomes treasury profit.

Choose ONE angle from:
- Why the deflationary burn model creates a structural supply squeeze over time
- How LP yields more than offset the 1% transfer tax (net-positive for LPs)
- Why multi-chain deployment matters for a liquidity token — reach vs depth tradeoffs
- How bribe farming + burns create a compounding deflationary loop
- What makes fBOMB different from typical liquidity tokens (treasury backing, burn mechanics)
- The mechanics of using fBOMB as a pairing asset for new ecosystem launches
- How the DAO uses fBOMB emissions to direct liquidity strategically

Style:
- Mechanistic — explain the tokenomics, not the price
- Reference actual numbers where useful ($0.0123, 462M supply, 1% burn, etc.)
- Sounds like the team that designed and deployed this
- No hashtags, no price targets

Write the tweet text only.""",
    },
    {
        "name": "$MCLB & DAO Governance",
        "weight": 20,
        "prompt": """Write a standalone tweet or short post (3-6 lines max) about $MCLB — MCLB DAO's governance token.

$MCLB context: The governance and strategic upside token. Backed by treasury buybacks and burns.
Governance rights over DAO decisions. Exposure to early-stage investments and portfolio growth.
The DAO equity layer — $MCLB captures the value of everything the DAO builds and deploys.

Choose ONE angle from:
- How treasury-backed buybacks create a structural floor mechanism for $MCLB
- Why $MCLB is more than a governance token — it's exposure to active capital deployment
- The difference between $MCLB (strategic/governance) and fBOMB (liquidity/execution)
- How early-stage investment exposure through the DAO differs from direct speculation
- Why DAO governance tokens with active treasuries compound differently than passive ones
- How $MCLB and fBOMB work as complementary layers (equity + liquidity) not competing tokens
- What "treasury-backed governance" actually means in practice

Style:
- Clear and credible — explain mechanisms, not hype
- Reference the two-token model where relevant
- Sounds like the team that designed the token structure
- No price talk, no hashtags

Write the tweet text only.""",
    },
    {
        "name": "Liquidity Strategy",
        "weight": 20,
        "prompt": """Write a standalone tweet or short post (3-6 lines max) about DeFi liquidity strategy — applicable to MCLB's approach and the broader space.

Choose ONE topic from:
- Why most liquidity mining programs fail long-term (emissions without retention)
- Protocol-owned liquidity vs rented liquidity — the real tradeoffs
- What makes TVL sticky vs mercenary capital
- LP incentive design: what works, what kills protocols
- How the DAO uses fBOMB as a pairing asset to seed new liquidity positions
- Why controlling your own liquidity changes the game for a DAO
- Concentrated vs wide-range LP positions — when each makes sense
- How MCLB thinks about liquidity as a strategic asset, not a cost

Style:
- Operator perspective — deployed capital, not theoretical analysis
- Sharp observation or mechanism as the lead
- Short list format fine if it makes the point cleaner
- No hashtags, no hype

Write the tweet text only.""",
    },
    {
        "name": "Treasury & Active Capital",
        "weight": 15,
        "prompt": """Write a standalone tweet or short post (3-6 lines max) about active treasury management and capital deployment — MCLB's approach and the broader DAO space.

Choose ONE topic from:
- Why most DAO treasuries are idle and why that's a mistake
- How MCLB deploys treasury capital into yield-generating DeFi positions
- The difference between treasury management and treasury speculation
- How to evaluate yield strategies for a DAO treasury on a risk-adjusted basis
- Why active capital allocation creates compounding advantages over time
- The role of protocol-owned liquidity in a DAO treasury strategy
- How the MCLB flywheel connects treasury growth to $MCLB and fBOMB demand
- What a real active-treasury DAO looks like vs a passive token treasury

Style:
- Conservative and credible — institutional frame, no hype
- Reference MCLB's actual approach where relevant ($40M+ deployed, $100M+ LP yield generated)
- No price speculation
- No hashtags

Write the tweet text only.""",
    },
    {
        "name": "Ecosystem & Incubation",
        "weight": 10,
        "prompt": """Write a standalone tweet or short post (3-6 lines max) about ecosystem building, product incubation, or protocol partnerships — from MCLB's perspective.

MCLB incubation context: The DAO can build, seed, and launch new DeFi products inside its ecosystem.
Example: Thena Strategy — a strategy-style token inspired by Aerostrategy, using staking, buybacks, and POL.
New products can be paired against fBOMB, creating demand for fBOMB liquidity while expanding the ecosystem.

Choose ONE topic from:
- How MCLB incubates new DeFi products (seed liquidity, token design, ecosystem integration)
- Why using fBOMB as the pairing asset for new launches creates a virtuous loop
- What makes a good protocol partnership for a liquidity DAO
- How product incubation differs from passive investment (active value-add vs capital alone)
- The strategic logic behind building inside your own ecosystem vs investing externally
- Why ecosystem flywheel design matters more than individual product success

Style:
- Practical and forward-looking
- Connect incubation to the broader $MCLB / fBOMB flywheel where relevant
- No vague buzzwords
- No hashtags

Write the tweet text only.""",
    },
    {
        "name": "DeFi Operator Insights",
        "weight": 10,
        "prompt": """Write a short, grounded post with a sharp DeFi observation from an operator's perspective.

Options:
- A lesson from actively managing a DAO treasury with $40M+ deployed
- Something most protocols get wrong about liquidity design
- What the data says about emission-based liquidity vs protocol-owned liquidity
- A real observation from operating on Sonic, Berachain, or across veToken ecosystems
- What $100M+ in LP yield generated for protocol partners teaches you about protocol health
- How DeFi flywheel design fails in practice (and what actually works)
- The gap between DeFi tokenomics theory and what happens on-chain

Style:
- Specific and honest — not PR copy, not generic takes
- Backed by real operational experience
- Short — 2-4 lines max
- No hashtags

Write the tweet text only.""",
    },
]

# ── Target accounts — loaded from target_accounts.json ────────────────────────

TARGET_ACCOUNTS_FILE = Path(__file__).parent / "target_accounts.json"

def load_target_accounts() -> list:
    if TARGET_ACCOUNTS_FILE.exists():
        return json.load(open(TARGET_ACCOUNTS_FILE))
    return [
        "ThenaFi_", "AerodromeFinance", "VelodromeFi", "CamelotDEX",
        "CurveFinance", "ConvexFinance", "FraxFinance",
        "BNBCHAIN", "BuildOnBase", "arbitrum",
        "pendle_fi", "ethena_labs", "aaveaave",
        "MorphoLabs", "eulerfinance", "PancakeSwap",
        "beefyfinance", "gauntlet_xyz",
    ]


def load_partner_accounts() -> list:
    if PARTNER_ACCOUNTS_FILE.exists():
        return json.load(open(PARTNER_ACCOUNTS_FILE))
    return []


def get_partner(author: str, partners: list):
    """Returns the partner dict if author is an active partner, else None."""
    lower = author.lower()
    for p in partners:
        if p.get("active", True) and p["handle"].lower() == lower:
            return p
    return None

# Broad topic searches as fallback
BROAD_QUERIES = [
    "protocol owned liquidity DeFi",
    "veToken vote market governance",
    "liquidity mining emissions DeFi",
    "DAO treasury management DeFi",
    "LP yield sustainable APY",
    "Aerodrome Velodrome ve33",
    "Thena BNB Chain liquidity",
    "Curve Convex vote market",
    "Pendle yield tokenisation",
    "DeFi protocol partnership BD",
    "tokenized RWA stablecoin",
    "institutional DeFi liquidity",
    "mercenary capital TVL DeFi",
    "POL protocol owned liquidity",
    "DeFi governance capture centralisation",
    "veToken emissions flywheel",
    "BNB Chain DeFi ecosystem",
    "on-chain yield optimization",
]

# ── Cookie loading ─────────────────────────────────────────────────────────────

def load_cookies() -> dict:
    cookies_json = os.getenv("BROWSER_COOKIES_JSON")
    if cookies_json:
        raw = json.loads(cookies_json)
    elif BROWSER_COOKIES_FILE.exists():
        with open(BROWSER_COOKIES_FILE) as f:
            raw = json.load(f)
    else:
        raise FileNotFoundError("No browser cookies found. Set BROWSER_COOKIES_JSON env var or provide browser_cookies.json.")
    if isinstance(raw, list):
        return {c["name"]: c["value"] for c in raw if "name" in c and "value" in c}
    return raw


def playwright_cookies(raw_cookies: list) -> list:
    """Convert Cookie-Editor export to Playwright cookie format."""
    pw = []
    for c in raw_cookies:
        if not c.get("name") or not c.get("value"):
            continue
        entry = {
            "name": c["name"],
            "value": c["value"],
            "domain": c.get("domain", ".x.com"),
            "path": c.get("path", "/"),
            "secure": c.get("secure", True),
            "httpOnly": c.get("httpOnly", False),
            "sameSite": "None",
        }
        if c.get("expirationDate"):
            entry["expires"] = int(c["expirationDate"])
        pw.append(entry)
    return pw


# ── Tweet age helper (snowflake ID → days old) ────────────────────────────────

def tweet_age_days(tweet_id: str) -> float:
    """Return how many days old a tweet is using its snowflake ID."""
    try:
        ms = (int(tweet_id) >> 22) + 1288834974657
        age_ms = time.time() * 1000 - ms
        return age_ms / (1000 * 86400)
    except (ValueError, TypeError, OverflowError):
        return 0.0

MAX_TWEET_AGE_DAYS = 4   # only process tweets posted in the last 4 days

# ── Twitter scraping via Playwright (DOM-primary) ─────────────────────────────

async def _dom_count(article, testid: str) -> int:
    """Read an engagement count (likes/retweets) from a tweet article."""
    try:
        el = await article.query_selector(f"[data-testid='{testid}'] span")
        if el:
            t = (await el.inner_text()).strip().replace(",", "")
            if "K" in t: return int(float(t.replace("K", "")) * 1000)
            if "M" in t: return int(float(t.replace("M", "")) * 1000000)
            return int(t) if t.isdigit() else 0
    except Exception:
        return 0
    return 0


async def _read_page_tweets(page, max_tweets: int = 30) -> list:
    """
    DOM-primary tweet reader. Reads directly from rendered articles so the
    author handle is always present — no GraphQL parsing needed.
    """
    tweets = []
    seen: set = set()

    articles = await page.query_selector_all("article[data-testid='tweet']")
    for article in articles:
        if len(tweets) >= max_tweets:
            break
        try:
            # ── Text ──────────────────────────────────────────────────────────
            text_el = await article.query_selector("[data-testid='tweetText']")
            text = (await text_el.inner_text()).strip() if text_el else ""
            if not text or text.startswith("RT @"):
                continue

            # ── Author — try User-Name section first (most reliable) ──────────
            author = ""
            user_section = await article.query_selector("[data-testid='User-Name']")
            if user_section:
                for a in await user_section.query_selector_all("a[href]"):
                    href = (await a.get_attribute("href") or "").strip("/")
                    if href and "/" not in href and not href.startswith("http"):
                        author = href
                        break

            # Fallback: extract author from any /status/ link in the card
            if not author:
                for a in await article.query_selector_all("a[href*='/status/']"):
                    href = (await a.get_attribute("href") or "").strip("/")
                    parts = href.split("/")
                    if len(parts) >= 3 and parts[1] == "status":
                        author = parts[0]
                        break

            if not author:
                continue

            # ── Tweet ID ──────────────────────────────────────────────────────
            tweet_id = ""
            for a in await article.query_selector_all("a[href*='/status/']"):
                href = (await a.get_attribute("href") or "").strip("/")
                parts = href.split("/")
                if len(parts) >= 3 and parts[1] == "status":
                    tweet_id = parts[2]
                    break

            if not tweet_id or tweet_id in seen:
                continue
            seen.add(tweet_id)

            # ── Engagement ────────────────────────────────────────────────────
            likes    = await _dom_count(article, "like")
            retweets = await _dom_count(article, "retweet")

            tweets.append({
                "id":               tweet_id,
                "text":             text,
                "author":           author,
                "author_followers": 0,
                "likes":            likes,
                "retweets":         retweets,
                "is_retweet":       False,
            })
        except Exception:
            continue

    return tweets


async def scrape_timeline(tab: str, page, max_tweets: int = 40) -> list:
    """Scrape For You or Following feed."""
    try:
        await page.goto("https://x.com/home", wait_until="domcontentloaded", timeout=25000)
        await page.wait_for_timeout(3000)

        if tab == "following":
            try:
                btn = await page.query_selector('[data-testid="primaryColumn"] nav a:nth-child(2), a[href="/home"][aria-label*="ollowing"]')
                if btn:
                    await btn.click()
                    await page.wait_for_timeout(2000)
            except Exception:
                pass

        for _ in range(5):
            await page.evaluate("window.scrollBy(0, 1400)")
            await page.wait_for_timeout(1200)

    except Exception as e:
        print(f"    Timeline error: {e}")

    return await _read_page_tweets(page, max_tweets)


async def scrape_user(handle: str, page, max_tweets: int = 10) -> list:
    """Fetch recent tweets from a user's profile."""
    try:
        await page.goto(f"https://x.com/{handle}", wait_until="domcontentloaded", timeout=25000)
    except Exception as e:
        print(f"    @{handle}: nav error — {e}")
        return []   # Don't read stale content from a previous page

    # Twitter is a React SPA — domcontentloaded fires before tweet articles render.
    # Wait for the first article to appear in the DOM before reading.
    try:
        await page.wait_for_selector("article[data-testid='tweet']", timeout=9000)
    except Exception:
        # Profile may have no tweets or be slow — brief fallback wait
        await page.wait_for_timeout(2500)

    return await _read_page_tweets(page, max_tweets)

# ── Claude: reply + quote tweet ───────────────────────────────────────────────

def generate_replies(tweet_text: str, tweet_author: str, is_target: bool, claude: anthropic.Anthropic, partner=None, instructions: str = "") -> tuple[str, str, str]:
    """Returns (bullish_reply, sarcastic_reply, alpha_reply)."""
    target_note = (
        f"@{tweet_author} is a high-priority account. High visibility — make the reply sharp and credible.\n\n"
        if is_target else ""
    )

    partner_note = ""
    if partner:
        partner_note = f"""PARTNER RELATIONSHIP: @{tweet_author} is an active MCLB DAO partner — {partner['name']}.
Relationship context: {partner['context']}
Write as someone with real shared history and actual skin in the game. Reference specifics from the context above where they add genuine value — not generic cheerleading.
For the tongue-in-cheek version: keep it warm and self-aware — this is a genuine partner, not a target for dry pushback.\n\n"""

    instructions_note = f"\nOPERATOR INSTRUCTIONS: {instructions}\nApply this framing/angle/tone across all variants.\n" if instructions else ""

    base_rules = f"""{target_note}{partner_note}Tweet from @{tweet_author}:
"{tweet_text}"{instructions_note}

Rules:
- NEVER use em dashes (—) or en dashes (–). Period or line break instead.
- Always write "$MCLB" and "fBOMB" exactly when mentioning MCLB tokens.
- No hashtags. No padding. Short.
- Always write something — never skip."""

    bullish_prompt = f"""{base_rules}

Write a SUPPORT / BULLISH reply — back this tweet from MCLB DAO's perspective.
Show genuine support or amplification of the point. Where it fits naturally, connect to MCLB's thesis, $MCLB value accrual, or fBOMB liquidity.
Don't force a token mention — only use it if it adds something real.
Show that MCLB has skin in the game and understands why this matters.

Bullish reply:"""

    sarcastic_prompt = f"""{base_rules}

Write a TONGUE-IN-CHEEK reply — dry, witty, or deadpan. Confident operator energy.
Short zinger, deadpan observation, or dry pushback on a lazy take.
Still smart — never cheap.

Examples: "We've seen this before 😂" / "The data says otherwise." / "Cool. Let us know how the emissions cliff goes." / "Narrator: the liquidity did not stay."

Tongue-in-cheek reply:"""

    if is_target and not partner:
        # Target account (not a partner) → MCLB Angle: connect tweet to MCLB's actual activities
        alpha_prompt = f"""{base_rules}

Write an MCLB ANGLE reply — show how this tweet directly relates to MCLB DAO's own activities, investments, or positioning.
Connect it to specific MCLB work: deployed liquidity, treasury operations, $MCLB value accrual, fBOMB ecosystem, or a specific portfolio investment.
Sound like an operator with genuine on-chain exposure in this exact area — not a generic observer.
1-3 sentences. No padding. Make it clear MCLB has real skin in the game here.

MCLB Angle reply:"""
    else:
        alpha_prompt = f"""{base_rules}

Write an OPERATOR ALPHA reply — drop a specific insight, mechanism detail, or on-chain observation that most people commenting on this tweet don't have.
This is the "we've deployed $40M in this space, here's what the data actually shows" angle.
Make it feel like inside knowledge from someone who has operated in this ecosystem at scale.
Reference MCLB's operational experience where it adds genuine value.
One sharp observation that makes readers think "they actually know this space."

Operator Alpha reply:"""

    bullish = claude.messages.create(
        model="claude-sonnet-4-6",
        max_tokens=150,
        system=IDENTITY,
        messages=[{"role": "user", "content": bullish_prompt}],
    ).content[0].text.strip()

    sarcastic = claude.messages.create(
        model="claude-sonnet-4-6",
        max_tokens=150,
        system=IDENTITY,
        messages=[{"role": "user", "content": sarcastic_prompt}],
    ).content[0].text.strip()

    alpha = claude.messages.create(
        model="claude-sonnet-4-6",
        max_tokens=200,
        system=IDENTITY,
        messages=[{"role": "user", "content": alpha_prompt}],
    ).content[0].text.strip()

    return bullish, sarcastic, alpha


def suggest_graphic(tweet_text: str, reply_text: str, claude: anthropic.Anthropic) -> str:
    """Returns a one-line graphic suggestion, or empty string if none adds value."""
    prompt = f"""Original tweet:
"{tweet_text}"

Reply draft:
"{reply_text}"

Should a graphic be attached to this reply to add value? Think: charts, screenshots, memes, infographics, data visuals.
Only suggest if it genuinely strengthens the reply. Most replies do NOT need a graphic.

If useful: reply with ONE short line starting with the type, e.g.:
  Chart: 30-day TVL comparison across ve(3,3) DEXs on Base
  Screenshot: MCLB's Aerodrome gauge position showing vote weight
  Meme: Distracted boyfriend — "new L1 narrative" vs "actual deployed liquidity"
  Infographic: fBOMB burn + LP yield flywheel

If no graphic adds value, reply with exactly: None

Graphic suggestion:"""

    result = claude.messages.create(
        model="claude-haiku-4-5",
        max_tokens=60,
        messages=[{"role": "user", "content": prompt}],
    ).content[0].text.strip()

    if result.lower() == "none" or result.lower().startswith("none"):
        return ""
    return result


def generate_qts(tweet_text: str, tweet_author: str, is_target: bool, claude: anthropic.Anthropic, partner=None, instructions: str = "") -> tuple[str, str, str]:
    """Returns (bullish_qt, sarcastic_qt, alpha_qt). All three always generated."""
    target_note = (
        f"@{tweet_author} is a high-priority account. A sharp QT here gets high visibility.\n\n"
        if is_target else ""
    )

    partner_note = ""
    if partner:
        partner_note = f"""PARTNER RELATIONSHIP: @{tweet_author} is an active MCLB DAO partner — {partner['name']}.
Relationship context: {partner['context']}
Write as someone with real shared history and actual skin in the game. Reference specifics where they add genuine value.
For the tongue-in-cheek version: keep it warm and self-aware — this is a genuine partner.\n\n"""

    instructions_note = f"\nOPERATOR INSTRUCTIONS: {instructions}\nApply this framing/angle/tone across all variants.\n" if instructions else ""

    base = f"""{target_note}{partner_note}Tweet from @{tweet_author}:
"{tweet_text}"{instructions_note}

Write a quote tweet comment — the text that goes ABOVE the quoted tweet.
Rules:
- 1-3 sentences max
- Must make sense without re-explaining the original
- No "this" or "exactly" as openers
- No hashtags. NEVER use em dashes (—) or en dashes (–). Period or line break instead.
- Short sentences. No padding.
- Always write something."""

    bullish_prompt = f"""{base}

SUPPORT / BULLISH version — amplify and back this tweet from MCLB DAO's perspective.
Where it fits naturally, connect to $MCLB or fBOMB. Don't force it — only if it adds something real.
Show genuine conviction: MCLB has skin in the game here.

QT comment:"""

    sarcastic_prompt = f"""{base}

TONGUE-IN-CHEEK version — dry, witty, or deadpan. Confident operator energy.
Examples: "Narrator: the liquidity did not stay." / "The data says otherwise." / "Cool. Let us know how the emissions cliff goes."

QT comment:"""

    if is_target and not partner:
        alpha_prompt = f"""{base}

MCLB ANGLE version — show how this tweet connects to MCLB DAO's actual investments, deployed liquidity, or $MCLB/$fBOMB ecosystem.
Sound like an operator with real exposure here. 1-3 sentences, no filler.
Make it clear MCLB has skin in this specific game.

QT comment:"""
    else:
        alpha_prompt = f"""{base}

OPERATOR ALPHA version — add the specific on-chain insight or mechanism detail most people won't have.
"We've deployed $40M in this space — here's what the data actually shows."
Reference MCLB's operational experience where it adds genuine credibility.
One observation that makes readers think "they actually know this."

QT comment:"""

    bullish = claude.messages.create(
        model="claude-sonnet-4-6",
        max_tokens=200,
        system=IDENTITY,
        messages=[{"role": "user", "content": bullish_prompt}],
    ).content[0].text.strip()

    sarcastic = claude.messages.create(
        model="claude-sonnet-4-6",
        max_tokens=200,
        system=IDENTITY,
        messages=[{"role": "user", "content": sarcastic_prompt}],
    ).content[0].text.strip()

    alpha = claude.messages.create(
        model="claude-sonnet-4-6",
        max_tokens=200,
        system=IDENTITY,
        messages=[{"role": "user", "content": alpha_prompt}],
    ).content[0].text.strip()

    return bullish, sarcastic, alpha

# ── Persistence ────────────────────────────────────────────────────────────────

CRYPTO_KEYWORDS = {
    "defi", "crypto", "blockchain", "web3", "token", "protocol", "liquidity",
    "yield", "apy", "tvl", "dao", "nft", "eth", "btc", "sol", "base", "l1", "l2",
    "on-chain", "onchain", "dex", "amm", "stablecoin", "governance", "tokenomics",
    "emissions", "airdrop", "validator", "restaking", "rwa", "vault", "lending",
    "borrow", "incentive", "ecosystem", "mainnet", "testnet", "rollup", "bridge",
    "wallet", "smart contract", "solana", "ethereum", "avalanche", "arbitrum",
    "optimism", "polygon", "monad", "berachain", "sonic", "hyperliquid", "pendle",
    "aave", "curve", "uniswap", "compound", "morpho", "ethena", "aerodrome",
    "$eth", "$btc", "$sol", "$avax", "$arb", "$bnb", "$cake", "$the", "$fbomb", "$mclb",
    "gwei", "mempool", "mev",
    # MCLB ecosystem specifics
    "fbomb", "mclb", "millennium club",
    "thena", "velodrome", "camelot", "pancakeswap", "beefy",
    "vetoken", "ve(3,3)", "vote market", "bribe", "votium", "hidden hand",
    "proof of liquidity", "pol", "protocol owned liquidity",
    "bnb chain", "bnbchain", "treasury management",
    "flywheel", "buyback", "burn", "deflationary", "protocol incubation",
    "thena strategy", "aerostrategy", "strategy token",
}

def is_crypto_tweet(text: str) -> bool:
    """Return True if tweet is clearly about crypto/Web3/blockchain."""
    if text.startswith("RT @"):
        return False
    lower = text.lower()
    for kw in CRYPTO_KEYWORDS:
        if kw.startswith("$"):
            if kw in lower:
                return True
        else:
            if re.search(r'\b' + re.escape(kw) + r'\b', lower):
                return True
    return False


TARGETS_FILE = Path(__file__).parent / "targets.txt"

def load_custom_targets() -> tuple[list, list]:
    """Read targets.txt — returns (handles, tweet_urls)."""
    if not TARGETS_FILE.exists():
        return [], []
    handles, urls = [], []
    for line in TARGETS_FILE.read_text().splitlines():
        line = line.strip()
        if not line or line.startswith("#"):
            continue
        if "x.com/" in line or "twitter.com/" in line:
            urls.append(line)
        else:
            handles.append(line.lstrip("@"))
    return handles, urls


def load_json_set(path: Path) -> set:
    return set(json.load(open(path))) if path.exists() else set()

def save_json_set(path: Path, data: set):
    json.dump(list(data), open(path, "w"), indent=2)

def load_drafts() -> list:
    return json.load(open(DRAFTS_FILE)) if DRAFTS_FILE.exists() else []

def save_drafts(drafts: list):
    json.dump(drafts, open(DRAFTS_FILE, "w"), indent=2)

# ── Main ───────────────────────────────────────────────────────────────────────

async def run():
    print(f"\n{'='*58}")
    print(f"  MCLB DAO Draft Generation — {time.strftime('%Y-%m-%d %H:%M:%S')}")
    print(f"{'='*58}")

    try:
        cookies = load_cookies()
        print(f"Loaded {len(cookies)} cookies.")
    except FileNotFoundError as e:
        print(f"\nERROR: {e}")
        return

    if "auth_token" not in cookies:
        print("\nERROR: auth_token missing — make sure you're logged in to Twitter before exporting cookies.")
        return

    existing_drafts = load_drafts()
    existing_ids = {d.get("tweet_id") for d in existing_drafts if d.get("tweet_id")}
    seen_posts = load_json_set(SEEN_POSTS_FILE)
    claude = anthropic.Anthropic(api_key=ANTHROPIC_API_KEY)
    TARGET_ACCOUNTS  = load_target_accounts()
    PARTNER_ACCOUNTS = load_partner_accounts()
    active_partner_handles = {p["handle"].lower() for p in PARTNER_ACCOUNTS if p.get("active", True)}
    all_target_handles = {a.lower() for a in TARGET_ACCOUNTS} | active_partner_handles
    print(f"  {len(TARGET_ACCOUNTS)} target accounts | {len(active_partner_handles)} active partners")

    custom_handles, custom_urls = load_custom_targets()
    if custom_handles or custom_urls:
        print(f"\n── Custom targets: {len(custom_handles)} handles, {len(custom_urls)} tweet URLs")

    print(f"\n── Searching for tweets (real browser)...")
    candidates = []

    raw_cookies_dict = load_cookies()
    raw_cookies = [{"name": k, "value": v} for k, v in raw_cookies_dict.items()]
    pw_cookies = playwright_cookies(raw_cookies)

    async with async_playwright() as pw:
        browser = await pw.chromium.launch(headless=True)
        context = await browser.new_context(
            user_agent="Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36",
            viewport={"width": 1280, "height": 800},
        )
        await context.add_cookies(pw_cookies)
        page = await context.new_page()

        await page.goto("https://x.com/home", wait_until="domcontentloaded", timeout=20000)
        await page.wait_for_timeout(2000)
        if "login" in page.url.lower():
            print("\nERROR: Not logged in. Re-export cookies from Cookie-Editor while logged in to twitter.com.")
            await browser.close()
            return
        print("  Logged in.")

        # ── 0. Custom targets from targets.txt ───────────────────────────────
        if custom_handles:
            print(f"  Custom handles ({len(custom_handles)})...")
            for handle in custom_handles:
                try:
                    tweets = await scrape_user(handle, page)
                    added = 0
                    for t in tweets:
                        if t["id"] in seen_posts or t["id"] in existing_ids or t["is_retweet"] or not t["text"]:
                            continue
                        if tweet_age_days(t["id"]) > MAX_TWEET_AGE_DAYS:
                            continue
                        if not is_crypto_tweet(t["text"]):
                            continue
                        candidates.append((t, True))
                        added += 1
                    print(f"    @{handle}: {added} tweets")
                except Exception as e:
                    print(f"    @{handle}: {e}")

        if custom_urls:
            print(f"  Custom tweet URLs ({len(custom_urls)})...")
            for url in custom_urls:
                try:
                    parts = url.rstrip("/").split("/")
                    tweet_id = parts[-1]
                    author = parts[-3] if len(parts) >= 3 else "unknown"
                    tweets = await scrape_user(author, page, max_tweets=20)
                    matched = [t for t in tweets if t["id"] == tweet_id]
                    if matched:
                        t = matched[0]
                        if t["id"] not in seen_posts and t["id"] not in existing_ids:
                            candidates.insert(0, (t, True))
                            print(f"    Added tweet {tweet_id} by @{author}")
                    else:
                        print(f"    Could not find tweet {tweet_id}")
                except Exception as e:
                    print(f"    URL error {url}: {e}")

        # ── 1. Partner accounts (always scraped directly — full list) ──────────
        active_partners = [p for p in PARTNER_ACCOUNTS if p.get("active", True)]
        random.shuffle(active_partners)   # rotate order each run to avoid always hitting rate-limits on the same accounts
        print(f"\n── Partner accounts ({len(active_partners)} accounts)")
        for p in active_partners:
            handle = p["handle"]
            try:
                tweets = await scrape_user(handle, page, max_tweets=5)
                added = 0
                n_seen = n_existing = n_old = n_bad = 0
                for t in tweets:
                    if t["id"] in seen_posts:
                        n_seen += 1; continue
                    if t["id"] in existing_ids:
                        n_existing += 1; continue
                    if t["is_retweet"] or not t["text"]:
                        n_bad += 1; continue
                    if tweet_age_days(t["id"]) > MAX_TWEET_AGE_DAYS:
                        n_old += 1; continue
                    # Partners bypass the crypto keyword filter — they're trusted accounts.
                    candidates.append((t, True))
                    added += 1
                if added:
                    print(f"  ♦ @{handle}: +{added} candidate(s) ({len(tweets)} scraped)")
                else:
                    parts = []
                    if not tweets:      parts.append("0 tweets loaded")
                    if n_seen:          parts.append(f"{n_seen} already seen")
                    if n_existing:      parts.append(f"{n_existing} already drafted")
                    if n_old:           parts.append(f"{n_old} too old (>{MAX_TWEET_AGE_DAYS}d)")
                    if n_bad:           parts.append(f"{n_bad} retweet/empty")
                    reason = ", ".join(parts) if parts else "unknown"
                    print(f"  ♦ @{handle}: skipped ({reason})")
            except Exception as e:
                print(f"  ♦ @{handle}: error — {e}")
            await page.wait_for_timeout(700)   # brief pause between profiles to reduce rate-limiting

        # ── 2. For You timeline ──────────────────────────────────────────────
        print("\n── Feed scraping")
        print("  Scraping For You feed...")
        try:
            for_you = await scrape_timeline("for_you", page)
            added = 0
            for t in for_you:
                if t["id"] in seen_posts or t["id"] in existing_ids or t["is_retweet"] or not t["text"]:
                    continue
                if tweet_age_days(t["id"]) > MAX_TWEET_AGE_DAYS:
                    continue
                # Partners bypass the keyword filter even in the timeline
                is_partner_tweet = get_partner(t["author"], PARTNER_ACCOUNTS) is not None
                if not is_partner_tweet and not is_crypto_tweet(t["text"]):
                    continue
                is_target = t["author"].lower() in all_target_handles
                candidates.append((t, is_target))
                added += 1
            print(f"    {added} tweets from For You")
        except Exception as e:
            print(f"    For You error: {e}")

        # ── 3. Following timeline ────────────────────────────────────────────
        print("  Scraping Following feed...")
        try:
            following = await scrape_timeline("following", page)
            added = 0
            for t in following:
                if t["id"] in seen_posts or t["id"] in existing_ids or t["is_retweet"] or not t["text"]:
                    continue
                if tweet_age_days(t["id"]) > MAX_TWEET_AGE_DAYS:
                    continue
                # Partners bypass the keyword filter even in the timeline
                is_partner_tweet = get_partner(t["author"], PARTNER_ACCOUNTS) is not None
                if not is_partner_tweet and not is_crypto_tweet(t["text"]):
                    continue
                is_target = t["author"].lower() in all_target_handles
                candidates.append((t, is_target))
                added += 1
            print(f"    {added} tweets from Following")
        except Exception as e:
            print(f"    Following error: {e}")

        # ── 4. Watchlist accounts (supplement if still low on candidates) ──────
        if len(candidates) < 10:
            target_sample = random.sample(TARGET_ACCOUNTS, min(5, len(TARGET_ACCOUNTS))) if TARGET_ACCOUNTS else []
            print(f"  Low candidates — checking {len(target_sample)} watchlist accounts...")
            for handle in target_sample:
                try:
                    tweets = await scrape_user(handle, page)
                    added = 0
                    for t in tweets:
                        if t["id"] in seen_posts or t["id"] in existing_ids or t["is_retweet"] or not t["text"]:
                            continue
                        if tweet_age_days(t["id"]) > MAX_TWEET_AGE_DAYS:
                            continue
                        if not is_crypto_tweet(t["text"]):
                            continue
                        candidates.append((t, True))
                        added += 1
                    if added:
                        print(f"    @{handle}: {added} tweets")
                except Exception as e:
                    print(f"    @{handle}: {e}")

        await browser.close()

    # Deduplicate
    seen_ids_set: set = set()
    unique = []
    for tweet, is_target in candidates:
        if tweet["id"] not in seen_ids_set:
            seen_ids_set.add(tweet["id"])
            unique.append((tweet, is_target))

    # Sort: partners first → other targets → broad; then by engagement within each tier
    def candidate_priority(item):
        tweet, is_target = item
        is_partner = get_partner(tweet["author"], PARTNER_ACCOUNTS) is not None
        engagement = tweet["likes"] + tweet["retweets"] * 3
        return (2 if is_partner else (1 if is_target else 0), engagement)

    unique.sort(key=candidate_priority, reverse=True)

    partner_count = sum(1 for t, _ in unique if get_partner(t["author"], PARTNER_ACCOUNTS))
    target_count  = sum(1 for _, it in unique if it)
    print(f"  {len(unique)} candidates ({partner_count} partners, {target_count} targets, {len(unique)-target_count} broad)")

    if not unique:
        print("\n  No candidates found — cookies may have expired. Re-export from Cookie-Editor.")
        return

    # ── Generate replies ───────────────────────────────────────────────────────
    print(f"\n── Replies (target: {MAX_REPLY_DRAFTS})")
    replies_added = 0
    qt_pool = []

    for tweet, is_target in unique:
        if replies_added >= MAX_REPLY_DRAFTS:
            qt_pool.extend([(t, it) for t, it in unique if t["id"] != tweet["id"]])
            break

        partner = get_partner(tweet["author"], PARTNER_ACCOUNTS)
        tag = "♦" if partner else ("★" if is_target else "·")
        print(f"\n  {tag} @{tweet['author']} ({tweet['likes']}❤): {tweet['text'][:70]}...")

        try:
            bullish, sarcastic, alpha = generate_replies(tweet["text"], tweet["author"], is_target, claude, partner=partner)
        except Exception as e:
            print(f"  Claude error: {e}")
            # Do NOT add to seen_posts on API error — tweet stays retryable next run
            continue

        all_skip = (
            bullish.strip().upper().startswith("SKIP") and
            sarcastic.strip().upper().startswith("SKIP") and
            alpha.strip().upper().startswith("SKIP")
        )
        if all_skip:
            # Do NOT add to seen_posts — same rule as API errors.
            # Tweet stays retryable next run; 4-day age limit cleans it naturally.
            print("  All variants skipped — moving to QT pool (not blacklisted).")
            qt_pool.append((tweet, is_target))
            continue

        if bullish.strip().upper().startswith("SKIP"):
            bullish = sarcastic
        if sarcastic.strip().upper().startswith("SKIP"):
            sarcastic = bullish
        if alpha.strip().upper().startswith("SKIP"):
            alpha = bullish

        graphic = ""
        try:
            graphic = suggest_graphic(tweet["text"], bullish, claude)
        except Exception:
            pass

        print(f"  [1 Bullish]   {bullish[:75]}...")
        print(f"  [2 Sarcastic] {sarcastic[:75]}...")
        print(f"  [3 Alpha]     {alpha[:75]}...")
        if graphic:
            print(f"  [Visual]      {graphic}")

        existing_drafts.append({
            "type": "reply",
            "is_target_account": is_target,
            "is_partner": partner is not None,
            "partner_name": partner["name"] if partner else None,
            "tweet_id": tweet["id"],
            "tweet_url": f"https://x.com/{tweet['author']}/status/{tweet['id']}",
            "author": tweet["author"],
            "tweet_text": tweet["text"],
            "likes": tweet["likes"],
            "draft_bullish":   bullish,
            "draft_sarcastic": sarcastic,
            "draft_alpha":     alpha,
            "draft_serious":   bullish,
            "draft_reply":     bullish,
            "retweets": tweet["retweets"],
            "graphic_suggestion": graphic,
            "created_at": time.strftime("%Y-%m-%d %H:%M:%S"),
        })
        seen_posts.add(tweet["id"])
        replies_added += 1

    # ── Generate quote tweets ──────────────────────────────────────────────────
    print(f"\n── Quote Tweets (target: {MAX_QT_DRAFTS})")

    replied_ids = {d["tweet_id"] for d in existing_drafts if d.get("type") == "reply"}
    qt_candidates = [(t, it) for t, it in unique if t["id"] not in replied_ids and t["id"] not in seen_posts]
    qt_candidates = (qt_pool + qt_candidates)[:MAX_QT_DRAFTS * 3]

    qts_added = 0
    for tweet, is_target in qt_candidates:
        if qts_added >= MAX_QT_DRAFTS:
            break

        partner = get_partner(tweet["author"], PARTNER_ACCOUNTS)
        tag = "♦" if partner else ("★" if is_target else "·")
        print(f"\n  {tag} @{tweet['author']} ({tweet['likes']}❤): {tweet['text'][:70]}...")

        try:
            qt_bullish, qt_sarcastic, qt_alpha = generate_qts(tweet["text"], tweet["author"], is_target, claude, partner=partner)
        except Exception as e:
            print(f"  Claude error: {e}")
            continue

        qt_graphic = ""
        try:
            qt_graphic = suggest_graphic(tweet["text"], qt_bullish, claude)
        except Exception:
            pass

        print(f"  [1 Bullish]   {qt_bullish[:75]}...")
        print(f"  [2 Sarcastic] {qt_sarcastic[:75]}...")
        print(f"  [3 Alpha]     {qt_alpha[:75]}...")
        if qt_graphic:
            print(f"  [Visual]      {qt_graphic}")

        existing_drafts.append({
            "type": "qt",
            "is_target_account": is_target,
            "is_partner": partner is not None,
            "partner_name": partner["name"] if partner else None,
            "tweet_id": tweet["id"],
            "author": tweet["author"],
            "tweet_text": tweet["text"],
            "likes": tweet["likes"],
            "retweets": tweet["retweets"],
            "draft_bullish":   qt_bullish,
            "draft_sarcastic": qt_sarcastic,
            "draft_alpha":     qt_alpha,
            "draft_serious":   qt_bullish,
            "draft_reply":     qt_bullish,
            "tweet_url": f"https://x.com/{tweet['author']}/status/{tweet['id']}",
            "graphic_suggestion": qt_graphic,
            "created_at": time.strftime("%Y-%m-%d %H:%M:%S"),
        })
        qts_added += 1

    save_drafts(existing_drafts)
    save_json_set(SEEN_POSTS_FILE, seen_posts)

    pending = sum(1 for d in existing_drafts if not d.get("reviewed"))
    print(f"\n── Done.")
    print(f"   {replies_added} repl(ies) | {qts_added} quote tweet(s) | {pending} total pending")
    print(f"\nOpen the dashboard to review and post.")


if __name__ == "__main__":
    asyncio.run(run())
