#!/usr/bin/env python3
"""
Manual Reply Helper - Generate witty replies without API limits

Usage:
    python reply_helper.py

Paste a reply you received, get an AI-generated response back.
No Twitter API needed - just copy/paste manually.
"""

import os
import sys
from google.cloud import aiplatform
import vertexai
from vertexai.generative_models import GenerativeModel

# Bot personality for consistent voice
BOT_PERSONALITY = """You are a cynical tech industry veteran running a Twitter account.
Your style:
- Dry wit, subtle sarcasm
- Call out hype but acknowledge real innovation
- Short, punchy responses (under 200 chars ideal)
- No emojis unless ironic
- Sound like someone who's seen every tech cycle since the 90s

Generate a reply that engages with their point while staying in character."""


def generate_reply(their_reply: str, original_post: str = "") -> str:
    """Generate a witty reply using Gemini."""

    project_id = os.environ.get("PROJECT_ID", "patriot-system-ai")

    try:
        vertexai.init(project=project_id, location="us-central1")
        model = GenerativeModel("gemini-1.5-flash-002")

        prompt = f"""{BOT_PERSONALITY}

{"ORIGINAL POST (yours): " + original_post if original_post else ""}

THEIR REPLY TO YOU:
{their_reply}

Generate 3 reply options (short, punchy, in character). Format:
1. [reply]
2. [reply]
3. [reply]"""

        response = model.generate_content(prompt)
        return response.text

    except Exception as e:
        return f"Error generating reply: {e}"


def main():
    print("\n" + "="*60)
    print("🤖 MANUAL REPLY HELPER - No API Limits!")
    print("="*60)
    print("\nPaste replies from Twitter, get AI responses back.")
    print("Type 'quit' to exit.\n")

    while True:
        print("-"*40)
        original = input("\n📝 Your original post (optional, press Enter to skip):\n> ").strip()

        if original.lower() == 'quit':
            break

        their_reply = input("\n💬 Their reply to you:\n> ").strip()

        if their_reply.lower() == 'quit':
            break

        if not their_reply:
            print("❌ Please paste their reply")
            continue

        print("\n⏳ Generating replies...")
        result = generate_reply(their_reply, original)

        print("\n" + "="*40)
        print("📤 SUGGESTED REPLIES:")
        print("="*40)
        print(result)
        print("\n✅ Copy your favorite and post it manually on Twitter!")


if __name__ == "__main__":
    main()
