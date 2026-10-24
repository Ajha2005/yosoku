# Partner figures: forecasts in money

The India Demand Index measures attention. To forecast money, Yosoku needs what past titles actually earned in
India, from a rights holder or platform. Those figures are confidential, so everything in this folder except this
README and the template stays out of git (`.gitignore`).

## What to send

`revenue.csv`, one row per title, with the columns of `revenue_template.csv`:

| Column | What goes in it |
| --- | --- |
| `anilist_id` | the title's AniList id (the number in its anilist.co address) |
| `title` | its name, for the partner's own checking; not used |
| `amount` | what it earned in India over **one fixed window for every title**, for example its first 90 days |
| `unit` | `JPY`, `INR`, `USD`, or `HOURS` for viewing hours; the same for every row |
| `notes` | anything that makes a row unusual (a re-release, a bundle deal) |

At least 30 of the titles must have an India Demand Index (released 2019–2024 and labelled); 30 to 50 is the
target. Licence fees, streaming revenue or viewing hours all work, as long as one kind is used throughout.

## What happens

    python -m yosoku.money                      # after python -m yosoku.run
    python -m yosoku.export_web --with-money    # only for a private site the partner has agreed to

`yosoku.money` fits the amounts to the index, checks the fit on each title left out in turn, and writes
`money.json` here: a range in the partner's unit for every forecast. The public site never shows it unless it is
exported with `--with-money`.
