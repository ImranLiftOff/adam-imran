# Lagos Traffic Intel — Build Spec

## What This Does

A daily morning intelligence system that monitors Lagos-specific traffic disruptions — presidential visits, road closures, bridge maintenance, major events — and sends a WhatsApp summary at 7am every day.

Google Maps shows you traffic right now. This tells you what is coming before you leave the house.

---

## The Problem It Solves

Standard navigation apps do not know:
- A presidential convoy is expected on Eko Bridge between 8-10am
- Third Mainland Bridge has scheduled maintenance this weekend
- Lagos Marathon is Sunday and will block Island routes from 6am
- A road closure is in effect due to flooding or construction on a specific route

This system collects that intelligence overnight and delivers it before you leave.

---

## Data Sources

### Source 1: Twitter/X Keyword Monitoring
Search for recent tweets containing:
- "road closure Lagos"
- "bridge maintenance Lagos"
- "presidential visit Lagos"
- "Third Mainland Bridge"
- "Eko Bridge closed"
- "Lagos marathon"
- "road blocked Lagos"
- "Lagos traffic alert"

Use the Twitter/X search API or a scraping approach via Playwright to pull the last 24 hours of tweets matching these keywords.

### Source 2: Pulse Nigeria
Scrape the news feed at pulse.ng filtering for articles containing "Lagos" and "traffic" or "road closure" or "bridge" published in the last 24 hours.

URL to scrape: https://www.pulse.ng/news/local

### Source 3: Vanguard Nigeria
Scrape vanguardngr.com for Lagos traffic and infrastructure news published in the last 24 hours.

URL to scrape: https://www.vanguardngr.com/category/metro-news/

### Source 4: Lagos State Government Twitter
Monitor the official Lagos State Government Twitter account @followlasg for announcements about road closures, bridge maintenance, and traffic advisories.

---

## How It Works — Step by Step

### Step 1: Data Collection (runs at 6am daily)
A scheduled script runs at 6am every morning. It hits all four data sources and collects raw text — tweets, article headlines, and article snippets — from the last 24 hours.

### Step 2: AI Analysis
Pass all collected raw text to Claude via the Anthropic API with this prompt:

```
You are a Lagos traffic intelligence analyst. Review the following news and social media content from the last 24 hours. 

Identify ONLY significant disruptions that would affect road travel in Lagos today or in the next 48 hours. These include:
- Presidential or VIP convoys and visits
- Road closures (permanent or temporary)
- Bridge maintenance or closures (Third Mainland, Eko, Carter, Falomo)
- Major events that will cause road blockages (marathons, concerts, state functions)
- Flooding or accident-related closures

For each disruption found, extract:
1. Type of disruption
2. Affected route or area
3. Expected time or date
4. Severity (HIGH / MEDIUM / LOW)

If nothing significant is found, say: "No major disruptions detected."

Return your response in plain text, not JSON. Keep it short and direct.

Content to analyze:
[INSERT SCRAPED CONTENT HERE]
```

### Step 3: Format the WhatsApp Message
Take the AI output and format it into a clean WhatsApp message:

```
Lagos Traffic Intel — [Day, Date]

[AI output here]

Stay safe out there.
```

Example output:

```
Lagos Traffic Intel — Monday, June 30

HIGH: Presidential convoy expected on Ozumba Mbadiwe Avenue 9-11am. Avoid Victoria Island routes during this window.

MEDIUM: Third Mainland Bridge lane closure (outbound) due to maintenance. Expect delays from 7am.

No other disruptions detected.

Stay safe out there.
```

### Step 4: Send via WhatsApp
Use the WhatsApp Cloud API (Meta) or Twilio WhatsApp API to send the formatted message to your number at 7am.

---

## Tech Stack

| Component | Tool |
|---|---|
| Scheduling | Python with schedule library or a cron job |
| Web scraping | Playwright or BeautifulSoup + requests |
| Twitter data | Twitter/X API v2 (basic tier) or Playwright scraping |
| AI analysis | Anthropic API (Claude) |
| WhatsApp delivery | WhatsApp Cloud API (free tier) or Twilio |
| Runtime | Run locally or deploy to a free tier on Railway or Render |

---

## File Structure

```
lagos-traffic-intel/
├── main.py              # Entry point, runs the full pipeline
├── scraper.py           # Handles all data collection from sources
├── analyzer.py          # Sends data to Claude API, returns analysis
├── whatsapp.py          # Formats and sends WhatsApp message
├── scheduler.py         # Sets up the 7am daily trigger
├── config.py            # API keys and phone number (use .env)
├── .env                 # Environment variables (never commit this)
└── requirements.txt     # Python dependencies
```

---

## Environment Variables

```
ANTHROPIC_API_KEY=your_key_here
WHATSAPP_TOKEN=your_meta_token_here
WHATSAPP_PHONE_ID=your_phone_number_id
RECIPIENT_PHONE=your_whatsapp_number_with_country_code
TWITTER_BEARER_TOKEN=your_twitter_bearer_token
```

---

## Dependencies

```
anthropic
playwright
beautifulsoup4
requests
schedule
python-dotenv
tweepy
```

---

## Cost Estimate

| Service | Cost |
|---|---|
| Anthropic API | Less than $0.01 per daily run |
| WhatsApp Cloud API | Free for first 1,000 messages per month |
| Twitter/X API | Free basic tier allows 500K tweets read per month |
| Hosting | Free tier on Railway or Render |

Monthly cost: effectively zero.

---

## Build Order for Claude Code

Tell Claude Code to build in this order:

1. Build scraper.py — start with Pulse Nigeria only, confirm it returns clean article text
2. Build analyzer.py — pass sample scraped text to Claude API, confirm the output is formatted correctly
3. Build whatsapp.py — send a test message to your number
4. Connect everything in main.py — scrape, analyze, send
5. Add remaining sources one by one — Vanguard, then Twitter
6. Add scheduler.py last — only after the full pipeline is confirmed working

---

## The LinkedIn Angle

When you demo this, the hook is not "I built a traffic app."

The hook is: "Google Maps tells you about traffic. It does not tell you the president is coming to Lagos tomorrow. So I built something that does."

Short Loom or screen recording. Show the morning WhatsApp message arriving. Show the sources it pulled from. Done.
