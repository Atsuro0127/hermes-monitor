import fs from 'fs';
import path from 'path';
import { EnrichedArticle, CliOptions, RunStats } from './types';

const TOP_N = 20;

function fmt(n: number): string {
  return n.toLocaleString();
}

function toMarkdown(articles: EnrichedArticle[], opts: CliOptions, stats: RunStats, costJpy: number): string {
  const costUsd = stats.searchRequestCount * 0.001 + stats.articleFetchFresh * 0.002;
  const top = articles.slice(0, TOP_N);

  const lines: string[] = [
    `# X Article Research Report`,
    ``,
    `| | |`,
    `|---|---|`,
    `| Mode | ${opts.mode} |`,
    `| Period | ${opts.since} ～ ${opts.until} |`,
    `| Min Faves | ${opts.minFaves} |`,
    `| Lang | ${opts.lang} |`,
    `| Items (ja) | ${articles.length} |`,
    `| API Cost (est.) | $${costUsd.toFixed(3)} ≈ ¥${Math.round(costJpy)} |`,
    ``,
    `> Showing TOP ${Math.min(TOP_N, articles.length)} of ${articles.length} articles. Full data in JSON.`,
    ``,
    `---`,
    ``,
  ];

  for (const [i, a] of top.entries()) {
    lines.push(`## ${i + 1}. ${a.title}`);
    lines.push(``);
    lines.push(`**[@${a.author.screenName}](https://x.com/${a.author.screenName})** · ${fmt(a.author.followersCount)} followers`);
    lines.push(``);
    lines.push(`❤️ ${fmt(a.stats.likes)} &nbsp; 🔁 ${fmt(a.stats.retweets)} &nbsp; 💬 ${fmt(a.stats.replies)} &nbsp; 🔖 ${fmt(a.stats.bookmarks)} &nbsp; 👁 ${fmt(a.stats.views)}`);
    lines.push(``);
    lines.push(`🔗 ${a.tweetUrl}`);
    lines.push(``);

    if (a.preview) {
      lines.push(`> ${a.preview.replace(/\n/g, '\n> ')}`);
      lines.push(``);
    }

    if (a.thumbnail) {
      lines.push(`![thumbnail](${a.thumbnail})`);
      lines.push(``);
    }

    if (a.body && a.source === 'api') {
      lines.push(`<details><summary>本文を読む</summary>`);
      lines.push(``);
      lines.push(a.body);
      lines.push(``);
      lines.push(`</details>`);
      lines.push(``);
    }

    lines.push(`---`);
    lines.push(``);
  }

  return lines.join('\n');
}

function toUnknownMarkdown(articles: EnrichedArticle[], opts: CliOptions): string {
  const lines: string[] = [
    `# X Article Research — Unknown Lang`,
    ``,
    `| | |`,
    `|---|---|`,
    `| Period | ${opts.since} ～ ${opts.until} |`,
    `| Articles (unknown) | ${articles.length} |`,
    ``,
    `---`,
    ``,
  ];

  for (const [i, a] of articles.entries()) {
    lines.push(`## ${i + 1}. ${a.title}`);
    lines.push(``);
    lines.push(`**[@${a.author.screenName}](https://x.com/${a.author.screenName})** · ${fmt(a.author.followersCount)} followers`);
    lines.push(``);
    lines.push(`❤️ ${fmt(a.stats.likes)} &nbsp; 🔁 ${fmt(a.stats.retweets)} &nbsp; 💬 ${fmt(a.stats.replies)}`);
    lines.push(``);
    lines.push(`🔗 ${a.tweetUrl}`);
    lines.push(``);
    lines.push(`---`);
    lines.push(``);
  }

  return lines.join('\n');
}

export function saveResults(
  jaArticles: EnrichedArticle[],
  unknownArticles: EnrichedArticle[],
  opts: CliOptions,
  stats: RunStats,
  usdToJpy = 150,
): void {
  const ts = new Date().toISOString().replace(/[:.]/g, '-').slice(0, 19);
  const base = path.join(process.cwd(), 'output', `report-${ts}`);

  const costUsd = stats.searchRequestCount * 0.001 + stats.articleFetchFresh * 0.002;
  const costJpy = costUsd * usdToJpy;

  // JSON: all data including unknown
  const allArticles = [...jaArticles, ...unknownArticles];
  fs.writeFileSync(`${base}.json`, JSON.stringify(allArticles, null, 2), 'utf-8');

  // Markdown: ja TOP20
  fs.writeFileSync(`${base}.md`, toMarkdown(jaArticles, opts, stats, costJpy), 'utf-8');

  // Markdown: unknown (if any)
  if (unknownArticles.length > 0) {
    fs.writeFileSync(`${base}-unknown.md`, toUnknownMarkdown(unknownArticles, opts), 'utf-8');
    console.log(`  💾 ${base}-unknown.md  (${unknownArticles.length} unknown-lang articles)`);
  }

  console.log(`\n  💾 ${base}.json`);
  console.log(`  💾 ${base}.md`);
  console.log(`\n  💰 Estimated API cost: $${costUsd.toFixed(3)} ≈ ¥${Math.round(costJpy)}`);
  console.log(`     (search: ${stats.searchRequestCount} req × $0.001, articles: ${stats.articleFetchFresh} fresh × $0.002)`);
}
