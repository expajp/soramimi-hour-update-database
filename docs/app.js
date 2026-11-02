'use strict';
const PAGE_SIZE = 50;
const COLUMNS = [
  { id: 'date', label: '放送日', cls: 'c-date', dir: 'desc' },
  { id: 'artist', label: 'アーティスト', cls: 'c-artist', dir: 'asc' },
  { id: 'title', label: '曲名', cls: 'c-title', dir: 'asc' },
  { id: 'soramimi', label: '空耳 / 原詞', cls: 'c-soramimi', dir: 'asc' },
  { id: 'rating', label: '評価', cls: 'c-rating', dir: 'desc' },
  { id: 'specials', label: '特番', cls: 'c-special', dir: 'desc' },
];
const ALL_SPECIALS = 'any';
const collator = new Intl.Collator('ja');
const form = document.getElementById('filters');
const $ = id => document.getElementById(id);
let data, works, listed = [];
let sort = { id: 'date', dir: 'desc' };
let page = 0;

// Folds differences that do not change the meaning of a search term:
// width, case, hiragana/katakana, separators, long vowels and ヴ.
function fold(s) {
  return s.normalize('NFKC').toLowerCase()
    .replace(/[ぁ-ゖ]/g, c => String.fromCharCode(c.charCodeAt(0) + 0x60))
    .replace(/ヴァ/g, 'バ').replace(/ヴィ/g, 'ビ').replace(/ヴェ/g, 'ベ').replace(/ヴォ/g, 'ボ').replace(/ヴ/g, 'ブ')
    .replace(/[\s・･·.,、。'’‘"”“\-‐–—―ー＝=「」『』()~〜]/g, '');
}
const terms = s => s.trim().split(/\s+/).map(fold).filter(Boolean);
const hasAll = (haystack, list) => list.every(t => haystack.includes(t));

function prepare(raw) {
  data = raw;
  works = raw.works.map(r => {
    const [id, date, artist, key, title, lyric, soramimi, rating, ratingOther, specials, award] = r;
    const names = [key, artist, ...(raw.spellings[key] || [])];
    return {
      id, date, artist, key, title, lyric, soramimi, rating, ratingOther, specials, award,
      foldArtist: names.map(fold).join(' '),
      foldTitle: fold(title),
      foldFree: fold([soramimi, lyric, ratingOther].join(' ')),
    };
  });
}

function buildControls() {
  const list = $('artist-list');
  const counts = new Map();
  works.forEach(w => { if (w.key) counts.set(w.key, (counts.get(w.key) || 0) + 1); });
  [...counts.keys()].sort(collator.compare).forEach(k => list.append(new Option(`${counts.get(k)} 作品`, k)));

  form.special.append(new Option('すべて', ''), new Option('いずれかの特番で紹介', ALL_SPECIALS));
  data.specials.forEach((s, i) => form.special.append(new Option(s.date ? `${s.name}（${s.date.slice(0, 4)}）` : s.name, String(i))));

  data.ratings.forEach((name, i) => {
    const label = document.createElement('label');
    const box = document.createElement('input');
    box.type = 'checkbox'; box.name = 'rating'; box.value = String(i);
    label.append(box, name);
    $('rating-checks').append(label);
  });

  const dates = works.map(w => w.date).sort();
  for (const name of ['from', 'to']) { form[name].min = dates[0]; form[name].max = dates[dates.length - 1]; }

  COLUMNS.forEach(c => {
    const th = document.createElement('th');
    th.scope = 'col'; th.className = c.cls; th.dataset.id = c.id;
    const b = document.createElement('button');
    b.type = 'button'; b.addEventListener('click', () => toggleSort(c));
    th.append(b); $('head').append(th);
    for (const dir of ['desc', 'asc']) {
      $('sort-select').append(new Option(`${c.label}（${dir === 'desc' ? '降順' : '昇順'}）`, `${c.id}:${dir}`));
    }
  });
  $('sort-select').addEventListener('change', e => {
    const [id, dir] = e.target.value.split(':');
    sort = { id, dir }; page = 0; update();
  });
}

function toggleSort(c) {
  sort = sort.id === c.id ? { id: c.id, dir: sort.dir === 'asc' ? 'desc' : 'asc' } : { id: c.id, dir: c.dir };
  page = 0;
  update();
}

function readFilters() {
  return {
    artist: form.artist.value, title: form.title.value, q: form.q.value,
    from: form.from.value, to: form.to.value, special: form.special.value,
    ratings: [...form.querySelectorAll('[name=rating]:checked')].map(b => Number(b.value)),
  };
}

const inPeriod = (w, f) => (!f.from || w.date >= f.from) && (!f.to || w.date <= f.to);

function matcher(f) {
  const artist = terms(f.artist), title = terms(f.title), q = terms(f.q);
  const ratings = new Set(f.ratings);
  return w => hasAll(w.foldArtist, artist) && hasAll(w.foldTitle, title) && hasAll(w.foldFree, q)
    && (!ratings.size || ratings.has(w.rating))
    && (!f.special || (f.special === ALL_SPECIALS ? w.specials.length > 0 : w.specials.includes(Number(f.special))));
}

const VALUE = {
  date: w => w.date, artist: w => w.key || w.artist, title: w => w.title, soramimi: w => w.soramimi,
  rating: w => w.rating, specials: w => w.specials.length,
};
function compare(a, b) {
  const x = VALUE[sort.id](a), y = VALUE[sort.id](b);
  const d = typeof x === 'number' ? x - y : collator.compare(x, y);
  return (sort.dir === 'asc' ? d : -d) || a.date.localeCompare(b.date) || a.id - b.id;
}

function renderCounts(f, period, matched, narrowed) {
  const label = f.from || f.to ? `${f.from || '最初'} 〜 ${f.to || '最後'}` : '全期間';
  $('counts-note').textContent = narrowed
    ? `${label}の評価数です。小さな数字は、ほかの検索条件にも一致する作品の数です。`
    : `${label}の評価数です。`;
  const tally = list => { const c = data.ratings.map(() => 0); list.forEach(w => c[w.rating]++); return c; };
  const all = tally(period), hit = tally(matched);
  const tile = (name, value, sub) => {
    const el = document.createElement('div');
    el.className = 'tile';
    const n = document.createElement('div'); n.className = 'name'; n.textContent = name;
    const v = document.createElement('div'); v.className = 'value'; v.textContent = value.toLocaleString('ja-JP');
    const s = document.createElement('div'); s.className = 'sub';
    s.textContent = narrowed ? `検索結果 ${sub.toLocaleString('ja-JP')}` : '';
    el.append(n, v, s);
    return el;
  };
  $('counts').replaceChildren(
    ...[4, 3, 2, 1, 0].map(i => tile(data.ratings[i], all[i], hit[i])),
    tile('作品数', period.length, matched.length));
}

function cell(column, ...children) {
  const td = document.createElement('td');
  td.className = column;
  td.append(...children);
  return td;
}
function div(className, text) {
  const el = document.createElement('div');
  el.className = className; el.textContent = text;
  return el;
}
function tag(text, cls) {
  const el = document.createElement('span');
  el.className = cls ? `tag ${cls}` : 'tag'; el.textContent = text;
  return el;
}

function renderRow(w) {
  const tr = document.createElement('tr');
  const artist = [w.key || w.artist];
  const original = w.artist.replace(/\s*\(.*$/, '');
  if (w.key && fold(original) !== fold(w.key)) artist.push(div('spelling', w.artist));
  const free = [div('soramimi', w.soramimi)];
  if (w.lyric) free.push(div('lyric', w.lyric));
  const rating = [data.ratings[w.rating]];
  if (w.ratingOther) rating.push(div('rating-other', w.ratingOther));
  const specials = w.specials.map(i => tag(data.specials[i].name));
  if (w.award) specials.unshift(tag(`グランプリ ${w.award}`, 'award'));
  tr.append(
    cell('c-date', w.date), cell('c-artist', ...artist), cell('c-title', w.title),
    cell('c-soramimi', ...free), cell('c-rating', ...rating), cell('c-special', ...specials));
  return tr;
}

function renderRows() {
  const pages = Math.max(1, Math.ceil(listed.length / PAGE_SIZE));
  page = Math.min(page, pages - 1);
  const start = page * PAGE_SIZE;
  const rows = listed.slice(start, start + PAGE_SIZE).map(renderRow);
  if (!rows.length) {
    const tr = document.createElement('tr');
    const td = document.createElement('td');
    td.colSpan = COLUMNS.length; td.className = 'empty'; td.textContent = '一致する作品はありません';
    tr.append(td); rows.push(tr);
  }
  $('rows').replaceChildren(...rows);
  const end = Math.min(start + PAGE_SIZE, listed.length);
  $('result-count').textContent = listed.length
    ? `${listed.length.toLocaleString('ja-JP')} 件中 ${(start + 1).toLocaleString('ja-JP')}〜${end.toLocaleString('ja-JP')} 件`
    : '0 件';

  const nav = (text, target, disabled) => {
    const b = document.createElement('button');
    b.type = 'button'; b.textContent = text; b.disabled = disabled;
    b.addEventListener('click', () => { page = target; renderRows(); $('results-title').scrollIntoView(); });
    return b;
  };
  const position = document.createElement('span');
  position.textContent = `${page + 1} / ${pages}`;
  $('pager').replaceChildren(
    nav('最初', 0, page === 0), nav('前へ', page - 1, page === 0), position,
    nav('次へ', page + 1, page >= pages - 1), nav('最後', pages - 1, page >= pages - 1));
}

function renderHead() {
  document.querySelectorAll('#head th').forEach(th => {
    const c = COLUMNS.find(x => x.id === th.dataset.id);
    const active = sort.id === c.id;
    if (active) th.setAttribute('aria-sort', sort.dir === 'asc' ? 'ascending' : 'descending');
    else th.removeAttribute('aria-sort');
    th.firstChild.textContent = active ? `${c.label} ${sort.dir === 'asc' ? '▲' : '▼'}` : c.label;
  });
  $('sort-select').value = `${sort.id}:${sort.dir}`;
}

function writeHash(f) {
  const p = new URLSearchParams();
  for (const k of ['artist', 'title', 'q', 'from', 'to', 'special']) if (f[k]) p.set(k, f[k]);
  if (f.ratings.length) p.set('rating', f.ratings.join(','));
  if (sort.id !== 'date' || sort.dir !== 'desc') p.set('sort', `${sort.id}:${sort.dir}`);
  history.replaceState(null, '', p.size ? `#${p}` : location.pathname);
}

function readHash() {
  const p = new URLSearchParams(location.hash.slice(1));
  for (const k of ['artist', 'title', 'q', 'from', 'to', 'special']) if (p.has(k)) form[k].value = p.get(k);
  const ratings = (p.get('rating') || '').split(',');
  form.querySelectorAll('[name=rating]').forEach(b => { b.checked = ratings.includes(b.value); });
  const [id, dir] = (p.get('sort') || '').split(':');
  if (VALUE[id] && (dir === 'asc' || dir === 'desc')) sort = { id, dir };
}

function update() {
  const f = readFilters();
  const period = works.filter(w => inPeriod(w, f));
  const matched = period.filter(matcher(f));
  listed = matched.slice().sort(compare);
  renderCounts(f, period, matched, matched.length !== period.length);
  renderHead();
  renderRows();
  writeHash(f);
}

let timer;
function schedule() {
  clearTimeout(timer);
  timer = setTimeout(() => { page = 0; update(); }, 120);
}

fetch('data.json').then(r => {
  if (!r.ok) throw new Error(r.status);
  return r.json();
}).then(raw => {
  prepare(raw);
  buildControls();
  readHash();
  const first = works.map(w => w.date).sort()[0], last = works.map(w => w.date).sort().pop();
  $('lead').textContent = `${first.slice(0, 4)}年〜${last.slice(0, 4)}年の全 ${works.length.toLocaleString('ja-JP')} 作品を検索できます`;
  form.addEventListener('input', schedule);
  form.addEventListener('submit', e => e.preventDefault());
  form.addEventListener('reset', () => setTimeout(() => { page = 0; update(); }));
  update();
}).catch(() => {
  $('lead').textContent = 'データを読み込めませんでした。ページを再読み込みしてください。';
});
