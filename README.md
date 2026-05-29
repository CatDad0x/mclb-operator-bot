# DeFi Operator Bot

A Twitter engagement command centre for DeFi DAOs and protocol operators. Monitors partner accounts across any number of chains and protocols, uses Claude AI to draft context-aware replies and quote-tweets, and surfaces everything through a local review dashboard for one-click posting.

This repo is the MCLB DAO instance, configured for MCLB's partner ecosystem across 8+ chains.

---

## Screenshots

### Command Centre
![Command Centre](screenshots/command-centre.png)

### Tweet Review
![Tweet Review](screenshots/tweet-review.png)

### Partner Registry
![Partners](screenshots/partners.png)

---

## What It Does

In DeFi, presence is part of the job. DAOs with active positions across many protocols need to show up consistently -- congratulating launches, engaging with governance announcements, amplifying partner milestones, and staying visible in the right conversations.

Doing that manually across 20+ accounts every day is not realistic. This tool keeps engagement consistent and on-brand without it becoming a full-time task.

Every run:
1. Scrapes all partner Twitter accounts directly + pulls from the Following and For You timelines
2. Filters by relevance: age, retweet exclusions, partner bypass logic
3. Sends each tweet to Claude with full partner context to generate 3 reply or quote-tweet variants
4. Saves drafts to the review dashboard
5. Operator reviews, picks a variant (or edits it), and posts with one click

The AI handles research and drafting. The operator handles judgment.

---

## Key Features

**Command Centre**
Live overview of bot status, review queue size, active partner count, and watchlist. Bot activity log shows exactly what happened on the last run.

**Tweet Review Queue**
Each captured tweet gets 3 AI-drafted response options, each with a tone label and confidence rating. Options can be posted directly, edited inline, regenerated for a fresh take, skipped, or permanently hidden.

**Partner Registry**
Full directory of partner protocols with chain, category, Twitter handle, and a custom context profile used by Claude when drafting responses. Partners can be added, edited, or deactivated without touching code.

**Watchlist**
Non-partner accounts worth monitoring (ecosystem players, key figures, competing protocols). Tweets from watchlist accounts go into a separate review tab.

**Partner-aware AI drafting**
Each partner has a detailed context profile: chain, protocol category, MCLB's position (ve(3,3) veNFT holder, LP, seed investor, etc.), and key team contacts. Claude uses this to write responses that sound like they come from someone who actually knows the protocol.

**Smart deduplication**
Tracks seen tweet IDs across runs so the same tweet is never drafted twice. Orphan protection ensures a tweet is only blacklisted if a draft was actually saved.

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

## MCLB Partner Ecosystem

This instance tracks 22 active partners across 8+ chains:

| Protocol | Chain | Category | Position |
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
| Yeet | TBA | Strategy | Largest investor |

---

## Setup

### Prerequisites

- Python 3.10+
- An Anthropic API key
- Twitter account cookies (logged into the operator account in Chrome)

### Install

```bash
cd mclb-bot
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt
playwright install chromium
```

### Configure

Copy `.env.example` to `.env` and add your Anthropic API key:

```bash
cp .env.example .env
```

Export your Twitter cookies from Chrome (using a browser extension like Cookie-Editor) and save to `browser_cookies.json`.

### Run

Start the review dashboard:
```bash
python3 dashboard.py
```

Open `http://localhost:5001` in your browser, then run the bot in a separate terminal:
```bash
python3 bot.py
```

Or use the included macOS launchers: `Run Bot.command` and `Start Dashboard.command`.

---

## Adapting for a Different DAO

To run this for a different protocol or operator account:

1. Replace `partner_accounts.json` with your own partner list
2. Update `target_accounts.json` with your watchlist
3. Point `browser_cookies.json` at your Twitter account
4. The bot and dashboard require no code changes

---

## Project Structure

```
mclb-bot/
├── bot.py                  # Core bot: scraping, AI drafting, deduplication
├── dashboard.py            # Flask dashboard: review, compose, post
├── partner_accounts.json   # Partner profiles with context for Claude
├── target_accounts.json    # Watchlist accounts to monitor
├── targets.txt             # Additional accounts list
├── requirements.txt
├── .env.example
├── Run Bot.command
└── Start Dashboard.command
```

---

## Notes

- All posts are manually reviewed before publishing. The AI drafts; the human decides.
- Partner context profiles are maintained in `partner_accounts.json` and updated as relationships evolve.
- Sensitive files (`browser_cookies.json`, `.env`, `drafts.json`, `seen_posts.json`) are gitignored and never committed.
