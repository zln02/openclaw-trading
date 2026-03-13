# OPENCLAW STRATEGIC PLAN v1.0
**Date:** 2026-03-13 | **Author:** Claude Opus (Strategic Architect) | **Executor:** Codex 5.4

---

## EXECUTIVE SUMMARY

OpenClaw GCP server hosts **two diverged repos** (`~/.openclaw/workspace/` and `~/openclaw/`) with 264+ orphaned `.pyc` files, a **world-writable secrets file** (`openclaw.json` at 0666), duplicate Telegram bot processes, and a dashboard that runs from the older repo while the newer one has 30 uncommitted changes. The plan prioritizes security fixes (P0), repo consolidation (P0), then dashboard/Telegram/agent upgrades (P1-P2).

---

## PRIORITY MATRIX

| Priority | Area | Est. Time | Risk |
|----------|------|-----------|------|
| **P0-IMMEDIATE** | Security: Fix `openclaw.json` permissions | 1 min | Zero risk |
| **P0** | Security: Fix all `.env` permissions | 2 min | Zero risk |
| **P0** | File Cleanup: `__pycache__`, `.pyc`, junk | 5 min | Zero risk |
| **P0** | Repo Consolidation: Decide primary repo | 30 min | Medium — must not break live trading |
| **P1** | Dashboard UI Upgrade | 2-3 hrs | Low — dashboard is view-only |
| **P1** | Telegram AI Service | 1 hr | Low — additive feature |
| **P1** | Agent Logging & Verification | 1 hr | Low — additive |
| **P1** | Kill duplicate Telegram bot | 2 min | Low |
| **P2** | Markdown consolidation | 20 min | Zero |
| **P2** | Infrastructure & monitoring | 30 min | Low |
| **P2** | Solar Shadow Map cleanup | 10 min | Zero |

---

## CURRENT SERVER STATE (as of 2026-03-13 15:30 KST)

### Running Processes
| Process | PID | User | CPU | Notes |
|---------|-----|------|-----|-------|
| `telegram_bot.py` | 1409032 | wlsdud5035 | 32min | Long-running (since Mar 5) |
| `telegram_bot.py` | 1528916 | root | — | **DUPLICATE — kill this** |
| `btc_dashboard.py` | 1543145 | root | — | Dashboard on port 8080 |
| `us_stock_trading_agent.py` | 1585418 | root | 26% | US agent |
| `btc_trading_agent.py` | 1585774 | root | 84% | **HIGH CPU — investigate** |

### Disk Usage
| Path | Size |
|------|------|
| `~/` total | 13 GB |
| `~/openclaw/node_modules/` | 1.9 GB (root-level, possibly unnecessary) |
| `~/openclaw/dashboard/` | 207 MB |
| `~/.openclaw/workspace/dashboard/` | 158 MB |
| `~/.openclaw/logs/` | ~50 MB (80+ log files) |

### Port Usage
| Port | Process |
|------|---------|
| 8080 | btc_dashboard.py (FastAPI) |
| 443 | nginx (SSL → proxy) |
| 80 | nginx (HTTP) |

### Nginx Config
- `jyp-openclaw.duckdns.org:443` → `localhost:18789`
- `opentrading.duckdns.org:443` → `127.0.0.1:18080`
- Note: Dashboard listens on 8080 but nginx proxies to 18080 — **possible port mismatch**

---

## AREA 1: FILE & FOLDER CLEANUP (P0)

### 1a. Junk File Removal

```bash
# Step 1: List all __pycache__ (review first)
find ~/.openclaw/workspace -path '*/.venv' -prune -o -type d -name '__pycache__' -print
find ~/openclaw -path '*/.venv' -prune -o -type d -name '__pycache__' -print

# Step 2: Remove __pycache__ (safe — Python regenerates)
find ~/.openclaw/workspace -path '*/.venv' -prune -o -type d -name '__pycache__' -exec rm -rf {} + 2>/dev/null
find ~/openclaw -path '*/.venv' -prune -o -type d -name '__pycache__' -exec rm -rf {} + 2>/dev/null

# Step 3: Remove catboost training artifacts
rm -rf ~/.openclaw/workspace/catboost_info/

# Step 4: Investigate gog-docker binary (22MB)
file ~/.openclaw/workspace/gog-docker
# If unnecessary: rm ~/.openclaw/workspace/gog-docker

# Step 5: Check root-level node_modules (1.9GB!)
cat ~/openclaw/package.json 2>/dev/null
# If only dashboard deps or unused: rm -rf ~/openclaw/node_modules/
```

**Risk:** Zero for `__pycache__` and `catboost_info`. `gog-docker` and root `node_modules` need human confirmation.
**Rollback:** `__pycache__` auto-regenerates on next import.

### 1b. Markdown File Consolidation

**Files found across both repos:**

| Category | Files |
|----------|-------|
| System Identity | `AGENTS.md`, `BOOTSTRAP.md`, `IDENTITY.md`, `SOUL.md`, `USER.md`, `HEARTBEAT.md`, `TOOLS.md` |
| README | `README.md`, `README.ko.md` |
| AI Rules | `.cursorrules`, `.windsurfrules` |
| Docs | `docs/code_health_todo.md`, `docs/telegram_commands.md`, `execution/README.md`, `company/README.md` |
| Brain Docs | `brain/daily-summary/*.md`, `brain/improve/*.md`, `brain/market/*.md`, `brain/news/*.md` |
| Orphaned | `FINAL_OPTIMIZATION_SPEC.md` (~/openclaw/ only), `.github/java-upgrade/*/plan.md` |

```bash
# Step 1: Create consolidated docs structure
mkdir -p ~/openclaw/docs/changelog
mkdir -p ~/openclaw/docs/brain-archive

# Step 2: Archive brain daily summaries
cp ~/.openclaw/workspace/brain/daily-summary/*.md ~/openclaw/docs/brain-archive/

# Step 3: Move orphaned docs
mv ~/openclaw/FINAL_OPTIMIZATION_SPEC.md ~/openclaw/docs/OPTIMIZATION_SPEC.md

# Step 4: Remove orphaned java-upgrade plan
rm -rf ~/openclaw/.github/java-upgrade/

# Step 5: Create docs/README.md index linking all documentation
```

### 1c. The Two-Repo Problem (CRITICAL)

**Two repos have diverged significantly:**

| Aspect | `~/.openclaw/workspace/` | `~/openclaw/` |
|--------|--------------------------|----------------|
| Dashboard | Older version | **Newer** (framer-motion, recharts) |
| Trading agents | Running from here (cron) | 30 uncommitted changes |
| Brain/ML models | Active (updated today) | `brain/` owned by root |
| Node modules | 158 MB (dashboard only) | 1.9 GB (root + dashboard) |
| Git status | 4 uncommitted changes | 30 uncommitted changes |

**Recommendation:** `~/openclaw/` should be the **single source of truth**.

```bash
# Step 1: Snapshot both repos
cd ~/.openclaw/workspace && git add -A && git commit -m "[consolidation] snapshot before merge"
cd ~/openclaw && git add -A && git commit -m "[consolidation] snapshot before merge"

# Step 2: Diff the two repos
diff -rq ~/.openclaw/workspace/btc ~/openclaw/btc --exclude='__pycache__'
diff -rq ~/.openclaw/workspace/stocks ~/openclaw/stocks --exclude='__pycache__'
diff -rq ~/.openclaw/workspace/common ~/openclaw/common --exclude='__pycache__'
diff -rq ~/.openclaw/workspace/agents ~/openclaw/agents --exclude='__pycache__'

# Step 3: Cherry-pick unique workspace changes into ~/openclaw/ (manual review)
# Step 4: Update all cron jobs to point to ~/openclaw/
# Step 5: Update symlinks
# Step 6: Restart services from ~/openclaw/
# Step 7: Keep ~/.openclaw/workspace/ as read-only archive for 2 weeks
```

**Risk:** HIGH — cron jobs, running processes, and symlinks all point to workspace.
**Rollback:** Keep workspace intact as backup. Only delete after 2-week burn-in.

---

## AREA 2: SECURITY AUDIT (P0)

### 2a. CRITICAL — Fix Immediately

```bash
# CRITICAL: openclaw.json is world-writable (0666) — contains ALL production API keys
chmod 600 /home/wlsdud5035/.openclaw/openclaw.json

# HIGH: .env files world-readable
chmod 600 /home/wlsdud5035/.openclaw/.env
chmod 600 /home/wlsdud5035/.openclaw/workspace/skills/kiwoom-api/.env
chmod 600 /home/wlsdud5035/.openclaw/workspace/secretary/.env

# MEDIUM: Kiwoom token world-readable
chmod 600 /home/wlsdud5035/.openclaw/workspace/brain/kiwoom_token.json
```

### 2b. Security Findings

| Severity | Finding | Fix | Key Rotation? |
|----------|---------|-----|---------------|
| **CRITICAL** | `openclaw.json` world-writable (0666) — ALL API keys | `chmod 600` | Rotate if multi-user server |
| **HIGH** | `.openclaw/.env` world-readable (0644) | `chmod 600` | No |
| **HIGH** | `kiwoom-api/.env` world-readable | `chmod 600` | No |
| **HIGH** | `secretary/.env` world-readable | `chmod 600` | No |
| **MEDIUM** | `brain/kiwoom_token.json` readable | `chmod 600` | No (short-lived token) |
| **LOW** | No nginx security headers | Add headers | N/A |
| **CLEAN** | No hardcoded secrets in source code | — | — |
| **CLEAN** | No secrets in git history | — | — |
| **CLEAN** | Dashboard auth: `secrets.compare_digest` + rate limiting | — | — |
| **CLEAN** | SSL certs properly secured | — | — |

### 2c. Nginx Security Headers

```bash
sudo cp /etc/nginx/sites-enabled/jyp-openclaw.duckdns.org /etc/nginx/sites-enabled/jyp-openclaw.duckdns.org.bak.$(date +%Y%m%d)
sudo cp /etc/nginx/sites-enabled/opentrading.duckdns.org /etc/nginx/sites-enabled/opentrading.duckdns.org.bak.$(date +%Y%m%d)

# Add inside each server { } block:
#   add_header X-Frame-Options "DENY" always;
#   add_header X-Content-Type-Options "nosniff" always;
#   add_header X-XSS-Protection "1; mode=block" always;
#   add_header Referrer-Policy "strict-origin-when-cross-origin" always;

sudo nginx -t && sudo systemctl reload nginx
```

### 2d. Kill Duplicate Telegram Bot

```bash
# Verify PIDs first
ps aux | grep telegram_bot
# Kill the root duplicate (PID 1528916), keep user-owned (PID 1409032)
sudo kill 1528916
```

---

## AREA 3: DASHBOARD UPGRADE (P1)

### 3a. Connection Stability Diagnosis

```bash
# Step 1: Check actual listening port
curl -v http://localhost:8080/api/status
curl -v http://localhost:18080/api/status
ss -tlnp | grep -E '8080|18080'

# Step 2: Check btc_dashboard.py port config
grep -n 'port' ~/openclaw/btc/btc_dashboard.py

# Step 3: Compare with nginx proxy target
grep proxy_pass /etc/nginx/sites-enabled/opentrading.duckdns.org

# LIKELY FIX: nginx proxies to 18080 but app listens on 8080
# Either change nginx or change app port
```

### 3b. UI/UX Upgrade Plan

All changes target `~/openclaw/dashboard/src/`. The repo already has `framer-motion` and `recharts`.

#### 1. Signal Bars — Value-Based Gradient Colors

```jsx
// Add to utils or inline in StatCard
function getSignalColor(value) {
  if (value <= 30) return '#ff4757';  // Red
  if (value <= 70) return '#ffa502';  // Amber
  return '#00d4aa';                    // Green
}
```

Apply to: F&G, RSI, Trend, BB, Volume, Funding bars in BtcPage, KrStockPage, UsStockPage.

#### 2. Composite Score — Fix Empty State

```jsx
// In ScoreGauge.jsx — when score === 0 or null
if (score === 0 || score === null) {
  return (
    <div className="score-gauge empty">
      <svg>{/* gray track ring */}</svg>
      <span className="score-value">0</span>
      <span className="score-label">No Signal</span>
    </div>
  );
}
```

#### 3. Typography — JetBrains Mono

```css
/* In index.css */
@import url('https://fonts.googleapis.com/css2?family=JetBrains+Mono:wght@400;500;600;700&display=swap');

.numeric, td, .price, .score-value, .stat-value {
  font-family: 'JetBrains Mono', monospace;
  font-variant-numeric: tabular-nums;
}
```

#### 4. Action Badges

```css
.badge-buy  { color: #00d4aa; border: 1px solid #00d4aa; background: rgba(0,212,170,0.1); }
.badge-sell { color: #ff4757; border: 1px solid #ff4757; background: rgba(255,71,87,0.1); }
.badge-hold { color: #8a8a8a; border: 1px solid #8a8a8a; background: rgba(138,138,138,0.1); }
.badge-skip { color: #ffa502; border: 1px solid #ffa502; background: rgba(255,165,2,0.1); }
```

#### 5. News Sentiment Badges

```css
.sentiment-bullish { color: #00d4aa; border-color: #00d4aa; }
.sentiment-bearish { color: #ff4757; border-color: #ff4757; }
.sentiment-neutral { color: #8a8a8a; border-color: #8a8a8a; }
```

#### 6. Layout Gap Consistency

```css
.card-grid, .dashboard-grid { gap: 12px; }
```

#### 7. Execution Feed

Connect to `/api/decisions/{market}` endpoint. Show: agent name, action, confidence, reasoning.

#### 8. New Agents Tab (`/agents`)

Create `src/pages/AgentsPage.jsx`:
- Agent status cards (5 agents: Market Analyst, News Analyst, Risk Manager, Reporter, Orchestrator)
- Decision timeline (scrollable, recent decisions)
- 7-day performance chart (using recharts)
- Add route in App.jsx

#### 9. Micro-Interactions (framer-motion)

1. Price pulse: `animate={{ scale: [1, 1.02, 1] }}` on price update
2. Count-up: `useSpring` for portfolio value changes
3. Trade slide-in: `AnimatePresence` + `motion.div` with `initial={{ x: 20, opacity: 0 }}`
4. Loading skeletons: Use existing `LoadingSkeleton.jsx`
5. Status dots: CSS `@keyframes pulse` animation
6. Score donut glow: `box-shadow` animation with `filter: blur()`
7. Confetti on profitable trade close (subtle, 1 second)
8. Tooltips with detailed breakdown on hover

### 3c. Build & Deploy

```bash
cd ~/openclaw/dashboard
npm run build
# Restart dashboard server
sudo kill $(pgrep -f btc_dashboard.py)
cd ~/openclaw && nohup python btc/btc_dashboard.py >> ~/.openclaw/logs/dashboard.log 2>&1 &
```

---

## AREA 4: TELEGRAM AI SERVICE (P1)

### 4a. Create `common/telegram_ai.py`

```python
"""Telegram AI responder using Claude API."""
import anthropic
from common.env_loader import load_env
from common.logger import get_logger

log = get_logger("telegram_ai")

_client = None
_chat_histories: dict[int, list] = {}  # user_id -> last 10 messages

def get_client():
    global _client
    if not _client:
        load_env()
        _client = anthropic.Anthropic()
    return _client

async def ai_respond(user_id: int, message: str, market_context: dict) -> str:
    """Generate AI response with live market context."""
    history = _chat_histories.setdefault(user_id, [])
    history.append({"role": "user", "content": message})
    if len(history) > 20:
        history[:] = history[-20:]

    system_prompt = f"""You are OpenClaw AI Trading Assistant.
Current market data:
- BTC Price: {market_context.get('btc_price', 'N/A')}
- Composite Score: {market_context.get('composite_score', 'N/A')}
- Position: {market_context.get('position', 'N/A')}
- Recent Signal: {market_context.get('signal', 'N/A')}
- Fear & Greed: {market_context.get('fear_greed', 'N/A')}

Answer in Korean. Be concise. If asked about trading decisions, explain the reasoning."""

    try:
        resp = get_client().messages.create(
            model="claude-haiku-4-5-20251001",
            max_tokens=500,
            system=system_prompt,
            messages=history
        )
        answer = resp.content[0].text
        history.append({"role": "assistant", "content": answer})
        return answer
    except Exception as e:
        log.error(f"Claude API error: {e}")
        return "AI 응답 실패. /help 로 명령어를 확인하세요."
```

### 4b. Integrate into `telegram_bot.py`

- In the message handler, add fallback: if no command matched, call `ai_respond()`
- New commands: `/why` (last decision reason), `/risk` (portfolio risk), `/agents` (agent status)

### 4c. Test

```bash
cd ~/openclaw && source .venv/bin/activate
python -c "
from common.telegram_ai import ai_respond
import asyncio
result = asyncio.run(ai_respond(123, '비트코인 지금 사도 될까?', {'btc_price': '82,450,000', 'composite_score': 65}))
print(result)
"
```

---

## AREA 5: AGENT SYSTEM VERIFICATION & LOGGING (P1)

### 5a. Agent Health Check

```bash
for log in phase14_signals phase15_signals phase16_signals btc_trading stock_trading us_trading; do
  echo "=== $log ==="
  tail -5 ~/.openclaw/logs/${log}.log
  echo "Last modified: $(stat -c %y ~/.openclaw/logs/${log}.log)"
done
```

### 5b. Decision Logging

Create Supabase table (schema already at `supabase/agent_decisions_schema.sql`):

```sql
CREATE TABLE IF NOT EXISTS agent_decisions (
  id bigint GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
  market text NOT NULL,
  agent_name text NOT NULL,
  action text NOT NULL,
  confidence float,
  reasoning text,
  context jsonb,
  created_at timestamptz DEFAULT now()
);
```

Add API endpoint in `btc/routes/btc_api.py`:

```python
@router.get("/api/decisions/{market}")
async def get_decisions(market: str, limit: int = 20):
    data = supabase.table("agent_decisions") \
        .select("*") \
        .eq("market", market) \
        .order("created_at", desc=True) \
        .limit(limit) \
        .execute()
    return api_success(data.data)
```

### 5c. Brain File Verification

```bash
cat ~/.openclaw/workspace/brain/agent_params.json | python3 -m json.tool
cat ~/.openclaw/workspace/brain/signal-ic/weights.json | python3 -m json.tool
cat ~/.openclaw/workspace/brain/alpha/best_params.json | python3 -m json.tool
```

---

## AREA 6: INFRASTRUCTURE & RELIABILITY (P2)

### 6a. Log Rotation

```bash
sudo tee /etc/logrotate.d/openclaw << 'EOF'
/home/wlsdud5035/.openclaw/logs/*.log {
    daily
    rotate 30
    compress
    delaycompress
    missingok
    notifempty
    copytruncate
}
EOF
sudo logrotate -d /etc/logrotate.d/openclaw
```

### 6b. Resource Monitoring

```bash
df -h /
du -sh ~/.openclaw/logs/
du -sh ~/openclaw/node_modules/
free -h
find ~ -type f -size +10M -exec ls -lh {} \; 2>/dev/null | sort -k5 -h
```

### 6c. BTC Agent CPU Investigation

```bash
# 84% CPU — check for tight polling loop
grep -n 'sleep\|time.sleep\|asyncio.sleep' ~/openclaw/btc/btc_trading_agent.py
top -p $(pgrep -f btc_trading_agent) -n 1 -b
```

### 6d. Cron Audit

```bash
crontab -l > ~/openclaw/docs/crontab_backup_$(date +%Y%m%d).txt
# Review for conflicts, missing lock files, correct paths
```

---

## AREA 7: SOLAR SHADOW MAP (P2)

**GitHub Repo:** https://github.com/zln02/solar-shadow-map-
**Stack:** React 19 + Three.js + Chart.js + Vite 8
**Local planning docs:** `~/CascadeProjects/sunlight-shadow-simulator/` (3 .md files, no code)

### Repo Structure
```
solar-shadow-map-/
├── index.html
├── package.json          (React 19, Three.js 0.183, Chart.js 4.5, Vite 8)
├── vite.config.js
├── eslint.config.js
├── public/
│   ├── favicon.svg
│   └── icons.svg
├── src/
│   ├── main.jsx
│   ├── App.jsx
│   ├── App.css
│   ├── ShadowSimulator.jsx   (핵심 3D 시뮬레이터)
│   ├── index.css
│   └── assets/ (hero.png, react.svg, vite.svg)
```

### 7a. Clone & Verify Build

```bash
# Step 1: Clone to dedicated project directory
cd ~ && git clone https://github.com/zln02/solar-shadow-map-.git solar-shadow-map

# Step 2: Install & test build
cd ~/solar-shadow-map
npm install
npm run build

# Step 3: Preview locally
npm run preview
# Check: http://localhost:4173
```

### 7b. Separate from OpenClaw

```bash
# Move planning docs from CascadeProjects to the actual project
cp ~/CascadeProjects/sunlight-shadow-simulator/*.md ~/solar-shadow-map/docs/
mkdir -p ~/solar-shadow-map/docs
mv ~/solar-shadow-map/PROJECT.md ~/solar-shadow-map/docs/ 2>/dev/null

# Verify no OpenClaw dependencies leak in
grep -r "openclaw\|upbit\|supabase" ~/solar-shadow-map/src/ || echo "CLEAN — no OpenClaw deps"

# Clean up CascadeProjects if empty after move
rmdir ~/CascadeProjects/sunlight-shadow-simulator 2>/dev/null
rmdir ~/CascadeProjects 2>/dev/null
```

### 7c. Prepare for Vercel Deployment

```bash
# Step 1: Create vercel.json
cat > ~/solar-shadow-map/vercel.json << 'EOF'
{
  "buildCommand": "npm run build",
  "outputDirectory": "dist",
  "framework": "vite",
  "rewrites": [
    { "source": "/(.*)", "destination": "/index.html" }
  ]
}
EOF

# Step 2: List required environment variables (if any)
grep -r "import.meta.env\|process.env" ~/solar-shadow-map/src/ || echo "No env vars needed"

# Step 3: Deploy via Vercel CLI (or connect GitHub repo in Vercel dashboard)
# npx vercel --prod
# OR: Go to vercel.com → Import Git Repository → zln02/solar-shadow-map-
```

### 7d. Optional Improvements
- Add `.nvmrc` with `20` (Node 20 LTS)
- Add `"homepage"` field to package.json
- Consider adding `@react-three/fiber` + `@react-three/drei` for cleaner Three.js integration (currently raw Three.js)

---

## RISK REGISTER

| Risk | Likelihood | Impact | Mitigation |
|------|-----------|--------|------------|
| Repo consolidation breaks live trading | Medium | CRITICAL | Snapshot first, update cron one-by-one, keep old workspace 2 weeks |
| Dashboard rebuild breaks UI | Low | Low | View-only, no trading impact |
| Telegram AI costs spike | Low | Low | Haiku (cheapest), 500 token limit |
| Killing wrong telegram_bot PID | Low | Medium | Verify PID first, watchdog restarts |
| Permission change breaks running process | Very Low | Medium | Already-open file handles unaffected |

---

## CODEX EXECUTION ORDER

### Phase 1: Security (P0) — 5 minutes
```bash
chmod 600 /home/wlsdud5035/.openclaw/openclaw.json
chmod 600 /home/wlsdud5035/.openclaw/.env
chmod 600 /home/wlsdud5035/.openclaw/workspace/skills/kiwoom-api/.env
chmod 600 /home/wlsdud5035/.openclaw/workspace/secretary/.env
chmod 600 /home/wlsdud5035/.openclaw/workspace/brain/kiwoom_token.json
# Kill duplicate telegram bot (verify PID first)
ps aux | grep telegram_bot
sudo kill 1528916
```

### Phase 2: Cleanup (P0) — 10 minutes
```bash
find ~/.openclaw/workspace -path '*/.venv' -prune -o -type d -name '__pycache__' -exec rm -rf {} + 2>/dev/null
find ~/openclaw -path '*/.venv' -prune -o -type d -name '__pycache__' -exec rm -rf {} + 2>/dev/null
rm -rf ~/.openclaw/workspace/catboost_info/
```

### Phase 3: Dashboard UI (P1) — 2-3 hours
Execute Area 3 changes in `~/openclaw/dashboard/src/`, build, restart.

### Phase 4: Telegram AI (P1) — 1 hour
Create `common/telegram_ai.py`, integrate, test.

### Phase 5: Agent Logging (P1) — 1 hour
Supabase table, API endpoint, wire into agents.

### Phase 6: Infrastructure (P2) — 30 minutes
Log rotation, resource audit, CPU investigation.

### Phase 7: Solar Shadow Map (P2) — 20 minutes
Clone repo, verify build, create vercel.json, clean up CascadeProjects.
