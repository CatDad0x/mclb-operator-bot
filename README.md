# MCLB Operator Bot

An AI-powered Twitter engagement bot built for the MCLB DAO operator role. It monitors partner protocol activity across 20+ DeFi ecosystems, drafts context-aware reply and quote-tweet content using Claude, and surfaces the best opportunities through a custom web dashboard for one-click review and posting.

---

## What This Does

Most DeFi DAOs miss engagement opportunities because manually tracking 20+ partner accounts across Aerodrome, Velodrome, Beets, SwapX, Pharaoh, Thena, and others is impossible to do consistently. This bot solves that.

Every run:
1. Scrapes partner Twitter accounts directly + pulls from the Following timeline
2. Filters tweets by relevance (age, retweet exclusions, partner bypass logic)
3. Sends each tweet to Claude with full partner context (chain, category, MCLB's relationship, key figures) to generate 3 reply or quote-tweet variants
4. Saves drafts to a review dashboard
5. Operator reviews, regenerates, skips, or hides -- then posts with one click

This is not a spam bot. Every post is reviewed by a human before it goes out. The AI handles research and drafting; the operator handles judgment.

---

## Key Features

**Partner-aware AI drafting**
Each partner has a custom context profile -- chain, protocol category, MCLB's position (ve(3,3) veNFT holder, LP, seed investor, etc.), and key team contacts. Claude uses this to write replies that sound like they come from someone who actually knows the protocol, not a generic comment.

**Multi-source tweet discovery**
- Direct profile scraping of all active partner accounts
- Following timeline scraping (For You + Following feeds)
- Partner tweets bypass keyword filters since their content is always relevant

**Smart deduplication**
Tracks seen tweet IDs across runs so the same tweet is never drafted twice. Orphan protection ensures a tweet is only blacklisted if a draft was actually saved.

**Review dashboard**
A local Flask web app with:
- Live draft cards showing tweet context, MCLB relationship, and all 3 Claude variants
- Regenerate button to get a fresh take
- Skip (soft dismiss) and Hide (permanent blacklist) per tweet
- Posting via Twitter API from the dashboard
- Session log showing which partners produced content and why others were skipped

**Rate limit resilience**
Partner accounts are shuffled each run and visited with delays to reduce Twitter rate-limit hits. Nav failures return empty results rather than reading stale page content.

---

## Tech Stack

| Layer | Tool |
|---|---|
| Twitter scraping | Playwright (headless Chromium, cookie auth) |
| AI drafting | Anthropic Claude API |
| Dashboard | Flask + vanilla JS |
| Data storage | JSON flat files |
| Automation | macOS `.command` launchers |

---

## Partner Ecosystem

Active partners tracked across 8+ chains:

| Protocol | Chain | Category | MCLB Position |
|---|---|---|---|
| Aerodrome | Base | ve(3,3) DEX | 2nd largest DAO veAERO holder globally |
| Velodrome | Optimism | ve(3,3) DEX | Large veNFT + continuous LPs |
| Beets | Sonic | DEX / LST | Biggest holder, revenue-positive protocol |
| SwapX | Sonic | DEX | Key LP partner + veNFT position |
| Pharaoh | Avalanche | ve(3,3) DEX | Large vePHAR + active LPs |
| Thena | BNB Chain | ve(3,3) DEX | veNFT governance + fBOMB pools |
| Blackhole | Avalanche | ve(3,3) DEX | Bribe + LP partner |
| BMX | Base | Perp / DEX | Governance position |
| Beradrome | Berachain | ve(3,3) DEX | veNFT + fBOMB LPs |
| Ramses | Hyperliquid | ve(3,3) DEX | veNFT + fBOMB LPs |
| Curvance | Monad | Lending | Seed investor |
| PaintSwap | Sonic | NFT Marketplace | Biggest BRUSH holder |
| Estfor Kingdom | Sonic | Gaming | Biggest BRUSH holder |
| Fate Adventure | Sonic | Gaming | Biggest holder |
| WAGMI | Sonic | DEX / Liquidity | Active position |
| HeyAnon | Sonic | AI / Dashboard | Active position |
| Massa | Massa | L1 | Seed investor |
| Mina | Mina | L1 | Investor |
| Mintlayer | Bitcoin | Bitcoin Layer | Investor |
| NAV Finance | Multi | Hedge Fund | LP |
| Etherex | Linea | ve(3,3) DEX | Seed LP |

---

## Setup

### Prerequisites

- Python 3.10+
- An Anthropic API key
- Twitter account cookies (logged into the MCLB account in Chrome)

### Install

```bash
cd mclb-bot
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt
playwright install chromium
```

### Configure

Copy `.env.example` to `.env` and fill in your Anthropic API key:

```bash
cp .env.example .env
```

Export your Twitter cookies from Chrome (using a browser extension like EditThisCookie or Cookie-Editor) and save to `browser_cookies.json`.

### Run

Start the review dashboard:
```bash
python3 dashboard.py
```

Open `http://localhost:5001` in your browser, then run the bot:
```bash
python3 bot.py
```

Or use the included macOS launchers: `Run Bot.command` and `Start Dashboard.command`.

---

## Project Structure

```
mclb-bot/
├── bot.py                  # Main bot: scraping, AI drafting, deduplication
├── dashboard.py            # Flask dashboard: review, regenerate, post
├── partner_accounts.json   # Partner profiles with context for Claude
├── target_accounts.json    # High-value non-partner accounts to monitor
├── targets.txt             # Additional accounts list
├── requirements.txt
├── .env.example
├── Run Bot.command
└── Start Dashboard.command
```

---

## Why This Exists

Running a DeFi DAO requires showing up consistently across protocols you hold positions in. veNFT governance, LP bribe markets, and protocol launches all move fast on Twitter. Missing a Velodrome epoch announcement or an Aerodrome gauge vote costs real yield.

This bot is how one operator keeps up across 20+ positions without spending 4 hours a day on Twitter -- while still sounding like a person who actually understands the protocols.

---

## Notes

- All posts are manually reviewed before publishing. The AI drafts; the human decides.
- Partner context profiles are maintained in `partner_accounts.json` and updated as relationships evolve.
- The bot is designed for a single operator account. Multi-account support is not in scope.
