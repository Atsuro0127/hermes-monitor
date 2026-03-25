import fs from 'fs';
import path from 'path';

// ── Types ────────────────────────────────────────────────────────────────────

interface Article {
  articleId: string;
  tweetId: string;
  tweetUrl: string;
  lang: 'ja' | 'unknown';
  title: string;
  body: string;
  preview: string;
  thumbnail: string;
  author: {
    name: string;
    screenName: string;
    bio: string;
    followersCount: number;
  };
  stats: {
    likes: number;
    retweets: number;
    replies: number;
    quotes: number;
    bookmarks: number;
    views: number;
  };
  engagementScore: number;
  createdAt?: string;
  source: string;
}

type Category =
  | 'consultant_career'
  | 'thinking_docs'
  | 'sales_clientwork'
  | 'ai_productivity'
  | 'independent_work'
  | 'other';

interface EnrichedArticle extends Article {
  category: Category;
  matchedKeywords: string[];
  why_useful_for_my_account: string;
  suggested_angle: string;
  priority_score: number;
  engagement_score: number;
  final_score: number;
}

// ── Helpers ───────────────────────────────────────────────────────────────────

/** TwitterスノーフレークIDから投稿日時を復元 */
function snowflakeToDate(id: string): string {
  try {
    const ms = Number(BigInt(id) >> 22n) + 1288834974657;
    return new Date(ms).toLocaleString('ja-JP', { timeZone: 'Asia/Tokyo' });
  } catch {
    return '不明';
  }
}

/** ひらがな・カタカナ・漢字を含む = 日本語テキスト */
const JP_REGEX = /[\u3040-\u309f\u30a0-\u30ff\u4e00-\u9fff]/;
function hasJapanese(text: string): boolean {
  return JP_REGEX.test(text);
}

// ── Classification keywords ───────────────────────────────────────────────────

// 強キーワード: 1件だけのヒットでも分類する
const STRONG_KEYWORDS: Record<Exclude<Category, 'other'>, string[]> = {
  consultant_career: [
    'コンサル', 'コンサルタント', 'ケース面接', 'コンサルファーム', 'フリーコンサル',
    'MBB', 'BCG', 'マッキンゼー', 'ベイン', 'デロイト', 'アクセンチュア', 'PEファンド',
  ],
  thinking_docs: [
    '論点', '仮説思考', 'MECE', 'イシュー', 'ロジカルシンキング', 'So What', '仕事術',
  ],
  sales_clientwork: [
    'クライアントワーク', '提案書', '顧客折衝', '商談', 'RFP',
  ],
  ai_productivity: [
    '生成AI', 'ChatGPT', 'Claude', 'LLM', 'プロンプト', 'OpenAI', 'Anthropic',
    'Perplexity', 'AIエージェント', 'Copilot', 'Gemini', 'Cursor', 'Notion AI',
  ],
  independent_work: [
    'フリーランス', 'フリーコンサル', 'ひとり社長', '独立後', '案件獲得',
  ],
};

// 弱キーワード: 2件以上ヒットで分類（単独では other）
const WEAK_KEYWORDS: Record<Exclude<Category, 'other'>, string[]> = {
  consultant_career: [
    '転職', '面接', 'キャリア', '昇進', 'ファーム', '外資', '戦略コンサル',
    '就活', '採用', '内定', '昇格', 'マネージャー', 'パートナー',
  ],
  thinking_docs: [
    '仮説', '資料作成', 'スライド', 'ロジック', 'フレームワーク', '問題解決',
    'パワポ', 'PowerPoint', '思考整理', 'ロジカル', '構造化', '整理術', 'メモ術', '思考法',
  ],
  sales_clientwork: [
    '営業', '提案', 'ヒアリング', 'セールス', '受注', '顧客', '契約',
    'ソリューション', '折衝', '交渉', 'SFA', 'CRM',
  ],
  ai_productivity: [
    'AI活用', 'AIで', 'AIを活用', '業務効率化', '生産性向上', '自動化',
    'RAG', 'ノーコード', 'ツール活用', 'DX推進',
  ],
  independent_work: [
    '独立', '副業', '案件', '個人事業', '起業', '自営業', '週4', 'ノマド', '複業',
  ],
};

const PRIORITY_BASE: Record<Category, number> = {
  consultant_career: 5,
  thinking_docs: 5,
  ai_productivity: 5,
  sales_clientwork: 4,
  independent_work: 4,
  other: 1,
};

// ── Classifier ────────────────────────────────────────────────────────────────

/** プレゼン（ト除外）などの特殊マッチ */
function matchKeyword(text: string, kw: string): boolean {
  if (kw === 'プレゼン') return /プレゼン(?!ト)/.test(text);
  if (kw === 'フリー') return /フリー(?!ター|ズ|ダム|キック|マーケット|ペーパー)/.test(text);
  if (kw === '戦略') return /戦略(?!的|ゲーム|家|シミュ)/.test(text);
  if (kw === '分析') return /分析(?!家|官)/.test(text);
  return text.includes(kw);
}

function classify(article: Article): { category: Category; matchedKeywords: string[] } {
  // 本文テキスト（メイン）
  const contentText = [
    article.title,
    article.body,
    article.preview,
  ].join(' ');

  // 著者テキスト（補助 — bioのみ、名前は除外）
  const bioText = article.author.bio ?? '';

  // テキストに日本語が含まれない場合は other
  if (!hasJapanese(contentText) && !hasJapanese(bioText)) {
    return { category: 'other', matchedKeywords: [] };
  }

  type Cat = Exclude<Category, 'other'>;
  const cats = Object.keys(STRONG_KEYWORDS) as Cat[];

  // 本文での強・弱ヒット
  const strongContent: Record<Cat, string[]> = {} as Record<Cat, string[]>;
  const weakContent:   Record<Cat, string[]> = {} as Record<Cat, string[]>;
  // bio での強ヒットのみ（弱はbioから取らない）
  const strongBio:     Record<Cat, string[]> = {} as Record<Cat, string[]>;

  for (const cat of cats) {
    strongContent[cat] = STRONG_KEYWORDS[cat].filter(kw => matchKeyword(contentText, kw));
    weakContent[cat]   = WEAK_KEYWORDS[cat].filter(kw => matchKeyword(contentText, kw));
    strongBio[cat]     = STRONG_KEYWORDS[cat].filter(kw => matchKeyword(bioText, kw));
  }

  // スコア: 本文強×3 + 本文弱×1 + bio強×1
  const scores: Record<Cat, number> = {} as Record<Cat, number>;
  for (const cat of cats) {
    scores[cat] = strongContent[cat].length * 3
                + weakContent[cat].length
                + strongBio[cat].length;
  }

  const best = cats.reduce((a, b) => (scores[a] >= scores[b] ? a : b));
  const allMatched = [
    ...strongContent[best],
    ...weakContent[best],
    ...strongBio[best].filter(kw => ![...strongContent[best], ...weakContent[best]].includes(kw)),
  ];

  // 証拠不十分 → other
  // （本文強0 + 本文弱0 + bio強1以下）
  if (
    strongContent[best].length === 0 &&
    weakContent[best].length === 0 &&
    strongBio[best].length <= 1
  ) {
    return { category: 'other', matchedKeywords: [] };
  }

  return { category: best, matchedKeywords: allMatched };
}

// ── Scoring ───────────────────────────────────────────────────────────────────

function calcPriorityScore(category: Category, kws: string[]): number {
  const base = PRIORITY_BASE[category];
  const boost = Math.min(0.5, kws.length * 0.1);
  return Math.min(5, +(base + boost).toFixed(2));
}

function calcEngagementScore(article: Article, maxEng: number): number {
  return +Math.min(5, (article.engagementScore / maxEng) * 5).toFixed(3);
}

function calcFinalScore(priority: number, engagement: number): number {
  return +(priority * 0.6 + engagement * 0.4).toFixed(3);
}

// ── Why useful / Suggested angle ─────────────────────────────────────────────

const WHY_USEFUL: Record<Category, (kws: string[]) => string> = {
  consultant_career: (kw) =>
    `コンサル業界・キャリアに関するリアルな知見（${kw.slice(0, 3).join('・') || 'キャリア'}）を含み、転職・キャリア軸の発信ネタとして直接転用しやすい。`,
  thinking_docs: (kw) =>
    `${kw.slice(0, 3).join('・') || '思考整理'}など実務の質を高めるスキルを扱っており、コンサルの仕事術発信に自然に落とし込める。`,
  sales_clientwork: (kw) =>
    `${kw.slice(0, 3).join('・') || 'クライアントワーク'}に関する具体的な知見があり、提案・クライアントワーク軸の発信として説得力が増す。`,
  ai_productivity: (kw) =>
    `${kw.slice(0, 3).join('・') || 'AI活用'}を扱っており、AI×コンサル実務という今最も注目されている発信テーマと直結する。`,
  independent_work: (kw) =>
    `${kw.slice(0, 3).join('・') || '独立・フリーランス'}に関するリアルな視点があり、独立・副業軸の発信ネタとして活用しやすい。`,
  other: (_kw) =>
    `テーマ合致は低いが、1万いいね超えのバズ構造・書き出し・オチの付け方がコンサル系発信のフォーマット参考になる。`,
};

const ANGLES: Record<Category, string[]> = {
  consultant_career: [
    'コンサル転職の本質',
    '面接で問われる本当の能力',
    'ファームで伸びる人・伸びない人',
    'キャリアの選び方を言語化する',
  ],
  thinking_docs: [
    '論点整理の実践テクニック',
    '資料作成で差がつくポイント',
    '仮説ドリブンの仕事術',
    'コンサル流の思考法を平易に語る',
  ],
  sales_clientwork: [
    '提案で刺さる論点の作り方',
    'クライアントとの信頼構築の本質',
    '商談で使えるフレームワーク',
    '顧客の課題を正しく掴む方法',
  ],
  ai_productivity: [
    'AIで短縮できる実務を具体的に語る',
    'コンサルのAI活用最前線',
    'AI時代の仕事の再定義',
    'プロンプト設計の現場感',
  ],
  independent_work: [
    '独立後に気づいたこと',
    '案件獲得の現実と戦略',
    'フリーコンサルで稼ぐ構造',
    '個人で戦う武器の作り方',
  ],
  other: [
    'バズる投稿の構造を分析する',
    '共感を呼ぶ切り口の作り方',
  ],
};

function pickAngle(category: Category, kws: string[], seed: string): string {
  const list = ANGLES[category];
  // Deterministic selection based on article ID
  const idx = seed.split('').reduce((acc, c) => acc + c.charCodeAt(0), 0) % list.length;
  return list[idx];
}

// ── Markdown output ───────────────────────────────────────────────────────────

function fmt(n: number): string {
  return n.toLocaleString('ja-JP');
}

function toTop20Md(articles: EnrichedArticle[], topN: number, allJa: EnrichedArticle[]): string {
  // コンサル系が少なすぎる場合はja全体のエンゲージメント上位で補完
  const consultantOnly = articles.filter(a => a.category !== 'other');
  const top = consultantOnly.length >= topN
    ? consultantOnly.slice(0, topN)
    : [
        ...consultantOnly,
        ...allJa.filter(a => !consultantOnly.includes(a)).slice(0, topN - consultantOnly.length),
      ];
  const consultantCount = top.filter(a => a.category !== 'other').length;
  const lines: string[] = [
    `# コンサル系Xアカウント向け 注目ツイート TOP${topN}`,
    ``,
    `> 生成: ${new Date().toLocaleString('ja-JP')}`,
    ``,
    `> **データ注記:** 収集データは「1万いいね以上の一般日本語ツイート」のため、コンサル系テーマとの直接一致は少ない（${consultantCount}件）。`,
    `> 残りはバズの**フォーマット・書き方・オチの構造**の参考として掲載。`,
    `> 次回はコンサル系キーワード絞り込みクエリ（B系）で収集するとより有用なデータが得られる。`,
    ``,
    `---`,
    ``,
  ];

  for (const [i, a] of top.entries()) {
    lines.push(`## ${i + 1}. ${a.title}`);
    lines.push(``);
    lines.push(
      `| | |`,
      `|---|---|`,
      `| カテゴリ | \`${a.category}\` |`,
      `| 最終スコア | ${a.final_score} (優先度 ${a.priority_score}/5 × エンゲージ ${a.engagement_score.toFixed(2)}/5) |`,
      `| キーワード | ${a.matchedKeywords.slice(0, 5).join(', ') || '—'} |`,
    );
    lines.push(``);
    lines.push(`**なぜ参考になるか:** ${a.why_useful_for_my_account}`);
    lines.push(``);
    lines.push(`**転用切り口:** 「${a.suggested_angle}」`);
    lines.push(``);
    lines.push(
      `❤️ ${fmt(a.stats.likes)} &nbsp; 🔁 ${fmt(a.stats.retweets)} &nbsp; 💬 ${fmt(a.stats.replies)} &nbsp; 引用 ${fmt(a.stats.quotes)} &nbsp; 🔖 ${fmt(a.stats.bookmarks)} &nbsp; 👁 ${fmt(a.stats.views)}`
    );
    lines.push(``);
    lines.push(
      `**[@${a.author.screenName}](https://x.com/${a.author.screenName})** &nbsp; フォロワー ${fmt(a.author.followersCount)} &nbsp; 📅 ${a.createdAt}`
    );
    lines.push(``);
    lines.push(`🔗 ${a.tweetUrl}`);
    lines.push(``);
    if (a.preview) {
      const snippet = a.preview.replace(/\n/g, ' ').slice(0, 200);
      lines.push(`> ${snippet}${a.preview.length > 200 ? '…' : ''}`);
      lines.push(``);
    }
    lines.push(`---`);
    lines.push(``);
  }

  return lines.join('\n');
}

function toSummaryMd(
  enriched: EnrichedArticle[],
  rawCount: number,
): string {
  const catCounts: Record<string, number> = {};
  const langCounts: Record<string, number> = {};

  for (const a of enriched) {
    catCounts[a.category] = (catCounts[a.category] || 0) + 1;
    langCounts[a.lang] = (langCounts[a.lang] || 0) + 1;
  }

  const consultantCount = enriched.filter(a => a.category !== 'other').length;

  const lines: string[] = [
    `# サマリーレポート`,
    ``,
    `> 生成: ${new Date().toLocaleString('ja-JP')}`,
    ``,
    `## 全体`,
    ``,
    `| 項目 | 件数 |`,
    `|---|---|`,
    `| 入力ツイート | ${fmt(rawCount)} |`,
    `| 分類対象（ja + unknown） | ${fmt(enriched.length)} |`,
    `| コンサル系（other除く） | ${fmt(consultantCount)} |`,
    ``,
    `## カテゴリ別内訳`,
    ``,
    `| カテゴリ | 件数 |`,
    `|---|---|`,
    ...Object.entries(catCounts)
      .sort((a, b) => b[1] - a[1])
      .map(([k, v]) => `| ${k} | ${fmt(v)} |`),
    ``,
    `## 言語別内訳`,
    ``,
    `| 言語 | 件数 |`,
    `|---|---|`,
    ...Object.entries(langCounts).map(([k, v]) => `| ${k} | ${fmt(v)} |`),
    ``,
    `## 注記`,
    ``,
    `- 分類はキーワードマッチングによるルールベース`,
    `- 記事詳細取得は未実施（source: tweet_only）`,
    `- 入力データ: output/ 内の最新 report-*.json`,
  ];

  return lines.join('\n');
}

// ── Main ─────────────────────────────────────────────────────────────────────

async function main() {
  const outputDir = path.join(process.cwd(), 'output');

  // Find latest report JSON
  const files = fs.readdirSync(outputDir)
    .filter(f => f.startsWith('report-') && f.endsWith('.json') && !f.includes('unknown'));
  if (files.length === 0) {
    console.error('output/ に report-*.json が見つかりません');
    process.exit(1);
  }
  files.sort().reverse();
  const inputFile = path.join(outputDir, files[0]);
  console.log(`\n📂 入力: ${files[0]}`);

  const raw: Article[] = JSON.parse(fs.readFileSync(inputFile, 'utf-8'));
  console.log(`  総件数: ${raw.length}`);

  // スノーフレークIDから日付を補完
  const withDate = raw.map(a => ({
    ...a,
    createdAt: a.createdAt ?? snowflakeToDate(a.tweetId),
  }));

  // 処理対象：日本語ツイートのみ（ja + unknownのうち本文/名前に日本語がある）
  const targets = withDate.filter(a =>
    hasJapanese([a.title, a.body, a.author.name, a.author.bio].join(' '))
  );
  console.log(`  日本語コンテンツ: ${targets.length} 件（全${raw.length}件中）`);

  const maxEng = Math.max(...targets.map(a => a.engagementScore), 1);

  console.log(`\n🔍 分類・スコアリング中...`);
  const enriched: EnrichedArticle[] = targets.map(a => {
    const { category, matchedKeywords } = classify(a);
    const pScore = calcPriorityScore(category, matchedKeywords);
    const eScore = calcEngagementScore(a, maxEng);
    const fScore = calcFinalScore(pScore, eScore);
    return {
      ...a,
      category,
      matchedKeywords,
      why_useful_for_my_account: WHY_USEFUL[category](matchedKeywords),
      suggested_angle: pickAngle(category, matchedKeywords, a.articleId),
      priority_score: pScore,
      engagement_score: eScore,
      final_score: fScore,
    };
  });

  // Sort: final_score desc → engagement_score desc → likes desc
  enriched.sort((a, b) => {
    if (b.final_score !== a.final_score) return b.final_score - a.final_score;
    if (b.engagement_score !== a.engagement_score) return b.engagement_score - a.engagement_score;
    return b.stats.likes - a.stats.likes;
  });

  const consultantTopics = enriched.filter(a => a.category !== 'other');
  const otherArticles = enriched.filter(a => a.category === 'other');

  // Category breakdown
  const catCounts: Record<string, number> = {};
  for (const a of enriched) catCounts[a.category] = (catCounts[a.category] || 0) + 1;

  console.log(`\n📊 カテゴリ内訳:`);
  for (const [k, v] of Object.entries(catCounts).sort((a, b) => b[1] - a[1])) {
    const bar = '█'.repeat(Math.round(v / enriched.length * 30));
    console.log(`  ${k.padEnd(22)} ${String(v).padStart(4)}件  ${bar}`);
  }

  // Output
  const ts = new Date().toISOString().replace(/[:.]/g, '-').slice(0, 19);
  const outDir = path.join(outputDir, `analysis-${ts}`);
  fs.mkdirSync(outDir, { recursive: true });

  fs.writeFileSync(path.join(outDir, 'all_articles.json'), JSON.stringify(enriched, null, 2));
  fs.writeFileSync(path.join(outDir, 'consultant_topics.json'), JSON.stringify(consultantTopics, null, 2));
  fs.writeFileSync(path.join(outDir, 'other_articles.json'), JSON.stringify(otherArticles, null, 2));
  // top20はエンゲージメント順のja全体リストを渡して補完
  const jaByEngagement = [...enriched].sort((a, b) => b.engagement_score - a.engagement_score);
  fs.writeFileSync(path.join(outDir, 'top20.md'), toTop20Md(consultantTopics, 20, jaByEngagement));
  fs.writeFileSync(path.join(outDir, 'summary.md'), toSummaryMd(enriched, raw.length));

  console.log(`\n💾 出力先: output/analysis-${ts}/`);
  console.log(`  all_articles.json     ${enriched.length} 件`);
  console.log(`  consultant_topics.json ${consultantTopics.length} 件`);
  console.log(`  other_articles.json   ${otherArticles.length} 件`);
  console.log(`  top20.md`);
  console.log(`  summary.md`);
  console.log(`\n✅ Done!`);
}

main().catch(err => {
  console.error('Fatal error:', err);
  process.exit(1);
});
