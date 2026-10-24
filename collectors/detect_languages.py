"""Step 4b (optional): which language each YouTube comment typed in Latin letters is in, by IndicLID.

IndicLID is AI4Bharat's language-ID model for Indian languages. This step uses its fast romanized
model (IndicLID-FTR, fastText) on every comment from youtube_comments.csv that uses Latin letters
only, and writes

  data/comment_languages.csv   comment_id, language (e.g. hin_Latn, eng_Latn, other), probability

merge.py and the models read it when it exists: a comment counts as Hinglish if IndicLID calls it an
Indian language and it has two Hindi words (see india_signals.py). Without the file nothing changes.
The file is small and committed, so only one person needs to run this.

Needs `pip install fasttext` (not in requirements.txt, it needs a C++ compiler on some laptops)
and the model, a 230 MB download from GitHub, saved in data/raw/indiclid/ the first time.
Comments already in comment_languages.csv are skipped, so rerun it after collecting more comments.

    python collectors/detect_languages.py
"""

import argparse
import sys
import zipfile

import pandas as pd

from common import RAW_DIR, add_data_dir_argument, data_file, india_only, session, use_data_dir

MODEL_URL = "https://github.com/AI4Bharat/IndicLID/releases/download/v1.0/indiclid-ftr.zip"
MODEL_PATH = RAW_DIR / "indiclid" / "indiclid-ftr" / "model_baseline_roman.bin"
COMMENTS_CSV = "youtube_comments.csv"
OUT_CSV = "comment_languages.csv"
LATIN_ONLY = r"^[\x00-\x7F -ɏ -⯿\U0001F000-\U0001FFFF️]*$"  # ASCII, accents, emoji


def download_model():
    archive = MODEL_PATH.parent.parent / "indiclid-ftr.zip"
    archive.parent.mkdir(parents=True, exist_ok=True)
    print(f"Downloading IndicLID-FTR (230 MB) to {archive.parent}")
    with session.get(MODEL_URL, stream=True, timeout=60) as response:
        response.raise_for_status()
        with open(archive, "wb") as f:
            for chunk in response.iter_content(1 << 20):
                f.write(chunk)
    with zipfile.ZipFile(archive) as z:
        z.extractall(archive.parent)
    archive.unlink()


def main():
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    add_data_dir_argument(parser)
    args = parser.parse_args()
    use_data_dir(args.data_dir, args.market)
    india_only("Language detection on trailer comments")
    try:
        import fasttext
    except ImportError:
        sys.exit("This step needs fastText: pip install fasttext")
    comments_path = data_file(COMMENTS_CSV)
    if not comments_path.exists():
        sys.exit(f"{comments_path} not found. Run `python collectors/collect_youtube.py` first.")
    if not MODEL_PATH.exists():
        download_model()

    comments = pd.read_csv(comments_path, encoding="utf-8-sig", usecols=["comment_id", "text"])
    comments = comments.drop_duplicates("comment_id")
    comments["text"] = comments["text"].fillna("").astype(str)
    out_path = data_file(OUT_CSV)
    done = pd.read_csv(out_path, encoding="utf-8-sig") if out_path.exists() else None
    todo = comments[comments["text"].str.match(LATIN_ONLY) & comments["text"].str.strip().ne("")]
    if done is not None:
        todo = todo[~todo["comment_id"].isin(done["comment_id"])]
    print(f"{len(todo)} new comments in Latin letters to label")

    if len(todo):
        model = fasttext.load_model(str(MODEL_PATH))
        # fastText reads one line at a time, and IndicLID was trained on lowercase text.
        lines = todo["text"].str.replace(r"\s+", " ", regex=True).str.lower().tolist()
        labels, probs = model.predict(lines, k=1)
        found = pd.DataFrame({"comment_id": todo["comment_id"].to_numpy(),
                              "language": [label[0].removeprefix("__label__") for label in labels],
                              "probability": [round(min(float(p[0]), 1.0), 4) for p in probs]})
        done = found if done is None else pd.concat([done, found])
    if done is None:
        return
    done = done[done["comment_id"].isin(comments["comment_id"])].sort_values("comment_id")
    done.to_csv(out_path, index=False, encoding="utf-8-sig")
    indian = ~done["language"].isin(["eng_Latn", "other"])
    print(f"Wrote {out_path}: {len(done)} comments, {indian.sum()} read as an Indian language "
          "(most are not: see india_signals.py for how they are used)")


if __name__ == "__main__":
    main()
