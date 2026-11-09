"""HarshCraftAI entry point.

    python run_bot.py                # typed commands
    python run_bot.py --voice        # microphone commands (optionally --wake "hey bot")
    python run_bot.py --say "get a stone pickaxe"     # run one command and exit when done
Start Minecraft (HarshCraft mod) and enter a world FIRST. Press F3+P once so the game doesn't pause when unfocused.
"""
import argparse
import sys
import threading
import time

from harshcraft_ai.agent import Bot
from harshcraft_ai.client import MCClient, MCError
from harshcraft_ai.llm import make_llm_parser
from harshcraft_ai.voice import Speaker, VoiceListener


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--voice", action="store_true")
    ap.add_argument("--wake", default=None, help="wake word, e.g. 'bot'")
    ap.add_argument("--tts", action="store_true", help="speak replies")
    ap.add_argument("--llm", action="store_true", help="use Anthropic API for commands the rules do not understand")
    ap.add_argument("--say", default=None)
    ap.add_argument("--url", default=None)
    a = ap.parse_args()

    client = MCClient(a.url) if a.url else MCClient()
    try:
        info = client.ping()
    except MCError as e:
        sys.exit(f"{e}\nIs Minecraft running with the HarshCraft mod and are you inside a world?")
    if not info.get("in_world"):
        sys.exit("Minecraft is running but you are not in a world yet.")
    bot = Bot(client, speak=Speaker() if a.tts else None)
    llm = make_llm_parser() if a.llm else None
    if a.llm and llm is None:
        print("[llm] ANTHROPIC_API_KEY not set; using rule parser only")
    bot.start()
    bot.say("HarshCraft bot ready.")

    if a.say:
        bot.command(a.say, llm)
        time.sleep(1.0)
        while bot.busy or not bot.q.empty():
            time.sleep(0.5)
        return

    if a.voice:
        vl = VoiceListener(a.wake)
        if vl.available:
            print(f"[voice] backend: {vl.backend}. Speak commands; say 'stop' to cancel. Typed commands also work.")

            def loop():
                while bot.running:
                    t = vl.listen()
                    if t:
                        print(f"[heard] {t}")
                        bot.command(t, llm)
            threading.Thread(target=loop, daemon=True).start()
        else:
            print("[voice] no speech backend installed (pip install faster-whisper sounddevice  OR  SpeechRecognition "
                  "pyaudio). Falling back to typed commands.")
    print("Type commands (e.g. 'get a stone pickaxe', 'kill zombies', 'build a house', 'stop', 'quit').")
    try:
        while True:
            line = input("> ").strip()
            if line in ("quit", "exit"):
                break
            if line:
                bot.command(line, llm)
    except (KeyboardInterrupt, EOFError):
        pass
    bot.shutdown()


if __name__ == "__main__":
    main()
