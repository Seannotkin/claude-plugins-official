# Instagram autoposter

Creates short vertical videos by itself, sends each one to you on Telegram, and posts it to
Instagram as a Reel only after you tap **Post it**.

```
Claude writes the script ─► free neural voiceover ─► stock footage (Pexels)
        ─► ffmpeg edit with captions ─► Telegram: ✅ Post it / 🔁 Redo / ❌ Drop ─► Instagram Reel
```

## Talking to it on Telegram

| You send | It does |
|---|---|
| any message, e.g. `3 mistakes people make with protein` | makes a video about that |
| `/new` | makes a video on a topic it chooses for your niche |
| `/niche home workouts for busy parents` | sets what the account is about |
| `/pause` and `/resume` | stops and restarts video making, for when you need the PC yourself |
| `/status` | says whether it is paused |
| tap ✅ / 🔁 / ❌ under a video | posts it / makes another one / drops it |
| reply to a video with `make the hook stronger` | remakes it with your feedback |
| reply to a video with `caption: new text` | changes only the caption |

It also makes videos on its own at the hours in `config.yaml` (`slots_utc`). Nothing is ever
posted without your tap, and the bot ignores everyone except your chat.

## What you need (all free except Claude usage)

1. **Telegram bot** – message `@BotFather`, send `/newbot`, copy the token → `TELEGRAM_BOT_TOKEN`.
   Send your new bot any message, then message `@userinfobot` to get your id → `TELEGRAM_CHAT_ID`.
2. **Claude API key** – console.anthropic.com → `ANTHROPIC_API_KEY`.
3. **Pexels key** (stock video) – pexels.com/api → `PEXELS_API_KEY`.
4. **Instagram** – the account must be Professional (Creator or Business) and linked to a
   Facebook Page. At developers.facebook.com create an app, add the Instagram product, and
   generate a token with `instagram_basic`, `instagram_content_publish` and `pages_show_list`
   → `IG_ACCESS_TOKEN`, and the Instagram account id → `IG_USER_ID`.
   Normal tokens expire after about 60 days; a System User token from Meta Business settings
   does not.

## Run it

**On Windows:** install [Python](https://www.python.org/downloads/) (tick "Add to PATH"), run
`winget install Gyan.FFmpeg` in a terminal, copy `.env.example` to `.env` and fill in the six
values, then double-click `start.bat`. Keep that window open; closing it stops the bot.

While paused the bot only listens for your messages, which uses almost no CPU. A video that is
already being made when you send `/pause` is finished first (a minute or two).

**On macOS or Linux** (answers Telegram instantly):

```bash
sudo apt install ffmpeg fonts-dejavu-core   # macOS: brew install ffmpeg
pip install -r requirements.txt
cp .env.example .env                        # fill in the six values
python -m autoposter check                  # confirms the keys and says hello on Telegram
python -m autoposter run
```

**Or free on GitHub Actions** (answers within about 10 minutes): put this folder at the root of
a new *private* repository, copy `github-workflows/autoposter.yml` to `.github/workflows/`,
and add the six values under Settings → Secrets and variables → Actions.

Set `DRY_RUN=1` to try the whole flow without posting.

## Good to know

- Put your own `.mp4` clips in a `footage/` folder and they are used instead of stock video.
- `voice.provider: none` in `config.yaml` makes caption-only videos.
- Videos posted through the API cannot use Instagram's music library.
- Tests: `python -m pytest tests` (renders a real video, fakes the outside services).
