"""
MCLB Operator — Dashboard v2
Run: python3 dashboard.py
Then open: http://localhost:8080
"""

import asyncio
import json
import os
import sys
from pathlib import Path

import httpx
from dotenv import load_dotenv
from flask import Flask, Response, jsonify, redirect, render_template_string, request, session

load_dotenv()

app = Flask(__name__)
app.secret_key = os.getenv("SECRET_KEY", os.urandom(24).hex())
DASHBOARD_PASSWORD = os.getenv("DASHBOARD_PASSWORD", "")

BASE                   = Path(__file__).parent
DRAFTS_FILE            = BASE / "drafts.json"
TARGETS_FILE           = BASE / "targets.txt"
COOKIES_FILE           = BASE / "browser_cookies.json"
TARGET_ACCOUNTS_FILE   = BASE / "target_accounts.json"
PARTNER_ACCOUNTS_FILE  = BASE / "partner_accounts.json"

TWITTER_BEARER = (
    "AAAAAAAAAAAAAAAAAAAAANRILgAAAAAAnNwIzUejRCOuH5E6I8xnZz4puTs"
    "%3D1Zv7ttfk8LF81IUq16cHjhLTvJu4FA33AGWWjCpTnA"
)


# ── Helpers ────────────────────────────────────────────────────────────────────

def load_cookies() -> dict:
    # On a deployed server, cookies are stored as a JSON env var instead of a file
    cookies_json = os.getenv("BROWSER_COOKIES_JSON")
    if cookies_json:
        raw = json.loads(cookies_json)
    elif COOKIES_FILE.exists():
        with open(COOKIES_FILE) as f:
            raw = json.load(f)
    else:
        raise FileNotFoundError("No browser cookies found. Set BROWSER_COOKIES_JSON env var or provide browser_cookies.json.")
    if isinstance(raw, list):
        return {c["name"]: c["value"] for c in raw if "name" in c and "value" in c}
    return raw


def make_headers(cookies: dict) -> dict:
    return {
        "authorization": f"Bearer {TWITTER_BEARER}",
        "x-csrf-token": cookies.get("ct0", ""),
        "x-twitter-auth-type": "OAuth2Session",
        "x-twitter-active-user": "yes",
        "x-twitter-client-language": "en",
        "user-agent": (
            "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
            "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36"
        ),
    }


async def _post_tweet(text: str, cookies: dict, reply_to_id: str = None, qt_url: str = None) -> dict:
    data = {"status": text}
    if reply_to_id:
        data["in_reply_to_status_id"] = reply_to_id
        data["auto_populate_reply_metadata"] = "true"
    if qt_url:
        data["attachment_url"] = qt_url
    async with httpx.AsyncClient(timeout=15) as client:
        resp = await client.post(
            "https://twitter.com/i/api/1.1/statuses/update.json",
            data=data,
            headers={**make_headers(cookies), "content-type": "application/x-www-form-urlencoded"},
            cookies=cookies,
        )
    return {"ok": resp.status_code == 200, "status": resp.status_code, "body": resp.text[:300]}


def read_target_accounts() -> list:
    if TARGET_ACCOUNTS_FILE.exists():
        return json.loads(TARGET_ACCOUNTS_FILE.read_text())
    return []


def write_target_accounts(accounts: list):
    TARGET_ACCOUNTS_FILE.write_text(json.dumps(accounts, indent=2))


def read_partner_accounts() -> list:
    if PARTNER_ACCOUNTS_FILE.exists():
        return json.loads(PARTNER_ACCOUNTS_FILE.read_text())
    return []


# ── Auth ───────────────────────────────────────────────────────────────────────

@app.before_request
def require_login():
    if request.endpoint in ("login", "logout", "static"):
        return
    if not session.get("logged_in"):
        return redirect("/login")


LOGIN_HTML = """<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>MCLB Operator — Login</title>
<style>
* { box-sizing: border-box; margin: 0; padding: 0; }
body {
  font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif;
  background: #030912;
  color: #eef4ff;
  min-height: 100vh;
  display: flex;
  align-items: center;
  justify-content: center;
}
.login-wrap {
  width: 100%;
  max-width: 380px;
  padding: 20px;
}
.login-logo {
  display: flex;
  align-items: center;
  gap: 12px;
  margin-bottom: 32px;
  justify-content: center;
}
.login-logo img {
  width: 40px; height: 40px;
  border-radius: 50%;
  box-shadow: 0 0 20px rgba(0,177,255,0.35);
}
.login-logo-text { text-align: left; }
.login-logo-title { font-size: 14px; font-weight: 700; color: #eef4ff; }
.login-logo-sub { font-size: 10px; color: #38587a; margin-top: 2px; }
.login-card {
  background: #071120;
  border: 1px solid #0f1e30;
  border-radius: 14px;
  padding: 28px 26px;
}
.login-title {
  font-size: 16px;
  font-weight: 700;
  color: #eef4ff;
  margin-bottom: 6px;
}
.login-sub {
  font-size: 12px;
  color: #38587a;
  margin-bottom: 24px;
}
label {
  display: block;
  font-size: 11px;
  font-weight: 700;
  color: #7a9ec4;
  text-transform: uppercase;
  letter-spacing: .8px;
  margin-bottom: 7px;
}
input[type=password] {
  width: 100%;
  background: #040c16;
  border: 1px solid #0f1e30;
  border-radius: 8px;
  padding: 10px 13px;
  color: #eef4ff;
  font-size: 14px;
  outline: none;
  transition: border-color .15s;
  font-family: inherit;
}
input[type=password]:focus { border-color: #3b82f6; }
.login-btn {
  width: 100%;
  margin-top: 18px;
  height: 40px;
  background: #3b82f6;
  color: #fff;
  border: none;
  border-radius: 8px;
  font-size: 13px;
  font-weight: 700;
  cursor: pointer;
  box-shadow: 0 0 18px rgba(59,130,246,0.35);
  transition: background .15s, box-shadow .15s;
  font-family: inherit;
}
.login-btn:hover { background: #2563eb; box-shadow: 0 0 26px rgba(59,130,246,0.5); }
.login-err {
  margin-top: 14px;
  background: rgba(239,68,68,0.1);
  border: 1px solid #7f1d1d;
  color: #ef4444;
  border-radius: 7px;
  padding: 9px 13px;
  font-size: 12px;
  text-align: center;
}
</style>
</head>
<body>
<div class="login-wrap">
  <div class="login-logo">
    <img src="https://pbs.twimg.com/profile_images/1880742617889681408/cSfBVJvV_400x400.jpg" alt="MCLB">
    <div class="login-logo-text">
      <div class="login-logo-title">MCLB Operator</div>
      <div class="login-logo-sub">Command Center</div>
    </div>
  </div>
  <div class="login-card">
    <div class="login-title">Sign in</div>
    <div class="login-sub">Enter the team password to access the dashboard.</div>
    <form method="POST" action="/login">
      <label for="pw">Password</label>
      <input type="password" id="pw" name="password" autofocus placeholder="Enter password">
      <button type="submit" class="login-btn">Access Dashboard</button>
      {% if error %}<div class="login-err">Incorrect password. Try again.</div>{% endif %}
    </form>
  </div>
</div>
</body>
</html>"""


@app.route("/login", methods=["GET", "POST"])
def login():
    error = False
    if request.method == "POST":
        if not DASHBOARD_PASSWORD:
            session["logged_in"] = True
            return redirect("/")
        if request.form.get("password") == DASHBOARD_PASSWORD:
            session["logged_in"] = True
            return redirect("/")
        error = True
    return render_template_string(LOGIN_HTML, error=error)


@app.route("/logout")
def logout():
    session.clear()
    return redirect("/login")


# ── Routes ─────────────────────────────────────────────────────────────────────

@app.route("/")
def index():
    return render_template_string(HTML)


@app.route("/run-bot")
def run_bot():
    import subprocess

    def generate():
        proc = subprocess.Popen(
            [sys.executable, str(BASE / "bot.py")],
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            text=True,
            cwd=str(BASE),
            bufsize=1,
        )
        for line in iter(proc.stdout.readline, ""):
            yield f"data: {json.dumps(line.rstrip())}\n\n"
        proc.wait()
        yield f"data: {json.dumps('__DONE__')}\n\n"

    return Response(
        generate(),
        mimetype="text/event-stream",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
    )


@app.route("/drafts")
def get_drafts():
    if not DRAFTS_FILE.exists():
        return jsonify([])
    return jsonify(json.loads(DRAFTS_FILE.read_text()))


# ── Target tweet URLs (targets.txt) ───────────────────────────────────────────

@app.route("/add-tweet-target", methods=["POST"])
def add_tweet_target():
    entry = (request.json or {}).get("url", "").strip()
    if not entry:
        return jsonify({"ok": False, "error": "empty"})
    if "x.com/" not in entry and "twitter.com/" not in entry:
        return jsonify({"ok": False, "error": "must be a tweet URL (x.com/...)"})
    current = TARGETS_FILE.read_text() if TARGETS_FILE.exists() else ""
    if entry in current:
        return jsonify({"ok": False, "error": "already in list"})
    with open(TARGETS_FILE, "a") as f:
        if current and not current.endswith("\n"):
            f.write("\n")
        f.write(entry + "\n")
    return jsonify({"ok": True})


# ── Target accounts (target_accounts.json) ────────────────────────────────────

@app.route("/accounts")
def get_accounts():
    return jsonify(read_target_accounts())


@app.route("/partners")
def get_partners():
    return jsonify(read_partner_accounts())


@app.route("/add-partner", methods=["POST"])
def add_partner():
    data    = request.json or {}
    handle  = data.get("handle", "").strip().lstrip("@")
    if not handle:
        return jsonify({"ok": False, "error": "handle required"})
    partners = read_partner_accounts()
    if any(p["handle"].lower() == handle.lower() for p in partners):
        return jsonify({"ok": False, "error": "already in list"})
    partners.append({
        "handle":   handle,
        "name":     data.get("name", handle).strip() or handle,
        "chain":    data.get("chain", "").strip(),
        "category": data.get("category", "").strip(),
        "active":   True,
        "context":  data.get("context", "").strip(),
    })
    PARTNER_ACCOUNTS_FILE.write_text(json.dumps(partners, indent=2))
    return jsonify({"ok": True, "partners": partners})


@app.route("/update-partner", methods=["POST"])
def update_partner():
    data    = request.json or {}
    handle  = data.get("handle", "").strip()
    partners = read_partner_accounts()
    for p in partners:
        if p["handle"].lower() == handle.lower():
            p["name"]     = data.get("name",     p.get("name", handle)).strip()
            p["chain"]    = data.get("chain",    p.get("chain", "")).strip()
            p["category"] = data.get("category", p.get("category", "")).strip()
            p["context"]  = data.get("context",  p.get("context", "")).strip()
            p["active"]   = bool(data.get("active", p.get("active", True)))
    PARTNER_ACCOUNTS_FILE.write_text(json.dumps(partners, indent=2))
    return jsonify({"ok": True, "partners": partners})


@app.route("/remove-partner", methods=["POST"])
def remove_partner():
    handle   = (request.json or {}).get("handle", "").strip()
    partners = [p for p in read_partner_accounts() if p["handle"].lower() != handle.lower()]
    PARTNER_ACCOUNTS_FILE.write_text(json.dumps(partners, indent=2))
    return jsonify({"ok": True, "partners": partners})


@app.route("/add-account", methods=["POST"])
def add_account():
    handle = (request.json or {}).get("handle", "").strip().lstrip("@")
    if not handle:
        return jsonify({"ok": False, "error": "empty"})
    accounts = read_target_accounts()
    if any(a.lower() == handle.lower() for a in accounts):
        return jsonify({"ok": False, "error": "already in list"})
    accounts.append(handle)
    write_target_accounts(accounts)
    return jsonify({"ok": True, "accounts": accounts})


@app.route("/remove-account", methods=["POST"])
def remove_account():
    handle = (request.json or {}).get("handle", "").strip().lstrip("@")
    accounts = read_target_accounts()
    accounts = [a for a in accounts if a.lower() != handle.lower()]
    write_target_accounts(accounts)
    return jsonify({"ok": True, "accounts": accounts})


# ── Custom reply generator ────────────────────────────────────────────────────

TONE_PROMPTS = {
    "analytical": "Tone: serious and mechanism-based. Add a real insight about how liquidity, tokenomics, or DeFi design works. Operator perspective.",
    "bullish":    "Tone: genuinely bullish. Why this is correct or underrated. Back it with a mechanism or data point from MCLB's operational experience. Not hype.",
    "bearish":    "Tone: skeptical or critical. What's missing, what will break. Direct. Reference MCLB's experience where relevant.",
    "sarcastic":  "Tone: dry, tongue-in-cheek. Deadpan operator energy. Short and confident. Still smart.",
    "contrarian": "Tone: contrarian. Push back on the consensus. Find the mechanism-level angle most people are missing.",
}


@app.route("/fetch-tweet", methods=["POST"])
def fetch_tweet():
    url = (request.json or {}).get("url", "").strip()
    if not url:
        return jsonify({"ok": False, "error": "no url"})

    async def _fetch():
        from playwright.async_api import async_playwright
        with open(COOKIES_FILE) as f:
            raw = json.load(f)
        from bot import playwright_cookies
        pw_cookies = playwright_cookies(raw if isinstance(raw, list) else [
            {"name": k, "value": v} for k, v in raw.items()
        ])
        async with async_playwright() as pw:
            browser = await pw.chromium.launch(headless=True)
            ctx = await browser.new_context(
                user_agent="Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36"
            )
            await ctx.add_cookies(pw_cookies)
            page = await ctx.new_page()
            try:
                await page.goto(url, wait_until="domcontentloaded", timeout=20000)
                await page.wait_for_timeout(3000)
                articles = await page.query_selector_all("article[data-testid='tweet']")
                text = ""
                author = ""
                for article in articles[:1]:
                    el = await article.query_selector("[data-testid='tweetText']")
                    if el:
                        text = await el.inner_text()
                    link_el = await article.query_selector("[data-testid='User-Name'] a")
                    if link_el:
                        href = await link_el.get_attribute("href")
                        if href:
                            author = href.strip("/").split("/")[0]
                return {"ok": True, "text": text, "author": author}
            except Exception as ex:
                return {"ok": False, "error": str(ex)}
            finally:
                await browser.close()

    try:
        result = asyncio.run(_fetch())
        return jsonify(result)
    except Exception as ex:
        return jsonify({"ok": False, "error": str(ex)})


@app.route("/generate-custom-reply", methods=["POST"])
def generate_custom_reply():
    import anthropic as _anthropic
    import os as _os
    data         = request.json or {}
    tweet_text   = data.get("tweet_text", "").strip()
    instructions = data.get("instructions", "").strip()
    tone         = data.get("tone", "analytical")
    tweet_url    = data.get("tweet_url", "").strip()

    if not tweet_text:
        return jsonify({"ok": False, "error": "no tweet text"})

    tone_instruction = TONE_PROMPTS.get(tone, TONE_PROMPTS["analytical"])
    instructions_block = f"\nMCLB DAO's angle: {instructions}\nUse these to shape the reply." if instructions else ""

    prompt = f"""Tweet to reply to:
"{tweet_text}"

{tone_instruction}{instructions_block}

Rules:
- Write as MCLB DAO (Millennium Club DAO — DeFi investment and liquidity DAO)
- Short. 1-4 lines max.
- NEVER use em dashes (—) or en dashes (–). Period or line break instead.
- Always write "$MCLB" and "fBOMB" exactly when mentioning MCLB tokens.
- No hashtags. No padding. Direct and credible.
- Capitalise sentence starts. No full stop needed on the last line.

Reply:"""

    try:
        client = _anthropic.Anthropic(api_key=_os.getenv("ANTHROPIC_API_KEY"))
        from bot import IDENTITY
        msg = client.messages.create(
            model="claude-sonnet-4-6",
            max_tokens=200,
            system=IDENTITY,
            messages=[{"role": "user", "content": prompt}],
        )
        reply_text = msg.content[0].text.strip()

        tweet_id = None
        if tweet_url:
            parts = tweet_url.rstrip("/").split("/")
            if parts:
                tweet_id = parts[-1]

        return jsonify({"ok": True, "reply": reply_text, "tweet_id": tweet_id, "tweet_url": tweet_url})
    except Exception as ex:
        return jsonify({"ok": False, "error": str(ex)})


@app.route("/post-custom", methods=["POST"])
def post_custom():
    data     = request.json or {}
    text     = data.get("text", "").strip()
    tweet_id = data.get("tweet_id")

    if not text:
        return jsonify({"ok": False, "error": "no text"})
    try:
        cookies = load_cookies()
    except Exception as ex:
        return jsonify({"ok": False, "error": str(ex)})

    result = asyncio.run(_post_tweet(text, cookies, reply_to_id=tweet_id))
    return jsonify(result)


# ── Original post generator ────────────────────────────────────────────────────

PILLAR_PROMPTS = {
    "fbomb":      "Topic: fBOMB mechanics. Cover one of: why the 1% burn creates structural supply pressure, how LP yields offset the burn tax so liquidity becomes treasury profit, multi-chain strategy for a liquidity token, bribe farming + burns compounding loop, fBOMB as a pairing asset for new ecosystem launches, how the DAO directs emissions and bribes strategically.",
    "mclb":       "Topic: $MCLB governance token. Cover one of: how treasury-backed buybacks create a structural floor, why $MCLB is active-capital exposure not passive governance, the $MCLB vs fBOMB two-token model (equity + liquidity layer), early-stage investment exposure through the DAO, why governance tokens with active treasuries compound differently.",
    "liquidity":  "Topic: Liquidity strategy. Cover one of: why liquidity mining fails long-term, protocol-owned vs rented liquidity tradeoffs, what makes TVL sticky vs mercenary, LP incentive design flaws, how MCLB uses fBOMB to seed liquidity positions, why controlling your own liquidity changes the game for a DAO.",
    "treasury":   "Topic: Active treasury management. Cover one of: why most DAO treasuries are idle and why that's a mistake, how MCLB deploys capital into yield-generating positions ($40M+ deployed), treasury vs speculation distinction, risk-adjusted yield evaluation, the flywheel connecting treasury growth to $MCLB and fBOMB demand, what an active-treasury DAO looks like in practice.",
    "ecosystem":  "Topic: Ecosystem building and incubation. Cover one of: how MCLB incubates new DeFi products (seed liquidity + token design), using fBOMB as a pairing asset for new launches to create virtuous loops, what makes a good protocol partnership for a liquidity DAO, how product incubation differs from passive investment, the strategic logic behind building inside your own ecosystem.",
    "operator":   "Topic: DeFi operator insights. Cover one of: a lesson from managing $40M+ in deployed capital, what most protocols get wrong about liquidity design, what $100M+ in LP yield generated teaches about protocol health, how DeFi flywheel design fails in practice (and what works), the gap between DeFi tokenomics theory and what happens on-chain, observations from operating across Sonic/Berachain/veToken ecosystems.",
    "bribes":     "Topic: Weekly bribe and liquidity incentive announcement for fBOMB pairs across ve(3,3) DEXs. The operator has provided the specifics below (epoch number, DEX names, pair names, bribe amounts, or vote links). Format as a clean, direct announcement. Lead with the epoch or action. If multiple DEXs are listed, present them clearly — one per line or in a tight list. End with a clear call to action for veNFT holders to vote for MCLB gauges. Tone: confident operator update. No fluff. Make it immediately useful for someone deciding where to cast their votes.",
    "weekly":     "Topic: Weekly MCLB DAO operational update. The operator has provided the key points below. Write a clear, readable update covering what happened this week: new deployments, partnership activity, treasury moves, notable events, and what is coming next. Sound like an operator giving a real briefing — specific over vague, confident without being promotional. If multiple things happened, a short thread works better than cramming everything into one tweet.",
}


@app.route("/generate-original", methods=["POST"])
def generate_original():
    import anthropic as _anthropic
    import os as _os
    data         = request.json or {}
    pillar       = data.get("pillar", "liquidity")
    instructions = data.get("instructions", "").strip()
    fmt          = data.get("format", "tweet")

    pillar_prompt = PILLAR_PROMPTS.get(pillar, PILLAR_PROMPTS["liquidity"])
    instructions_block = f"\nSpecific angle or idea: {instructions}" if instructions else ""

    if fmt == "thread":
        format_instructions = """Write a Twitter thread of 4-6 tweets.

Format your response as numbered tweets like this:
1/ [tweet text]

2/ [tweet text]

3/ [tweet text]

Each tweet must be under 280 characters and stand alone.
The first tweet should hook immediately — lead with the sharpest point.
No "thread:" opener. No emoji clusters. Just start with the insight."""
    else:
        format_instructions = """Write a single standalone tweet. 2-6 lines max.
Lead with the sharpest observation. No throat-clearing.
Under 280 characters."""

    prompt = f"""{pillar_prompt}{instructions_block}

{format_instructions}

Rules:
- Write as MCLB DAO (Millennium Club DAO) — DeFi investment and liquidity DAO
- Short sentences. Period or line break. Never comma-chained clauses.
- NEVER use em dashes (—) or en dashes (–)
- Always write "$MCLB" and "fBOMB" exactly when mentioning MCLB tokens.
- No hashtags. No hype. No padding.
- Capitalise sentence starts. No full stop needed on the last line.
- Sounds like an operator posting between meetings, not a marketing team.
- No "1/" opener for single tweets.

Write the post:"""

    try:
        client = _anthropic.Anthropic(api_key=_os.getenv("ANTHROPIC_API_KEY"))
        from bot import IDENTITY
        msg = client.messages.create(
            model="claude-sonnet-4-6",
            max_tokens=500,
            system=IDENTITY,
            messages=[{"role": "user", "content": prompt}],
        )
        text = msg.content[0].text.strip()

        if fmt == "thread":
            import re as _re
            parts = _re.split(r'\n\s*\d+/', "\n" + text)
            tweets = [t.strip() for t in parts if t.strip()]
            return jsonify({"ok": True, "format": "thread", "tweets": tweets})
        else:
            return jsonify({"ok": True, "format": "tweet", "tweets": [text]})

    except Exception as ex:
        return jsonify({"ok": False, "error": str(ex)})


@app.route("/post-thread", methods=["POST"])
def post_thread():
    data   = request.json or {}
    tweets = data.get("tweets", [])
    if not tweets:
        return jsonify({"ok": False, "error": "no tweets"})
    try:
        cookies = load_cookies()
    except Exception as ex:
        return jsonify({"ok": False, "error": str(ex)})

    async def _post_sequence():
        results = []
        prev_id = None
        for tweet_text in tweets:
            tweet_text = tweet_text.strip()
            if not tweet_text:
                continue
            res = await _post_tweet(tweet_text, cookies, reply_to_id=prev_id)
            results.append(res)
            if not res["ok"]:
                break
            try:
                body = json.loads(res.get("body", "{}"))
                prev_id = body.get("id_str") or body.get("id")
            except Exception:
                prev_id = None
        return results

    results = asyncio.run(_post_sequence())
    all_ok = all(r["ok"] for r in results)
    return jsonify({"ok": all_ok, "results": results, "posted": len([r for r in results if r["ok"]])})


# ── Draft actions ──────────────────────────────────────────────────────────────

@app.route("/post-draft", methods=["POST"])
def post_draft():
    data          = request.json or {}
    tweet_id      = data.get("tweet_id")
    version       = data.get("version", "serious")
    text_override = data.get("text_override", "").strip()

    if not DRAFTS_FILE.exists():
        return jsonify({"ok": False, "error": "no drafts file"})

    drafts = json.loads(DRAFTS_FILE.read_text())
    draft  = next((d for d in drafts if d.get("tweet_id") == tweet_id and not d.get("reviewed")), None)
    if not draft:
        return jsonify({"ok": False, "error": "draft not found"})

    if text_override:
        text = text_override
    else:
        text = (
            draft.get("draft_bullish")   if version == "bullish"   else
            draft.get("draft_sarcastic") if version == "sarcastic" else
            draft.get("draft_alpha")     if version == "alpha"     else
            draft.get("draft_serious")   if version == "serious"   else
            draft.get("draft_reply", "")
        ) or draft.get("draft_bullish") or draft.get("draft_serious") or draft.get("draft_sarcastic") or draft.get("draft_alpha") or draft.get("draft_reply", "")

    if not text:
        return jsonify({"ok": False, "error": "no text to post"})

    try:
        cookies = load_cookies()
    except Exception as ex:
        return jsonify({"ok": False, "error": str(ex)})

    reply_to = draft.get("tweet_id") if draft.get("type") == "reply" else None
    qt_url   = draft.get("tweet_url") if draft.get("type") == "qt"    else None

    result = asyncio.run(_post_tweet(text, cookies, reply_to_id=reply_to, qt_url=qt_url))

    if result["ok"]:
        draft["reviewed"]       = True
        draft["action"]         = "posted"
        draft["posted_version"] = version
        DRAFTS_FILE.write_text(json.dumps(drafts, indent=2))

    return jsonify(result)


@app.route("/last-scrape")
def last_scrape():
    import datetime
    if not DRAFTS_FILE.exists():
        return jsonify({"time": None})
    mtime = DRAFTS_FILE.stat().st_mtime
    dt    = datetime.datetime.fromtimestamp(mtime)
    label = dt.strftime("%-d %b %Y, %-I:%M %p")
    return jsonify({"time": label})


@app.route("/skip-draft", methods=["POST"])
def skip_draft():
    tweet_id = (request.json or {}).get("tweet_id")
    if not DRAFTS_FILE.exists():
        return jsonify({"ok": False})
    drafts = json.loads(DRAFTS_FILE.read_text())
    for d in drafts:
        if d.get("tweet_id") == tweet_id and not d.get("reviewed"):
            d["reviewed"] = True
            d["action"]   = "skipped"
    DRAFTS_FILE.write_text(json.dumps(drafts, indent=2))
    return jsonify({"ok": True})


@app.route("/hide-draft", methods=["POST"])
def hide_draft():
    """Hide a draft permanently — removes from UI and blacklists the tweet so the bot never re-drafts it."""
    tweet_id = (request.json or {}).get("tweet_id")
    if not tweet_id or not DRAFTS_FILE.exists():
        return jsonify({"ok": False})
    # Mark ALL drafts for this tweet_id as hidden (handles reply + QT pairs)
    drafts = json.loads(DRAFTS_FILE.read_text())
    for d in drafts:
        if d.get("tweet_id") == tweet_id:
            d["reviewed"] = True
            d["action"]   = "hidden"
    DRAFTS_FILE.write_text(json.dumps(drafts, indent=2))
    # Add to seen_posts so the bot never generates drafts for this tweet again
    seen_file = BASE / "seen_posts.json"
    seen = set(json.loads(seen_file.read_text())) if seen_file.exists() else set()
    seen.add(tweet_id)
    seen_file.write_text(json.dumps(list(seen), indent=2))
    return jsonify({"ok": True})


# ── Regenerate draft ───────────────────────────────────────────────────────────

@app.route("/regenerate-draft", methods=["POST"])
def regenerate_draft():
    import anthropic as _ant
    import os as _os
    data         = request.json or {}
    tweet_id     = data.get("tweet_id")
    instructions = data.get("instructions", "").strip()
    if not DRAFTS_FILE.exists():
        return jsonify({"ok": False, "error": "no drafts"})
    drafts = json.loads(DRAFTS_FILE.read_text())
    draft  = next((d for d in drafts if d.get("tweet_id") == tweet_id and not d.get("reviewed")), None)
    if not draft:
        return jsonify({"ok": False, "error": "draft not found"})
    try:
        from bot import generate_replies, generate_qts, IDENTITY, load_partner_accounts, get_partner
        partners  = load_partner_accounts()
        partner   = get_partner(draft.get("author", ""), partners)
        is_target = draft.get("is_target_account", False)
        client    = _ant.Anthropic(api_key=_os.getenv("ANTHROPIC_API_KEY"))
        if draft.get("type") == "reply":
            bullish, sarcastic, alpha = generate_replies(
                draft.get("tweet_text", ""), draft.get("author", ""),
                is_target, client, partner=partner, instructions=instructions
            )
        else:
            bullish, sarcastic, alpha = generate_qts(
                draft.get("tweet_text", ""), draft.get("author", ""),
                is_target, client, partner=partner, instructions=instructions
            )
        draft["draft_bullish"]   = bullish
        draft["draft_sarcastic"] = sarcastic
        draft["draft_alpha"]     = alpha
        draft["draft_serious"]   = bullish
        if instructions:
            draft["regen_instructions"] = instructions
        DRAFTS_FILE.write_text(json.dumps(drafts, indent=2))
        return jsonify({"ok": True, "bullish": bullish, "sarcastic": sarcastic, "alpha": alpha})
    except Exception as ex:
        return jsonify({"ok": False, "error": str(ex)})


# ── HTML ───────────────────────────────────────────────────────────────────────

HTML = r"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>MCLB Operator</title>
<style>
* { box-sizing: border-box; margin: 0; padding: 0; }

/* ── Variables ───────────────────────────────────────────────────────────── */
:root {
  --bg:         #030912;
  --surface:    #071120;
  --surface2:   #060e1a;
  --surface3:   #040c16;
  --border:     #0f1e30;
  --border2:    #1a3660;
  --text:       #eef4ff;
  --text2:      #7a9ec4;
  --text3:      #38587a;
  --accent:     #3b82f6;
  --accent2:    #60a5fa;
  --accent-glow:rgba(59,130,246,0.15);
  --accent-lt:  #0d1e38;
  --green:      #10b981;
  --green-lt:   #031810;
  --green-br:   #065f46;
  --amber:      #f59e0b;
  --amber-lt:   #1a1000;
  --amber-br:   #92400e;
  --purple:     #818cf8;
  --purple-lt:  #0d0a1e;
  --purple-br:  #312e81;
  --cyan:       #06b6d4;
  --cyan-lt:    #042e38;
  --cyan-br:    #0e7490;
  --red:        #ef4444;
  --red-lt:     #1c0505;
  --red-br:     #7f1d1d;
  --topbar-h:      62px;
  --sidebar-w:     220px;
  --sidebar-w-col: 58px;
}

body {
  font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif;
  background: var(--bg);
  color: var(--text);
  min-height: 100vh;
}

/* ── App Shell ───────────────────────────────────────────────────────────── */
.app-shell {
  display: flex;
  min-height: calc(100vh - var(--topbar-h));
  margin-top: var(--topbar-h);
}

/* ── Sidebar ─────────────────────────────────────────────────────────────── */
.sidebar {
  width: var(--sidebar-w);
  position: fixed;
  top: var(--topbar-h); bottom: 0; left: 0;
  background: var(--surface);
  border-right: 1px solid var(--border);
  display: flex;
  flex-direction: column;
  align-items: flex-start;
  padding: 10px 10px 14px;
  z-index: 30;
  gap: 2px;
  transition: width .22s ease;
  overflow: hidden;
}

.sidebar-brand {
  display: flex;
  align-items: center;
  gap: 10px;
  width: 100%;
  margin-bottom: 18px;
  padding: 0 2px;
  flex-shrink: 0;
  overflow: hidden;
}
.sidebar-logo {
  width: 34px; height: 34px;
  border-radius: 50%;
  overflow: hidden;
  flex-shrink: 0;
  box-shadow: 0 0 16px rgba(0,177,255,0.3);
}
.sidebar-brand-text {
  min-width: 0;
  overflow: hidden;
  transition: opacity .15s;
}
.sidebar-brand-title {
  font-size: 12px;
  font-weight: 700;
  color: var(--text);
  line-height: 1.3;
  word-break: break-word;
}
.sidebar-brand-sub {
  font-size: 9.5px;
  color: var(--text3);
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
  margin-top: 2px;
  letter-spacing: .1px;
}

.nav-sep {
  width: calc(100% - 4px);
  height: 1px;
  background: var(--border);
  margin: 6px 2px;
  transition: width .22s ease;
}

.nav-item {
  position: relative;
  width: 100%;
  height: 38px;
  border-radius: 8px;
  border: 1px solid transparent;
  background: none;
  color: var(--text2);
  cursor: pointer;
  display: flex;
  align-items: center;
  justify-content: flex-start;
  gap: 10px;
  padding: 0 10px;
  transition: background .15s, color .15s, border-color .15s;
  flex-shrink: 0;
  white-space: nowrap;
  overflow: hidden;
}
.nav-item:hover {
  background: rgba(255,255,255,0.05);
  color: var(--text);
}
.nav-item.active {
  background: rgba(59,130,246,0.12);
  color: var(--text);
  border-color: rgba(59,130,246,0.25);
}
.nav-item svg { width: 18px; height: 18px; flex-shrink: 0; }

.nav-label {
  font-size: 13px;
  font-weight: 500;
  letter-spacing: .1px;
  transition: opacity .15s;
  overflow: hidden;
}

/* Tooltip — only shown when sidebar is collapsed */
.nav-item::after {
  content: attr(data-tip);
  position: absolute;
  left: calc(100% + 10px);
  top: 50%; transform: translateY(-50%);
  background: #0d1e38;
  border: 1px solid var(--border2);
  color: var(--text2);
  font-size: 11px;
  font-weight: 600;
  white-space: nowrap;
  padding: 5px 10px;
  border-radius: 6px;
  pointer-events: none;
  opacity: 0;
  transition: opacity .1s;
  z-index: 100;
}
.sidebar.collapsed .nav-item:hover::after { opacity: 1; }

/* ── Sidebar: collapsed state ─────────────────────────────────────────────── */
.sidebar.collapsed {
  width: var(--sidebar-w-col);
  align-items: center;
  padding: 10px 0 14px;
}
.sidebar.collapsed .sidebar-brand { justify-content: center; padding: 0; margin-bottom: 18px; }
.sidebar.collapsed .sidebar-brand-text { display: none; }
.sidebar.collapsed .nav-item {
  width: 40px;
  justify-content: center;
  padding: 0;
  gap: 0;
}
.sidebar.collapsed .nav-label { opacity: 0; width: 0; }
.sidebar.collapsed .nav-sep { width: 28px; margin: 6px 0; }
.sidebar.collapsed .sidebar-toggle { width: 40px; justify-content: center; padding: 0; }
.sidebar.collapsed .sidebar-toggle .toggle-label { display: none; }

/* ── Sidebar run widget (above toggle) ──────────────────────────────────── */
.sidebar-run-widget {
  margin-top: auto;
  width: 100%;
  background: var(--surface2);
  border: 1px solid var(--border);
  border-radius: 10px;
  padding: 11px 12px 10px;
  margin-bottom: 8px;
  flex-shrink: 0;
  overflow: hidden;
  transition: all .22s ease;
}
.sidebar.collapsed .sidebar-run-widget {
  border-color: transparent;
  background: none;
  padding: 0;
  margin-bottom: 6px;
  border-radius: 0;
}
.srw-status {
  display: flex;
  justify-content: space-between;
  align-items: center;
  font-size: 11px;
  color: var(--text3);
  margin-bottom: 9px;
  transition: opacity .15s;
}
.srw-status-val {
  display: flex;
  align-items: center;
  gap: 5px;
  color: var(--text2);
  font-weight: 600;
}
.srw-status-val .stat-dot { width: 6px; height: 6px; }
.sidebar.collapsed .srw-status { display: none; }

.sidebar-run-btn {
  width: 100%;
  height: 34px;
  background: var(--accent);
  color: #fff;
  border: none;
  border-radius: 8px;
  font-size: 12px;
  font-weight: 700;
  cursor: pointer;
  display: flex;
  align-items: center;
  justify-content: center;
  gap: 6px;
  box-shadow: 0 0 14px rgba(59,130,246,0.3);
  transition: all .15s;
  white-space: nowrap;
  overflow: hidden;
}
.sidebar-run-btn:hover { background: #2563eb; box-shadow: 0 0 22px rgba(59,130,246,0.5); }
.sidebar-run-btn:disabled { background: var(--border2); color: var(--text3); cursor: not-allowed; box-shadow: none; }
.sidebar.collapsed .sidebar-run-btn {
  width: 40px;
  height: 40px;
  border-radius: 10px;
  gap: 0;
}
.sidebar.collapsed .sidebar-run-btn .srb-label { display: none; }

/* ── Sidebar toggle button (bottom) ──────────────────────────────────────── */
.sidebar-toggle {
  margin-top: 0;
  width: 100%;
  height: 36px;
  border-radius: 8px;
  border: none;
  background: none;
  color: var(--text3);
  cursor: pointer;
  display: flex;
  align-items: center;
  justify-content: flex-start;
  gap: 10px;
  padding: 0 10px;
  transition: background .15s, color .15s, width .22s;
  flex-shrink: 0;
  white-space: nowrap;
  overflow: hidden;
}
.sidebar-toggle:hover { color: var(--text); background: rgba(255,255,255,0.05); }
.toggle-label { font-size: 12px; font-weight: 500; letter-spacing: .1px; }

/* ── Main Area ───────────────────────────────────────────────────────────── */
.main-area {
  margin-left: var(--sidebar-w);
  flex: 1;
  display: flex;
  flex-direction: column;
  min-height: 100vh;
  min-width: 0;
}

/* ── Top Bar (full-width fixed) ──────────────────────────────────────────── */
.stats-bar {
  position: fixed;
  top: 0; left: 0; right: 0;
  height: var(--topbar-h);
  background: var(--surface);
  border-bottom: 1px solid var(--border);
  display: flex;
  align-items: center;
  gap: 0;
  z-index: 40;
  box-shadow: 0 1px 20px rgba(0,0,0,0.3);
  padding: 0;
}

/* Brand section aligns with sidebar width */
.topbar-brand {
  display: flex;
  align-items: center;
  gap: 10px;
  width: var(--sidebar-w);
  min-width: var(--sidebar-w);
  height: 100%;
  padding: 0 14px;
  border-right: 1px solid var(--border);
  flex-shrink: 0;
  overflow: hidden;
  transition: width .22s ease, min-width .22s ease;
}
.topbar-logo-wrap {
  width: 32px; height: 32px;
  border-radius: 50%;
  overflow: hidden;
  flex-shrink: 0;
  box-shadow: 0 0 14px rgba(0,177,255,0.28);
}
.topbar-brand-text { min-width: 0; overflow: hidden; transition: opacity .15s; }
.topbar-title {
  font-size: 12px;
  font-weight: 700;
  color: var(--text);
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
}
.topbar-sub {
  font-size: 9.5px;
  color: var(--text3);
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
  margin-top: 1px;
}

/* Stats section */
.topbar-stats {
  display: flex;
  align-items: center;
  height: 100%;
  flex: 1;
  padding: 0 22px;
  gap: 0;
}

/* Pending badge */
.pending-badge {
  background: rgba(59,130,246,0.14);
  border: 1px solid rgba(59,130,246,0.28);
  color: var(--accent2);
  font-size: 13px;
  font-weight: 700;
  padding: 2px 11px;
  border-radius: 20px;
  min-width: 32px;
  text-align: center;
  line-height: 1.6;
}

/* Collapsed sidebar → collapse brand text too */
body.sidebar-collapsed .topbar-brand {
  width: var(--sidebar-w-col);
  min-width: var(--sidebar-w-col);
  justify-content: center;
  padding: 0;
}
body.sidebar-collapsed .topbar-brand-text { display: none; }

.stat-block {
  display: flex;
  align-items: center;
  gap: 9px;
  padding: 0 18px;
  border-right: 1px solid var(--border);
  height: 100%;
}
.stat-block:first-child { padding-left: 0; }

.stat-dot {
  width: 7px; height: 7px;
  border-radius: 50%;
  background: var(--border2);
  flex-shrink: 0;
}
.stat-dot.ready  { background: var(--green); box-shadow: 0 0 6px rgba(16,185,129,0.5); }
.stat-dot.running { background: var(--amber); animation: blink 1s infinite; box-shadow: 0 0 6px rgba(245,158,11,0.5); }
@keyframes blink { 0%,100%{opacity:1} 50%{opacity:.25} }

.stat-info { display: flex; flex-direction: column; gap: 1px; }
.stat-label { font-size: 9px; font-weight: 700; color: var(--text3); text-transform: uppercase; letter-spacing: .8px; }
.stat-val   { font-size: 13px; font-weight: 700; color: var(--text); line-height: 1; }
.stat-val.green  { color: var(--green); }
.stat-val.amber  { color: var(--amber); }

.stat-refresh {
  background: none;
  border: 1px solid var(--border);
  color: var(--text3);
  font-size: 14px;
  cursor: pointer;
  width: 26px; height: 26px;
  border-radius: 6px;
  display: flex; align-items: center; justify-content: center;
  transition: all .15s;
  flex-shrink: 0;
  padding: 0;
}
.stat-refresh:hover { border-color: var(--border2); color: var(--text2); }

.stats-right {
  margin-left: auto;
  display: flex;
  align-items: center;
  gap: 8px;
}
.token-pill {
  background: var(--accent-lt);
  border: 1px solid var(--border2);
  border-radius: 20px;
  padding: 4px 11px;
  font-size: 11px;
  font-weight: 700;
  color: var(--accent2);
  letter-spacing: .3px;
}

/* ── Pages ───────────────────────────────────────────────────────────────── */
.pages-wrap { flex: 1; }

.page { display: none; padding: 22px; }
.page.active { display: block; }

/* ── Dashboard: Welcome + Overview + Grid ────────────────────────────────── */
.welcome-hdr {
  padding: 4px 0 18px;
  border-bottom: 1px solid var(--border);
  margin-bottom: 18px;
}
.welcome-title {
  font-size: 19px;
  font-weight: 700;
  color: var(--text);
  letter-spacing: -.3px;
}
.welcome-sub {
  font-size: 12.5px;
  color: var(--text3);
  margin-top: 3px;
}

.overview-row {
  display: grid;
  grid-template-columns: repeat(3, 1fr);
  gap: 12px;
  margin-bottom: 18px;
}
.overview-card {
  background: var(--surface);
  border: 1px solid var(--border);
  border-radius: 12px;
  padding: 15px 17px;
}
.ov-label {
  font-size: 10px;
  font-weight: 700;
  letter-spacing: 1px;
  color: var(--text3);
  text-transform: uppercase;
  margin-bottom: 8px;
}
.ov-val {
  font-size: 26px;
  font-weight: 800;
  color: var(--text);
  display: flex;
  align-items: center;
  gap: 8px;
  line-height: 1;
}
.ov-val .stat-dot { flex-shrink: 0; }
.ov-val.green { color: var(--green); }
.ov-val.amber { color: var(--amber); }
.ov-val.cyan  { color: var(--cyan); }
.ov-sub { font-size: 11px; color: var(--text3); margin-top: 5px; }

.dash-grid {
  display: grid;
  grid-template-columns: 1fr 1.45fr;
  gap: 14px;
  align-items: start;
}
.dash-left { display: flex; flex-direction: column; gap: 14px; }
.dash-right { min-width: 0; }

/* Activity log rows */
.dash-act-list { display: flex; flex-direction: column; }
.dash-act-row {
  display: flex;
  align-items: flex-start;
  gap: 9px;
  padding: 6px 0;
  border-bottom: 1px solid var(--border);
  font-size: 12px;
}
.dash-act-row:last-child { border-bottom: none; }
.dash-act-dot {
  width: 6px; height: 6px; border-radius: 50%;
  flex-shrink: 0; margin-top: 4px;
}
.dash-act-dot.g { background: var(--green); }
.dash-act-dot.b { background: var(--accent2); }
.dash-act-dot.y { background: var(--amber); }
.dash-act-dot.r { background: var(--red); }
.dash-act-dot.c { background: var(--cyan); }
.dash-act-dot.p { background: var(--purple); }
.dash-act-time {
  color: var(--text3); font-size: 10px; flex-shrink: 0; padding-top: 2px;
  font-variant-numeric: tabular-nums; font-family: "SF Mono", "Consolas", monospace;
  letter-spacing: 0; white-space: nowrap;
}
.dash-act-text { color: var(--text2); line-height: 1.4; flex: 1; min-width: 0; }
.dash-act-handle { color: var(--accent2); font-weight: 600; }
.dash-act-idle {
  display: flex; align-items: center; gap: 9px;
  padding: 10px 2px; color: var(--text3); font-size: 12px;
}
.dash-act-idle-dot {
  width: 7px; height: 7px; border-radius: 50%;
  background: var(--text3); flex-shrink: 0; opacity: .5;
}
.dash-act-viewall {
  display: block; text-align: center; margin-top: 12px; padding-top: 10px;
  border-top: 1px solid var(--border);
  color: var(--accent2); font-size: 11.5px; font-weight: 600;
  text-decoration: none; cursor: pointer;
  transition: color .15s;
}
.dash-act-viewall:hover { color: var(--accent); }

/* Dashboard partners list */
.dash-partner-row {
  display: flex;
  align-items: center;
  gap: 10px;
  padding: 8px 0;
  border-bottom: 1px solid var(--border);
  font-size: 12px;
  cursor: default;
  transition: background .12s;
}
.dash-partner-row:last-child { border-bottom: none; }
.dash-partner-av {
  width: 30px; height: 30px; border-radius: 50%;
  display: flex; align-items: center; justify-content: center;
  font-size: 12px; font-weight: 800; color: #fff; flex-shrink: 0;
  overflow: hidden;
}
.dash-partner-info { flex: 1; min-width: 0; }
.dash-partner-name { font-weight: 600; color: var(--text); font-size: 12.5px; white-space: nowrap; overflow: hidden; text-overflow: ellipsis; }
.dash-partner-sub { color: var(--text3); font-size: 11px; margin-top: 1px; }
.dash-partner-sub .dp-handle { color: var(--text3); }
.dash-partner-sub .dp-chain  { color: var(--text3); }
.dash-partner-right { display: flex; align-items: center; gap: 7px; flex-shrink: 0; }
.dash-partner-badge {
  font-size: 10px; font-weight: 700; padding: 2px 8px;
  border-radius: 20px; flex-shrink: 0;
  background: rgba(16,185,129,0.12); color: var(--green);
  border: 1px solid var(--green-br);
}
.dash-partner-dot { width: 6px; height: 6px; border-radius: 50%; background: var(--green); flex-shrink: 0; }
.dash-viewall-link {
  display: block; text-align: center; margin-top: 11px; padding-top: 10px;
  border-top: 1px solid var(--border);
  color: var(--accent2); font-size: 11.5px; font-weight: 600;
  cursor: pointer; transition: color .15s;
}
.dash-viewall-link:hover { color: var(--accent); }

/* Target account chips */
.dash-targets-hdr { display: flex; align-items: center; gap: 8px; margin-bottom: 12px; }
.dash-targets-title { font-size: 12px; font-weight: 700; color: var(--text); text-transform: uppercase; letter-spacing: 1px; flex: 1; }
.dash-targets-count { font-size: 11px; color: var(--text3); font-weight: 500; }
.dash-targets-edit {
  font-size: 11px; font-weight: 600; color: var(--accent2); background: none;
  border: 1px solid var(--border2); border-radius: 6px; padding: 2px 9px;
  cursor: pointer; transition: all .15s;
}
.dash-targets-edit:hover { background: var(--accent-lt); }
.dash-targets-grid { display: flex; flex-wrap: wrap; gap: 7px; padding-top: 2px; }
.target-chip {
  display: flex; align-items: center; gap: 5px;
  background: var(--surface2); border: 1px solid var(--border);
  border-radius: 20px; padding: 3px 9px 3px 4px;
  font-size: 11.5px; color: var(--text2); font-weight: 500;
}
.target-chip-av {
  width: 20px; height: 20px; border-radius: 50%;
  display: flex; align-items: center; justify-content: center;
  font-size: 8px; font-weight: 800; color: #fff; flex-shrink: 0;
}
.target-chip-more {
  display: flex; align-items: center;
  background: var(--surface2); border: 1px solid var(--border2);
  border-radius: 20px; padding: 3px 10px;
  font-size: 11px; color: var(--accent2); font-weight: 600;
}

/* Tweet filter tabs */
.draft-filter-row {
  display: flex; gap: 8px; margin-bottom: 22px; align-items: center;
}
.draft-filter-btn {
  display: flex; align-items: center; gap: 8px;
  font-size: 13px; font-weight: 700; padding: 8px 20px; border-radius: 10px;
  border: 1px solid var(--border); background: var(--surface2); color: var(--text3);
  cursor: pointer; white-space: nowrap;
  transition: all .18s cubic-bezier(.4,0,.2,1);
  letter-spacing: .1px;
}
.draft-filter-btn:hover {
  border-color: var(--border2); color: var(--text2);
  background: rgba(255,255,255,0.04);
  transform: translateY(-1px);
}
.draft-filter-count {
  font-size: 11px; font-weight: 700; min-width: 20px; text-align: center;
  padding: 1px 7px; border-radius: 20px; line-height: 1.6;
  background: rgba(255,255,255,0.07); color: inherit; transition: all .18s;
}
/* All — blue */
.draft-filter-btn[data-filter="all"].active {
  background: rgba(59,130,246,0.18); border-color: rgba(59,130,246,0.5);
  color: var(--accent2);
  box-shadow: 0 0 16px rgba(59,130,246,0.2), inset 0 0 12px rgba(59,130,246,0.06);
}
.draft-filter-btn[data-filter="all"].active .draft-filter-count {
  background: rgba(59,130,246,0.25); color: var(--accent2);
}
/* Partners — purple */
.draft-filter-btn[data-filter="partners"].active {
  background: rgba(129,140,248,0.15); border-color: rgba(129,140,248,0.45);
  color: var(--purple);
  box-shadow: 0 0 16px rgba(129,140,248,0.18), inset 0 0 12px rgba(129,140,248,0.06);
}
.draft-filter-btn[data-filter="partners"].active .draft-filter-count {
  background: rgba(129,140,248,0.22); color: var(--purple);
}
/* Watchlist — cyan */
.draft-filter-btn[data-filter="targets"].active {
  background: rgba(6,182,212,0.13); border-color: rgba(6,182,212,0.4);
  color: var(--cyan);
  box-shadow: 0 0 16px rgba(6,182,212,0.16), inset 0 0 12px rgba(6,182,212,0.05);
}
.draft-filter-btn[data-filter="targets"].active .draft-filter-count {
  background: rgba(6,182,212,0.2); color: var(--cyan);
}

/* Draft panel (right of dash-grid) */
.draft-panel { flex: 1; min-width: 0; }

.panel-hdr {
  display: flex;
  align-items: center;
  gap: 10px;
  margin-bottom: 16px;
}
.panel-title {
  font-size: 13px;
  font-weight: 700;
  color: var(--text);
  text-transform: uppercase;
  letter-spacing: 1.2px;
}
.draft-count {
  background: var(--accent-lt);
  border: 1px solid var(--border2);
  border-radius: 20px;
  padding: 2px 10px;
  font-size: 11px;
  color: var(--accent2);
  font-weight: 600;
}
.btn-ref {
  margin-left: auto;
  background: none;
  border: 1px solid var(--border);
  color: var(--text3);
  font-size: 12px;
  cursor: pointer;
  padding: 5px 12px;
  border-radius: 6px;
  transition: all .15s;
}
.btn-ref:hover { border-color: var(--border2); color: var(--text2); }

.empty {
  text-align: center;
  padding: 52px 0;
  color: var(--text3);
  font-size: 13px;
}

/* ── Draft Card v2 ───────────────────────────────────────────────────────── */
.dcard {
  background: var(--surface);
  border: 1px solid var(--border);
  border-radius: 12px;
  padding: 13px 15px;
  margin-bottom: 10px;
  transition: border-color .15s;
}
.dcard:hover:not(.done) { border-color: #1a2e4a; }
.dcard.done { opacity: .35; }

.dmeta {
  display: flex;
  gap: 6px;
  align-items: center;
  flex-wrap: wrap;
  margin-bottom: 11px;
}

.tag {
  display: inline-block;
  padding: 3px 9px;
  border-radius: 20px;
  font-size: 10px;
  font-weight: 700;
  letter-spacing: .5px;
  white-space: nowrap;
}
.tag.reply   { background: var(--accent-lt); color: var(--accent2); border: 1px solid var(--border2); }
.tag.qt      { background: #0d1a2e; color: var(--purple); border: 1px solid #1e2a4a; }
.tag.target  { background: rgba(245,158,11,0.12); color: var(--amber); border: 1px solid var(--amber-br); }
.tag.partner { background: rgba(129,140,248,0.14); color: var(--purple); border: 1px solid var(--purple-br); }
.tag.posted  { background: var(--green-lt); color: var(--green); border: 1px solid var(--green-br); }
.tag.skipped { background: var(--surface2); color: var(--text3); border: 1px solid var(--border); }

.dmeta-date {
  margin-left: auto;
  display: flex;
  flex-direction: column;
  align-items: flex-end;
  gap: 1px;
  flex-shrink: 0;
}
.dmeta-reltime {
  font-size: 11.5px;
  font-weight: 600;
  color: var(--text2);
  white-space: nowrap;
}
.dmeta-abstime {
  font-size: 10px;
  color: var(--text3);
  white-space: nowrap;
}

.dmeta-author {
  font-size: 13.5px;
  font-weight: 700;
  color: var(--accent2);
  letter-spacing: -.1px;
  flex-shrink: 0;
}

.orig {
  background: var(--surface2);
  border: 1px solid var(--border);
  border-left: 3px solid var(--border2);
  border-radius: 0 7px 7px 0;
  padding: 10px 13px;
  margin-bottom: 12px;
}
.orig-who  { font-size: 11px; color: var(--text3); margin-bottom: 4px; display: flex; align-items: center; gap: 8px; flex-wrap: wrap; }
.orig-who b { color: var(--accent2); font-weight: 600; }
.orig-txt  { font-size: 13px; color: var(--text2); line-height: 1.6; }
.view-link {
  display: inline-block;
  background: var(--accent-lt);
  border: 1px solid var(--border2);
  color: var(--accent2);
  font-size: 10px;
  font-weight: 600;
  text-decoration: none;
  padding: 2px 8px;
  border-radius: 5px;
  transition: all .15s;
}
.view-link:hover { background: var(--accent); color: #fff; }

/* Version blocks */
.versions { display: flex; flex-direction: column; gap: 7px; margin-bottom: 11px; }

.vb {
  border-radius: 8px;
  padding: 9px 11px;
  position: relative;
}
.vb.bullish   { background: var(--green-lt);  border: 1px solid var(--green-br); }
.vb.sarcastic { background: var(--amber-lt);  border: 1px solid var(--amber-br); }
.vb.alpha     { background: var(--purple-lt); border: 1px solid var(--purple-br); }
.vb.qtblock   { background: var(--green-lt);  border: 1px solid var(--green-br); }

.vb-hdr {
  display: flex;
  align-items: center;
  gap: 8px;
  margin-bottom: 7px;
}
.vlabel {
  font-size: 10px;
  font-weight: 700;
  text-transform: uppercase;
  letter-spacing: .6px;
  flex: 1;
}
.vb.bullish   .vlabel { color: var(--green); }
.vb.sarcastic .vlabel { color: var(--amber); }
.vb.alpha     .vlabel { color: var(--purple); }
.vb.qtblock   .vlabel { color: var(--green); }

.vb-actions {
  display: flex;
  gap: 4px;
  flex-shrink: 0;
}
.vb-btn {
  background: none;
  border: 1px solid transparent;
  color: var(--text3);
  font-size: 11px;
  font-weight: 600;
  cursor: pointer;
  padding: 2px 7px;
  border-radius: 5px;
  transition: all .12s;
  white-space: nowrap;
}
.vb-btn:hover {
  border-color: var(--border2);
  color: var(--text2);
  background: rgba(255,255,255,0.04);
}
.vb-btn.copied { color: var(--green); border-color: var(--green-br); }

/* Confidence badge inside version header */
.vb-confidence {
  font-size: 10px;
  font-weight: 700;
  padding: 2px 8px;
  border-radius: 20px;
  letter-spacing: .3px;
  white-space: nowrap;
}
.vb-confidence.high   { background: rgba(16,185,129,0.15);  color: var(--green);   border: 1px solid var(--green-br); }
.vb-confidence.medium { background: rgba(245,158,11,0.12);  color: var(--amber);   border: 1px solid var(--amber-br); }
.vb-confidence.alt    { background: rgba(129,140,248,0.12); color: var(--purple);  border: 1px solid var(--purple-br); }
.vb-confidence.mclb   { background: rgba(59,130,246,0.15);  color: var(--accent2); border: 1px solid rgba(59,130,246,0.35); }

/* Tone tags row inside version block */
.vb-footer {
  display: flex;
  align-items: center;
  justify-content: space-between;
  flex-wrap: wrap;
  gap: 6px;
  margin-top: 9px;
}
.vb-tags { display: flex; gap: 5px; flex-wrap: wrap; }
.vtag {
  font-size: 10.5px;
  color: var(--text2);
  background: rgba(255,255,255,0.07);
  border: 1px solid var(--border2);
  padding: 2px 8px;
  border-radius: 20px;
  white-space: nowrap;
  font-weight: 500;
}

/* Post buttons inside version block */
.vb-post-row {
  display: flex;
  gap: 5px;
  flex-shrink: 0;
}
.vb-post-primary {
  background: var(--accent);
  color: #fff;
  border: none;
  border-radius: 6px;
  padding: 4px 12px;
  font-size: 11px;
  font-weight: 700;
  cursor: pointer;
  transition: all .15s;
  white-space: nowrap;
}
.vb-post-primary:hover { background: #2563eb; }
.vb-post-primary:disabled { opacity: .3; cursor: not-allowed; }
.vb-edit-post {
  background: none;
  border: 1px solid var(--border2);
  color: var(--text2);
  border-radius: 6px;
  padding: 4px 10px;
  font-size: 11px;
  cursor: pointer;
  transition: all .15s;
  white-space: nowrap;
}
.vb-edit-post:hover { border-color: var(--accent2); color: var(--accent2); }

/* Context panel big stat items */
.ctx-big-stats { display: flex; flex-direction: column; gap: 0; }
.ctx-big-row {
  display: flex;
  justify-content: space-between;
  align-items: center;
  padding: 9px 0;
  border-bottom: 1px solid var(--border);
  font-size: 12.5px;
}
.ctx-big-row:last-child { border-bottom: none; }
.ctx-big-label { color: var(--text3); }
.ctx-big-val {
  font-size: 18px;
  font-weight: 800;
  color: var(--text);
  line-height: 1;
}
.ctx-big-val.green { color: var(--green); }
.ctx-big-val.amber { color: var(--amber); }
.ctx-big-val.cyan  { color: var(--cyan); }

.vtext {
  font-size: 12.5px;
  line-height: 1.65;
  color: var(--text);
  white-space: pre-wrap;
  cursor: text;
}
.vedit {
  width: 100%;
  background: rgba(0,0,0,0.2);
  border: 1px solid var(--border2);
  border-radius: 5px;
  padding: 7px 9px;
  color: var(--text);
  font-size: 12.5px;
  line-height: 1.65;
  resize: vertical;
  outline: none;
  font-family: inherit;
  min-height: 60px;
}
.vedit:focus { border-color: var(--accent); }

/* Card footer actions */
/* Graphic suggestion strip */
.graphic-suggestion {
  display: flex; align-items: flex-start; gap: 8px;
  background: rgba(245,158,11,0.07); border: 1px solid rgba(245,158,11,0.2);
  border-radius: 8px; padding: 8px 12px; margin-top: 10px;
  font-size: 12px; line-height: 1.4;
}
.graphic-icon { font-size: 14px; flex-shrink: 0; margin-top: 1px; }
.graphic-label {
  font-size: 10px; font-weight: 700; color: var(--amber);
  text-transform: uppercase; letter-spacing: .5px;
  flex-shrink: 0; padding-top: 2px; white-space: nowrap;
}
.graphic-text { color: var(--text2); flex: 1; }

.dactions {
  display: flex;
  gap: 6px;
  flex-wrap: wrap;
  align-items: center;
  padding-top: 10px;
  border-top: 1px solid var(--border);
}

.bp {
  border: none;
  border-radius: 6px;
  padding: 6px 13px;
  font-size: 12px;
  font-weight: 600;
  cursor: pointer;
  transition: all .15s;
}
.bp.s1  { background: var(--green-lt);  color: var(--green);  border: 1px solid var(--green-br); }
.bp.s1:hover  { background: #042a18; }
.bp.s2  { background: var(--amber-lt);  color: var(--amber);  border: 1px solid var(--amber-br); }
.bp.s2:hover  { background: #221400; }
.bp.s3  { background: var(--purple-lt); color: var(--purple); border: 1px solid var(--purple-br); }
.bp.s3:hover  { background: #130d2e; }
.bp.qt  { background: var(--green-lt);  color: var(--green);  border: 1px solid var(--green-br); }
.bp.qt:hover  { background: #042a18; }
.bp.regen {
  background: var(--accent-lt);
  color: var(--accent2);
  border: 1px solid var(--border2);
}
.bp.regen:hover { background: #112040; }

.bsk {
  background: var(--surface2);
  border: 1px solid var(--border);
  color: var(--text3);
  border-radius: 6px;
  padding: 6px 12px;
  font-size: 12px;
  cursor: pointer;
  transition: all .15s;
}
.bsk:hover { border-color: var(--border2); color: var(--text2); }
.bp:disabled, .bsk:disabled { opacity: .25; cursor: not-allowed; }

.regen-input {
  flex: 1;
  min-width: 0;
  background: var(--surface3);
  border: 1px solid var(--border2);
  border-radius: 6px;
  padding: 6px 11px;
  color: var(--text);
  font-size: 12px;
  font-family: inherit;
  outline: none;
  transition: border-color .15s;
}
.regen-input:focus { border-color: var(--accent); }
.regen-input::placeholder { color: var(--text3); }
.bhide {
  background: none;
  border: 1px solid transparent;
  color: var(--text3);
  border-radius: 6px;
  padding: 6px 10px;
  font-size: 12px;
  cursor: pointer;
  transition: all .15s;
  margin-left: auto;
}
.bhide:hover { border-color: var(--red-br); color: var(--red); background: var(--red-lt); }

.afb { font-size: 12px; display: none; }
.afb.ok  { color: var(--green); }
.afb.err { color: var(--red); }

/* ── Context Panel (right of dashboard) ──────────────────────────────────── */
.context-panel {
  width: 248px;
  flex-shrink: 0;
  display: flex;
  flex-direction: column;
  gap: 12px;
  position: sticky;
  top: 72px;
  max-height: calc(100vh - 80px);
  overflow-y: auto;
}
.context-panel::-webkit-scrollbar { width: 4px; }
.context-panel::-webkit-scrollbar-thumb { background: var(--border2); border-radius: 4px; }

.ctx-card {
  background: var(--surface);
  border: 1px solid var(--border);
  border-radius: 10px;
  padding: 14px 15px;
}
.ctx-title {
  font-size: 10px;
  font-weight: 700;
  color: var(--text3);
  text-transform: uppercase;
  letter-spacing: 1px;
  margin-bottom: 12px;
  padding-bottom: 10px;
  border-bottom: 1px solid var(--border);
}

/* Queue stats */
.ctx-stats { display: flex; flex-direction: column; gap: 7px; }
.ctx-stat-row {
  display: flex;
  justify-content: space-between;
  align-items: center;
  font-size: 12px;
}
.ctx-stat-name { color: var(--text3); }
.ctx-stat-val  { font-weight: 700; color: var(--text); }
.ctx-stat-val.green  { color: var(--green); }
.ctx-stat-val.amber  { color: var(--amber); }
.ctx-stat-val.purple { color: var(--purple); }

/* Activity log */
.activity-list { display: flex; flex-direction: column; gap: 7px; }
.activity-item {
  font-size: 11px;
  line-height: 1.4;
  padding: 7px 9px;
  border-radius: 6px;
  background: var(--surface2);
  border: 1px solid var(--border);
}
.activity-item .act-meta { color: var(--text3); margin-bottom: 2px; display: flex; gap: 5px; }
.activity-item .act-handle { color: var(--accent2); font-weight: 600; }
.activity-item .act-result { }
.activity-item .act-result.posted  { color: var(--green); }
.activity-item .act-result.skipped { color: var(--text3); }
.activity-item .act-text { color: var(--text2); overflow: hidden; display: -webkit-box; -webkit-line-clamp: 2; -webkit-box-orient: vertical; }
.ctx-empty { font-size: 12px; color: var(--text3); padding: 4px 0; }

/* ── Card (generic) ──────────────────────────────────────────────────────── */
.card {
  background: var(--surface);
  border: 1px solid var(--border);
  border-radius: 12px;
  padding: 20px 22px;
  margin-bottom: 14px;
}

/* ── Section label ───────────────────────────────────────────────────────── */
.slabel {
  font-size: 12px;
  font-weight: 700;
  color: var(--text);
  text-transform: uppercase;
  letter-spacing: 1.2px;
  margin-bottom: 15px;
  padding-bottom: 12px;
  border-bottom: 1px solid var(--border);
  display: flex;
  align-items: center;
  gap: 9px;
}
.slabel-count {
  background: var(--accent-lt);
  border: 1px solid var(--border2);
  border-radius: 20px;
  padding: 2px 9px;
  font-size: 10px;
  color: var(--accent2);
  font-weight: 600;
  letter-spacing: 0;
  text-transform: none;
}

/* ── Inputs ──────────────────────────────────────────────────────────────── */
.inputs-grid {
  display: grid;
  grid-template-columns: 1fr 1fr;
  gap: 12px;
  margin-bottom: 14px;
}
@media (max-width: 640px) { .inputs-grid { grid-template-columns: 1fr; } }

.input-card {
  background: var(--surface2);
  border: 1px solid var(--border);
  border-radius: 9px;
  padding: 14px 16px;
}
.input-card-label {
  font-size: 10px;
  font-weight: 700;
  color: var(--text3);
  text-transform: uppercase;
  letter-spacing: .7px;
  margin-bottom: 9px;
}
.input-row { display: flex; gap: 7px; }

.itext {
  flex: 1;
  background: var(--surface);
  border: 1px solid var(--border);
  border-radius: 7px;
  padding: 8px 11px;
  color: var(--text);
  font-size: 13px;
  outline: none;
  min-width: 0;
  transition: border-color .15s;
}
.itext::placeholder { color: var(--text3); }
.itext:focus { border-color: var(--border2); }

.btn-add {
  background: var(--accent-lt);
  border: 1px solid var(--border2);
  color: var(--accent2);
  border-radius: 7px;
  padding: 8px 14px;
  font-size: 12px;
  font-weight: 700;
  cursor: pointer;
  white-space: nowrap;
  transition: all .15s;
}
.btn-add:hover {
  background: var(--accent);
  border-color: var(--accent);
  color: #fff;
}

.imsg { font-size: 12px; margin-top: 6px; display: none; min-height: 16px; }
.imsg.ok  { color: var(--green); }
.imsg.err { color: var(--red); }

/* ── Account chips ───────────────────────────────────────────────────────── */
.accounts-wrap { display: flex; flex-wrap: wrap; gap: 7px; min-height: 32px; }
.ac-chip {
  display: inline-flex;
  align-items: center;
  gap: 6px;
  background: var(--surface2);
  border: 1px solid var(--border);
  border-radius: 20px;
  padding: 4px 10px 4px 8px;
  font-size: 12px;
  color: var(--text2);
  transition: border-color .15s;
}
.ac-chip:hover { border-color: var(--border2); }
.ac-chip .handle { color: var(--accent2); font-weight: 600; }
.ac-chip .rm {
  background: none; border: none; color: var(--text3);
  cursor: pointer; font-size: 12px; line-height: 1; padding: 0; margin-left: 2px;
}
.ac-chip .rm:hover { color: var(--red); }
.no-accounts { font-size: 12px; color: var(--text3); padding: 4px 0; }

/* ── Run Bot ─────────────────────────────────────────────────────────────── */
.run-row { display: flex; align-items: center; gap: 12px; flex-wrap: wrap; }
.btn-run {
  background: var(--accent);
  color: #fff;
  border: none;
  border-radius: 8px;
  padding: 10px 22px;
  font-size: 13px;
  font-weight: 700;
  cursor: pointer;
  transition: all .15s;
  box-shadow: 0 0 16px rgba(59,130,246,0.3);
}
.btn-run:hover:not(:disabled) { background: #2563eb; box-shadow: 0 0 24px rgba(59,130,246,0.5); }
.btn-run:disabled { background: var(--border2); color: var(--text3); cursor: not-allowed; box-shadow: none; }

.log {
  background: var(--surface2);
  border: 1px solid var(--border);
  border-radius: 8px;
  padding: 12px 14px;
  font-family: "SF Mono","Menlo",monospace;
  font-size: 12px;
  line-height: 1.85;
  color: var(--text3);
  height: 200px;
  overflow-y: auto;
  margin-top: 14px;
  display: none;
}
.log.show { display: block; }
.ll { white-space: pre-wrap; }
.ll.g { color: var(--green); }
.ll.y { color: var(--amber); }
.ll.r { color: var(--red); }
.ll.b { color: var(--accent2); }
.run-st { font-size: 12px; color: var(--text3); }

/* ── Partner grid ────────────────────────────────────────────────────────── */
.partners-grid {
  display: grid;
  grid-template-columns: repeat(auto-fill, minmax(240px, 1fr));
  gap: 10px;
}
.partner-card {
  background: var(--surface2);
  border: 1px solid var(--border);
  border-radius: 9px;
  padding: 13px 14px;
  transition: border-color .15s;
}
.partner-card:hover  { border-color: var(--cyan-br); }
.partner-card.inactive { opacity: .42; }
.pc-name   { font-size: 13px; font-weight: 700; color: var(--text); margin-bottom: 2px; }
.pc-meta   { font-size: 11px; color: var(--cyan); font-weight: 600; margin-bottom: 5px; }
.pc-handle { font-size: 11px; color: var(--text3); margin-bottom: 6px; }
.pc-ctx    { font-size: 11px; color: var(--text2); line-height: 1.5; display: -webkit-box; -webkit-line-clamp: 3; -webkit-box-orient: vertical; overflow: hidden; }

/* ── Tone / pillar pill buttons ──────────────────────────────────────────── */
.tone-btn {
  background: var(--surface2);
  border: 1px solid var(--border);
  color: var(--text2);
  border-radius: 20px;
  padding: 6px 14px;
  font-size: 12px;
  font-weight: 500;
  cursor: pointer;
  transition: all .15s;
}
.tone-btn:hover { border-color: var(--border2); color: var(--text); }
.tone-btn.active {
  background: var(--accent);
  border-color: var(--accent);
  color: #fff;
  font-weight: 700;
  box-shadow: 0 0 10px rgba(59,130,246,0.3);
}

/* ── Textareas ───────────────────────────────────────────────────────────── */
.dark-ta {
  width: 100%;
  background: var(--surface2);
  border: 1px solid var(--border);
  border-radius: 7px;
  padding: 9px 11px;
  color: var(--text);
  font-size: 13px;
  line-height: 1.6;
  resize: vertical;
  outline: none;
  font-family: inherit;
  transition: border-color .15s;
}
.dark-ta:focus { border-color: var(--border2); }
.dark-ta::placeholder { color: var(--text3); }

.result-ta {
  width: 100%;
  background: var(--green-lt);
  border: 1px solid var(--green-br);
  border-radius: 7px;
  padding: 9px 11px;
  color: var(--text);
  font-size: 14px;
  line-height: 1.65;
  resize: vertical;
  outline: none;
  font-family: inherit;
}

/* ── Page: Compose layout ────────────────────────────────────────────────── */
.compose-grid {
  display: grid;
  grid-template-columns: 1fr 1fr;
  gap: 14px;
  align-items: start;
}
@media (max-width: 820px) { .compose-grid { grid-template-columns: 1fr; } }

/* ── Divider ─────────────────────────────────────────────────────────────── */
.divider { border: none; border-top: 1px solid var(--border); margin: 14px 0; }
</style>
</head>
<body>
<div class="app-shell">

<!-- ── Sidebar ─────────────────────────────────────────────────────────── -->
<nav class="sidebar">

  <!-- Command Centre -->
  <button class="nav-item active" data-page="home" data-tip="Command Centre" onclick="showPage('home')">
    <svg viewBox="0 0 20 20" fill="none" stroke="currentColor" stroke-width="1.6">
      <rect x="2" y="2" width="7" height="7" rx="1.5"/>
      <rect x="11" y="2" width="7" height="7" rx="1.5"/>
      <rect x="2" y="11" width="7" height="7" rx="1.5"/>
      <rect x="11" y="11" width="7" height="7" rx="1.5"/>
    </svg>
    <span class="nav-label">Command Centre</span>
  </button>

  <!-- Tweet Review -->
  <button class="nav-item" data-page="tweets" data-tip="Tweet Review" onclick="showPage('tweets')">
    <svg viewBox="0 0 20 20" fill="none" stroke="currentColor" stroke-width="1.6">
      <rect x="3" y="2" width="14" height="16" rx="2"/>
      <line x1="6.5" y1="7" x2="13.5" y2="7"/>
      <line x1="6.5" y1="10.5" x2="13.5" y2="10.5"/>
      <line x1="6.5" y1="14" x2="10" y2="14"/>
    </svg>
    <span class="nav-label">Tweet Review</span>
  </button>

  <!-- Compose -->
  <button class="nav-item" data-page="compose" data-tip="Compose" onclick="showPage('compose')">
    <svg viewBox="0 0 20 20" fill="none" stroke="currentColor" stroke-width="1.6">
      <path d="M14.5 2.5a2.12 2.12 0 013 3L6 17l-4 1 1-4L14.5 2.5z"/>
    </svg>
    <span class="nav-label">Compose</span>
  </button>

  <!-- Targeting -->
  <button class="nav-item" data-page="targeting" data-tip="Watchlist" onclick="showPage('targeting')">
    <svg viewBox="0 0 20 20" fill="none" stroke="currentColor" stroke-width="1.6">
      <circle cx="10" cy="10" r="7"/>
      <circle cx="10" cy="10" r="3"/>
      <line x1="10" y1="1" x2="10" y2="4"/>
      <line x1="10" y1="16" x2="10" y2="19"/>
      <line x1="1" y1="10" x2="4" y2="10"/>
      <line x1="16" y1="10" x2="19" y2="10"/>
    </svg>
    <span class="nav-label">Watchlist</span>
  </button>

  <!-- Partners -->
  <button class="nav-item" data-page="partners" data-tip="Partners" onclick="showPage('partners')">
    <svg viewBox="0 0 20 20" fill="none" stroke="currentColor" stroke-width="1.6">
      <circle cx="7" cy="7" r="3"/>
      <path d="M1.5 18c0-3 2.5-5.5 5.5-5.5s5.5 2.5 5.5 5.5"/>
      <circle cx="14.5" cy="6.5" r="2.5"/>
      <path d="M18.5 17c0-2.5-1.5-4.5-4-5"/>
    </svg>
    <span class="nav-label">Partners</span>
  </button>

  <!-- Run Bot widget -->
  <div class="sidebar-run-widget">
    <div class="srw-status">
      <span>Bot Status</span>
      <span class="srw-status-val">
        <span class="stat-dot ready" id="sidebarDot"></span>
        <span id="sidebarStatus">Ready</span>
      </span>
    </div>
    <button class="sidebar-run-btn" id="sidebarRunBtn" onclick="runBot()">
      <svg viewBox="0 0 20 20" fill="currentColor" width="13" height="13"><path d="M7 5l9 5-9 5z"/></svg>
      <span class="srb-label">Run Bot</span>
    </button>
  </div>

  <!-- Collapse toggle -->
  <button class="sidebar-toggle" onclick="toggleSidebar()" data-tip="Expand">
    <svg viewBox="0 0 20 20" fill="none" stroke="currentColor" stroke-width="1.6" style="width:16px;height:16px;flex-shrink:0">
      <path d="M3 5h14M3 10h10M3 15h14"/>
    </svg>
    <span class="toggle-label">Collapse</span>
  </button>

  <!-- Logout -->
  <a href="/logout" class="sidebar-toggle" data-tip="Sign out" style="text-decoration:none;margin-top:2px;">
    <svg viewBox="0 0 20 20" fill="none" stroke="currentColor" stroke-width="1.6" style="width:16px;height:16px;flex-shrink:0">
      <path d="M13 15l4-5-4-5M17 10H7M10 3H4a1 1 0 00-1 1v12a1 1 0 001 1h6"/>
    </svg>
    <span class="toggle-label">Sign out</span>
  </a>
</nav>

<!-- ── Main Area ────────────────────────────────────────────────────────── -->
<div class="main-area">

  <!-- Stats Bar / Topbar -->
  <div class="stats-bar">

    <!-- Brand (aligns with sidebar) -->
    <div class="topbar-brand">
      <div class="topbar-logo-wrap">
        <svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 284.43 284.43" width="32" height="32" style="display:block">
          <defs>
            <linearGradient id="tb-lg1" x1="142.22" y1="284.43" x2="142.22" y2="0" gradientUnits="userSpaceOnUse">
              <stop offset="0" stop-color="#00b1ff"/>
              <stop offset="1" stop-color="#001a99"/>
            </linearGradient>
          </defs>
          <circle fill="url(#tb-lg1)" cx="142.22" cy="142.22" r="142.22"/>
          <path fill="#fff" d="m142.46,182.88l-44.79-36.16c1.99-5.76,5.05-11.03,8.95-15.55l35.71,28.83,74.91-60.55-.02-10.58-38.23,30.9c-10.15-8.7-22.94-13.45-36.43-13.42-13.97.03-26.74,5.23-36.53,13.76l-39.45-31.85.02,10.61,33.6,27.12c-3.87,4.53-7.02,9.68-9.29,15.28l-23.36-18.86.21,94.31,8.24-.02-.17-77.02,12.43,10.03c-.93,4.06-1.43,8.27-1.42,12.61.07,30.8,25.18,55.79,55.98,55.73,15.49-.03,29.87-6.26,40.5-17.52l-5.99-5.66c-9.06,9.6-21.33,14.91-34.53,14.94-26.25.06-47.66-21.25-47.72-47.5,0-2.28.16-4.51.47-6.71l46.93,37.88,66.97-54.14.17,77.06,8.24-.02-.21-94.27-75.18,60.77Zm.12-68.3c10.98-.02,21.43,3.66,29.88,10.46l-30.14,24.36-29.77-24.04c8.19-6.71,18.64-10.76,30.03-10.78Z"/>
          <path fill="#fff" d="m173.86,109.63l2.83-7.29c-5.3-3.1-10.96-5.43-16.83-6.97l4.62-22.74,12.81,13.85-9.96-20.52,25.1-6.89-25.02-.28,1.05-23.63-7.27,22.92-21.35-8.58,17.89,14.06-15.27,14.36,14.89-6.61-4.58,22.58c-6.3-.94-12.75-.96-19.15-.06l.02,7.79c13.95-2.22,28.23.61,40.25,7.99Z"/>
        </svg>
      </div>
      <div class="topbar-brand-text">
        <div class="topbar-title">MCLB Operator</div>
        <div class="topbar-sub">Command Center</div>
      </div>
    </div>

    <!-- Stats -->
    <div class="topbar-stats">
      <div class="stat-block">
        <div class="stat-dot ready" id="statDot"></div>
        <div class="stat-info">
          <div class="stat-label">Bot Status</div>
          <div class="stat-val" id="statStatus">Ready</div>
        </div>
      </div>
      <div class="stat-block">
        <div class="stat-info">
          <div class="stat-label">Drafts Pending</div>
          <div class="stat-val"><span class="pending-badge" id="statPending">—</span></div>
        </div>
      </div>
      <div class="stat-block" style="gap:10px">
        <div class="stat-info">
          <div class="stat-label">Last Scrape</div>
          <div class="stat-val" id="statLastScrape" style="font-size:12px;font-weight:600;color:var(--text2)">—</div>
        </div>
        <button class="stat-refresh" onclick="loadDrafts()" title="Refresh drafts">↻</button>
      </div>
    </div>

  </div>

  <!-- ── Pages ────────────────────────────────────────────────────────── -->
  <div class="pages-wrap">

    <!-- ① Dashboard: Command Center -->
    <div class="page active" id="page-home">

      <!-- Welcome header -->
      <div class="welcome-hdr">
        <div class="welcome-title">Welcome back, MCLB Ops</div>
        <div class="welcome-sub">Here's what's happening with your bot</div>
      </div>

      <!-- Overview stat cards (4) -->
      <div class="overview-row" style="grid-template-columns:repeat(4,1fr)">
        <div class="overview-card">
          <div class="ov-label">Bot Status</div>
          <div class="ov-val green" id="ovStatus">
            <span class="stat-dot ready" id="ovDot"></span>Ready
          </div>
        </div>
        <div class="overview-card">
          <div class="ov-label">Review Queue</div>
          <div class="ov-val amber" id="ovQueue">—</div>
          <div class="ov-sub">pending review</div>
        </div>
        <div class="overview-card">
          <div class="ov-label">Partners</div>
          <div class="ov-val cyan" id="ovPartners">—</div>
          <div class="ov-sub">active</div>
        </div>
        <div class="overview-card">
          <div class="ov-label">Watchlist</div>
          <div class="ov-val" style="color:var(--purple)" id="ovTargets">—</div>
          <div class="ov-sub">monitored</div>
        </div>
      </div>

      <!-- Main 2-col: Activity Log | (Partners + Targets stacked) -->
      <div class="dash-grid" style="grid-template-columns:1.2fr 1fr;align-items:start">

        <!-- Left: Activity Log -->
        <div class="card" style="margin-bottom:0">
          <div class="slabel">
            Bot Activity Log
            <span style="margin-left:auto;display:flex;align-items:center;gap:4px;font-size:11px;font-weight:600;color:var(--green)">
              <span class="stat-dot ready" style="width:5px;height:5px;flex-shrink:0"></span>Live
            </span>
          </div>
          <div id="dashActivityLog"><div class="ctx-empty" style="padding:8px 0 2px">No activity yet.</div></div>
        </div>

        <!-- Right: Partners + Watchlist stacked -->
        <div style="display:flex;flex-direction:column;gap:14px">

          <!-- Partners -->
          <div class="card" style="margin-bottom:0">
            <div class="slabel">
              Partners
              <span class="slabel-count" id="dashPartnerCount">—</span>
              <button onclick="showPage('partners')" style="margin-left:auto;background:none;border:none;color:var(--accent2);font-size:11.5px;font-weight:600;cursor:pointer;padding:0;transition:color .15s" onmouseover="this.style.color='var(--accent)'" onmouseout="this.style.color='var(--accent2)'">View all →</button>
            </div>
            <div id="dashPartnersList"><div class="ctx-empty" style="padding:8px 0 2px">Loading…</div></div>
          </div>

          <!-- Watchlist -->
          <div class="card" style="margin-bottom:0">
            <div class="dash-targets-hdr">
              <span class="dash-targets-title">Watchlist</span>
              <span class="dash-targets-count" id="dashTargetCount">—</span>
              <button class="dash-targets-edit" onclick="showPage('targeting')">Edit</button>
            </div>
            <div class="dash-targets-grid" id="dashTargets">
              <div class="ctx-empty" style="padding:4px 0">Loading…</div>
            </div>
          </div>

        </div>

      </div>
    </div>

    <!-- ② Tweet Review -->
    <div class="page" id="page-tweets">
      <div class="panel-hdr">
        <div class="panel-title">Tweet Review</div>
        <span class="draft-count" id="draftCount">—</span>
        <button class="btn-ref" onclick="loadDrafts()">↻ Refresh</button>
      </div>
      <!-- Filter tabs -->
      <div class="draft-filter-row">
        <button class="draft-filter-btn active" data-filter="all"      onclick="setDraftFilter(this,'all')">All <span class="draft-filter-count" id="fCount-all">—</span></button>
        <button class="draft-filter-btn"        data-filter="partners" onclick="setDraftFilter(this,'partners')">♦ Partners <span class="draft-filter-count" id="fCount-partners">—</span></button>
        <button class="draft-filter-btn"        data-filter="targets"  onclick="setDraftFilter(this,'targets')">★ Watchlist <span class="draft-filter-count" id="fCount-targets">—</span></button>
      </div>
      <div id="draftsWrap"><div class="empty">Run the bot to generate drafts.</div></div>
    </div>

    <!-- ② Compose -->
    <div class="page" id="page-compose">
      <div class="compose-grid">

        <!-- Custom Reply -->
        <div class="card" style="margin-bottom:0">
          <div class="slabel">Custom Reply</div>

          <div style="margin-bottom:13px">
            <div class="input-card-label" style="margin-bottom:6px">Tweet URL</div>
            <div class="input-row">
              <input id="customTweetUrl" class="itext" type="text" placeholder="https://x.com/user/status/..." oninput="onUrlInput()">
              <button class="btn-add" id="fetchBtn" onclick="fetchTweet()">Fetch</button>
            </div>
            <div id="fetchStatus" style="font-size:11px;color:var(--text3);margin-top:5px;display:none"></div>
          </div>

          <div style="margin-bottom:13px">
            <div class="input-card-label" style="margin-bottom:5px">Tweet text <span style="color:var(--text3);font-weight:400;text-transform:none;letter-spacing:0;font-size:11px">— auto-filled or paste</span></div>
            <textarea id="customTweetText" rows="3" class="dark-ta" placeholder="Paste tweet text or fetch from URL…"></textarea>
          </div>

          <div style="margin-bottom:13px">
            <div class="input-card-label" style="margin-bottom:5px">Your angle <span style="color:var(--text3);font-weight:400;text-transform:none;letter-spacing:0;font-size:11px">— optional</span></div>
            <input id="customInstructions" class="itext" type="text" style="width:100%" placeholder="e.g. focus on fBOMB flywheel, push back on TVL…">
          </div>

          <div style="margin-bottom:14px">
            <div class="input-card-label" style="margin-bottom:7px">Tone</div>
            <div style="display:flex;flex-wrap:wrap;gap:6px">
              <button class="tone-btn active" data-tone="analytical" onclick="setTone(this)">Analytical</button>
              <button class="tone-btn" data-tone="bullish" onclick="setTone(this)">Bullish</button>
              <button class="tone-btn" data-tone="bearish" onclick="setTone(this)">Bearish</button>
              <button class="tone-btn" data-tone="sarcastic" onclick="setTone(this)">Sarcastic</button>
              <button class="tone-btn" data-tone="contrarian" onclick="setTone(this)">Contrarian</button>
            </div>
          </div>

          <button class="btn-run" id="genBtn" onclick="generateCustom()" style="font-size:12px;padding:8px 18px">Generate Reply</button>

          <div id="customResult" style="display:none;margin-top:14px;padding-top:14px;border-top:1px solid var(--border)">
            <div class="input-card-label" style="margin-bottom:5px">Generated <span style="color:var(--text3);font-weight:400;text-transform:none;letter-spacing:0;font-size:11px">— edit if needed</span></div>
            <textarea id="customReplyText" rows="4" class="result-ta"></textarea>
            <div style="display:flex;gap:7px;margin-top:9px;align-items:center;flex-wrap:wrap">
              <button class="bp s1" id="postCustomBtn" onclick="postCustom()">Post as Reply</button>
              <button class="bsk" onclick="generateCustom()">Regenerate</button>
              <span id="customFb" class="afb"></span>
            </div>
          </div>
        </div>

        <!-- Original Post -->
        <div class="card" style="margin-bottom:0">
          <div class="slabel">Original Post</div>

          <div style="margin-bottom:13px">
            <div class="input-card-label" style="margin-bottom:7px">Topic pillar</div>
            <div style="display:flex;flex-wrap:wrap;gap:6px">
              <button class="tone-btn active" data-pillar="fbomb"     onclick="setPillar(this)">fBOMB</button>
              <button class="tone-btn" data-pillar="mclb"             onclick="setPillar(this)">$MCLB</button>
              <button class="tone-btn" data-pillar="liquidity"        onclick="setPillar(this)">Liquidity</button>
              <button class="tone-btn" data-pillar="treasury"         onclick="setPillar(this)">Treasury</button>
              <button class="tone-btn" data-pillar="ecosystem"        onclick="setPillar(this)">Ecosystem</button>
              <button class="tone-btn" data-pillar="operator"         onclick="setPillar(this)">Operator</button>
              <button class="tone-btn" data-pillar="bribes"           onclick="setPillar(this)">Bribes</button>
              <button class="tone-btn" data-pillar="weekly"           onclick="setPillar(this)">Weekly Update</button>
            </div>
          </div>

          <div style="margin-bottom:13px">
            <div class="input-card-label" style="margin-bottom:5px" id="origDetailsLabel">Angle <span style="color:var(--text3);font-weight:400;text-transform:none;letter-spacing:0;font-size:11px">— optional</span></div>
            <textarea id="origInstructions" class="itext" rows="3" style="width:100%;resize:vertical;font-family:inherit" placeholder="Leave blank to let AI pick the angle…"></textarea>
          </div>

          <div style="margin-bottom:14px">
            <div class="input-card-label" style="margin-bottom:7px">Format</div>
            <div style="display:flex;gap:6px">
              <button class="tone-btn active" data-format="tweet"  onclick="setFormat(this)">Single Tweet</button>
              <button class="tone-btn" data-format="thread"        onclick="setFormat(this)">Thread (4–6)</button>
            </div>
          </div>

          <button class="btn-run" id="origGenBtn" onclick="generateOriginal()" style="font-size:12px;padding:8px 18px">Generate</button>

          <div id="origResult" style="display:none;margin-top:14px;padding-top:14px;border-top:1px solid var(--border)">
            <div class="input-card-label" style="margin-bottom:9px">Generated <span style="color:var(--text3);font-weight:400;text-transform:none;letter-spacing:0;font-size:11px">— edit if needed</span></div>
            <div id="origTweets"></div>
            <div style="display:flex;gap:7px;margin-top:10px;align-items:center;flex-wrap:wrap">
              <button class="bp s1" id="origPostBtn" onclick="postOriginal()">Post Tweet</button>
              <button class="bsk" onclick="generateOriginal()">Regenerate</button>
              <span id="origFb" class="afb"></span>
            </div>
          </div>
        </div>

      </div>
    </div>

    <!-- ③ Targeting -->
    <div class="page" id="page-targeting">

      <div class="inputs-grid" style="margin-bottom:16px">
        <div class="input-card">
          <div class="input-card-label">Target a specific tweet</div>
          <div class="input-row">
            <input class="itext" id="tweetUrlInput" type="text" placeholder="https://x.com/user/status/…"
                   onkeydown="if(event.key==='Enter')addTweetTarget()">
            <button class="btn-add" onclick="addTweetTarget()">Add</button>
          </div>
          <div class="imsg" id="tweetMsg"></div>
        </div>
        <div class="input-card">
          <div class="input-card-label">Add account to watchlist</div>
          <div class="input-row">
            <input class="itext" id="accountInput" type="text" placeholder="@handle"
                   onkeydown="if(event.key==='Enter')addAccount()">
            <button class="btn-add" onclick="addAccount()">Add</button>
          </div>
          <div class="imsg" id="accountMsg"></div>
        </div>
      </div>

      <div class="card">
        <div class="slabel">
          Watchlist
          <span class="slabel-count" id="acCount">0</span>
        </div>
        <div class="accounts-wrap" id="accountsWrap">
          <span class="no-accounts">Loading…</span>
        </div>
      </div>

    </div>

    <!-- ④ Partners -->
    <div class="page" id="page-partners">
      <div class="card">
        <div class="slabel">
          Partners
          <span class="slabel-count" id="partnerCount">—</span>
          <button class="btn-add" onclick="showAddPartner()" style="padding:4px 11px;font-size:11px">+ Add</button>
        </div>
        <div class="partners-grid" id="partnersGrid">
          <span class="no-accounts">Loading…</span>
        </div>
      </div>
    </div>

    <!-- ⑤ Run Bot -->
    <div class="page" id="page-run">
      <div class="card">
        <div class="slabel">Run Bot</div>
        <div class="run-row">
          <button class="btn-run" id="runBtn" onclick="runBot()">▶ Run Bot</button>
          <div class="stat-dot ready" id="dot" style="display:none"></div>
          <span class="run-st" id="runSt">Ready — click to scrape tweets and generate drafts</span>
        </div>
        <div class="log" id="log"></div>
      </div>
    </div>

  </div><!-- end pages-wrap -->
</div><!-- end main-area -->
</div><!-- end app-shell -->

<script>
// ── Globals ───────────────────────────────────────────────────────────────────
let running      = false;
let _allDrafts   = [];
let _liveLogs    = [];   // { time: "HH:MM:SS", dot: "g/b/y/r/c/p", html: "..." }
let _draftFilter = "all";
const _edits    = {};   // { tweetId: { bullish: str, sarcastic: str, alpha: str } }
let _partners   = [];

// ── Sidebar collapse ──────────────────────────────────────────────────────────
function toggleSidebar() {
  const sidebar  = document.querySelector(".sidebar");
  const togBtn   = document.querySelector(".sidebar-toggle");
  const label    = togBtn?.querySelector(".toggle-label");
  const collapsed = sidebar.classList.toggle("collapsed");
  document.documentElement.style.setProperty("--sidebar-w", collapsed ? "58px" : "220px");
  document.body.classList.toggle("sidebar-collapsed", collapsed);
  if (label) label.textContent = collapsed ? "Expand" : "Collapse";
  if (togBtn) togBtn.setAttribute("data-tip", collapsed ? "Expand" : "Collapse");
  localStorage.setItem("sidebarCollapsed", collapsed ? "1" : "0");
}

// Restore sidebar state from last session
(function() {
  if (localStorage.getItem("sidebarCollapsed") === "1") {
    const sidebar = document.querySelector(".sidebar");
    if (sidebar) {
      sidebar.classList.add("collapsed");
      document.documentElement.style.setProperty("--sidebar-w", "58px");
      document.body.classList.add("sidebar-collapsed");


      const label = document.querySelector(".sidebar-toggle .toggle-label");
      if (label) label.textContent = "Expand";
    }
  }
})();

// ── Page navigation ───────────────────────────────────────────────────────────
function showPage(id) {
  document.querySelectorAll(".page").forEach(p => p.classList.remove("active"));
  document.querySelectorAll(".nav-item").forEach(n => {
    n.classList.toggle("active", n.dataset.page === id);
  });
  const pg = document.getElementById("page-" + id);
  if (pg) pg.classList.add("active");

  // Lazy-load data for pages
  if (id === "targeting")  loadAccounts();
  if (id === "partners")   loadPartners();
}

// ── Run Bot ───────────────────────────────────────────────────────────────────
function runBot() {
  if (running) return;
  running = true;
  const btn    = document.getElementById("runBtn");
  const sBtn   = document.getElementById("sidebarRunBtn");
  const dot    = document.getElementById("dot");
  const st     = document.getElementById("runSt");
  const log    = document.getElementById("log");

  if (btn) { btn.disabled = true; }
  if (sBtn) sBtn.disabled = true;
  if (dot) { dot.style.display = "block"; dot.className = "stat-dot running"; }
  if (st) st.textContent = "Running…";
  if (log) { log.className = "log show"; log.innerHTML = ""; }

  // Update topbar + sidebar status
  setStatus("running");

  const es = new EventSource("/run-bot");
  es.onmessage = ev => {
    const line = JSON.parse(ev.data);
    if (line === "__DONE__") {
      es.close(); running = false;
      if (btn) btn.disabled = false;
      if (sBtn) sBtn.disabled = false;
      if (dot) dot.className = "stat-dot ready";
      if (st) st.textContent = "Done ✓";
      setStatus("ready");
      // Add a "Done" entry to live logs
      _pushLiveLog("g", "Run complete — drafts ready for review");
      loadDrafts();
      return;
    }
    // Append to full log panel
    const d  = document.createElement("div");
    const lo = line.toLowerCase();
    d.className = "ll" + (
      lo.includes("error")  ? " r" :
      lo.includes("skip")   ? " y" :
      lo.includes("──") || lo.includes("===") ? " b" :
      lo.includes("★") || lo.includes("♦") || lo.match(/\d+ repl|qt:|done/) ? " g" : ""
    );
    d.textContent = line;
    if (log) { log.appendChild(d); log.scrollTop = log.scrollHeight; }
    // Capture summary lines into _liveLogs for dashboard
    _captureLogLine(line);
  };
  es.onerror = () => {
    es.close(); running = false;
    if (btn) btn.disabled = false;
    if (sBtn) sBtn.disabled = false;
    if (dot) dot.className = "stat-dot ready";
    if (st) st.textContent = "Error — check terminal";
    setStatus("ready");
  };
}

function setStatus(state) {
  const isRunning = state === "running";
  const dotCls = isRunning ? "stat-dot running" : "stat-dot ready";
  const lbl2   = isRunning ? "Running" : "Ready";
  const col    = isRunning ? "var(--amber)" : "";

  // Topbar dot + label
  const dot  = document.getElementById("statDot");
  const lbl  = document.getElementById("statStatus");
  if (dot) dot.className = dotCls;
  if (lbl) { lbl.textContent = lbl2; lbl.style.color = col; }

  // Sidebar widget
  const sDot = document.getElementById("sidebarDot");
  const sLbl = document.getElementById("sidebarStatus");
  if (sDot) sDot.className = dotCls;
  if (sLbl) { sLbl.textContent = lbl2; sLbl.style.color = col; }

  // Overview card
  const ovDot = document.getElementById("ovDot");
  const ovSt  = document.getElementById("ovStatus");
  if (ovDot) ovDot.className = dotCls;
  if (ovSt) {
    ovSt.className = isRunning ? "ov-val amber" : "ov-val green";
    // Keep dot + text
    ovSt.innerHTML = `<span class="${dotCls}" id="ovDot"></span>${lbl2}`;
  }
}

// ── Inputs (targeting page) ───────────────────────────────────────────────────
async function addTweetTarget() {
  const inp = document.getElementById("tweetUrlInput");
  const msg = document.getElementById("tweetMsg");
  const val = inp.value.trim();
  if (!val) return;
  const res = await post("/add-tweet-target", {url: val});
  showMsg(msg, res.ok ? "Added — picked up on next run." : "Error: " + res.error, res.ok);
  if (res.ok) inp.value = "";
}

async function addAccount() {
  const inp = document.getElementById("accountInput");
  const msg = document.getElementById("accountMsg");
  const val = inp.value.trim();
  if (!val) return;
  const res = await post("/add-account", {handle: val});
  showMsg(msg, res.ok ? "Added to target list." : "Error: " + res.error, res.ok);
  if (res.ok) { inp.value = ""; renderAccounts(res.accounts); }
}

async function loadAccounts() {
  const accounts = await fetch("/accounts").then(r => r.json());
  renderAccounts(accounts);
}

function renderAccounts(accounts) {
  const wrap  = document.getElementById("accountsWrap");
  const count = document.getElementById("acCount");
  count.textContent = accounts.length;
  if (!accounts.length) {
    wrap.innerHTML = '<span class="no-accounts">No accounts in watchlist yet.</span>';
    return;
  }
  wrap.innerHTML = accounts.map(h =>
    `<div class="ac-chip">
      <span class="handle">@${e(h)}</span>
      <button class="rm" onclick="removeAccount('${ea(h)}')" title="Remove">✕</button>
    </div>`
  ).join("");
}

async function removeAccount(handle) {
  const res = await post("/remove-account", {handle});
  if (res.ok) renderAccounts(res.accounts);
}

// ── Drafts ────────────────────────────────────────────────────────────────────
// Sort by actual tweet posted time (snowflake), fall back to scrape time
function tweetTime(d) {
  const dt = tweetPostedDate(d.tweet_id);
  if (dt && !isNaN(dt)) return dt.getTime();
  const s = d.created_at ? new Date(d.created_at.replace(" ", "T")) : null;
  return s && !isNaN(s) ? s.getTime() : 0;
}
function byNewest(a, b) { return tweetTime(b) - tweetTime(a); }
// Partners always surface first, then watchlist, then newest within each tier
function byPriorityThenNewest(a, b) {
  const pa = a.is_partner ? 2 : (a.is_target_account ? 1 : 0);
  const pb = b.is_partner ? 2 : (b.is_target_account ? 1 : 0);
  if (pb !== pa) return pb - pa;
  return tweetTime(b) - tweetTime(a);
}

async function loadDrafts() {
  const raw = await fetch("/drafts").then(r => r.json());
  _allDrafts = raw;
  const all = raw.filter(d => d.action !== "hidden");  // hidden excluded from stats/log too
  updateStats(all);
  renderActivityLog(all);
  renderFilteredDrafts();
}

function renderFilteredDrafts() {
  // Never show hidden drafts anywhere in the UI
  const all = _allDrafts.filter(d => d.action !== "hidden");

  // Count badges — based on fresh tweets only (≤4 days)
  const MAX_AGE_MS_C  = 4 * 24 * 60 * 60 * 1000;
  const freshAll      = all.filter(d => Date.now() - tweetTime(d) < MAX_AGE_MS_C);
  const countAll      = freshAll.length;
  const countPartners = freshAll.filter(d => d.is_partner).length;
  const countTargets  = freshAll.filter(d => d.is_target_account && !d.is_partner).length;
  const cAll = document.getElementById("fCount-all");
  const cPar = document.getElementById("fCount-partners");
  const cTgt = document.getElementById("fCount-targets");
  if (cAll) cAll.textContent = countAll;
  if (cPar) cPar.textContent = countPartners;
  if (cTgt) cTgt.textContent = countTargets;

  // Drop tweets older than 4 days (by actual tweet posted time)
  const MAX_AGE_MS = 4 * 24 * 60 * 60 * 1000;
  const fresh = all.filter(d => {
    const age = Date.now() - tweetTime(d);
    return age < MAX_AGE_MS;
  });

  // Apply Partners / Watchlist filter
  let filtered = fresh;
  if (_draftFilter === "partners") filtered = fresh.filter(d => d.is_partner);
  else if (_draftFilter === "targets") filtered = fresh.filter(d => d.is_target_account && !d.is_partner);

  const pending = filtered.filter(d => !d.reviewed).sort(byPriorityThenNewest);
  const posted  = filtered.filter(d => d.action === "posted").sort(byNewest);
  const skipped = filtered.filter(d => d.action === "skipped").sort(byNewest);

  const allPending = all.filter(d => !d.reviewed).length;
  const el = document.getElementById("draftCount");
  if (el) el.textContent = allPending + " pending";

  const ordered = [...pending, ...posted, ...skipped];
  const wrap    = document.getElementById("draftsWrap");
  if (!wrap) return;
  if (!ordered.length) {
    const label = _draftFilter === "partners" ? "No partner drafts yet." :
                  _draftFilter === "targets"  ? "No watchlist drafts yet." :
                  "No drafts yet. Run the bot first.";
    wrap.innerHTML = `<div class="empty">${label}</div>`;
    return;
  }
  wrap.innerHTML = ordered.map(renderDraft).join("");
}

function setDraftFilter(btn, filter) {
  _draftFilter = filter;
  document.querySelectorAll(".draft-filter-btn").forEach(b => b.classList.remove("active"));
  btn.classList.add("active");
  renderFilteredDrafts();
}

function updateStats(all) {
  const pending = all.filter(d => !d.reviewed).length;

  // Topbar
  document.getElementById("statPending").textContent = pending;

  // Last scrape time
  fetch("/last-scrape").then(r => r.json()).then(data => {
    document.getElementById("statLastScrape").textContent = data.time || "Never";
  }).catch(() => {});

  // Overview cards
  const ovQ = document.getElementById("ovQueue");
  if (ovQ) ovQ.textContent = pending;

  // Partners count + panel
  fetch("/partners").then(r => r.json()).then(data => {
    const active = Array.isArray(data) ? data.filter(p => p.active !== false) : [];
    const ovEl = document.getElementById("ovPartners");
    if (ovEl) ovEl.textContent = active.length;
    renderDashPartners(active);
  }).catch(() => {});

  // Target accounts count (4th card)
  fetch("/accounts").then(r => r.json()).then(data => {
    const el = document.getElementById("ovTargets");
    if (el) el.textContent = Array.isArray(data) ? data.length : 0;
  }).catch(() => {});

  // Activity log
  renderDashActivity();

  // Target accounts chips on Command Centre
  loadDashTargets();
}

const _chipColors = ["#f59e0b","#3b82f6","#10b981","#8b5cf6","#ef4444","#06b6d4","#f97316","#ec4899","#14b8a6","#a3e635"];
function chipColor(handle) {
  let h = 0;
  for (let i = 0; i < handle.length; i++) h = (h * 31 + handle.charCodeAt(i)) & 0xffff;
  return _chipColors[h % _chipColors.length];
}

// Push a line into _liveLogs (max 30 kept)
function _pushLiveLog(dot, html) {
  const now = new Date();
  const hh  = String(now.getHours()).padStart(2,"0");
  const mm  = String(now.getMinutes()).padStart(2,"0");
  const ss  = String(now.getSeconds()).padStart(2,"0");
  _liveLogs.unshift({ time: `${hh}:${mm}:${ss}`, dot, html });
  if (_liveLogs.length > 30) _liveLogs.length = 30;
}

// Called on each SSE line from bot — extract summary events
function _captureLogLine(line) {
  if (!line || !line.trim()) return;
  const lo = line.toLowerCase();
  // Skip noisy internal lines
  if (lo.includes("draft_bullish") || lo.includes("draft_serious") || lo.includes("draft_sarcastic")) return;

  if (lo.includes("error")) {
    _pushLiveLog("r", `Error: ${e(line.slice(0, 80))}`);
  } else if (lo.includes("logged in")) {
    _pushLiveLog("g", "Authenticated — session active");
  } else if (lo.match(/\d+ candidates/)) {
    const m = line.match(/(\d+) candidates/);
    _pushLiveLog("c", `Found ${m ? m[0] : "tweets"} in pool`);
  } else if (lo.match(/for you|following feed/)) {
    _pushLiveLog("b", lo.includes("for you") ? "Scanning For You feed…" : "Scanning Following feed…");
  } else if (lo.match(/target accounts?/i) && lo.match(/\d+/)) {
    const m = line.match(/(\d+) target/);
    _pushLiveLog("b", `Scanning ${m ? m[1] : ""} watchlist accounts`);
  } else if (lo.match(/\[1 bullish\]|\[2 sarcastic\]|\[3 alpha\]/)) {
    // Skip individual variant lines
  } else if (lo.match(/★/) && lo.match(/@\w+/)) {
    const auth = line.match(/@[\w\d_]+/);
    _pushLiveLog("g", `Generated variants for <span class="dash-act-handle">${auth ? e(auth[0]) : "account"}</span> ☆`);
  } else if (lo.includes("repl") && lo.match(/\d+.*repl/)) {
    const m = line.match(/(\d+) repl/);
    _pushLiveLog("g", `Added ${m ? m[1] : "new"} replies to review queue`);
  } else if (lo.includes("quote") && lo.match(/\d+/)) {
    const m = line.match(/(\d+)/);
    _pushLiveLog("c", `Added ${m ? m[1] : "new"} quote tweets to queue`);
  } else if (lo.includes("done") && (lo.includes("repl") || lo.includes("pending"))) {
    _pushLiveLog("g", `Run complete`);
  } else if (lo.match(/──\s*\[(?:partner|target)\]/i)) {
    const auth = line.match(/@[\w\d_]+/);
    _pushLiveLog("p", `Scanning <span class="dash-act-handle">${auth ? e(auth[0]) : "account"}</span>…`);
  }
  // Refresh dashboard activity log as lines come in
  if (document.getElementById("page-home")?.classList.contains("active")) {
    renderDashActivity();
  }
}

function renderDashActivity() {
  const el = document.getElementById("dashActivityLog");
  if (!el) return;

  // Only show real live logs captured from actual bot SSE output.
  // Never fabricate entries from draft data.
  if (!_liveLogs.length) {
    el.innerHTML = `<div class="dash-act-idle">
      <span class="dash-act-idle-dot"></span>
      Bot is idle — press <strong>Run Bot</strong> to see live activity
    </div>`;
    return;
  }

  const shown = _liveLogs.slice(0, 8);
  el.innerHTML = '<div class="dash-act-list">' + shown.map(r =>
    `<div class="dash-act-row">
       <span class="dash-act-dot ${r.dot}"></span>
       ${r.time ? `<span class="dash-act-time">${e(r.time)}</span>` : ""}
       <span class="dash-act-text">${r.html}</span>
     </div>`
  ).join("") + "</div>" +
  `<a class="dash-act-viewall" onclick="showPage('run')">View full logs →</a>`;
}

function loadDashTargets() {
  const wrap    = document.getElementById("dashTargets");
  const countEl = document.getElementById("dashTargetCount");
  if (!wrap) return;
  fetch("/accounts").then(r => r.json()).then(accounts => {
    if (!Array.isArray(accounts) || !accounts.length) {
      wrap.innerHTML = '<span class="ctx-empty" style="padding:4px 0">No accounts added yet.</span>';
      if (countEl) countEl.textContent = "0 monitored";
      return;
    }
    if (countEl) countEl.textContent = accounts.length + " monitored";
    const MAX_SHOW = 8;
    const shown = accounts.slice(0, MAX_SHOW);
    const rest  = accounts.length - MAX_SHOW;
    let html = shown.map(handle => {
      const h = handle.replace(/^@/, "");
      const initial = h[0].toUpperCase();
      const col = chipColor(h);
      return `<div class="target-chip">
        <div class="target-chip-av" style="background:${col}">${initial}</div>
        <span>@${e(h)}</span>
      </div>`;
    }).join("");
    if (rest > 0) {
      html += `<div class="target-chip-more">+${rest} more</div>`;
    }
    html += `<div style="width:100%;margin-top:10px;padding-top:10px;border-top:1px solid var(--border)">
      <span class="dash-viewall-link" onclick="showPage('targeting')">View all →</span>
    </div>`;
    wrap.innerHTML = html;
  }).catch(() => {
    wrap.innerHTML = '<span class="ctx-empty" style="padding:4px 0">Failed to load.</span>';
  });
}

function renderDashPartners(partners) {
  const wrap    = document.getElementById("dashPartnersList");
  const countEl = document.getElementById("dashPartnerCount");
  if (!wrap) return;
  if (!partners || !partners.length) {
    wrap.innerHTML = '<div class="ctx-empty" style="padding:8px 0 2px">No partners yet.</div>';
    if (countEl) countEl.textContent = "0";
    return;
  }
  if (countEl) countEl.textContent = partners.length + " active";
  const rows = partners.slice(0, 6).map(p => {
    const name     = p.name || p.handle || "Partner";
    const handle   = (p.handle || "").replace(/^@/, "");
    const initial  = name[0].toUpperCase();
    const col      = chipColor(handle || name);
    const category = p.category || "";
    const chain    = p.chain || "";
    // Logo: use logo_url if provided, else unavatar.io Twitter, else initial
    const imgSrc = p.logo_url
      ? p.logo_url
      : `https://unavatar.io/twitter/${encodeURIComponent(handle)}`;
    const avatar = `<div class="dash-partner-av" style="background:${col}">
      <img src="${imgSrc}" alt="${e(initial)}"
           style="width:30px;height:30px;border-radius:50%;display:block;object-fit:cover"
           onerror="this.style.display='none';this.parentNode.style.display='flex';this.parentNode.innerHTML='${initial}'">
    </div>`;
    // Sub line: handle · chain · category
    const sub = [`@${e(handle)}`, chain ? e(chain) : "", category ? e(category) : ""].filter(Boolean).join(" · ");
    return `<div class="dash-partner-row">
      ${avatar}
      <div class="dash-partner-info">
        <div class="dash-partner-name">${e(name)}</div>
        <div class="dash-partner-sub">${sub}</div>
      </div>
      <div class="dash-partner-right">
        <span class="dash-partner-badge">High</span>
        <span class="dash-partner-dot"></span>
      </div>
    </div>`;
  }).join("");
  wrap.innerHTML = rows +
    `<div class="dash-viewall-link" onclick="showPage('partners')">View all partners →</div>`;
}

function renderActivityLog(all) {
  const actions = all
    .filter(d => d.action === "posted" || d.action === "skipped")
    .sort(byNewest)
    .slice(0, 8);

  const container = document.getElementById("ctxActivity");
  if (!container) return;   // panel removed — nothing to update
  if (!actions.length) {
    container.innerHTML = '<div class="ctx-empty">No activity yet.</div>';
    return;
  }
  container.innerHTML = actions.map(d => {
    let author = d.author && d.author !== "unknown" ? "@" + d.author : "unknown";
    const snippet = (d.tweet_text || "").slice(0, 60) + (d.tweet_text && d.tweet_text.length > 60 ? "…" : "");
    const result  = d.action === "posted" ? "posted" : "skipped";
    return `<div class="activity-item">
      <div class="act-meta">
        <span class="act-handle">${e(author)}</span>
        <span class="act-result ${result}">${result}</span>
      </div>
      ${snippet ? `<div class="act-text">${e(snippet)}</div>` : ""}
    </div>`;
  }).join("");
}

// Decode the actual tweet posted time from its Twitter snowflake ID
function tweetPostedDate(tweet_id) {
  if (!tweet_id) return null;
  try {
    // Snowflake: timestamp_ms = (id >> 22) + 1288834974657
    const ms = Number(BigInt(String(tweet_id)) >> 22n) + 1288834974657;
    return new Date(ms);
  } catch(e) { return null; }
}

function relTime(dt) {
  // Accepts a Date object or a "YYYY-MM-DD HH:MM:SS" string
  if (!dt) return { rel: "", abs: "" };
  if (typeof dt === "string") dt = new Date(dt.replace(" ", "T"));
  if (isNaN(dt)) return { rel: "", abs: "" };
  const diffMs  = Date.now() - dt.getTime();
  const diffMin = Math.round(diffMs / 60000);
  const abs = dt.toLocaleTimeString([], { hour: "2-digit", minute: "2-digit" }) +
              " · " + dt.toLocaleDateString([], { day: "numeric", month: "short" });
  if (diffMin < 1)  return { rel: "Just now", abs };
  if (diffMin < 60) return { rel: `${diffMin} ${diffMin === 1 ? "min" : "mins"} ago`, abs };
  const h = Math.floor(diffMin / 60);
  const m = diffMin % 60;
  if (h < 24) return { rel: m > 0 ? `${h}h ${m}m ago` : `${h}h ago`, abs };
  const days = Math.floor(h / 24);
  const remH = h % 24;
  return { rel: remH > 0 ? `${days}d ${remH}h ago` : `${days}d ago`, abs };
}

function renderDraft(d) {
  const done    = d.action === "posted" || d.action === "skipped";

  // Resolve author first — used in both the header and the quote block
  let author = d.author && d.author !== "unknown" ? d.author : "";
  if (!author && d.tweet_url) {
    const parts = d.tweet_url.replace("https://x.com/","").replace("https://twitter.com/","").split("/");
    if (parts.length >= 1) author = parts[0];
  }
  const displayAuth = author ? "@" + author : null;
  const tweetHref   = d.tweet_id
    ? (author ? `https://x.com/${e(author)}/status/${e(d.tweet_id)}` : `https://x.com/i/status/${e(d.tweet_id)}`)
    : "";
  const viewLink    = tweetHref ? `<a href="${tweetHref}" target="_blank" class="view-link">↗ View</a>` : "";

  // Tags + prominent author for card header
  const typetag  = `<span class="tag ${d.type || "reply"}">${(d.type || "reply") === "qt" ? "QUOTE TWEET" : "REPLY"}</span>`;
  const ptag     = d.is_partner ? `<span class="tag partner">♦ ${e(d.partner_name || "PARTNER")}</span>` : "";
  const tgtag    = !d.is_partner && d.is_target_account ? `<span class="tag target">★ WATCHLIST</span>` : "";
  const statag   = d.action === "posted"  ? `<span class="tag posted">POSTED</span>`  :
                   d.action === "skipped" ? `<span class="tag skipped">SKIPPED</span>` : "";
  const authorEl = displayAuth ? `<span class="dmeta-author">${e(displayAuth)}</span>` : "";

  const orig = d.tweet_text
    ? `<div class="orig">
        <div class="orig-who">
          <span>❤ ${d.likes || 0} &nbsp;🔁 ${d.retweets || 0}</span>
          ${viewLink}
        </div>
        <div class="orig-txt">${e(d.tweet_text)}</div>
      </div>`
    : "";

  const db = d.draft_bullish   || d.draft_serious || "";
  const ds = d.draft_sarcastic || "";
  const da = d.draft_alpha     || "";
  const tid = ea(d.tweet_id);

  // Version block with confidence + tags + inline post button
  function vblock(version, optNum, confLabel, confCls, tags, cls, text) {
    if (!text) return "";
    const vid = `v-${tid}-${version}`;
    const postBtn = !done
      ? `<div class="vb-post-row">
           <button class="vb-post-primary" onclick="postDraft('${tid}','${version}',this)">Post Reply</button>
           <button class="vb-edit-post" onclick="editVersion('${tid}','${version}')">✎ Edit</button>
           <button class="vb-btn" onclick="copyVersion('${tid}','${version}',this)">⧉</button>
         </div>`
      : `<div class="vb-post-row"><button class="vb-btn" onclick="copyVersion('${tid}','${version}',this)">⧉ Copy</button></div>`;
    const tagsHtml = tags.map(t => `<span class="vtag">${t}</span>`).join("");
    return `<div class="vb ${cls}" id="vb-${tid}-${version}">
      <div class="vb-hdr">
        <div class="vlabel">OPTION ${optNum}</div>
        <span class="vb-confidence ${confCls}">${confLabel}</span>
        <div style="flex:1"></div>
        <button class="vb-btn" onclick="editVersion('${tid}','${version}')" id="edit-btn-${tid}-${version}" style="display:none"></button>
      </div>
      <div class="vtext" id="${vid}">${e(text)}</div>
      <div class="vb-footer">
        <div class="vb-tags">${tagsHtml}</div>
        ${postBtn}
      </div>
    </div>`;
  }

  // Option 3: MCLB Angle for target accounts, Operator Alpha for everyone else
  const isTarget = d.is_target_account && !d.is_partner;
  const opt3Label = isTarget ? "MCLB Angle"        : "Alternative Angle";
  const opt3Cls   = isTarget ? "mclb"              : "alt";
  const opt3Tags  = isTarget ? ["MCLB DAO","Relevance"] : ["Analytical","Operator Alpha"];

  let body = "";
  if (db || ds || da) {
    body = `<div class="versions">
      ${vblock("bullish",   1, "High Confidence",   "high",   ["Bullish","Ecosystem Support"],  "bullish",   db)}
      ${vblock("sarcastic", 2, "Medium Confidence", "medium", ["Tongue-in-Cheek","Contrarian"], "sarcastic", ds)}
      ${vblock("alpha",     3, opt3Label,            opt3Cls,  opt3Tags,                        "alpha",     da)}
    </div>`;
  } else if (d.draft_reply) {
    body = `<div class="versions">${vblock("bullish", 1, "Reply", "high", [], "bullish", d.draft_reply)}</div>`;
  }

  // Graphic suggestion row
  const graphicRow = d.graphic_suggestion
    ? `<div class="graphic-suggestion">
        <span class="graphic-icon">🎨</span>
        <span class="graphic-label">Visual</span>
        <span class="graphic-text">${e(d.graphic_suggestion)}</span>
       </div>`
    : "";

  let acts = "";
  if (!done) {
    acts = `<button class="bp regen" onclick="showRegenPrompt('${tid}')">↺ Regenerate</button>
            <button class="bsk" onclick="skipDraft('${tid}',this)">Skip</button>
            <span class="afb" id="fb${tid}"></span>
            <button class="bhide" onclick="hideDraft('${tid}')" title="Hide permanently — bot won't redraft this tweet">✕ Hide</button>`;
  }

  // Use actual tweet posted time from snowflake ID; fall back to bot scrape time
  const postedDt = tweetPostedDate(d.tweet_id);
  const rt = relTime(postedDt || d.created_at);
  const dateEl = rt.rel
    ? `<span class="dmeta-date"><span class="dmeta-reltime">${rt.rel}</span><span class="dmeta-abstime">${rt.abs}</span></span>`
    : "";

  return `<div class="dcard${done ? " done" : ""}" id="card-${d.tweet_id}">
    <div class="dmeta">${authorEl}${typetag}${ptag}${tgtag}${statag}${dateEl}</div>
    ${orig}
    ${body}
    ${graphicRow}
    ${acts ? `<div class="dactions">${acts}</div>` : ""}
  </div>`;
}

// ── Version editing ───────────────────────────────────────────────────────────
function editVersion(tid, version) {
  const vid     = `v-${tid}-${version}`;
  const el      = document.getElementById(vid);
  const editBtn = document.getElementById(`edit-btn-${tid}-${version}`);
  if (!el) return;

  if (el.tagName === "TEXTAREA") {
    // Save edit
    const val = el.value;
    if (!_edits[tid]) _edits[tid] = {};
    _edits[tid][version] = val;
    // Replace with vtext div
    const div = document.createElement("div");
    div.className = "vtext";
    div.id = vid;
    div.textContent = val;
    el.replaceWith(div);
    if (editBtn) editBtn.textContent = "✎ Edit";
  } else {
    // Enter edit mode
    const currentText = (_edits[tid] && _edits[tid][version]) || el.textContent;
    const ta = document.createElement("textarea");
    ta.className = "vedit";
    ta.id = vid;
    ta.value = currentText;
    ta.rows  = Math.max(3, Math.ceil(currentText.length / 55));
    el.replaceWith(ta);
    ta.focus();
    if (editBtn) editBtn.textContent = "✓ Done";
  }
}

function copyVersion(tid, version, btn) {
  const vid = `v-${tid}-${version}`;
  const el  = document.getElementById(vid);
  if (!el) return;
  const text = el.tagName === "TEXTAREA" ? el.value : el.textContent;
  navigator.clipboard.writeText(text).then(() => {
    btn.textContent = "✓ Copied";
    btn.classList.add("copied");
    setTimeout(() => { btn.textContent = "⧉ Copy"; btn.classList.remove("copied"); }, 1500);
  }).catch(() => {
    btn.textContent = "⧉ Copy"; // fallback silent fail
  });
}

// ── Draft actions ─────────────────────────────────────────────────────────────
async function postDraft(tid, version, btn) {
  lock(tid);
  // Check for local edits
  const text_override = (_edits[tid] && _edits[tid][version]) || "";
  const res = await post("/post-draft", {tweet_id: tid, version, text_override});
  const fb  = document.getElementById("fb" + tid);
  if (res.ok) {
    fb.style.display = "inline"; fb.className = "afb ok"; fb.textContent = "Posted!";
    setTimeout(loadDrafts, 800);
  } else {
    fb.style.display = "inline"; fb.className = "afb err";
    fb.textContent = "Failed: " + (res.error || res.body || "unknown");
    unlock(tid);
  }
}

async function skipDraft(tid) {
  lock(tid);
  await post("/skip-draft", {tweet_id: tid});
  setTimeout(loadDrafts, 400);
}

async function hideDraft(tid) {
  // Instantly remove the card from view, then call backend
  const card = document.getElementById("card-" + tid);
  if (card) {
    card.style.transition = "opacity .2s, transform .2s";
    card.style.opacity = "0";
    card.style.transform = "translateX(12px)";
    setTimeout(() => card.remove(), 220);
  }
  await post("/hide-draft", {tweet_id: tid});
  // Reload drafts silently in background so counts update
  setTimeout(loadDrafts, 300);
}

function showRegenPrompt(tid) {
  const actions = document.getElementById("card-" + tid)?.querySelector(".dactions");
  if (!actions) return;
  actions.innerHTML = `
    <input type="text" class="regen-input" id="ri-${tid}"
           placeholder="Framing, tone, angle, keywords... (optional — leave blank to just regenerate)"
           onkeydown="if(event.key==='Enter')regenDraft('${tid}',document.getElementById('rg-${tid}'))">
    <button class="bp regen" id="rg-${tid}" onclick="regenDraft('${tid}',this)">↺ Go</button>
    <button class="bsk" onclick="loadDrafts()">Cancel</button>
  `;
  document.getElementById("ri-" + tid)?.focus();
}

async function regenDraft(tid, btn) {
  const instructions = document.getElementById("ri-" + tid)?.value?.trim() || "";
  lock(tid);
  if (btn) { btn.disabled = true; btn.textContent = "Regenerating…"; }
  const res = await post("/regenerate-draft", {tweet_id: tid, instructions});
  if (res.ok) {
    delete _edits[tid];
    setTimeout(loadDrafts, 300);
  } else {
    const fb = document.getElementById("fb" + tid);
    if (fb) { fb.style.display = "inline"; fb.className = "afb err"; fb.textContent = "Regen failed: " + (res.error || "unknown"); }
    unlock(tid);
    if (btn) { btn.disabled = false; btn.textContent = "↺ Go"; }
  }
}

// ── Utils ─────────────────────────────────────────────────────────────────────
function lock(tid)   { document.getElementById("card-" + tid)?.querySelectorAll("button").forEach(b => b.disabled = true); }
function unlock(tid) { document.getElementById("card-" + tid)?.querySelectorAll("button").forEach(b => b.disabled = false); }
function post(url, body) { return fetch(url, {method:"POST", headers:{"Content-Type":"application/json"}, body:JSON.stringify(body)}).then(r => r.json()); }
function e(s)  { return String(s || "").replace(/&/g,"&amp;").replace(/</g,"&lt;").replace(/>/g,"&gt;"); }
function ea(s) { return String(s || "").replace(/'/g,"\\'"); }
function showMsg(el, txt, ok) {
  el.style.display = "block"; el.className = "imsg " + (ok ? "ok" : "err"); el.textContent = txt;
  setTimeout(() => el.style.display = "none", 3000);
}

// ── Custom Reply ──────────────────────────────────────────────────────────────
let selectedTone = "analytical";
let customTweetId = null;

function setTone(btn) {
  btn.closest("div").querySelectorAll(".tone-btn[data-tone]").forEach(b => b.classList.remove("active"));
  btn.classList.add("active");
  selectedTone = btn.dataset.tone;
}

function onUrlInput() {
  document.getElementById("customResult").style.display = "none";
}

async function fetchTweet() {
  const url = document.getElementById("customTweetUrl").value.trim();
  if (!url) return;
  const btn    = document.getElementById("fetchBtn");
  const status = document.getElementById("fetchStatus");
  btn.disabled = true; btn.textContent = "Fetching…";
  status.style.display = "block"; status.textContent = "Opening tweet… (~5s)";

  const res = await post("/fetch-tweet", {url});
  btn.disabled = false; btn.textContent = "Fetch";

  if (res.ok && res.text) {
    document.getElementById("customTweetText").value = res.text;
    status.textContent = res.author ? `Fetched from @${res.author}` : "Fetched.";
    status.style.color = "var(--green)";
  } else {
    status.textContent = "Couldn't fetch — paste tweet text manually.";
    status.style.color = "var(--red)";
  }
  setTimeout(() => status.style.display = "none", 3000);
}

async function generateCustom() {
  const text         = document.getElementById("customTweetText").value.trim();
  const instructions = document.getElementById("customInstructions").value.trim();
  const url          = document.getElementById("customTweetUrl").value.trim();
  if (!text) { alert("Add the tweet text first."); return; }

  const btn = document.getElementById("genBtn");
  btn.disabled = true; btn.textContent = "Generating…";

  const res = await post("/generate-custom-reply", {tweet_text: text, instructions, tone: selectedTone, tweet_url: url});
  btn.disabled = false; btn.textContent = "Generate Reply";

  if (!res.ok) { alert("Error: " + res.error); return; }

  customTweetId = res.tweet_id;
  document.getElementById("customReplyText").value = res.reply;
  document.getElementById("customResult").style.display = "block";
  document.getElementById("postCustomBtn").style.display = customTweetId ? "inline-block" : "none";
}

async function postCustom() {
  const text = document.getElementById("customReplyText").value.trim();
  if (!text) return;
  const btn = document.getElementById("postCustomBtn");
  btn.disabled = true; btn.textContent = "Posting…";
  const fb = document.getElementById("customFb");

  const res = await post("/post-custom", {text, tweet_id: customTweetId});
  btn.disabled = false; btn.textContent = "Post as Reply";
  fb.style.display = "inline";

  if (res.ok) {
    fb.className = "afb ok"; fb.textContent = "Posted!";
    setTimeout(() => {
      ["customTweetText","customTweetUrl","customInstructions","customReplyText"].forEach(id => {
        const el = document.getElementById(id);
        if (el) el.value = "";
      });
      document.getElementById("customResult").style.display = "none";
      fb.style.display = "none";
    }, 1500);
  } else {
    fb.className = "afb err"; fb.textContent = "Failed: " + (res.error || res.body || "unknown");
    setTimeout(() => fb.style.display = "none", 4000);
  }
}

// ── Original Post ─────────────────────────────────────────────────────────────
let selectedPillar = "fbomb";
let selectedFormat = "tweet";
let origTweets     = [];

const PILLAR_META = {
  bribes: {
    label:       "Details",
    labelNote:   "— paste your epoch data",
    placeholder: "e.g. Epoch 142. Aerodrome fBOMB/ETH: 500 USDC. Velodrome fBOMB/USDC: 300 USDC. SwapX fBOMB/S: 200 USDC.",
  },
  weekly: {
    label:       "This week's updates",
    labelNote:   "— bullet points are fine",
    placeholder: "e.g. Launched fBOMB pool on Beradrome. Treasury up 12%. Curvance going live on Monad next week. Epoch 142 bribes deployed.",
  },
};

function setPillar(btn) {
  btn.closest("div").querySelectorAll(".tone-btn[data-pillar]").forEach(b => b.classList.remove("active"));
  btn.classList.add("active");
  selectedPillar = btn.dataset.pillar;

  const meta  = PILLAR_META[selectedPillar];
  const label = document.getElementById("origDetailsLabel");
  const input = document.getElementById("origInstructions");
  if (meta && label && input) {
    label.innerHTML = `${meta.label} <span style="color:var(--text3);font-weight:400;text-transform:none;letter-spacing:0;font-size:11px">${meta.labelNote}</span>`;
    input.placeholder = meta.placeholder;
  } else if (label && input) {
    label.innerHTML = `Angle <span style="color:var(--text3);font-weight:400;text-transform:none;letter-spacing:0;font-size:11px">— optional</span>`;
    input.placeholder = "Leave blank to let AI pick the angle…";
  }
}

function setFormat(btn) {
  btn.closest("div").querySelectorAll(".tone-btn[data-format]").forEach(b => b.classList.remove("active"));
  btn.classList.add("active");
  selectedFormat = btn.dataset.format;
}

async function generateOriginal() {
  const instructions = document.getElementById("origInstructions").value.trim();
  const btn = document.getElementById("origGenBtn");
  btn.disabled = true; btn.textContent = "Generating…";

  const res = await post("/generate-original", {pillar: selectedPillar, instructions, format: selectedFormat});
  btn.disabled = false; btn.textContent = "Generate";

  if (!res.ok) { alert("Error: " + res.error); return; }

  origTweets = res.tweets;
  const container = document.getElementById("origTweets");
  container.innerHTML = origTweets.map((t, i) => `
    <div style="margin-bottom:9px">
      ${origTweets.length > 1 ? `<div style="font-size:10px;font-weight:700;color:var(--text3);margin-bottom:3px;text-transform:uppercase;letter-spacing:.6px">Tweet ${i+1}</div>` : ""}
      <textarea id="origTweet${i}" rows="${Math.max(2, Math.ceil(t.length / 60))}" class="result-ta"
        oninput="origTweets[${i}]=this.value;updateCharCount(${i})">${e(t)}</textarea>
      <div style="font-size:11px;color:var(--text3);text-align:right;margin-top:2px" id="chars${i}">${t.length}/280</div>
    </div>`).join("");

  document.getElementById("origPostBtn").textContent = origTweets.length > 1
    ? `Post Thread (${origTweets.length} tweets)` : "Post Tweet";
  document.getElementById("origResult").style.display = "block";
}

function updateCharCount(i) {
  const el  = document.getElementById("chars" + i);
  const len = origTweets[i]?.length || 0;
  if (el) { el.textContent = `${len}/280`; el.style.color = len > 280 ? "var(--red)" : "var(--text3)"; }
}

async function postOriginal() {
  const tweets = origTweets.map((_, i) => (document.getElementById("origTweet" + i)?.value || "").trim()).filter(Boolean);
  if (!tweets.length) return;

  const btn = document.getElementById("origPostBtn");
  const fb  = document.getElementById("origFb");
  btn.disabled = true; btn.textContent = "Posting…";

  const res = await post("/post-thread", {tweets});
  btn.disabled = false;
  btn.textContent = tweets.length > 1 ? `Post Thread (${tweets.length} tweets)` : "Post Tweet";
  fb.style.display = "inline";

  if (res.ok) {
    fb.className = "afb ok";
    fb.textContent = tweets.length > 1 ? `Thread posted (${res.posted} tweets)!` : "Posted!";
    setTimeout(() => {
      document.getElementById("origInstructions").value = "";
      document.getElementById("origResult").style.display = "none";
      fb.style.display = "none";
      origTweets = [];
    }, 2000);
  } else {
    fb.className = "afb err";
    fb.textContent = "Failed: " + ((res.results || []).find(r => !r.ok)?.body || res.error || "unknown");
    setTimeout(() => fb.style.display = "none", 4000);
  }
}

// ── Partners ──────────────────────────────────────────────────────────────────
async function loadPartners() {
  const partners = await fetch("/partners").then(r => r.json());
  _partners = partners;
  const active   = partners.filter(p => p.active !== false);
  const inactive = partners.filter(p => p.active === false);
  document.getElementById("partnerCount").textContent = active.length + " active";

  const grid = document.getElementById("partnersGrid");
  if (!partners.length) {
    grid.innerHTML = '<span class="no-accounts">No partners yet. Click + Add to get started.</span>';
    return;
  }
  grid.innerHTML = [...active, ...inactive].map(p => `
    <div class="partner-card${p.active === false ? " inactive" : ""}" id="pc-${ea(p.handle)}">
      <div style="display:flex;justify-content:space-between;align-items:flex-start;gap:8px">
        <div style="min-width:0">
          <div class="pc-name">${e(p.name)}${p.active === false ? ` <span style="font-size:10px;color:var(--text3);font-weight:400">(inactive)</span>` : ""}</div>
          <div class="pc-meta">${e(p.chain || "")}${p.chain && p.category ? " · " : ""}${e(p.category || "")}</div>
          <div class="pc-handle">@${e(p.handle)}</div>
        </div>
        <div style="display:flex;gap:4px;flex-shrink:0">
          <button class="bsk" style="padding:3px 8px;font-size:11px" onclick="editPartner('${ea(p.handle)}')">Edit</button>
          <button class="bsk" style="padding:3px 8px;font-size:11px;color:var(--red);border-color:var(--red-br)" onclick="removePartner('${ea(p.handle)}')">✕</button>
        </div>
      </div>
      <div class="pc-ctx" style="margin-top:7px">${e(p.context || "")}</div>
    </div>`).join("");
}

function editPartner(handle) {
  const p = _partners.find(x => x.handle === handle);
  if (!p) return;
  const card = document.getElementById("pc-" + handle);
  const chk  = p.active !== false ? "checked" : "";
  card.innerHTML = `
    <div style="font-size:10px;font-weight:700;color:var(--cyan);text-transform:uppercase;letter-spacing:.8px;margin-bottom:9px">Editing @${e(handle)}</div>
    <div style="margin-bottom:6px">
      <div class="input-card-label" style="margin-bottom:3px">Name</div>
      <input id="pce-name-${ea(handle)}" class="itext" style="width:100%" value="${ea(p.name||"")}">
    </div>
    <div style="display:flex;gap:5px;margin-bottom:6px">
      <div style="flex:1">
        <div class="input-card-label" style="margin-bottom:3px">Chain</div>
        <input id="pce-chain-${ea(handle)}" class="itext" style="width:100%" value="${ea(p.chain||"")}">
      </div>
      <div style="flex:1">
        <div class="input-card-label" style="margin-bottom:3px">Category</div>
        <input id="pce-cat-${ea(handle)}" class="itext" style="width:100%" value="${ea(p.category||"")}">
      </div>
    </div>
    <div style="margin-bottom:7px">
      <div class="input-card-label" style="margin-bottom:3px">Context</div>
      <textarea id="pce-ctx-${ea(handle)}" class="dark-ta" rows="4">${e(p.context||"")}</textarea>
    </div>
    <div style="display:flex;gap:7px;align-items:center;flex-wrap:wrap">
      <label style="font-size:12px;color:var(--text2);display:flex;align-items:center;gap:5px;cursor:pointer">
        <input type="checkbox" id="pce-active-${ea(handle)}" ${chk}> Active
      </label>
      <button class="bp s1" onclick="savePartner('${ea(handle)}')">Save</button>
      <button class="bsk" onclick="loadPartners()">Cancel</button>
      <span id="pce-fb-${ea(handle)}" style="font-size:11px;color:var(--red)"></span>
    </div>`;
}

async function savePartner(handle) {
  const name   = document.getElementById("pce-name-"   + handle)?.value.trim();
  const chain  = document.getElementById("pce-chain-"  + handle)?.value.trim();
  const cat    = document.getElementById("pce-cat-"    + handle)?.value.trim();
  const ctx    = document.getElementById("pce-ctx-"    + handle)?.value.trim();
  const active = document.getElementById("pce-active-" + handle)?.checked ?? true;
  const res    = await post("/update-partner", {handle, name, chain, category: cat, context: ctx, active});
  if (res.ok) loadPartners();
  else {
    const fb = document.getElementById("pce-fb-" + handle);
    if (fb) fb.textContent = "Error: " + (res.error || "unknown");
  }
}

async function removePartner(handle) {
  if (!confirm("Remove @" + handle + " from partners?")) return;
  await post("/remove-partner", {handle});
  loadPartners();
}

function showAddPartner() {
  const grid = document.getElementById("partnersGrid");
  const existing = document.getElementById("pc-new");
  if (existing) { existing.remove(); return; }
  const div = document.createElement("div");
  div.id = "pc-new";
  div.className = "partner-card";
  div.style.borderColor = "var(--border2)";
  div.innerHTML = `
    <div style="font-size:10px;font-weight:700;color:var(--cyan);text-transform:uppercase;letter-spacing:.8px;margin-bottom:9px">New Partner</div>
    <div style="margin-bottom:6px">
      <div class="input-card-label" style="margin-bottom:3px">Twitter handle</div>
      <input id="pcn-handle" class="itext" style="width:100%" placeholder="@handle">
    </div>
    <div style="margin-bottom:6px">
      <div class="input-card-label" style="margin-bottom:3px">Name</div>
      <input id="pcn-name" class="itext" style="width:100%" placeholder="Protocol name">
    </div>
    <div style="display:flex;gap:5px;margin-bottom:6px">
      <div style="flex:1">
        <div class="input-card-label" style="margin-bottom:3px">Chain</div>
        <input id="pcn-chain" class="itext" style="width:100%" placeholder="e.g. Sonic">
      </div>
      <div style="flex:1">
        <div class="input-card-label" style="margin-bottom:3px">Category</div>
        <input id="pcn-cat" class="itext" style="width:100%" placeholder="e.g. DEX">
      </div>
    </div>
    <div style="margin-bottom:7px">
      <div class="input-card-label" style="margin-bottom:3px">Partnership context</div>
      <textarea id="pcn-ctx" class="dark-ta" rows="3" placeholder="Position held, what MCLB does with them…"></textarea>
    </div>
    <div style="display:flex;gap:7px;align-items:center;flex-wrap:wrap">
      <button class="bp s1" onclick="addPartner()">Add Partner</button>
      <button class="bsk" onclick="document.getElementById('pc-new').remove()">Cancel</button>
      <span id="pcn-fb" style="font-size:11px;color:var(--red)"></span>
    </div>`;
  grid.insertBefore(div, grid.firstChild);
}

async function addPartner() {
  const handle = (document.getElementById("pcn-handle")?.value || "").trim().replace(/^@/, "");
  const name   = (document.getElementById("pcn-name")?.value   || "").trim() || handle;
  const chain  = (document.getElementById("pcn-chain")?.value  || "").trim();
  const cat    = (document.getElementById("pcn-cat")?.value    || "").trim();
  const ctx    = (document.getElementById("pcn-ctx")?.value    || "").trim();
  const fb     = document.getElementById("pcn-fb");
  if (!handle) { if (fb) fb.textContent = "Handle required"; return; }
  const res = await post("/add-partner", {handle, name, chain, category: cat, context: ctx, active: true});
  if (res.ok) loadPartners();
  else if (fb) fb.textContent = "Error: " + (res.error || "unknown");
}

// ── Init ──────────────────────────────────────────────────────────────────────
loadDrafts();
</script>
</body>
</html>"""


if __name__ == "__main__":
    port = int(os.getenv("PORT", 8080))
    import threading, webbrowser, time as _time
    def _open():
        _time.sleep(1.5)
        webbrowser.open(f"http://localhost:{port}")
    threading.Thread(target=_open, daemon=True).start()
    print(f"\n  MCLB Operator — http://localhost:{port}\n")
    app.run(debug=False, host="0.0.0.0", port=port)
