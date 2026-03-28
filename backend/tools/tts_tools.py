"""
TTS Tools — generates bilingual Hindi/English audio briefs.
Uses LLM-generated natural script + gTTS for audio synthesis.
Supports Hindi-only, English-only, and Hinglish (mixed) modes.
"""

import asyncio
import os
import logging
from gtts import gTTS

logger = logging.getLogger(__name__)

AUDIO_DIR = os.path.join(os.path.dirname(os.path.dirname(__file__)), "data", "audio")
os.makedirs(AUDIO_DIR, exist_ok=True)


def _build_hindi_script(company: str, headline: str, summary: str, confidence: float, what_to_watch: str = "") -> str:
    """Build a natural Hinglish audio script that sounds conversational."""
    # Clean up for audio
    company_mention = f"{company} ke baare mein" if company and company != "Unknown" else "market mein"

    script_parts = [
        f"Namaskar investors.",
        f"ET Mosaic ne {company_mention} ek important signal detect kiya hai.",
        f"Signal headline hai: {headline}.",
    ]

    # Add a conversational summary
    if summary:
        # Take first sentence only for brevity
        first_sentence = summary.split('. ')[0].strip()
        if first_sentence:
            script_parts.append(f"Analysis ke mutaabik, {first_sentence}.")

    # Confidence
    conf_int = int(confidence)
    if conf_int >= 75:
        script_parts.append(f"Is signal ki confidence {conf_int} percent hai, jo ki quite high hai.")
    elif conf_int >= 50:
        script_parts.append(f"Signal ki confidence {conf_int} percent hai, moderate level par.")
    else:
        script_parts.append(f"Abhi confidence level {conf_int} percent hai, toh cautiously monitor karein.")

    # What to watch
    if what_to_watch:
        script_parts.append(f"Aage dekhne wali cheez: {what_to_watch}.")

    script_parts.append("Yeh sirf research ke liye hai, investment advice nahi hai. Dhanyavaad.")

    return " ".join(script_parts)


def _build_english_script(company: str, headline: str, summary: str, confidence: float, what_to_watch: str = "") -> str:
    """Build a natural English audio script."""
    company_mention = company if company and company != "Unknown" else "the market"

    script_parts = [
        f"Hello investors.",
        f"ET Mosaic has detected an important signal regarding {company_mention}.",
        f"The signal headline reads: {headline}.",
    ]

    if summary:
        first_sentence = summary.split('. ')[0].strip()
        if first_sentence:
            script_parts.append(f"According to our analysis, {first_sentence}.")

    conf_int = int(confidence)
    if conf_int >= 75:
        script_parts.append(f"The confidence level is {conf_int} percent, which is notably high.")
    elif conf_int >= 50:
        script_parts.append(f"Confidence stands at {conf_int} percent, a moderate level.")
    else:
        script_parts.append(f"Current confidence is {conf_int} percent, so monitor cautiously.")

    if what_to_watch:
        script_parts.append(f"Key metric to watch: {what_to_watch}.")

    script_parts.append("This is for research purposes only, not investment advice. Thank you.")

    return " ".join(script_parts)


async def generate_hindi_audio(
    signal_id: str,
    company: str,
    summary_hindi: str,
    confidence: float,
    headline: str = "",
    what_to_watch: str = "",
    lang: str = "hi",
) -> str:
    """
    Generate an audio brief for a signal.
    lang: 'hi' for Hinglish, 'en' for English. Defaults to Hinglish.
    Returns the file path of the generated MP3.
    """
    try:
        def _generate():
            if lang == "en":
                text = _build_english_script(company, headline, summary_hindi, confidence, what_to_watch)
                tts_lang = "en"
            else:
                text = _build_hindi_script(company, headline, summary_hindi, confidence, what_to_watch)
                tts_lang = "hi"

            filepath = os.path.join(AUDIO_DIR, f"{signal_id}.mp3")
            tts = gTTS(text=text, lang=tts_lang, slow=False)
            tts.save(filepath)
            return filepath

        return await asyncio.to_thread(_generate)
    except Exception as e:
        logger.error(f"TTS generation error for {signal_id}: {e}")
        return ""
