"""Find comments written by people in India, and the language hub each one points to.

Most Indian fans comment in English or in Hinglish typed in Latin letters, not in Indian scripts
(fewer than 1 in 2,000 comments here use an Indian script). A comment counts as Indian if any of:

  script     it uses Devanagari, Bengali, Tamil, Telugu, Kannada or Malayalam letters
  hinglish   it has Hindi words typed in Latin letters: two from the strong list, or one strong
             plus two common ones. Common words alone ("hai", "ke") also occur in Japanese
             romaji and Italian, so they never count on their own.
  mention    it names India, an Indian language or a big Indian city
  lid        optional: IndicLID (collectors/detect_languages.py) reads it as an Indian language typed in
             Latin letters, and it has two Hindi words from any list here. This catches short Hinglish
             like "Kab release hogi ye movie" that the word rules miss. IndicLID alone is not enough: it
             only knows Indian languages and English, so it calls Spanish, Indonesian and emoji Indian too,
             and it mixes up which Indian language Hinglish is. Only its "Indian or not" is used.

dub_ask marks comments asking for or about an Indian-language dub ("hindi dub kab aayega", "please dub in
tamil"). Comments with a link are left out: those are mostly channels announcing a dub, not fans asking.

Hubs (for the regional view): a script, the language's name ("tamil dub pls") or, for Hindi,
Hinglish. A comment can point to no hub (English mentioning India) or to more than one.
Mostly a word list: it misses some Indian English and will catch a few non-Indian comments.
Check samples before trusting a number.
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
# Only counted together with IndicLID, never on their own.
LID_WORDS = (r"hoga|hogi|honge|hoge|liya|kiya|diya|badiya|badhiya|kha|kahan|kaha|kis|kisko|kisne|lao|jyada|zyada|"
             r"sundar|aaya|aya|gaya|raha|rahi|rahe|nai|tera|mera|tum|aap|hum|kar|karna|pura|pyar|maza|mazaa")
LID_MIN_PROB = 0.5
LID_MIN_WORDS = 3  # Latin words; shorter comments ("wow", "0:59") get confident but random labels
LANGS = r"hindi|tamil|telugu|bengali|bangla|kannada|malayalam|marathi"
DUB = (rf"\b(?:{LANGS})\s*(?:dub|dubbed|dubbing|version|audio|me|mein|mai)\b"
       rf"|\bdub(?:bed|bing)?\s+(?:in|me|mein|mai)\s+(?:{LANGS})\b")
MENTION = (r"india|indian|indians|hindi|marathi|tamil|telugu|bengali|bangla|kannada|malayalam|desi|"
           r"mumbai|delhi|bangalore|bengaluru|kolkata|chennai|hyderabad|pune|ahmedabad|jaipur|lucknow")


def classify(text, indic=None):
    """DataFrame (same index as text) of booleans: script, hinglish, mention, india, dub_ask and one column per hub.

    `indic` (optional, same index) is True where IndicLID read the comment as an Indian language; see indic_flags.
    """
    text = text.fillna("").astype(str)
    lower = text.str.lower()
    strong = lower.str.count(rf"\b(?:{STRONG})\b")
    common = lower.str.count(rf"\b(?:{COMMON})\b")
    out = pd.DataFrame(index=text.index)
    scripts = {hub: text.str.contains(f"[{letters}]", regex=True) for hub, (letters, _) in HUBS.items()}
    out["script"] = pd.concat(scripts, axis=1).any(axis=1)
    out["hinglish"] = (strong >= 2) | ((strong >= 1) & (common >= 2))
    if indic is not None:
        hindi_words = strong + common + lower.str.count(rf"\b(?:{LID_WORDS})\b")
        latin_words = lower.str.count(r"[a-z]{2,}")
        out["lid"] = indic.reindex(text.index, fill_value=False).astype(bool) & (hindi_words >= 2) & (
            latin_words >= LID_MIN_WORDS)
        out["hinglish"] |= out["lid"]
    out["mention"] = lower.str.contains(rf"\b(?:{MENTION})\b", regex=True)
    out["india"] = out["script"] | out["hinglish"] | out["mention"]
    out["dub_ask"] = lower.str.contains(DUB, regex=True) & ~lower.str.contains("http", regex=False)
    for hub, (_, names) in HUBS.items():
        out[hub] = scripts[hub] | lower.str.contains(rf"\b(?:{names})\b", regex=True)
    out["hindi"] |= out["hinglish"]
    return out


COUNTS = ["n", "india", "dub_ask", "any_hub", *HUBS]  # the columns of youtube_comment_daily.csv besides its keys


def daily_counts(comments, languages=None):
    """Comments per title, video and day (UTC): how many, and how many are Indian, ask for a dub or point to each hub.

    Everything merge.py and the models read from the comments, without their text, so this file can be shared
    and kept instead of youtube_comments.csv. `languages` as for indic_flags.
    """
    found = classify(comments["text"], indic_flags(comments, languages))
    flags = found[["india", "dub_ask", *HUBS]].astype(int).assign(any_hub=found[list(HUBS)].any(axis=1).astype(int), n=1)
    day = pd.to_datetime(comments["published_at"], utc=True).dt.strftime("%Y-%m-%d")
    keys = pd.DataFrame({"anilist_id": comments["anilist_id"], "video_id": comments["video_id"], "date": day})
    return pd.concat([keys, flags], axis=1).groupby(["anilist_id", "video_id", "date"], as_index=False)[COUNTS].sum()


def indic_flags(comments, languages):
    """Series (index of comments) that is True where IndicLID read the comment as an Indian language.

    `languages` is comment_languages.csv (comment_id, language, probability) or None; None gives None,
    so classify falls back to the word rules alone.
    """
    if languages is None:
        return None
    indian = languages[~languages["language"].isin(["eng_Latn", "other"])
                       & (languages["probability"] >= LID_MIN_PROB)]
    return comments["comment_id"].isin(indian["comment_id"])
