// 稟議書: the forecast sheet's decision as a one-page Japanese brief, laid out the way a Japanese company approves one
// (ringi-sho): conclusion, grounds, precedents, risks and the next decision dates, with boxes for the approvers' seals.
// Built only from what the sheet shows. The Japanese is templated by machine: a fluent speaker should check it first.

import { VERDICTS, esc, round, pct } from "./data.js?v=12";

const GENRE = {
  Action: "アクション", Adventure: "冒険", Comedy: "コメディ", Drama: "ドラマ", Ecchi: "お色気", Fantasy: "ファンタジー", Horror: "ホラー",
  "Mahou Shoujo": "魔法少女", Mecha: "ロボット", Music: "音楽", Mystery: "ミステリー", Psychological: "心理", Romance: "恋愛",
  "Sci-Fi": "SF", "Slice of Life": "日常", Sports: "スポーツ", Supernatural: "超常", Thriller: "サスペンス",
};
const SOURCE = {
  MANGA: "漫画", LIGHT_NOVEL: "ライトノベル", ORIGINAL: "オリジナル", VIDEO_GAME: "ゲーム", VISUAL_NOVEL: "ノベルゲーム",
  NOVEL: "小説", WEB_NOVEL: "Web小説", OTHER: "その他",
};
const FORMAT = { TV: "TVシリーズ", TV_SHORT: "TV（短編）", MOVIE: "劇場版", ONA: "配信（ONA）", OVA: "OVA", SPECIAL: "特番" };
const AUDIENCE = { Kids: "児童向け", "Teens (boys)": "少年向け", "Teens (girls)": "少女向け", "Adults (men)": "青年向け", "Adults (women)": "女性向け" };
const HUB = { Hindi: "ヒンディー語", Bengali: "ベンガル語", Tamil: "タミル語", Telugu: "テルグ語", Kannada: "カンナダ語", Malayalam: "マラヤーラム語" };
const SEASON = { Winter: "冬", Spring: "春", Summer: "夏", Fall: "秋" };
const STAGE = { cold: "放送前（話題データなし）", "t-28": "放送28日前", "t+7": "放送7日後" };
const RULE = {
  "Genre average": "ジャンル平均", "Sequel carry-over": "前作の実績", "Global buzz (en+ja Wikipedia)": "英語・日本語Wikipediaの閲覧数",
  "India Wikipedia alone": "インドの言語のWikipedia閲覧数", "India YouTube alone": "インドからの予告編コメント数",
};
const DRIVER = {
  "Global buzz": "世界での話題（Wikipedia閲覧数）", "India buzz": "インドでの話題（予告編へのコメント）",
  "Franchise history": "シリーズ作品のインドでの実績", "Similar past titles": "類似作品のインドでの実績",
};
const WINDOW = [  // the release-window warnings of yosoku/decision.py, by their first words
  ["Festive", "祭事シーズン（ディワリ、10〜11月）：公開作品が多く、余暇の支出も大きい"],
  ["Board exams", "統一試験期間（2〜3月）：中心視聴層の学生の視聴が減る"],
  ["IPL", "IPLクリケット（3月下旬〜5月）：夜の視聴時間を奪い合う"],
];
const RECOMMEND = {
  Launch: () => "インドでの本格展開を推奨します。ライセンス、宣伝、配信日程を今の段階で決めます。80%範囲の全体が投入ラインを上回っています。",
  "Test-market": (moment) => (moment === "t+7"
    ? "限定展開を継続します。初週の反応は、本格展開にも撤退にも決め手を欠いています。"
    : "限定的な展開でのライセンスを推奨します。宣伝費を抑えた字幕配信とし、最低保証（MG）は小さく、放送7日後の判定に連動する追加支払いを条件に加えます。学びを得つつ、撤退も容易な形です。"),
  Hold: (moment) => (moment === "t+7"
    ? "インドでの展開は見送り、または延期を推奨します。初週のインドでの関心が低いままです。"
    : "現時点では契約を見送ります。80%範囲の全体が見送りラインを下回っています。初週に話題が出た場合に限り再検討します。"),
};

/** An amount as a Japanese brief writes it: 万円 and 億円 for yen, the unit otherwise. */
function amountJa(x, money) {
  if (money.unit === "JPY") return x >= 1e8 ? `${(x / 1e8).toFixed(1)}億円` : `${Math.round(x / 1e4).toLocaleString("ja-JP")}万円`;
  if (money.unit === "HOURS") return `${Math.round(x).toLocaleString("ja-JP")}時間`;
  return `${money.symbol}${Math.round(x).toLocaleString("ja-JP")}`;
}

/** Country names in Japanese, from their codes (the browser knows them); the English name if it does not. */
function regionJa() {
  let names = null;
  try { names = new Intl.DisplayNames(["ja"], { type: "region" }); } catch { /* an old browser: English names */ }
  return (c) => { try { return names?.of(c.iso2) || c.name; } catch { return c.name; } };
}

const jaDate = (iso) => { const [y, m, d] = iso.split("-").map(Number); return `${y}年${m}月${d}日`; };
const addDays = (iso, days) => new Date(Date.parse(`${iso}T00:00:00Z`) + days * 864e5).toISOString().slice(0, 10);
const signed = (x) => `${x >= 0 ? "+" : "−"}${Math.abs(x).toFixed(1)}`;
const two = (x) => (Number.isFinite(x) ? x.toFixed(2) : "–");
const seasonJa = (s) => { const [name, year] = String(s).split(" "); return SEASON[name] ? `${year}年${SEASON[name]}` : s; };
const byKey = (map, value) => Object.entries(map).find(([k]) => k.toLowerCase().replace(/_/g, " ") === String(value).toLowerCase())?.[1];

/** A driver's name ("India buzz", "Genre: Drama", "Format: Ona") in Japanese. */
function driverJa(name) {
  if (DRIVER[name]) return DRIVER[name];
  const [kind, value] = name.split(": ");
  const named = { Genre: ["ジャンル", GENRE], Format: ["形式", FORMAT], Source: ["原作", SOURCE], Audience: ["対象層", AUDIENCE] }[kind];
  return named ? `${named[0]}（${byKey(named[1], value) || value}）` : name;
}

/** Why a past title is a precedent: what it shares with this one (the genres go without saying within a series). */
function sharedJa(s) {
  if (!s) return "";
  return [s.franchise ? "同シリーズ" : s.genres.length ? `ジャンル：${s.genres.map((g) => GENRE[g] || g).join("・")}` : "",
    s.studio ? `同スタジオ（${s.studio}）` : "", s.source ? `${SOURCE[s.source] || s.source}原作` : "",
    s.format ? FORMAT[s.format] || s.format : "", s.audience ? AUDIENCE[s.audience] || "" : "",
    s.tags ? `共通タグ${s.tags}件` : ""].filter(Boolean).join("、");
}

/** Where a past title's India Demand Index sits against this stage's verdict lines. */
function placeJa(x, lines) {
  if (x == null) return "未測定";
  return `${round(x)}（${x >= lines.launch_line ? "投入圏" : x < lines.hold_line ? "見送り圏" : "中間"}）`;
}

/** The chance of a top-third result, where the backtests show it (models.top_third), with its record. */
function chanceJa(f, top) {
  if (f.top_third == null || !top) return "";
  return `<p>インドで上位3分の1（需要指数${round(top.line_live)}以上）に入る確率：<b>${pct(f.top_third)}</b>${top.sure_calls
    ? `（過去の検証では、確率${pct(top.sure)}以上とした${top.sure_calls}件のうち${pct(top.sure_right)}が実際に上位3分の1）` : ""}</p>`;
}

/** The rows of 次の判断日: the stages still ahead of an upcoming title, and when its index is written. */
function nextDates(t, data) {
  if (t.group !== "upcoming") {
    return `<p>放送済み（${t.start_date ? jaDate(t.start_date) : esc(seasonJa(t.season))}）。過去の作品で手法を検証するための予測です。</p>`;
  }
  if (!t.start_date) return "<p>放送日は未発表です。発表され次第、放送28日前と放送7日後に再判定します。</p>";
  const clock = data.clock || [], at = (day) => clock.find((d) => d.day === day)?.rolling;
  const later = data.thresholds["t+7"];
  const rows = [
    [-28, "T−28判定", "予告編とWikipediaへの反応を加えて再判定する"],
    [3, "吹替・宣伝の準備", `吹替と宣伝の準備を始めるかを判断する（過去20シーズンの検証で、放送3日後の順位相関は${two(at(3))}、放送1週間前は${two(at(-7))}）`],
    [7, "T+7判定", `本格展開と吹替の最終判断（投入ライン${later?.launch_line ?? "–"}、見送りライン${later?.hold_line ?? "–"}）`],
    [28, "指数の確定", "インド需要指数が確定し、封印した予測が採点される"],
  ].map(([days, what, todo]) => {
    const when = addDays(t.start_date, days), done = when < data.generated;
    return `<tr class="${done ? "r-done" : ""}"><td class="r-nowrap">${jaDate(when)}${done ? "（済）" : ""}</td><td class="r-nowrap">放送${days < 0 ? `${-days}日前` : `${days}日後`}</td><td><b>${what}</b>：${todo}</td></tr>`;
  }).join("");
  return `<table class="r-sub"><thead><tr><th>日付</th><th>時点</th><th>判断すること</th></tr></thead><tbody>${rows}</tbody></table>`;
}

/** The whole brief, for #print-root. `seal` is the latest seal's ledger row (data/sealed/latest.json), if any. */
export function ringiHTML(t, moment, data, seal) {
  const f = t.forecasts[moment];
  const th = data.thresholds[moment];
  const lines = f.sealed ? { launch_line: f.sealed.launch_line, hold_line: f.sealed.hold_line } : th;
  const ev = data.evaluation?.moments?.[moment], used = ev?.used ?? ev?.main;
  const name = t.title_japanese || t.name;
  const today = new Date().toLocaleDateString("ja-JP", { timeZone: "Asia/Tokyo", year: "numeric", month: "long", day: "numeric" });

  const facts = [t.start_date ? `放送開始 ${jaDate(t.start_date)}` : `${seasonJa(t.season)}（放送日未発表）`, FORMAT[t.format] || t.format,
    `原作：${SOURCE[t.source] || t.source}`, `ジャンル：${t.genres.map((g) => GENRE[g] || g).join("・")}`,
    AUDIENCE[t.audience] || "", t.is_sequel ? "続編" : ""].filter(Boolean).join("　／　");

  const rule = lines.launch_line === lines.hold_line
    ? `80%範囲の下端が${lines.launch_line}以上なら投入推奨、上端が${lines.hold_line}未満なら見送り、それ以外はテスト販売`
    : `80%範囲の下端が投入ライン（${lines.launch_line}）以上なら投入推奨、上端が見送りライン（${lines.hold_line}）未満なら見送り、それ以外はテスト販売`;
  const sealed = f.sealed ? `<p class="r-small">この予測は${jaDate(f.sealed.date)}に封印済みで、放送後はこの数値で採点されます。${f.now && f.now.index !== f.index
    ? `現在のモデルによる本日の予測は ${round(f.now.index)}（80%範囲 ${round(f.now.low)}〜${round(f.now.high)}）です。` : ""}</p>` : "";

  // 根拠: how the forecast was made, and the evidence on the sheet.
  const grounds = [];
  const ruleName = RULE[th.method];
  if (ruleName) grounds.push(`この時点の予測は単純ルール「${ruleName}」によるものです。2024年の検証で当社モデルを上回ったため採用しています。`);
  else if (f.drivers.length) grounds.push(`当社モデルによる予測です。主な要因：${f.drivers.slice(0, 3).map((d) => `${driverJa(d.name)} ${signed(d.points)}`).join("、")}（平均的な作品との差、指数ポイント）。`);
  const dub = f.dub_demand || {};
  if (dub.share != null) {
    const typical = Number.isFinite(data.dub_typical) ? `（平均的な作品では${pct(data.dub_typical)}）` : "";
    grounds.push(dub.share > 0
      ? `吹替需要：類似作品${dub.titles}本の予告編に寄せられたインドからのコメントのうち${pct(dub.share)}が、ヒンディー語などインドの言語での吹替を求めています${typical}。`
      : `吹替需要：類似作品${dub.titles}本の予告編に寄せられたインドからのコメントに、インドの言語での吹替を求める声はありませんでした${typical}。`);
  }
  const hubs = Object.entries(f.regions || {}).filter(([, s]) => s >= 0.1).sort((a, b) => b[1] - a[1]);
  if (hubs.length) {
    grounds.push(`言語ハブ：${hubs.map(([h, s]) => `${HUB[h] || h} ${pct(s)}`).join("、")}（言語を示すコメント${f.region_comments ?? "–"}件に基づく推定）。`);
  }
  if (t.travel?.countries?.length) {
    const m = t.travel, ja = regionJa();
    const list = m.countries.filter((c) => c.iso2 !== "IN").slice(0, 4).map((c) => `${ja(c)}${c.titles}本`).join("、");
    const india = m.countries.find((c) => c.iso2 === "IN");
    grounds.push(`他の市場：Netflixのいずれかの国でTop 10に入った類似作品${m.of}本のうち、${list}がその国でもTop 10入りしました（放送開始から6か月以内${india ? `。インドは${india.titles}本` : ""}）。`);
  }
  if (t.actual_index != null) {
    const inside = t.actual_index >= f.low && t.actual_index <= f.high;
    grounds.push(`実績：インド需要指数 ${round(t.actual_index)}（予測との差 ${signed(t.actual_index - f.index)}、80%範囲の${inside ? "内" : "外"}）。`);
  }

  // 前例: the closest past titles, why they are close, and how they did.
  const looks = (f.lookalikes || []).slice(0, 3);
  const known = looks.filter((l) => l.india_index != null);
  const precedents = looks.length ? `<table class="r-sub r-looks"><colgroup><col style="width:31%"><col style="width:6%"><col style="width:7%"><col style="width:41%"><col style="width:15%"></colgroup>
    <thead><tr><th>類似作品</th><th>年</th><th>類似度</th><th>共通点</th><th>インド需要指数</th></tr></thead><tbody>${looks.map((l) => `
      <tr><td><b>${esc(l.title_japanese || l.name)}</b>${l.title_japanese ? `<br><span class="r-small">${esc(l.name)}</span>` : ""}</td><td>${esc(l.year ?? "–")}</td>
        <td>${two(l.similarity)}</td><td>${esc(sharedJa(l.shared))}</td><td>${placeJa(l.india_index, lines)}</td></tr>`).join("")}</tbody></table>
    ${known.length ? `<p class="r-small">類似作品${known.length}本のインド需要指数の平均は ${round(known.reduce((a, l) => a + l.india_index, 0) / known.length)}（本作の予測は ${round(f.index)}）。投入圏は投入ライン以上、見送り圏は見送りライン未満。類似度は、ジャンル・タグ・原作・形式・スタジオ・対象層・あらすじの語から算出しています。</p>` : ""}`
    : "<p>比較できる過去作品がありません。</p>";

  // リスク: how far to trust this.
  const risks = [];
  const rolling = ev?.table?.rolling_spearman?.[used];
  if (moment === "cold") risks.push(`放送前の予測で、話題データを使っていません。過去20シーズンの検証で、作品の順位を当てる精度（順位相関）は${two(rolling)}にとどまります。`);
  else if (moment === "t-28") risks.push(`放送28日前の予測です。過去20シーズンの検証での順位相関は${two(rolling)}です。`);
  else risks.push(`初週のデータを含む「実況値」で、純粋な予測ではありません（過去20シーズンの順位相関 ${two(rolling)}）。`);
  const split = ev?.coverage_by_part;
  if (Number.isFinite(ev?.coverage)) {
    risks.push(`80%範囲は${round(f.low)}〜${round(f.high)}です。2024年の検証で実績が80%範囲に収まったのは${pct(ev.coverage)}でした（目標70〜90%）${split?.youtube_titles
      ? `。YouTubeのデータを含む作品では${pct(split.youtube)}、含まない作品では${pct(split.other)}です` : ""}。${t.group === "upcoming"
      ? "放送前の作品の範囲は、YouTubeのデータを含む過去作品の外れ幅から広めに設定しています。" : ""}`);
  }
  if (f.region_comments != null && f.region_comments < 30) risks.push(`言語ハブの推定は、コメント${f.region_comments}件のみに基づく参考値です。`);
  for (const flag of t.release_window_flags || []) {
    const ja = WINDOW.find(([start]) => flag.startsWith(start));
    if (ja) risks.push(`公開時期：${ja[1]}。`);
  }
  risks.push("インド需要指数は、YouTube・Netflix・Wikipediaでのインドの関心を合成した0〜100の指標で、売上や視聴者数そのものではありません。");

  const sealRow = t.sealed ? `封印：${jaDate(t.sealed.date)}（${esc(t.sealed.file)}${seal?.file === t.sealed.file && seal.sha256 ? `、SHA-256 ${esc(seal.sha256.slice(0, 16))}…` : ""}）。公開台帳で照合できます。` : "";
  return `<article class="ringi-doc" lang="ja">
    <div class="r-top">
      <div><h1>稟議書（案）</h1><p class="r-meta">起案日 ${esc(today)}　／　データ時点 ${jaDate(data.generated)}　／　作成 Yosoku 予測（自動生成）</p></div>
      <table class="r-hanko" aria-label="承認欄"><tr><th>起案</th><th>課長</th><th>部長</th><th>決裁</th></tr><tr><td></td><td></td><td></td><td></td></tr></table>
    </div>
    <p class="r-subject">件名：インド向けライセンスの判断　「${esc(name)}」</p>
    <table class="r-form"><tbody>
      <tr><th>作品</th><td><b>${esc(name)}</b>${t.title_japanese ? `（${esc(t.name)}）` : ""}<br><span class="r-small">${esc(facts)}</span></td></tr>
      <tr><th>結論</th><td>
        <p class="r-verdict"><span class="r-stamp">${esc(VERDICTS[f.verdict].ja)}</span>インド需要指数の予測 <b>${round(f.index)}</b>（80%範囲 ${round(f.low)}〜${round(f.high)}）　判定時点：${STAGE[moment]}</p>
        ${chanceJa(f, ev?.top_third)}
        ${f.money && data.money ? `<p>インドでの${data.money.unit === "HOURS" ? "視聴時間" : "売上"}見込み：<b>${esc(amountJa(f.money.point, data.money))}</b>（80%範囲 ${esc(amountJa(f.money.low, data.money))}〜${esc(amountJa(f.money.high, data.money))}。過去${esc(data.money.titles)}作品の実績から推定）</p>` : ""}
        <p>${RECOMMEND[f.verdict](moment)}</p>
        <p class="r-small">判定ルール：${rule}。</p>${sealed}</td></tr>
      <tr><th>根拠</th><td><ul>${grounds.map((g) => `<li>${esc(g)}</li>`).join("")}</ul></td></tr>
      <tr><th>前例</th><td>${precedents}</td></tr>
      <tr><th>リスク</th><td><ul>${risks.map((r) => `<li>${esc(r)}</li>`).join("")}</ul></td></tr>
      <tr><th>次の<br>判断日</th><td>${nextDates(t, data)}</td></tr>
    </tbody></table>
    <p class="r-foot">${sealRow}${esc(location.href)}<br>本書の日本語は自動生成です。社外で使用する前に、日本語話者による確認を行ってください。</p>
  </article>`;
}
