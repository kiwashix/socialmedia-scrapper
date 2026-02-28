# 🎮 Marathon News Bot

An automated Telegram bot that monitors multiple sources for news about **Marathon** (the upcoming Bungie extraction shooter), processes them with Claude AI, and posts summaries directly to your Telegram channel or chat.

---

## ✨ Features

- 🔄 **7 news sources** monitored automatically
- 🤖 **AI-powered** relevance filtering and summarisation (Claude Haiku)
- 📸 **Media support** — sends images inline, includes links to videos/GIFs
- 🔂 **Deduplication** — never sends the same item twice (SQLite-backed)
- ⏰ **Configurable polling** — default every 30 minutes
- 🏷 **Category labels** — Official Update, Media, Community, News, Rumour
- 📊 **Logging** — full logs to file + console

---

## 📡 Sources Monitored

| Source | Method | Notes |
|--------|--------|-------|
| **Bungie.net** | Official API | Direct from Bungie |
| **Reddit r/Marathon** | JSON API / PRAW | Filters by score |
| **Twitter @MarathonTheGame** | Nitter RSS | No API key required |
| **YouTube (Bungie channel)** | YouTube RSS | Filters Marathon videos |
| **Steam** | Steam News API | App ID 3065800 |
| **IGN, PCGamer, GamesRadar, Kotaku, Eurogamer, VG247, Polygon** | RSS feeds | Keyword-filtered |
| **marathonthegame.com** | HTML scraper | Official game site |

---

## 🚀 Quick Start

### 1. Clone / Download the project

```bash
cd marathon_bot
```

### 2. Install dependencies

```bash
pip install -r requirements.txt
```

> **Python 3.10+** is required.

### 3. Create your `.env` file

```bash
cp .env.example .env
```

Then fill in:

```env
TELEGRAM_BOT_TOKEN=your_token_here
TELEGRAM_CHAT_ID=your_chat_id_here
ANTHROPIC_API_KEY=your_key_here
```

### 4. Run the bot

```bash
python main.py
```

The bot will immediately do a first scan and then check every 30 minutes (configurable).

---

## ⚙️ Configuration Reference

All settings live in `.env`:

| Variable | Default | Description |
|----------|---------|-------------|
| `TELEGRAM_BOT_TOKEN` | required | From [@BotFather](https://t.me/botfather) |
| `TELEGRAM_CHAT_ID` | required | Your chat or channel ID |
| `GROQ_API_KEY` | required | API key for AI summaries |
| `POLL_INTERVAL_MINUTES` | `30` | How often to check for news |
| `REDDIT_MIN_SCORE` | `10` | Minimum Reddit post score to include |
| `MAX_ITEMS_PER_RUN` | `5` | Max items processed per source per run |
| `SUMMARY_LANGUAGE` | `English` | Language for AI summaries |
---

## 🔑 How to Get API Keys

### Telegram Bot Token
1. Open Telegram, message [@BotFather](https://t.me/botfather)
2. Send `/newbot`, follow prompts
3. Copy the token

### Telegram Chat ID
- **For yourself**: Send any message to your bot, then visit:
  `https://api.telegram.org/bot<TOKEN>/getUpdates`
  Look for `"chat": {"id": <YOUR_ID>}`
- **For a channel**: Add the bot as an admin to the channel, then use `@channel_username` as the chat ID

---

## 🌐 Twitter/X Note

Twitter/X severely restricts API access (paid plans start at ~$100/month). This bot uses **public Nitter instances** as a free workaround. Nitter instances can sometimes be down — if all fail, the bot will skip the Twitter source gracefully and log a warning.

**If you have Twitter API access**, edit `parsers/twitter.py` and replace `_fetch_nitter()` with an authenticated API call using `tweepy`.

---

## 🐳 Running with Docker (optional)

```dockerfile
FROM python:3.11-slim
WORKDIR /app
COPY requirements.txt .
RUN pip install -r requirements.txt
COPY . .
CMD ["python", "main.py"]
```

```bash
docker build -t marathon-bot .
docker run -d --env-file .env --restart unless-stopped marathon-bot
```

---

## 🖥 Running as a Systemd Service (Linux)

Create `/etc/systemd/system/marathon-bot.service`:

```ini
[Unit]
Description=Marathon News Telegram Bot
After=network.target

[Service]
Type=simple
User=your_user
WorkingDirectory=/path/to/marathon_bot
ExecStart=/usr/bin/python3 /path/to/marathon_bot/main.py
Restart=always
RestartSec=30

[Install]
WantedBy=multi-user.target
```

```bash
sudo systemctl enable marathon-bot
sudo systemctl start marathon-bot
sudo systemctl status marathon-bot
```

---

## 📂 Project Structure

```
marathon_bot/
├── main.py              # Entry point & scheduler
├── config.py            # Settings loader
├── database.py          # SQLite deduplication
├── ai_processor.py      # Claude AI summarisation & filtering
├── telegram_sender.py   # Telegram message sender
├── parsers/
│   ├── __init__.py      # Exports ALL_PARSERS list
│   ├── base.py          # Abstract base class
│   ├── bungie.py        # Bungie.net official API
│   ├── reddit.py        # Reddit r/Marathon
│   ├── twitter.py       # @MarathonTheGame via Nitter RSS
│   ├── youtube.py       # Bungie YouTube channel
│   ├── steam.py         # Steam store news
│   ├── gaming_news.py   # IGN, PCGamer, Kotaku, etc.
│   └── official_site.py # marathonthegame.com
├── requirements.txt
├── .env
└── README.md
```

---

## ➕ Adding More Sources

1. Create `parsers/my_source.py` inheriting from `BaseParser`
2. Implement the `async def fetch(self) -> List[NewsItem]:` method
3. Add your class to `parsers/__init__.py`'s `ALL_PARSERS` list

That's it — the bot will automatically pick it up.

---

## 💰 Cost Estimate

Using Claude Haiku (cheapest model, great for summarisation):
- ~$0.0008 per news item processed
- Running 24/7 at 30-min intervals with ~10 new items/day ≈ **< $0.01/day**

---

## 📝 License

MIT – use freely, modify, share.
