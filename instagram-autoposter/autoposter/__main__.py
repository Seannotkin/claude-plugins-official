"""python -m autoposter run | tick | new [brief] | check"""
import sys
import time

from . import pipeline
from . import telegram as tg
from .config import load_config, load_env_file, load_state, secret


def check():
    for name in ("ANTHROPIC_API_KEY", "TELEGRAM_BOT_TOKEN", "TELEGRAM_CHAT_ID", "PEXELS_API_KEY",
                 "IG_USER_ID", "IG_ACCESS_TOKEN"):
        secret(name)
    print("Telegram bot:", tg.call("getMe")["username"])
    tg.say("👋 Connected. Send /help to see what I can do.")
    print("All secrets present and Telegram works.")


def main():
    load_env_file()
    command = sys.argv[1] if len(sys.argv) > 1 else "run"
    cfg, state = load_config(), load_state()
    if command == "check":
        check()
    elif command == "tick":
        pipeline.tick(state, cfg)
    elif command == "new":
        pipeline.generate(state, cfg, brief=" ".join(sys.argv[2:]) or None)
    elif command == "run":
        print("Running. Ctrl+C to stop.")
        while True:
            try:
                pipeline.tick(state, cfg, wait=25)
            except Exception as e:  # network blips must not kill the bot
                print("tick failed:", e)
                time.sleep(10)
    else:
        sys.exit(__doc__)


if __name__ == "__main__":
    main()
