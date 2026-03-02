# PIB v5 — CoS Enablement Spec
## Full-Stack Project Execution Capability

**Purpose:** Everything needed for PIB on a Mac Mini to autonomously execute real-world household projects — research, outreach, hiring, booking, procurement, coordination — with human gates only where judgment, signature, or physical presence is required.

**Design principle:** Only production-grade, well-documented, actively-maintained technology. No beta APIs, no workarounds, no "it mostly works." Every component has a fallback. Every financial or reputational action has a gate.

---

## 1. CAPABILITY INVENTORY

### 1.1 What Exists (no work needed)

| Capability | Implementation | Status |
|---|---|---|
| Send/receive email | `gog gmail send/read` | ✅ Production |
| Send/receive iMessage | BlueBubbles + OpenClaw channel | ✅ Production |
| Send/receive SMS | Twilio SMS + OpenClaw channel | ✅ Production |
| Send/receive Signal | signal-cli + OpenClaw channel | ✅ Production |
| Read/write Google Calendar | `gog calendar` | ✅ Production |
| Read/write Google Sheets | `gog sheets` | ✅ Production |
| Read/write Google Docs | `gog docs` | ✅ Production |
| Read/write Google Contacts | `gog contacts` | ✅ Production |
| Task state machine | c40v `ops_tasks` | ✅ Production |
| Memory / knowledge store | c40v `mem_long_term` + `cap_captures` | ✅ Production |
| Custody-aware scheduling | c40v `custody.py` | ✅ Production |
| Cron scheduling | OpenClaw cron engine | ✅ Production |
| Image/document analysis | Claude Vision via message attachments | ✅ Production |
| Structured data comparison | Google Sheets + c40v financial domain | ✅ Production |
| Approval gates | c40v `governance.yaml` | ✅ Production |
| Audit trail | c40v `ops_ledger` | ✅ Production |

### 1.2 What Must Be Added (this spec)

| # | Capability | Technology | Effort | Risk |
|---|---|---|---|---|
| **C1** | Web search | Brave Search API | 1 day | Low |
| **C2** | Web browsing + form filling | Playwright (Python) | 3 days | Medium |
| **C3** | Outbound voice calls + 2-way AI voice | Twilio Voice + Deepgram STT + ElevenLabs TTS | 5 days | Medium |
| **C4** | Virtual payment cards | Privacy.com API | 2 days | Low |
| **C5** | Project management (multi-phase, gated) | c40v domain extension | 2 days | Low |
| **C6** | Contact/vendor CRM | c40v domain extension | 1 day | Low |
| **C7** | Document generation (PDF) | Playwright print-to-PDF | 0.5 day | Low |
| **C8** | Physical mail (letters, certified) | Lob.com API | 1 day | Low |

**Total estimated build: ~15 days of agent work (after core c40v is deployed)**

---

## 2. CREDENTIALS & ACCOUNTS

### 2.1 Accounts to Create

| Account | Purpose | Cost | Identity |
|---|---|---|---|
| **Brave Search API** | Web search | Free: 2,000 queries/mo. $3/1000 after. | James's email |
| **Privacy.com** | Virtual payment cards | Free plan: 12 cards/mo. Premium $10/mo: unlimited. | James's identity + bank link |
| **Twilio** | Voice calls + SMS | Pay-per-use: ~$0.02/min outbound, ~$1/mo per number | James's email |
| **Deepgram** | Speech-to-text for calls | Free: $200 credit. Then ~$0.0043/min | James's email |
| **ElevenLabs** | Text-to-speech for calls | Free: 10K chars/mo. $5/mo starter. | James's email |
| **Lob.com** | Physical mail API | Pay-per-piece: ~$1.00/letter | James's email |

**Already have:** GitHub, Google Workspace (jrstice@gmail.com), Anthropic, Apple ID, OpenClaw.

### 2.2 Credential Storage

All API keys stored via `openclaw config set`:

```bash
openclaw config set BRAVE_SEARCH_API_KEY "BSA..."
openclaw config set PRIVACY_API_KEY "pk_..."
openclaw config set TWILIO_ACCOUNT_SID "AC..."
openclaw config set TWILIO_AUTH_TOKEN "..."
openclaw config set TWILIO_PHONE_NUMBER "+1..."
openclaw config set DEEPGRAM_API_KEY "dg_..."
openclaw config set ELEVENLABS_API_KEY "el_..."
openclaw config set LOB_API_KEY "live_..."
```

Accessible from Python via `os.environ` (OpenClaw injects into child process environment).

---

## 3. CAPABILITY SPECS

### C1: Web Search

**Technology:** Brave Search API
**Why Brave:** Free tier is generous (2,000/mo). REST API with JSON response. No Google account dependency. Web + news + local search. Well-documented. Stable for 2+ years.

**Fallback:** If Brave is down, fall back to DuckDuckGo HTML scraping (less structured but works).

```python
# pib/tools/web_search.py

import httpx
from pib.db import get_config

BRAVE_ENDPOINT = "https://api.search.brave.com/res/v1/web/search"

async def web_search(
    query: str,
    count: int = 10,
    search_type: str = "web",  # web | news | local
    freshness: str | None = None,  # past_day | past_week | past_month
) -> dict:
    """
    Search the web. Returns structured results.
    
    Used by: LLM tool `web_search`, project research phases,
             vendor discovery, price comparison.
    
    Returns:
      {
        "query": "piano teachers buckhead atlanta",
        "results": [
          {
            "title": "Sarah Chen Piano Studio — Buckhead",
            "url": "https://...",
            "description": "Private piano lessons for children ages 4-18...",
            "age": "2024-11-15",  # page date if available
          }, ...
        ],
        "local_results": [  # if search_type includes local
          {
            "name": "Buckhead Music Academy",
            "address": "3456 Peachtree Rd NE, Atlanta, GA 30326",
            "phone": "+14045551234",
            "rating": 4.8,
            "review_count": 47,
            "hours": "Mon-Sat 9am-7pm",
          }, ...
        ],
        "result_count": 10,
        "cost_cents": 0.3,  # tracked for budget awareness
      }
    """
    api_key = os.environ.get("BRAVE_SEARCH_API_KEY")
    if not api_key:
        raise ConfigError("BRAVE_SEARCH_API_KEY not set")
    
    params = {"q": query, "count": count}
    if freshness:
        params["freshness"] = freshness
    
    # For local search, use Brave's local endpoint
    endpoint = BRAVE_ENDPOINT
    if search_type == "local":
        endpoint = "https://api.search.brave.com/res/v1/local/search"
    
    async with httpx.AsyncClient(timeout=10) as client:
        resp = await client.get(
            endpoint,
            headers={"X-Subscription-Token": api_key, "Accept": "application/json"},
            params=params,
        )
        resp.raise_for_status()
        data = resp.json()
    
    results = []
    for item in data.get("web", {}).get("results", []):
        results.append({
            "title": item.get("title", ""),
            "url": item.get("url", ""),
            "description": item.get("description", ""),
            "age": item.get("age"),
        })
    
    local_results = []
    for item in data.get("locations", {}).get("results", []):
        local_results.append({
            "name": item.get("title", ""),
            "address": item.get("address", {}).get("streetAddress", ""),
            "phone": item.get("phone", ""),
            "rating": item.get("rating", {}).get("ratingValue"),
            "review_count": item.get("rating", {}).get("ratingCount"),
        })
    
    return {
        "query": query,
        "results": results,
        "local_results": local_results,
        "result_count": len(results),
    }
```

**CLI:** `python3 -m pib.cli web-search --query "..." --type local --count 10 --json`

**LLM Tool:**
```python
{"name": "web_search",
 "description": "Search the web for information. Use for research, finding businesses, "
                "comparing options, checking prices, reading reviews. Supports web, news, "
                "and local business search.",
 "parameters": {
     "query": "Search query",
     "count": "Number of results (default 10, max 20)",
     "search_type": "web | news | local (local includes address, phone, ratings)",
     "freshness": "Optional: past_day | past_week | past_month",
 }}
```

**Cost control:** Track queries in `pib_config` counter. Alert at 1,500/mo (75% of free tier). Auto-degrade to cached results if limit approached for non-urgent queries.

---

### C2: Web Browsing + Form Filling

**Technology:** Playwright (Python). Microsoft-maintained, 70K+ GitHub stars, works natively on macOS with WebKit (Safari engine), Chromium, and Firefox. Headless by default.

**Why Playwright over Puppeteer:** Python-native (matches c40v). Multi-browser. Better macOS support. Built-in auto-wait (less flaky). Better form-filling API.

**Why NOT the `human-browser` npm package:** It's designed for anti-bot evasion. We don't need that — we're filling out piano teacher contact forms and camp registrations, not scraping. Standard Playwright is more reliable for legitimate use.

**Architecture:** Browser runs as a long-lived Playwright context (not launched per-request). Screenshots taken at every navigation step. All form submissions require gate approval unless pre-authorized.

```python
# pib/tools/browser.py

import asyncio
import json
import os
from datetime import datetime
from pathlib import Path
from playwright.async_api import async_playwright, Browser, Page

SCREENSHOT_DIR = Path("state/browser_screenshots")
SCREENSHOT_DIR.mkdir(parents=True, exist_ok=True)


class BrowserTool:
    """
    Web browsing and form filling for PIB.
    
    SECURITY MODEL:
    - All navigation is logged with timestamps and screenshots
    - Form submissions require gate approval (governance.yaml: browser_form_submit: confirm)
    - Payment form detection: if page contains credit card fields, ALWAYS gate
    - Login form detection: if page contains password fields, ALWAYS gate
    - Download directory is sandboxed to state/browser_downloads/
    - No access to local filesystem beyond sandbox
    - Cookie jar is per-project (isolated)
    - 30-second timeout on all operations
    
    SCREENSHOT POLICY:
    - Screenshot after every navigate()
    - Screenshot before every form_submit()
    - Screenshot after every form_submit()
    - Screenshots stored in state/browser_screenshots/{project_id}/
    - Retained for 30 days, then pruned
    """
    
    def __init__(self):
        self._playwright = None
        self._browser: Browser | None = None
        self._contexts: dict[str, any] = {}  # project_id → BrowserContext
    
    async def start(self):
        """Launch browser. Called once at PIB startup."""
        self._playwright = await async_playwright().start()
        self._browser = await self._playwright.webkit.launch(
            headless=True,
            args=["--disable-gpu"],
        )
    
    async def stop(self):
        if self._browser:
            await self._browser.close()
        if self._playwright:
            await self._playwright.stop()
    
    async def _get_context(self, project_id: str = "default"):
        """Get or create an isolated browser context per project."""
        if project_id not in self._contexts:
            self._contexts[project_id] = await self._browser.new_context(
                viewport={"width": 1280, "height": 900},
                user_agent="Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
                          "AppleWebKit/605.1.15 (KHTML, like Gecko) "
                          "Version/18.0 Safari/605.1.15",
                accept_downloads=True,
            )
        return self._contexts[project_id]
    
    async def navigate(self, url: str, project_id: str = "default") -> dict:
        """
        Navigate to URL. Returns page title, text content, and screenshot path.
        
        The LLM receives the text content (not HTML) for reasoning.
        Screenshot is stored for audit trail and can be sent to vision model
        if the LLM needs to understand page layout.
        """
        ctx = await self._get_context(project_id)
        page = await ctx.new_page()
        
        try:
            await page.goto(url, timeout=30000, wait_until="networkidle")
        except Exception:
            await page.goto(url, timeout=30000, wait_until="domcontentloaded")
        
        # Screenshot
        ts = datetime.utcnow().strftime("%Y%m%d_%H%M%S")
        ss_dir = SCREENSHOT_DIR / project_id
        ss_dir.mkdir(parents=True, exist_ok=True)
        ss_path = ss_dir / f"nav_{ts}.png"
        await page.screenshot(path=str(ss_path), full_page=False)
        
        # Extract readable text
        text = await page.evaluate("""() => {
            // Remove scripts, styles, hidden elements
            document.querySelectorAll('script,style,noscript,[hidden]').forEach(e => e.remove());
            return document.body?.innerText?.substring(0, 15000) || '';
        }""")
        
        title = await page.title()
        current_url = page.url
        
        return {
            "title": title,
            "url": current_url,
            "text": text[:15000],  # Cap at 15K chars for context window
            "screenshot": str(ss_path),
            "page_id": id(page),
        }
    
    async def read_page(self, page_id: int) -> dict:
        """Re-read current page content (after JS has loaded more content)."""
        # Find page by id in open pages
        ...
    
    async def click(self, page_id: int, selector: str = None, text: str = None) -> dict:
        """
        Click an element by CSS selector or visible text.
        Returns updated page content + screenshot.
        """
        ...
    
    async def fill_form(self, page_id: int, fields: dict[str, str]) -> dict:
        """
        Fill form fields. Keys are field names/labels/selectors.
        Values are what to type.
        
        Example:
          fields = {
            "First Name": "James",
            "Last Name": "Stice", 
            "Email": "jrstice@gmail.com",
            "Phone": "4048495800",
            "Child's Age": "6",
            "Message": "I'm looking for piano lessons for my 6-year-old son..."
          }
        
        Returns screenshot of filled form BEFORE submission.
        Submission is a separate call (gate opportunity).
        """
        ctx_page = ...  # find by page_id
        
        for label, value in fields.items():
            # Try multiple strategies to find the field
            filled = False
            
            # Strategy 1: label text match
            try:
                await ctx_page.get_by_label(label).fill(value, timeout=3000)
                filled = True
            except Exception:
                pass
            
            # Strategy 2: placeholder match
            if not filled:
                try:
                    await ctx_page.get_by_placeholder(label).fill(value, timeout=3000)
                    filled = True
                except Exception:
                    pass
            
            # Strategy 3: CSS selector (if label looks like a selector)
            if not filled and (label.startswith("#") or label.startswith(".")):
                try:
                    await ctx_page.fill(label, value, timeout=3000)
                    filled = True
                except Exception:
                    pass
            
            if not filled:
                return {"error": f"Could not find field: {label}",
                        "fields_filled": {k: "✓" for k in list(fields.keys())[:list(fields.keys()).index(label)]}}
        
        # Screenshot filled form
        ts = datetime.utcnow().strftime("%Y%m%d_%H%M%S")
        ss_path = SCREENSHOT_DIR / "default" / f"form_filled_{ts}.png"
        await ctx_page.screenshot(path=str(ss_path))
        
        return {
            "status": "filled",
            "screenshot": str(ss_path),
            "message": "Form filled. Call submit_form() to submit, or review screenshot first.",
        }
    
    async def submit_form(self, page_id: int, submit_selector: str = None) -> dict:
        """
        Submit a form. GATED by governance.yaml.
        
        If submit_selector not provided, clicks the first visible
        submit button or input[type=submit].
        
        SECURITY:
        - Screenshots before AND after submission
        - Full form data logged to ops_ledger
        - If page contains card/payment fields → HARD GATE (always confirm)
        - If page contains password fields → HARD GATE
        """
        ...
    
    async def download_file(self, page_id: int, link_selector: str) -> dict:
        """Download a file to state/browser_downloads/. Returns local path."""
        ...
    
    async def close_page(self, page_id: int):
        """Close a browser tab."""
        ...
    
    async def close_project(self, project_id: str):
        """Close all pages and cookies for a project."""
        if project_id in self._contexts:
            await self._contexts[project_id].close()
            del self._contexts[project_id]
```

**CLI:**
```
python3 -m pib.cli browse --url "https://..." --json
python3 -m pib.cli browse --page-id 123 --fill '{"Name":"James Stice","Email":"jrstice@gmail.com"}' --json
python3 -m pib.cli browse --page-id 123 --submit --json
python3 -m pib.cli browse --page-id 123 --screenshot --json
```

**LLM Tools:**
```python
BROWSER_TOOLS = [
    {"name": "browse_navigate", "description": "Open a URL and read the page content. Returns text + screenshot.", 
     "parameters": {"url": "URL to visit", "project_id": "Optional: project to scope cookies/state"}},
    
    {"name": "browse_click", "description": "Click a link or button on the current page.",
     "parameters": {"page_id": "Page from browse_navigate", "text": "Visible text to click", "selector": "CSS selector (alternative)"}},
    
    {"name": "browse_fill_form", "description": "Fill a web form. Does NOT submit — call browse_submit separately.",
     "parameters": {"page_id": "Page ID", "fields": "Dict of field labels to values"}},
    
    {"name": "browse_submit", "description": "Submit a filled form. REQUIRES APPROVAL for payment/password pages.",
     "parameters": {"page_id": "Page ID", "submit_selector": "Optional: specific submit button"}},
    
    {"name": "browse_read", "description": "Re-read current page content (useful after clicking or scrolling).",
     "parameters": {"page_id": "Page ID"}},
]
```

**Governance gates:**
```yaml
# governance.yaml additions
browser_navigate: true           # No approval needed to visit a URL
browser_fill_form: true          # No approval needed to fill a form
browser_submit_form: confirm     # Requires approval before submitting
browser_submit_payment: confirm  # ALWAYS requires approval (can't be overridden)
browser_submit_login: confirm    # ALWAYS requires approval
browser_download: true           # No approval for downloads
```

**Install on Mac Mini:**
```bash
pip install playwright
playwright install webkit  # Just WebKit — smallest footprint, native macOS engine
```

---

### C3: Outbound Voice Calls + 2-Way AI Voice

**Technology stack:**
- **Twilio Voice** — Outbound call placement and telephony (proven, 15+ years in production)
- **Deepgram** — Speech-to-text (lowest latency STT available, ~300ms, production-grade)
- **ElevenLabs** — Text-to-speech (most natural-sounding, streaming-capable, production-grade)
- **Claude** — Conversation reasoning (already integrated via c40v)

**Why this stack over OpenAI Realtime API:** The Realtime API bundles STT+reasoning+TTS into one WebSocket, which is elegant but opaque. You can't swap the voice, can't control the reasoning model, and can't audit the conversation mid-call. The unbundled stack (Deepgram + Claude + ElevenLabs) gives full control at each layer, is individually battle-tested, and lets you use Claude (which already knows your household context) instead of GPT for reasoning.

**Architecture:**

```
                    ┌──────────────────┐
                    │   Twilio Voice    │
                    │  (telephony)      │
                    └────────┬─────────┘
                             │ WebSocket (bidirectional audio)
                    ┌────────┴─────────┐
                    │  pib/voice/call.py│
                    │  (orchestrator)   │
                    └──┬─────────┬─────┘
                       │         │
              ┌────────┴───┐ ┌──┴────────┐
              │  Deepgram   │ │ ElevenLabs │
              │  (STT)      │ │ (TTS)      │
              └────────┬───┘ └──┬────────┘
                       │        │
                   text in   text out
                       │        │
                    ┌──┴────────┴──┐
                    │   Claude      │
                    │  (reasoning)  │
                    │  + context    │
                    └──────────────┘
```

```python
# pib/voice/call.py

import asyncio
import json
from datetime import datetime
from twilio.rest import Client as TwilioClient
from twilio.twiml.voice_response import VoiceResponse, Connect

class VoiceCallManager:
    """
    Manages outbound AI voice calls.
    
    IDENTITY RULES (NON-NEGOTIABLE):
    1. PIB ALWAYS identifies as: "Hi, this is PIB calling on behalf of James Stice"
    2. PIB NEVER claims to be James
    3. If asked "are you a real person?" → "I'm James's AI assistant. 
       Would you prefer James call you back?"
    4. If asked to speak to James → "Absolutely, let me have James call you. 
       What's a good time?" → creates task
    5. PIB ends with: "Thanks for your time. James or I will follow up by email."
    
    CALL FLOW:
    1. PIB dials number via Twilio
    2. When answered, Twilio streams audio to our WebSocket server
    3. Audio → Deepgram STT → text
    4. Text + call context → Claude → response text
    5. Response text → ElevenLabs TTS → audio
    6. Audio → Twilio → caller hears it
    7. Full transcript logged to cap_captures + ops_ledger
    
    GATES:
    - Every call requires pre-approval (governance: voice_call_place: confirm)
    - Call purpose and script must be defined before dialing
    - Maximum call duration: 10 minutes (configurable per project)
    - If Claude is uncertain about how to respond → "Let me check with James 
      and get back to you" → ends call gracefully
    
    COST:
    - Twilio: ~$0.02/min outbound to US numbers
    - Deepgram: ~$0.0043/min
    - ElevenLabs: ~$0.003/min at Starter tier
    - Claude: ~$0.01/min (estimated for call conversation)
    - Total: ~$0.04/min = ~$0.40 per 10-min call
    """
    
    def __init__(self, db, config):
        self.db = db
        self.twilio = TwilioClient(
            os.environ["TWILIO_ACCOUNT_SID"],
            os.environ["TWILIO_AUTH_TOKEN"]
        )
        self.from_number = os.environ["TWILIO_PHONE_NUMBER"]
    
    async def place_call(
        self,
        to_number: str,
        purpose: str,
        context: str,
        script_outline: str,
        project_id: str | None = None,
        max_duration_sec: int = 600,
    ) -> dict:
        """
        Place an outbound call.
        
        Args:
            to_number: Phone number to call (E.164 format)
            purpose: Why we're calling ("inquiry about piano lessons for 6-year-old")
            context: Background context for Claude ("calling Sarah Chen Piano Studio, 
                     rated 4.8 stars, $45/30min listed on website")
            script_outline: Key points to cover ("1. Availability for Saturday mornings 
                           2. Price for weekly 30-min lessons 3. Trial lesson? 
                           4. Experience with young beginners")
            project_id: Links call to a project for context continuity
            max_duration_sec: Hard cutoff (default 10 min)
        
        Returns:
            {
              "call_sid": "CA...",
              "status": "completed",
              "duration_sec": 185,
              "transcript": [
                {"speaker": "pib", "text": "Hi, this is PIB calling on behalf of James Stice..."},
                {"speaker": "human", "text": "Hi, how can I help you?"},
                ...
              ],
              "summary": "Sarah has Saturday 10am slots available. $50/30min. 
                         Trial lesson free. 15 years teaching kids. Will email details.",
              "extracted_data": {
                "price": "$50/30min",
                "availability": "Saturday 10am",
                "trial_lesson": "free",
                "next_step": "Will email lesson details to jrstice@gmail.com"
              },
              "cost_cents": 38,
              "capture_id": "cap-20260302-0042",  # Full transcript stored
            }
        """
        ...
    
    async def _build_system_prompt(self, purpose, context, script_outline):
        """Build Claude's system prompt for this call."""
        return f"""You are PIB, an AI assistant calling on behalf of James Stice.

IDENTITY: You are PIB, James's AI assistant. You are NOT James. If asked, say so honestly.
PURPOSE: {purpose}
CONTEXT: {context}

KEY POINTS TO COVER:
{script_outline}

STYLE:
- Friendly, professional, concise
- Don't ramble. Get the information needed.
- Take notes on everything they say (you'll summarize after).
- If you don't understand something, ask them to repeat.
- If they ask something you can't answer, say "Let me check with James and get back to you."

CLOSING: "Thanks so much for your time. James or I will follow up by email at jrstice@gmail.com. Have a great day!"

HARD RULES:
- Never agree to a price, contract, or commitment. Say "That sounds reasonable, I'll confirm with James."
- Never provide James's address or sensitive personal information.
- Never pretend to be James or a human.
- If they seem confused or uncomfortable talking to an AI, immediately offer to have James call back.
"""
```

**CLI:**
```
python3 -m pib.cli call --to "+14045551234" --purpose "piano lesson inquiry" \
  --script "1. Availability Sat mornings 2. Price for weekly 30min 3. Trial lesson? 4. Experience with young kids" \
  --context "Sarah Chen Piano Studio, Buckhead, 4.8 stars" \
  --json
```

**LLM Tool:**
```python
{"name": "place_call",
 "description": "Call a phone number. PIB identifies as James's AI assistant. "
                "REQUIRES APPROVAL before dialing. Provide purpose, context, "
                "and key points to discuss.",
 "parameters": {
     "to_number": "Phone number (E.164 format: +14045551234)",
     "purpose": "Why we're calling (one sentence)",
     "context": "Background info for the conversation",
     "script_outline": "Numbered list of key points to cover",
     "project_id": "Optional: link to project",
 }}
```

**Governance:**
```yaml
voice_call_place: confirm         # Always requires approval
voice_call_max_minutes: 10        # Hard cutoff
voice_call_commit_anything: off   # Can NEVER agree to terms on call
```

**Twilio setup on Mac Mini:**
```bash
pip install twilio deepgram-sdk elevenlabs

# Twilio webhook receives call events at a local endpoint.
# The PIB console server (port 3333) handles /api/voice/twilio-webhook
# For Twilio to reach it: Cloudflare tunnel OR ngrok (already in Phase 5 of bootstrap)
```

**Voice selection:** ElevenLabs has pre-made voices. Select a professional, friendly male or female voice. Store voice_id in pib_config. James picks during setup.

---

### C4: Virtual Payment Cards

**Technology:** Privacy.com API

**Why Privacy.com:** 
- Creates virtual Visa cards linked to your bank account
- Per-card spending limits
- Per-card merchant locks
- Pause/close cards instantly
- Full transaction API
- Free plan: 12 cards/month. Premium ($10/mo): unlimited + 1% cashback.

```python
# pib/tools/payments.py

import httpx

class PaymentManager:
    """
    Virtual card management for project-based spending.
    
    SECURITY MODEL:
    1. James links his bank account to Privacy.com (one-time, manual)
    2. PIB creates virtual cards via API, each with:
       - A spending limit set by James (per project)
       - An optional merchant lock (only charges from specific merchant)
       - A label (project name)
    3. PIB uses the card number to fill payment forms or read over phone
    4. Every charge is logged to ops_ledger AND fin_transactions
    5. James gets real-time notifications from Privacy.com app
    
    GATES:
    - Card creation: confirm (James must approve budget)
    - Payment under $50 on approved card: true (auto-approved)
    - Payment $50-$200 on approved card: confirm
    - Payment over $200: confirm (always)
    - Payment on non-project card: off (never)
    
    ADDITIONAL SAFETY:
    - Cards auto-pause after project completion
    - Monthly spending report generated
    - Any charge without a corresponding ops_ledger entry triggers alert
    """
    
    PRIVACY_API = "https://api.privacy.com/v1"
    
    async def create_project_card(
        self,
        project_id: str,
        budget_cents: int,
        merchant_lock: str | None = None,
        memo: str = "",
    ) -> dict:
        """
        Create a virtual card for a project.
        
        Returns:
          {
            "card_id": "...",
            "card_number": "4111...",  # stored encrypted, shown to LLM only when filling forms
            "exp_month": "03",
            "exp_year": "2027",
            "cvv": "123",
            "spending_limit_cents": 50000,
            "project_id": "proj-piano-coach",
          }
        """
        api_key = os.environ["PRIVACY_API_KEY"]
        
        async with httpx.AsyncClient() as client:
            resp = await client.post(
                f"{self.PRIVACY_API}/card",
                headers={"Authorization": f"api-key {api_key}"},
                json={
                    "type": "SINGLE_USE" if budget_cents < 10000 else "MERCHANT_LOCKED",
                    "memo": f"PIB: {memo or project_id}",
                    "spend_limit": budget_cents,
                    "spend_limit_duration": "TRANSACTION" if budget_cents < 10000 else "MONTHLY",
                    **({"merchant_lock": merchant_lock} if merchant_lock else {}),
                },
            )
            resp.raise_for_status()
            card = resp.json()
        
        # Store card reference (NOT the full number) in project record
        await self.db.execute(
            """INSERT INTO proj_cards (card_id, project_id, budget_cents, created_at)
               VALUES (?, ?, ?, ?)""",
            [card["token"], project_id, budget_cents, datetime.utcnow().isoformat()],
        )
        
        return {
            "card_id": card["token"],
            "card_number": card["pan"],
            "exp_month": card["exp_month"],
            "exp_year": card["exp_year"],
            "cvv": card["cvv"],
            "spending_limit_cents": budget_cents,
        }
    
    async def get_card_transactions(self, card_id: str) -> list[dict]:
        """Get all transactions on a card. For reconciliation and reporting."""
        ...
    
    async def pause_card(self, card_id: str) -> dict:
        """Pause a card (project complete or suspicious activity)."""
        ...
    
    async def close_card(self, card_id: str) -> dict:
        """Permanently close a card."""
        ...
```

**Governance:**
```yaml
payment_card_create: confirm       # James approves budget
payment_under_50: true             # Auto-approved on approved cards
payment_50_to_200: confirm         # Requires confirmation
payment_over_200: confirm          # Always requires confirmation  
payment_recurring: confirm         # Subscriptions always confirmed
```

---

### C5: Project Management

This is the architectural piece that ties everything together. Projects are multi-phase efforts with gates, budgets, contacts, and deliverables.

```sql
-- migrations/008_projects.sql

CREATE TABLE IF NOT EXISTS proj_projects (
    id TEXT PRIMARY KEY,                    -- proj-YYYYMMDD-XXXX
    title TEXT NOT NULL,                    -- "Find Piano Coach for Charlie"
    description TEXT,                       -- Full project brief from James
    status TEXT NOT NULL DEFAULT 'planning'
        CHECK (status IN ('planning','active','blocked','paused','completed','cancelled')),
    
    -- Ownership
    assigned_to TEXT DEFAULT 'pib',         -- who's executing (always pib unless delegated)
    requested_by TEXT NOT NULL,             -- m-james
    
    -- Budget
    budget_cents INTEGER,                   -- Total approved budget (NULL = no budget set yet)
    spent_cents INTEGER DEFAULT 0,          -- Running total from card transactions
    budget_status TEXT DEFAULT 'unset'
        CHECK (budget_status IN ('unset','approved','warning','exceeded')),
    
    -- Timeline
    deadline TEXT,                          -- Hard deadline if any
    estimated_hours REAL,                   -- PIB's estimate of total effort
    
    -- Classification
    project_type TEXT                       -- research | procurement | booking | administrative | construction
        CHECK (project_type IN ('research','procurement','booking','administrative','construction','creative')),
    complexity TEXT DEFAULT 'medium'
        CHECK (complexity IN ('simple','medium','complex')),
    
    -- Card
    card_id TEXT,                           -- Privacy.com virtual card for this project
    
    -- Lifecycle
    started_at TEXT,
    completed_at TEXT,
    created_at TEXT NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%SZ','now')),
    updated_at TEXT NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%SZ','now'))
);

CREATE TABLE IF NOT EXISTS proj_phases (
    id TEXT PRIMARY KEY,                    -- phase-YYYYMMDD-XXXX
    project_id TEXT NOT NULL REFERENCES proj_projects(id),
    title TEXT NOT NULL,                    -- "Research Candidates"
    sequence INTEGER NOT NULL,              -- 1, 2, 3... (execution order)
    status TEXT NOT NULL DEFAULT 'pending'
        CHECK (status IN ('pending','active','completed','skipped')),
    
    -- Gate
    gate_type TEXT DEFAULT 'none'
        CHECK (gate_type IN ('none','inform','confirm','approve')),
    -- none: auto-advance to next phase
    -- inform: notify James, auto-advance
    -- confirm: wait for James to confirm before advancing
    -- approve: wait for explicit approval (used for spending, contracting)
    
    gate_message TEXT,                      -- What to present at the gate
    gate_response TEXT,                     -- James's response (stored for audit)
    gate_responded_at TEXT,
    
    -- Phase details
    deliverable TEXT,                       -- What this phase produces
    estimated_hours REAL,
    
    started_at TEXT,
    completed_at TEXT,
    created_at TEXT NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%SZ','now'))
);

CREATE INDEX idx_proj_phases ON proj_phases(project_id, sequence);

CREATE TABLE IF NOT EXISTS proj_contacts (
    id TEXT PRIMARY KEY,                    -- contact-YYYYMMDD-XXXX
    project_id TEXT NOT NULL REFERENCES proj_projects(id),
    name TEXT NOT NULL,
    role TEXT,                              -- "piano teacher", "architect", "plumber"
    phone TEXT,
    email TEXT,
    website TEXT,
    
    -- Evaluation
    rating REAL,                            -- from reviews
    review_count INTEGER,
    price_info TEXT,                        -- "$50/30min", "$150/hr"
    notes TEXT,                             -- free-form notes from calls/emails
    
    -- Status
    status TEXT DEFAULT 'identified'
        CHECK (status IN ('identified','contacted','responded','shortlisted',
                         'selected','rejected','hired','completed')),
    contacted_at TEXT,
    responded_at TEXT,
    
    created_at TEXT NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%SZ','now')),
    updated_at TEXT NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%SZ','now'))
);

CREATE INDEX idx_proj_contacts ON proj_contacts(project_id, status);

CREATE TABLE IF NOT EXISTS proj_cards (
    card_id TEXT PRIMARY KEY,               -- Privacy.com card token
    project_id TEXT NOT NULL REFERENCES proj_projects(id),
    budget_cents INTEGER NOT NULL,
    spent_cents INTEGER DEFAULT 0,
    status TEXT DEFAULT 'active'
        CHECK (status IN ('active','paused','closed')),
    created_at TEXT NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%SZ','now'))
);
```

**Project Templates:**

```python
# pib/projects/templates.py

PROJECT_TEMPLATES = {
    "find_service_provider": {
        "phases": [
            {"title": "Research", "gate_type": "none",
             "deliverable": "Google Sheet with 10-15 candidates"},
            {"title": "Outreach", "gate_type": "inform",
             "deliverable": "Emails/calls sent, responses tracked"},
            {"title": "Comparison", "gate_type": "confirm",
             "deliverable": "Top 3-5 shortlist with recommendation"},
            {"title": "Schedule", "gate_type": "none",
             "deliverable": "Trial/consultation booked"},
            {"title": "Evaluate", "gate_type": "approve",
             "deliverable": "Final recommendation after trial"},
            {"title": "Book", "gate_type": "confirm",
             "deliverable": "Ongoing service booked and paid"},
        ],
    },
    
    "book_travel": {
        "phases": [
            {"title": "Research Destinations", "gate_type": "none",
             "deliverable": "Options doc with 3 itinerary packages"},
            {"title": "Present Options", "gate_type": "approve",
             "deliverable": "Family picks a package"},
            {"title": "Book Flights", "gate_type": "confirm",
             "deliverable": "Flights confirmed"},
            {"title": "Book Accommodation", "gate_type": "confirm",
             "deliverable": "Hotel/resort confirmed"},
            {"title": "Book Activities", "gate_type": "inform",
             "deliverable": "Activities scheduled"},
            {"title": "Pre-Trip Logistics", "gate_type": "none",
             "deliverable": "Packing list, pet sitter, mail hold"},
        ],
    },
    
    "construction_project": {
        "phases": [
            {"title": "Zoning & Code Research", "gate_type": "inform",
             "deliverable": "Zoning summary + feasibility assessment"},
            {"title": "Find Professionals", "gate_type": "none",
             "deliverable": "Shortlist of architects/designers"},
            {"title": "Get Proposals", "gate_type": "none",
             "deliverable": "Proposals + cost comparison"},
            {"title": "Select Professional", "gate_type": "approve",
             "deliverable": "Recommended firm with rationale"},
            {"title": "Contract", "gate_type": "approve",
             "deliverable": "Contract for James to sign"},
            {"title": "Design Phase", "gate_type": "confirm",
             "deliverable": "Mockups/renderings for review"},
            {"title": "Design Revision", "gate_type": "approve",
             "deliverable": "Final approved design"},
            {"title": "Permitting", "gate_type": "inform",
             "deliverable": "Permits filed (professional handles)"},
        ],
    },
    
    "administrative_cleanup": {
        "phases": [
            {"title": "Research & Plan", "gate_type": "none",
             "deliverable": "Action plan with all steps"},
            {"title": "Execute", "gate_type": "inform",
             "deliverable": "Progress report with completion %"},
            {"title": "Follow Up", "gate_type": "none",
             "deliverable": "Outstanding items tracked"},
            {"title": "Final Report", "gate_type": "inform",
             "deliverable": "Completion summary"},
        ],
    },
    
    "enrollment_deadline": {
        "phases": [
            {"title": "Research Options", "gate_type": "none",
             "deliverable": "Comparison matrix"},
            {"title": "Present Options", "gate_type": "approve",
             "deliverable": "Family picks"},
            {"title": "Register", "gate_type": "confirm",
             "deliverable": "Registration submitted + confirmation"},
            {"title": "Payment", "gate_type": "confirm",
             "deliverable": "Deposit/fee paid"},
            {"title": "Calendar & Logistics", "gate_type": "none",
             "deliverable": "Dates blocked, logistics planned"},
        ],
    },
    
    "emergency_repair": {
        "phases": [
            {"title": "Find Available Provider NOW", "gate_type": "none",
             "deliverable": "Available providers with quotes (parallel calls)"},
            {"title": "Select & Confirm", "gate_type": "approve",
             "deliverable": "Provider booked, arrival window set"},
            {"title": "Coordinate Arrival", "gate_type": "none",
             "deliverable": "James notified, calendar blocked"},
            {"title": "Payment", "gate_type": "confirm",
             "deliverable": "Invoice paid"},
        ],
    },
}
```

**LLM Tools:**
```python
PROJECT_TOOLS = [
    {"name": "create_project",
     "description": "Create a new project from a template or custom phases. "
                    "Use when James assigns a multi-step real-world task.",
     "parameters": {
         "title": "Project title",
         "description": "Full brief",
         "template": "Optional: find_service_provider | book_travel | construction_project | "
                     "administrative_cleanup | enrollment_deadline | emergency_repair",
         "budget_cents": "Optional: total budget in cents",
         "deadline": "Optional: ISO date",
     }},
    
    {"name": "advance_project",
     "description": "Mark current phase complete and advance to next. "
                    "If next phase has a gate, present the gate to James.",
     "parameters": {
         "project_id": "Project ID",
         "phase_deliverable": "What was produced in this phase",
         "gate_message": "What to present to James at the gate (if gated)",
     }},
    
    {"name": "add_project_contact",
     "description": "Add a vendor/contact to a project's contact list.",
     "parameters": {
         "project_id": "Project ID",
         "name": "Contact name",
         "phone": "Phone number",
         "email": "Email",
         "role": "Their role (piano teacher, architect, plumber)",
         "price_info": "Pricing information",
         "rating": "Review rating",
         "notes": "Notes from research or conversation",
     }},
    
    {"name": "project_status",
     "description": "Get full project status: phases, contacts, budget, timeline.",
     "parameters": {"project_id": "Project ID"}},
]
```

---

### C7: Document Generation (PDF)

```python
# pib/tools/pdf.py

async def generate_pdf(html_content: str, filename: str, project_id: str = None) -> str:
    """
    Generate PDF from HTML using Playwright's print-to-PDF.
    Used for: project reports, comparison documents, invoices, contracts.
    
    Returns path to generated PDF.
    """
    async with async_playwright() as p:
        browser = await p.webkit.launch(headless=True)
        page = await browser.new_page()
        await page.set_content(html_content)
        
        pdf_dir = Path("state/documents") / (project_id or "general")
        pdf_dir.mkdir(parents=True, exist_ok=True)
        pdf_path = pdf_dir / filename
        
        await page.pdf(path=str(pdf_path), format="Letter",
                       margin={"top": "1in", "bottom": "1in",
                               "left": "0.75in", "right": "0.75in"})
        await browser.close()
        
    return str(pdf_path)
```

### C8: Physical Mail

```python
# pib/tools/mail.py

import httpx

async def send_letter(
    to_name: str,
    to_address: dict,  # {line1, line2, city, state, zip}
    content: str,       # Plain text or HTML
    project_id: str = None,
    certified: bool = False,
) -> dict:
    """
    Send a physical letter via Lob.com API.
    
    Used for: data broker opt-outs requiring physical mail,
              formal notices, anything needing paper trail.
    
    Cost: ~$1.00/letter standard, ~$5.00 certified
    
    Gate: ALWAYS confirm (physical mail can't be unsent)
    """
    api_key = os.environ["LOB_API_KEY"]
    
    async with httpx.AsyncClient() as client:
        resp = await client.post(
            "https://api.lob.com/v1/letters",
            auth=(api_key, ""),
            json={
                "to": {
                    "name": to_name,
                    "address_line1": to_address["line1"],
                    "address_line2": to_address.get("line2", ""),
                    "address_city": to_address["city"],
                    "address_state": to_address["state"],
                    "address_zip": to_address["zip"],
                },
                "from": {
                    "name": "James Stice",
                    "address_line1": "...",  # from pib_config
                    "address_city": "Atlanta",
                    "address_state": "GA",
                    "address_zip": "...",
                },
                "file": content,  # HTML rendered by Lob
                "color": False,
                "mail_type": "usps_first_class",
                **({"extra_service": "certified"} if certified else {}),
            },
        )
        resp.raise_for_status()
        letter = resp.json()
    
    return {
        "letter_id": letter["id"],
        "expected_delivery": letter["expected_delivery_date"],
        "cost_cents": int(float(letter.get("price", "1.00")) * 100),
        "tracking": letter.get("tracking_number"),
    }
```

**Governance:**
```yaml
physical_mail_send: confirm        # Always requires approval
```

---

## 4. RISK GATING FRAMEWORK

### 4.1 Governance Additions (complete)

```yaml
# Full governance.yaml for CoS enablement

# === EXISTING (from c40v) ===
task_create: true
task_complete: true
task_delete: off
calendar_hold_create: confirm
calendar_event_create: confirm
financial_write: off

# === SEARCH & BROWSE ===
web_search: true                    # Searching is always safe
browser_navigate: true              # Visiting URLs is always safe
browser_fill_form: true             # Filling forms is safe (not submitted yet)
browser_submit_form: confirm        # Submitting requires approval
browser_submit_payment: confirm     # HARD GATE — payment forms always confirmed
browser_submit_login: confirm       # HARD GATE — login forms always confirmed
browser_download: true              # Downloads to sandbox

# === COMMUNICATION ===
email_send_reply: true              # Replying to existing thread (context exists)
email_send_new: confirm             # New outbound email (reputational risk)
email_send_bulk: confirm            # 3+ emails in one batch
imessage_send: confirm              # iMessage is personal — always confirm
sms_send: confirm                   # SMS is personal — always confirm
voice_call_place: confirm           # Phone calls always confirmed
voice_call_commit: off              # Can NEVER commit to terms on a call

# === FINANCIAL ===
payment_card_create: confirm        # Creating a virtual card = approving a budget
payment_under_50: true              # Small charges on approved project cards
payment_50_to_200: confirm          # Medium charges need confirmation
payment_over_200: confirm           # Large charges always confirmed
payment_recurring: confirm          # Subscriptions always confirmed

# === PHYSICAL ===
physical_mail_send: confirm         # Physical mail can't be unsent

# === PROJECT ===
project_create: true                # Creating a project is just planning
project_advance_phase: true         # Advancing when gate_type is 'none'
project_advance_gated: confirm      # Advancing when gate_type is 'confirm' or 'approve'
project_close: confirm              # Closing/cancelling a project

# === TRUST RAMP (adjustable over time) ===
# After 2 weeks of successful operation, James can loosen:
#   email_send_new: true           (PIB proved it writes good emails)
#   payment_under_50: true         (already set)
#   payment_50_to_200: true        (trust earned)
#
# After 1 month:
#   voice_call_place: true         (PIB proved it handles calls well)
#   browser_submit_form: true      (non-payment forms auto-submitted)
```

### 4.2 Reputational Risk Controls

```python
# pib/safety/reputation.py

OUTBOUND_RULES = {
    "email": {
        "max_per_hour": 10,             # Rate limit
        "max_per_day": 50,
        "require_signature": True,       # Always sign as "James Stice (via PIB)"
        "forbidden_domains": [           # Never email these without explicit approval
            "*.gov", "*.court.*", "*.irs.gov",
            "laura*@*",                  # Never email Laura's work contacts
        ],
        "tone_check": True,             # LLM review of tone before sending
    },
    
    "voice": {
        "max_calls_per_hour": 5,
        "max_calls_per_day": 15,
        "always_identify_as_ai": True,   # Non-negotiable
        "record_all_calls": True,        # For audit
        "prohibited_topics": [
            "medical details",
            "social security numbers",
            "legal matters",             # Only James or Laura's attorney
        ],
    },
    
    "social_media": {
        "post_to_x": confirm,           # Always gate public posts
        "reply_on_x": confirm,
        "dm_on_x": confirm,
    },
}

async def pre_send_check(channel: str, content: str, recipient: str) -> dict:
    """
    Pre-flight check before any outbound communication.
    Returns {approved: bool, reason: str, modified_content: str | None}
    
    Checks:
    1. Rate limits not exceeded
    2. Recipient not in forbidden list
    3. Content doesn't contain PII (SSN, bank accounts, passwords)
    4. Tone is professional (quick Haiku check for emails)
    5. Content matches stated purpose (no hallucinated information)
    """
    ...
```

### 4.3 Financial Risk Controls

```python
# pib/safety/financial.py

class FinancialGuardrails:
    """
    Multi-layer financial protection.
    
    Layer 1: Per-transaction governance gates (governance.yaml)
    Layer 2: Per-card spending limits (Privacy.com)
    Layer 3: Per-project budget tracking (proj_projects.budget_cents)
    Layer 4: Global monthly cap (pib_config: max_monthly_spend_cents)
    Layer 5: James gets Privacy.com push notification on every charge
    Layer 6: Daily reconciliation (cron) catches any discrepancy
    """
    
    async def check_spend_allowed(
        self, project_id: str, amount_cents: int, merchant: str
    ) -> dict:
        """
        Called before every payment. Returns {allowed, reason, gate_required}.
        
        Checks (in order):
        1. Global monthly cap not exceeded
        2. Project budget not exceeded  
        3. Card limit not exceeded (redundant with Privacy.com but defense-in-depth)
        4. Governance gate satisfied
        """
        # Check global monthly cap
        monthly_total = await self.db.execute(
            """SELECT COALESCE(SUM(amount_cents), 0) as total 
               FROM fin_transactions 
               WHERE date >= date('now', 'start of month')
               AND source = 'privacy_card'"""
        )
        global_cap = int(await get_config(self.db, "max_monthly_spend_cents", "100000"))  # $1000 default
        if monthly_total + amount_cents > global_cap:
            return {"allowed": False, "reason": f"Would exceed monthly cap (${global_cap/100:.0f})"}
        
        # Check project budget
        project = await self.db.execute(
            "SELECT budget_cents, spent_cents FROM proj_projects WHERE id = ?",
            [project_id]
        )
        row = project.fetchone()
        if row and row["budget_cents"] and (row["spent_cents"] + amount_cents) > row["budget_cents"]:
            return {"allowed": False, 
                    "reason": f"Would exceed project budget (${row['budget_cents']/100:.0f}). "
                              f"Already spent: ${row['spent_cents']/100:.0f}"}
        
        # Determine gate requirement
        gate = "true"  # default: auto-approved
        if amount_cents >= 20000:
            gate = "confirm"
        elif amount_cents >= 5000:
            gate = "confirm"
        
        return {"allowed": True, "gate_required": gate}
```

### 4.4 Technical Risk Controls

```python
# Defense against common agent failure modes

TECHNICAL_SAFEGUARDS = {
    "browser_timeout": 30,              # 30-second hard timeout on all browser operations
    "call_max_duration": 600,           # 10-minute hard cutoff on calls
    "search_max_per_minute": 5,         # Rate limit web searches
    "form_fill_review": True,           # Screenshot before every submission
    "email_preview": True,              # Full email shown in gate approval
    "parallel_calls_max": 3,            # Max simultaneous outbound calls
    "project_max_active": 5,            # Max concurrent active projects
    "browser_contexts_max": 10,         # Max open browser sessions
    
    # Anti-hallucination: for factual queries about vendors, ALWAYS
    # cite the source URL or call transcript. Never state a price,
    # availability, or rating without a source.
    "require_source_citation": True,
    
    # Anti-loop: if PIB has retried the same browser action 3 times,
    # stop and report the failure instead of burning tokens.
    "browser_retry_max": 3,
    
    # Anti-spam: cooldown between contacting the same vendor
    "vendor_contact_cooldown_hours": 24,
}
```

---

## 5. FILE MANIFEST

### New Python Files

```
pib/
├── tools/
│   ├── web_search.py              # Brave Search API (C1)
│   ├── browser.py                 # Playwright browsing + forms (C2)
│   ├── payments.py                # Privacy.com virtual cards (C4)
│   ├── pdf.py                     # PDF generation (C7)
│   └── mail.py                    # Lob.com physical mail (C8)
│
├── voice/
│   ├── call.py                    # Outbound call orchestrator (C3)
│   ├── deepgram_stt.py            # Speech-to-text integration
│   ├── elevenlabs_tts.py          # Text-to-speech integration
│   └── webhook.py                 # Twilio webhook handler (FastAPI routes)
│
├── projects/
│   ├── manager.py                 # Project lifecycle (C5)
│   ├── templates.py               # Project templates (C5)
│   └── reporting.py               # Project status reports
│
├── safety/
│   ├── reputation.py              # Outbound communication guards
│   ├── financial.py               # Spending guards
│   └── pre_send.py                # Pre-flight checks for all outbound
│
└── tests/
    ├── test_web_search.py
    ├── test_browser.py
    ├── test_voice_call.py
    ├── test_payments.py
    ├── test_projects.py
    ├── test_safety_gates.py
    └── test_financial_guards.py
```

### New Migration

```
migrations/
├── 008_projects.sql               # proj_projects, proj_phases, proj_contacts, proj_cards
```

### Modified Files

```
governance.yaml                     # Add all new gates (§4.1)
pib/cli.py                         # Add subcommands: web-search, browse, call, project, card
pib/llm.py tools section           # Add: web_search, browse_*, place_call, create_project, etc.
console/server.mjs                 # Add: /api/projects, /api/voice/twilio-webhook
```

### Console Additions

```
console/src/pages/
├── Projects.jsx                   # Project list + phase progress + contact tracker
├── ProjectDetail.jsx              # Single project: phases, contacts, budget, timeline
```

---

## 6. INSTALL SEQUENCE (Mac Mini)

```bash
# After core c40v is deployed (bootstrap Prompts 1-10 complete):

# 1. Python packages
pip install playwright httpx twilio deepgram-sdk elevenlabs

# 2. Browser engine
playwright install webkit

# 3. API keys (James provides these)
openclaw config set BRAVE_SEARCH_API_KEY "..."
openclaw config set PRIVACY_API_KEY "..."
openclaw config set DEEPGRAM_API_KEY "..."
openclaw config set ELEVENLABS_API_KEY "..."
openclaw config set LOB_API_KEY "..."
# (Twilio already configured in bootstrap Phase 4)

# 4. Run migration
python3 -m pib.cli migrate  # applies 008_projects.sql

# 5. Verify
python3 -m pib.cli web-search --query "test" --json
python3 -m pib.cli browse --url "https://example.com" --json
python3 -m pib.cli project --list --json

# 6. Voice webhook (requires Cloudflare tunnel from bootstrap Phase 5)
# Twilio console: set Voice webhook to https://pib.your-tunnel.com/api/voice/twilio-webhook
```

---

## 7. CRON ADDITIONS

```yaml
# New cron jobs for CoS enablement

# Project status digest (daily 8pm — what progressed today)
- schedule: "0 20 * * *"
  command: "python3 -m pib.cli projects --daily-digest --json"
  deliver: true

# Financial reconciliation (daily 3am — match card charges to ledger)
- schedule: "0 3 * * *"
  command: "python3 -m pib.cli finance --reconcile-cards --json"
  deliver: false  # only alert on discrepancy

# Project follow-ups (every 4 hours during business hours)
- schedule: "0 9,13,17 * * 1-5"
  command: "python3 -m pib.cli projects --check-followups --json"
  deliver: false  # fires individual follow-up actions

# Browser session cleanup (daily midnight)
- schedule: "0 0 * * *"
  command: "python3 -m pib.cli browse --cleanup --json"
  deliver: false

# Screenshot pruning (weekly Sunday 4am — delete screenshots older than 30 days)
- schedule: "0 4 * * 0"
  command: "find state/browser_screenshots -mtime +30 -delete"
  deliver: false
```

---

## 8. THE TRUST RAMP

Week 1-2 governance (tight):
```yaml
email_send_new: confirm
voice_call_place: confirm
browser_submit_form: confirm
payment_under_50: confirm         # Even small charges confirmed initially
```

Week 3-4 governance (loosening):
```yaml
email_send_new: true              # PIB proved it writes good professional emails
browser_submit_form: true         # Non-payment forms auto-submitted
payment_under_50: true            # Small charges on approved project cards
```

Month 2+ governance (operational):
```yaml
voice_call_place: true            # PIB handles calls well, auto-dial
payment_50_to_200: true           # Medium charges within project budget
email_send_bulk: true             # Batch outreach auto-approved
```

The ramp is driven by James's comfort, not a timer. Each loosening is a conscious `governance.yaml` edit after reviewing the audit trail.

---

## 9. WHAT THIS ENABLES

With this spec fully built, PIB handles:

| Project Type | Example | PIB Does | James Does |
|---|---|---|---|
| **Service Provider Search** | Piano teacher, plumber, tutor, dog walker | Research → outreach → calls → compare → shortlist → book | Pick from shortlist, attend trial |
| **Travel Booking** | Family vacation, weekend getaway | Research → compare → present options → book everything | Pick the package |
| **Administrative** | Delete me from internet, insurance shopping, utility switching | Research → execute → follow up → report | Solve CAPTCHAs, sign things |
| **Enrollment** | Summer camp, school registration, activities | Research → compare → register → pay | Pick the program |
| **Emergency Repair** | Plumber, electrician, HVAC | Parallel calls → quotes → recommend → schedule | Approve choice, be home |
| **Construction/Renovation** | ADU, kitchen remodel, deck | Zoning research → find pros → get proposals → compare | Pick designer, sign contract, approve design |
| **Procurement** | Furniture, appliances, baby gear | Research → compare → find best price → purchase | Approve big purchases |
| **Event Planning** | Birthday party, dinner party, date night | Research venues → compare → book → coordinate | Approve plan |
