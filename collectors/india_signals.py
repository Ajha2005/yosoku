"""Find comments written by people in India, and the language hub each one points to.

Most Indian fans comment in English or in Hinglish typed in Latin letters, not in Indian scripts
(fewer than 1 in 2,000 comments here use an Indian script). A comment counts as Indian if any of:

  script     it uses Devanagari, Bengali, Tamil, Telugu, Kannada or Malayalam letters
  hinglish   it has Hindi words typed in Latin letters: two from the strong list, or one strong
             plus two common ones. Common words alone ("hai", "ke") also occur in Japanese
             romaji and Italian, so they never count on their own.
  mention    it names India, an Indian language or a big Indian city

Hubs (for the regional view): a script, the language's name ("tamil dub pls") or, for Hindi,
Hinglish. A comment can point to no hub (English mentioning India) or to more than one.
This is a word list, not a language model: it misses some Indian English and will catch a few
non-Indian comments. Check samples before trusting a number.
"""

import pandas as pd

HUBS = {  # hub: (script letters, words that name the language)
    "hindi": ("ऀ-ॿ", r"hindi|marathi"),
    "bengali": ("ঀ-৿", r"bengali|bangla"),
    "tamil": ("஀-௿", r"tamil"),
    "telugu": ("ఀ-౿", r"telugu"),
    "kannada": ("ಀ-೿", r"kannada"),
    "malayalam": ("ഀ-ൿ", r"malayalam"),
}
STRONG = (r"bhai|bhaiya|nahi|nahin|nhi|kya|kyu|kyun|kyon|yaar|yar|accha|acha|achha|achi|achhi|bahut|bohot|bhot|"
          r"bhaut|kab|aayega|ayega|aaega|chahiye|chaiye|dekh|dekho|dekhna|dekha|kuch|kaise|kaisa|jaldi|matlab|"
          r"mujhe|hume|humko|bilkul|ekdum|zabardast|jabardast|karo|kardo|krdo|wala|wali|waala|walo|isko|usko|"
          r"iska|uska|apna|abhi|sabse|lekin|pehle|pehli")
COMMON = r"hai|hain|toh|bhi|mein|mai|aur|tha|thi|ke|ki|ka|ko|ye|yeh|wo|woh|sab|ab"
MENTION = (r"india|indian|indians|hindi|marathi|tamil|telugu|bengali|bangla|kannada|malayalam|desi|"
           r"mumbai|delhi|bangalore|bengaluru|kolkata|chennai|hyderabad|pune|ahmedabad|jaipur|lucknow")


def classify(text):
    """DataFrame (same index as text) of booleans: script, hinglish, mention, india, and one column per hub."""
    text = text.fillna("").astype(str)
    lower = text.str.lower()
    strong = lower.str.count(rf"\b(?:{STRONG})\b")
    common = lower.str.count(rf"\b(?:{COMMON})\b")
    out = pd.DataFrame(index=text.index)
    scripts = {hub: text.str.contains(f"[{letters}]", regex=True) for hub, (letters, _) in HUBS.items()}
    out["script"] = pd.concat(scripts, axis=1).any(axis=1)
    out["hinglish"] = (strong >= 2) | ((strong >= 1) & (common >= 2))
    out["mention"] = lower.str.contains(rf"\b(?:{MENTION})\b", regex=True)
    out["india"] = out["script"] | out["hinglish"] | out["mention"]
    for hub, (_, names) in HUBS.items():
        out[hub] = scripts[hub] | lower.str.contains(rf"\b(?:{names})\b", regex=True)
    out["hindi"] |= out["hinglish"]
    return out
