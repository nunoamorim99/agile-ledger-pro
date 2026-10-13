/* Agile-Ledger Pro dashboard.
 *
 * Reads the ledger through /api and renders it. Every write goes back through
 * one action endpoint, which returns the re-read repo, so the page always shows
 * what is actually on disk rather than an optimistic guess.
 *
 * All ledger text is injected with textContent (never innerHTML), because the
 * ledger is free-form prose typed by people.
 */
'use strict';

const EMPTY = '—';

const state = {
  workspace: null,
  repo: null,
  slug: null,
  person: '',
  route: null,
  revision: 0,
  commands: null,
  syncedAt: null,
  externalEdit: false,
  pendingOwnWrite: false,
  drift: null,
};

/* ------------------------------------------------------------------ utils */

function el(tag, attrs, ...children) {
  const node = document.createElement(tag);
  for (const [key, value] of Object.entries(attrs || {})) {
    if (value === null || value === undefined || value === false) continue;
    if (key === 'class') node.className = value;
    else if (key === 'text') node.textContent = value;
    else if (key.startsWith('on')) node.addEventListener(key.slice(2), value);
    else if (key === 'dataset') Object.assign(node.dataset, value);
    else node.setAttribute(key, value === true ? '' : value);
  }
  for (const child of children.flat()) {
    if (child === null || child === undefined || child === false) continue;
    node.append(child instanceof Node ? child : document.createTextNode(String(child)));
  }
  return node;
}

const isSet = (v) => v !== undefined && v !== null && String(v).trim() !== '' && String(v).trim() !== EMPTY;
const show = (v) => (isSet(v) ? String(v) : EMPTY);
const num = (v) => (String(v ?? '').trim().match(/^\d+$/) ? parseInt(v, 10) : 0);

function nameOf(assignee) {
  return String(assignee || '').replace(/^@/, '').trim();
}

/* ------------------------------------------------- inline Markdown -------
 * Ledger prose is Markdown, so render its formatting instead of showing the
 * asterisks. Everything is built as DOM nodes — never innerHTML — because this
 * is free text typed by people.
 *
 * Underline is deliberately absent: Markdown has no underline, and inventing a
 * syntax for it would render as literal punctuation in GitHub and VS Code
 * preview, where this ledger also has to stay readable.
 */
// Each delimiter pair closes on its own backreference, so the group numbers
// here must match the alternation's own numbering: 1/2, 3/4, 5/6, then 7, 8,
// and 9/10 for a link.
const INLINE = new RegExp([
  '(\\*\\*\\*|___)(?=\\S)([\\s\\S]*?\\S)\\1',   // 1,2  ***bold italic***
  '(\\*\\*|__)(?=\\S)([\\s\\S]*?\\S)\\3',       // 3,4  **bold**
  '(?<![A-Za-z0-9])(\\*|_)(?=\\S)([\\s\\S]*?\\S)\\5(?![A-Za-z0-9])', // 5,6 *italic*
  '`([^`]+)`',                                  // 7    `code`
  '~~(?=\\S)([\\s\\S]*?\\S)~~',                 // 8    ~~struck~~
  '\\[([^\\]]+)\\]\\(([^)]*)\\)',               // 9,10 [text](target)
].join('|'));

/** Ledger text with its Markdown markers removed, for plain-text contexts. */
function plain(text) {
  return String(text ?? '')
    .replace(/\[([^\]]+)\]\([^)]*\)/g, '$1')
    .replace(/(\*\*\*|___|\*\*|__|~~)(.*?)\1/g, '$2')
    .replace(/(?<![A-Za-z0-9])([*_])(\S(?:[\s\S]*?\S)?)\1(?![A-Za-z0-9])/g, '$2')
    .replace(/`([^`]+)`/g, '$1');
}

const ID_TEXT = /^(US|EPIC|BUG|TASK)-\d+$/i;

function rich(text) {
  const frag = document.createDocumentFragment();
  const lines = String(text ?? '').split('\n');
  lines.forEach((line, i) => {
    if (i) frag.append(el('br', {}));
    inline(line, frag);
  });
  return frag;
}

function inline(text, parent) {
  let rest = String(text ?? '');
  while (rest) {
    const m = INLINE.exec(rest);
    if (!m) { parent.append(document.createTextNode(rest)); return; }
    if (m.index) parent.append(document.createTextNode(rest.slice(0, m.index)));

    let node;
    if (m[2] !== undefined) { node = el('strong', {}); inline(m[2], node); node = wrapEm(node); }
    else if (m[4] !== undefined) { node = el('strong', {}); inline(m[4], node); }
    else if (m[6] !== undefined) { node = el('em', {}); inline(m[6], node); }
    else if (m[7] !== undefined) { node = el('code', { text: m[7] }); }
    else if (m[8] !== undefined) { node = el('del', {}); inline(m[8], node); }
    else { node = linkNode(m[9], m[10]); }

    parent.append(node);
    rest = rest.slice(m.index + m[0].length);
  }
}

function wrapEm(strongNode) {
  const em = el('em', {});
  em.append(strongNode);
  return em;
}

/* A link to another ledger entry becomes a button that opens it here; the .md
 * targets the ledger uses would 404 in a browser. Anything else stays text, so
 * no ledger content can inject a URL into the page. */
function linkNode(label, target) {
  const id = ID_TEXT.test(label.trim()) ? label.trim().toUpperCase()
    : (String(target || '').match(/#((?:us|epic|bug|task)-\d+)\s*$/i) || [])[1];
  if (id) {
    return el('button', { class: 'idlink', type: 'button', title: `Open ${id.toUpperCase()}`,
      onclick: () => openItem(id.toUpperCase()) }, label);
  }
  return document.createTextNode(label);
}

/** A block of ledger prose, formatted. Falls back to the empty dash. */
function prose(text, tag, attrs) {
  const node = el(tag || 'p', attrs || {});
  if (isSet(text)) node.append(rich(text));
  else node.textContent = EMPTY;
  return node;
}

async function api(path, options) {
  const response = await fetch(path, options);
  let payload;
  try { payload = await response.json(); }
  catch { throw new Error(`${response.status} ${response.statusText}`); }
  if (!response.ok || payload.error) throw new Error(payload.error || `${response.status}`);
  return payload;
}

function toast(kind, title, message, list) {
  const node = el('div', { class: `toast ${kind}` },
    el('h5', { text: title }),
    message ? el('p', { text: message }) : null,
    list && list.length ? el('ul', {}, list.map((i) => el('li', { text: i }))) : null);
  document.getElementById('toasts').append(node);
  setTimeout(() => node.remove(), kind === 'err' ? 9000 : 5200);
}

/* ---------------------------------------------------------------- actions */

async function act(action, params, successTitle) {
  try {
    const result = await api(`/api/repo/${encodeURIComponent(state.slug)}/action`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ action, params: params || {} }),
    });
    state.pendingOwnWrite = true;
    if (result.repo) {
      state.repo = result.repo;
      state.revision = result.repo.revision;
      state.syncedAt = Date.now();
    }
    const warnings = result.warnings || [];
    toast(warnings.length ? 'warn' : 'ok',
      successTitle || result.message || 'Done',
      successTitle ? result.message : null,
      warnings);
    render();
    refreshWorkspaceQuietly();
    return result;
  } catch (error) {
    toast('err', 'Could not do that', error.message);
    throw error;
  }
}

/* ------------------------------------------------------------ modal forms */

let modalSubmit = null;

function openModal(title, fields, onSubmit, options) {
  const form = document.getElementById('modal-form');
  const body = document.getElementById('modal-body');
  document.getElementById('modal-title').textContent = title;
  document.getElementById('modal-submit').textContent = (options && options.submit) || 'Save';
  document.getElementById('modal-note').textContent = (options && options.note) || '';
  body.replaceChildren(...fields);
  modalSubmit = onSubmit;
  document.getElementById('modal').hidden = false;
  const first = body.querySelector('input, textarea, select');
  if (first) setTimeout(() => first.focus(), 30);
  form.onsubmit = async (event) => {
    event.preventDefault();
    const data = Object.fromEntries(new FormData(form).entries());
    try { await modalSubmit(data, form); closeModal(); }
    catch { /* act() has already reported it; keep the form open */ }
  };
}

function closeModal() {
  document.getElementById('modal').hidden = true;
  modalSubmit = null;
}

function field(label, input, hint) {
  return el('label', { class: 'form-row' },
    el('span', { class: 'field-label', text: label }),
    input,
    hint ? el('span', { class: 'hint', text: hint }) : null);
}

function textInput(name, value, placeholder) {
  return el('input', { type: 'text', name, value: value && value !== EMPTY ? value : '', placeholder: placeholder || '' });
}

function textArea(name, value, placeholder, rows) {
  const node = el('textarea', { name, placeholder: placeholder || '', rows: rows || 3 });
  node.value = value && value !== EMPTY ? value : '';
  return node;
}

function selectInput(name, options, value) {
  return el('select', { name }, options.map((option) => {
    const [val, label] = Array.isArray(option) ? option : [option, option];
    const node = el('option', { value: val, text: label });
    if (String(val) === String(value || '')) node.selected = true;
    return node;
  }));
}

function priorityInput(value) {
  const vocab = state.workspace.vocabulary.priorities;
  return selectInput('priority', [['', EMPTY], ...vocab.map((p) => [p.value, `${p.value} ${p.name}`])], value);
}

const linesOf = (text) => String(text || '').split('\n').map((l) => l.trim()).filter(Boolean);

/* ------------------------------------------------------------------ chart */

/* Velocity over time: one series, so no legend box — the caption names it.
 * Bars are capped at 24px with a 4px rounded cap and a 2px surface gap, and
 * only the latest and the best sprint are direct-labelled; the history table
 * below is the table view for every other value. */
function velocityChart(sprints) {
  const data = sprints.slice().reverse()
    .map((s) => ({ sprint: s, name: s.name, value: num(s.velocity) }));
  if (!data.length) return el('p', { class: 'empty', text: 'No closed sprints yet.' });

  const W = 760, H = 210, padL = 34, padR = 12, padT = 16, padB = 34;
  const plotW = W - padL - padR, plotH = H - padT - padB;
  const max = Math.max(...data.map((d) => d.value), 1);
  const ceiling = Math.max(4, Math.ceil(max / 4) * 4);
  const band = plotW / data.length;
  const barW = Math.min(24, Math.max(8, band - 14));
  const y = (v) => padT + plotH - (v / ceiling) * plotH;

  const svgNS = 'http://www.w3.org/2000/svg';
  const make = (tag, attrs) => {
    const node = document.createElementNS(svgNS, tag);
    for (const [k, v] of Object.entries(attrs)) node.setAttribute(k, v);
    return node;
  };

  const svg = make('svg', { viewBox: `0 0 ${W} ${H}`, role: 'img' });
  const caption = make('title', {});
  caption.textContent =
    `Velocity by sprint: ${data.map((d) => `${d.name} ${d.value} points`).join('; ')}`;
  svg.append(caption);

  for (let i = 0; i <= 4; i++) {
    const value = (ceiling / 4) * i;
    const yy = y(value);
    const line = make('line', { x1: padL, x2: W - padR, y1: yy, y2: yy,
      class: i === 0 ? 'axis' : 'gridline' });
    svg.append(line);
    const tick = make('text', { x: padL - 7, y: yy + 3.5, 'text-anchor': 'end', class: 'tick' });
    tick.textContent = String(value);
    svg.append(tick);
  }

  // Axis labels are the short sprint tag ("2026-S02" -> "S02"); the full name,
  // dates and goal live in the tooltip. Long names side by side were unreadable.
  const shortName = (name) => {
    const text = String(name || '').trim();
    const tail = text.split(/[-\s/]/).filter(Boolean).pop() || text;
    return (tail.length <= 6 ? tail : tail.slice(-6)) || text;
  };
  // Still too tight? Label every Nth bar rather than overlap them.
  const widest = Math.max(...data.map((d) => shortName(d.name).length), 1);
  const every = Math.max(1, Math.ceil((widest * 6.6 + 8) / band));

  const best = Math.max(...data.map((d) => d.value));
  data.forEach((d, i) => {
    const x = padL + band * i + (band - barW) / 2;
    const top = y(d.value);
    const height = Math.max(0, padT + plotH - top);
    // 2px surface gap between neighbours comes from the band's leftover air.
    const bar = make('rect', { x, y: top, width: barW, height,
      rx: Math.min(4, barW / 2), class: 'bar' });
    const hit = make('rect', { x: padL + band * i, y: padT, width: band, height: plotH,
      class: 'bar-hit', tabindex: '0' });

    const s = d.sprint || {};
    const tip = make('title', {});
    tip.textContent = [
      s.name || d.name,
      isSet(s.title) ? `“${plain(s.title)}”` : '',
      isSet(s.start) ? `${s.start}${isSet(s.end) ? ' → ' + s.end : ''}` : '',
      `velocity ${d.value} pts`,
      isSet(s.committed) ? `committed ${s.committed} pts` : '',
      isSet(s.goal) ? `Goal: ${plain(s.goal)}` : '',
    ].filter(Boolean).join('\n');
    hit.append(tip);
    // The hit area precedes its bar so the `.bar-hit:hover + .bar` rule lights it up.
    svg.append(hit, bar);

    // Label the newest bar always, then every Nth going back, so the most
    // recent sprint is never the one that gets dropped.
    if ((data.length - 1 - i) % every === 0) {
      const label = make('text', { x: x + barW / 2, y: padT + plotH + 16,
        'text-anchor': 'middle', class: 'cat' });
      label.textContent = shortName(d.name);
      svg.append(label);
    }

    if (i === data.length - 1 || (d.value === best && best > 0)) {
      const value = make('text', { x: x + barW / 2, y: top - 6,
        'text-anchor': 'middle', class: 'direct' });
      value.textContent = String(d.value);
      svg.append(value);
    }
  });

  return el('figure', { class: 'chart', style: 'margin:0' },
    el('figcaption', {
      text: 'Completed story points per closed sprint, oldest first. '
          + 'Hover a bar for its full name, dates and goal.' }),
    svg);
}

/* ------------------------------------------------------------------ parts */

function badge(text, tone) {
  return el('span', { class: `badge${tone ? ' ' + tone : ''}`, text });
}

/* ------------------------------------------------------- state glyphs ----
 * Shape says what kind of thing it is, fill says how far along, an extra mark
 * says something is wrong. Drawn as SVG rather than emoji so the UI can set
 * weight and colour — but the ledger's own token (e.g. "✅ Ready") is always
 * on the title, because that is the word actually written in the file, and it
 * is what tells "✅ Ready" apart from "✅ Delivered".
 */
const SVG_NS = 'http://www.w3.org/2000/svg';

function svg(tag, attrs, ...kids) {
  const node = document.createElementNS(SVG_NS, tag);
  for (const [k, v] of Object.entries(attrs || {})) {
    if (v !== null && v !== undefined) node.setAttribute(k, v);
  }
  for (const kid of kids.flat()) if (kid) node.append(kid);
  return node;
}

const OUTER = {
  story: () => svg('circle', { cx: 7, cy: 7, r: 5.5, fill: 'none',
    stroke: 'currentColor', 'stroke-width': 1.5 }),
  bug: () => svg('path', { d: 'M7 1.25 12.75 7 7 12.75 1.25 7Z', fill: 'none',
    stroke: 'currentColor', 'stroke-width': 1.5, 'stroke-linejoin': 'round' }),
  epic: () => svg('rect', { x: 1.75, y: 1.75, width: 10.5, height: 10.5, rx: 2.5,
    fill: 'none', stroke: 'currentColor', 'stroke-width': 1.5 }),
};

// The ring's fill is the board column — how far round the clock the work is.
const COLUMN_FILL = {
  story: {
    'To Do': 'M7 5.5a1.5 1.5 0 1 1 0 3a1.5 1.5 0 1 1 0-3Z',
    'In Progress': 'M7 7V3.25A3.75 3.75 0 0 1 10.75 7Z',
    'In Review': 'M7 7V3.25A3.75 3.75 0 0 1 7 10.75Z',
    'In PR': 'M7 7V3.25A3.75 3.75 0 1 1 3.25 7Z',
    'Done': 'M7 3.25a3.75 3.75 0 1 1 0 7.5a3.75 3.75 0 1 1 0-7.5Z',
  },
  bug: {
    'To Do': 'M7 5.5a1.5 1.5 0 1 1 0 3a1.5 1.5 0 1 1 0-3Z',
    'In Progress': 'M7 4 10 7H7Z',
    'In Review': 'M7 4 10 7 7 10Z',
    'In PR': 'M7 4 10 7 7 10 4 7 7 7Z',
    'Done': 'M7 4 10 7 7 10 4 7Z',
  },
};

const CHECK = () => svg('path', { d: 'M4.4 7.2 6.2 9 9.7 5.2', fill: 'none',
  stroke: 'var(--surface)', 'stroke-width': 1.6,
  'stroke-linecap': 'round', 'stroke-linejoin': 'round' });
const BARS = () => svg('path', { d: 'M5 4.75h1.4v4.5H5ZM7.6 4.75H9v4.5H7.6Z',
  fill: 'currentColor' });
const SLASH = (d) => svg('path', { d, fill: 'none', stroke: 'currentColor',
  'stroke-width': 1.5, 'stroke-linecap': 'round' });

/** Tone class per state — colour supports the glyph, never replaces the word. */
const TONE = {
  story: { Draft: 'draft', Ready: 'ready', 'In Sprint': 'motion',
    Delivered: 'done', Paused: 'paused', Discarded: 'dropped' },
  bug: { Inbox: 'draft', Triaged: 'triaged', Confirmed: 'confirmed',
    'In Sprint': 'motion', Fixed: 'done', Deferred: 'paused', "Won't fix": 'dropped' },
  epic: { Proposed: 'draft', 'In Progress': 'motion', Done: 'done',
    Paused: 'paused', Discarded: 'dropped' },
};

const DASHED = { story: 'Draft', bug: 'Inbox', epic: 'Proposed' };

function glyph(entity, state, column) {
  const kids = [];
  const dashed = DASHED[entity] === state;

  if (state === 'Delivered' || state === 'Fixed' || (entity === 'epic' && state === 'Done')) {
    if (entity === 'story') kids.push(svg('circle', { cx: 7, cy: 7, r: 6.25, fill: 'currentColor' }));
    else if (entity === 'bug') kids.push(svg('path', { d: 'M7 .5 13.5 7 7 13.5 .5 7Z', fill: 'currentColor' }));
    else kids.push(svg('rect', { x: 1, y: 1, width: 12, height: 12, rx: 3, fill: 'currentColor' }));
    kids.push(CHECK());
  } else {
    const outer = OUTER[entity]();
    if (dashed) outer.setAttribute('stroke-dasharray', '2.6 1.9');
    kids.push(outer);

    if (state === 'In Sprint' && column && COLUMN_FILL[entity]) {
      const d = COLUMN_FILL[entity][column];
      if (d) kids.push(svg('path', { d, fill: 'currentColor' }));
    }
    if (entity === 'bug' && state === 'Confirmed') {
      kids.push(svg('circle', { cx: 7, cy: 7, r: 1.6, fill: 'currentColor' }));
    }
    if (entity === 'epic' && state === 'In Progress') {
      kids.push(svg('path', { d: 'M7 7V3.25A3.75 3.75 0 0 1 10.75 7Z', fill: 'currentColor' }));
    }
    if (state === 'Paused' || state === 'Deferred') kids.push(BARS());
    if (state === 'Discarded') kids.push(SLASH('M3.2 10.8 10.8 3.2'));
    if (state === "Won't fix") kids.push(SLASH('M4.6 9.4 9.4 4.6'));
  }
  return svg('svg', { width: 14, height: 14, viewBox: '0 0 14 14',
    'aria-hidden': 'true', focusable: 'false' }, kids);
}

/** The ledger's own token for a state, straight from /api/workspace. */
function ledgerWord(entity, state) {
  const labels = state && state_labels();
  return (labels && labels[entity] && labels[entity][state]) || show(state);
}

function state_labels() {
  return state.workspace && state.workspace.vocabulary && state.workspace.vocabulary.labels;
}

/** Which board column an item is sitting in right now, if any. */
function boardColumn(id) {
  const board = state.repo && state.repo.sprint && state.repo.sprint.board;
  if (!board) return '';
  for (const [column, items] of Object.entries(board)) {
    if (items.some((i) => i.id === id)) return column;
  }
  return '';
}

/**
 * The two-state chip: glyph, lifecycle word, and — only while the item is in a
 * sprint — a hairline and its board column. One object for the two states the
 * ledger really keeps.
 */
function stateChip(entity, stateName, options) {
  const opts = options || {};
  const name = show(stateName);
  const column = opts.column !== undefined ? opts.column : '';
  const chip = el('span', { class: `st st-${TONE[entity] && TONE[entity][name] || 'draft'}`,
    title: ledgerWord(entity, name) });
  chip.append(glyph(entity, name, column));
  chip.append(el('span', { class: 'st-word', text: name }));
  if (column) chip.append(el('span', { class: 'st-sub', text: column }));
  return chip;
}

/** Priority as ascending bars; the word and the ledger token come with it. */
function priorityMark(value) {
  const vocab = (state.workspace && state.workspace.vocabulary.priorities) || [];
  const entry = vocab.find((p) => p.value === String(value || '').trim());
  if (!entry) return el('span', { class: 'hint', text: EMPTY });
  const rank = vocab.indexOf(entry);              // 0 = highest
  const lit = vocab.length - rank;                // high lights all three
  const node = el('span', {
    class: `prio prio-${entry.name.toLowerCase()}`,
    title: entry.value, role: 'img', 'aria-label': `${entry.name} priority`,
  });
  for (let i = 1; i <= vocab.length; i++) {
    node.append(el('i', { class: i <= lit ? '' : 'off' }));
  }
  return node;
}

/** A section heading that carries its state's glyph, so the group header is
 *  itself the glyph + word pairing rather than a bare string. */
function stateHeading(entity, stateName) {
  const name = show(stateName);
  return el('span', { class: `st st-${(TONE[entity] || {})[name] || 'draft'}`,
      style: 'font-size:inherit', title: ledgerWord(entity, name) },
    glyph(entity, name, ''),
    el('span', { class: 'st-word', style: 'font-size:inherit', text: name }));
}

/** An epic index line stores the ledger's label ("✅ Ready"); reduce to the word. */
function indexState(label) {
  const text = show(label);
  const word = text.replace(/^[^\p{L}]*/u, '').trim();
  return word || 'Draft';
}

/** The blocked mark: icon plus the ledger's word, never colour alone. */
function blockedMark(reason) {
  const node = el('span', { class: 'mark-blocked', title: 'Blocked' });
  node.append(svg('svg', { width: 13, height: 13, viewBox: '0 0 14 14',
    'aria-hidden': 'true', focusable: 'false' }, [
    svg('circle', { cx: 7, cy: 7, r: 5.6, fill: 'none', stroke: 'currentColor', 'stroke-width': 1.5 }),
    svg('path', { d: 'M3.6 7h6.8', stroke: 'currentColor', 'stroke-width': 1.5, 'stroke-linecap': 'round' }),
  ]));
  node.append(el('span', { style: 'font-size:11.5px;font-weight:550',
    text: isSet(reason) ? `Blocked · ${reason}` : 'Blocked' }));
  return node;
}

/** Severity as a word pill — never a bare colour. */
function severityPill(value) {
  const name = show(value);
  if (name === EMPTY) return el('span', { class: 'hint', text: EMPTY });
  return el('span', { class: `badge sev sev-${name.toLowerCase()}`, text: name });
}

function kpi(label, value, note) {
  return el('div', { class: 'kpi' },
    el('div', { class: 'label', text: label }),
    el('div', { class: 'value', text: String(value) }),
    note ? el('div', { class: 'note', text: note }) : null);
}

function meter(done, total) {
  const pct = total > 0 ? Math.round((done / total) * 100) : 0;
  return el('div', { class: 'progress' },
    el('div', { class: 'nums' }, el('span', { text: `${done}/${total}` }), el('span', { text: `${pct}%` })),
    el('div', { class: 'meter', role: 'img', 'aria-label': `${done} of ${total} complete` },
      el('i', { style: `width:${pct}%` })));
}

function sectionHead(title, sub, ...actions) {
  const heading = el('h2', {});
  if (title instanceof Node) heading.append(title);
  else heading.textContent = title;
  return el('div', { class: 'section-head' },
    heading,
    sub ? el('span', { class: 'sub', text: sub }) : null,
    el('span', { class: 'grow' }), ...actions);
}

function matchesPerson(assignee) {
  if (!state.person) return true;
  return nameOf(assignee).toLowerCase() === state.person.toLowerCase();
}

/* ------------------------------------------------------------------ views */

const VIEWS = {};

VIEWS.overview = () => {
  const repo = state.repo;
  const s = repo.stats;
  const wrap = el('div', {});

  const placement = repo.placement === 'in-repo'
    ? `${repo.slug} · ledger inside this repo`
    : `${repo.slug} · ledger in its own repo`;
  wrap.append(el('section', { class: 'section' },
    sectionHead('At a glance', placement),
    el('div', { class: 'kpis' },
      kpi('Ready to build', s.ready, `${s.ready_points} pts waiting`),
      kpi('In this sprint', s.in_sprint, isSet(s.sprint_name) ? s.sprint_name : 'no sprint open'),
      kpi('Blocked', s.blocked, s.blocked ? 'needs a decision' : 'nothing blocked'),
      kpi('Open bugs', s.open_bugs, `${s.inbox_bugs} untriaged`),
      kpi('Unreleased', s.increment, 'done, awaiting a release'),
      kpi('Ideas waiting', s.inbox_ideas, 'in the inbox'))));

  if (isSet(s.sprint_name)) {
    const sprint = repo.sprint;
    wrap.append(el('section', { class: 'section' },
      sectionHead('Current sprint', `${show(sprint.name)} · ${show(sprint.dates)}`),
      el('div', { class: 'card' },
        prose(sprint.goal, 'p', { style: 'margin:0 0 10px' }),
        el('div', { class: 'chips' },
          state.workspace.vocabulary.board_columns.map((col) =>
            badge(`${col} ${sprint.board[col].length}`, col === 'Done' ? 'good' : ''))))));
  }

  wrap.append(el('section', { class: 'section' },
    sectionHead('Velocity', 'how much the team actually completes'),
    velocityChart(repo.history.sprints)));

  const mine = repo.stories.filter((x) => x.state === 'In Sprint' && matchesPerson(x.assignee));
  if (state.person) {
    wrap.append(el('section', { class: 'section' },
      sectionHead(`${state.person}'s sprint work`, `${mine.length} item(s)`),
      mine.length ? storyTable(mine) : el('p', { class: 'empty', text: 'Nothing assigned in this sprint.' })));
  }
  return wrap;
};

VIEWS.board = () => {
  const repo = state.repo;
  const sprint = repo.sprint;
  const wrap = el('div', {});

  const planBtn = el('button', { class: 'btn primary', type: 'button', onclick: planSprintForm }, 'Plan sprint');
  const closeBtn = el('button', { class: 'btn', type: 'button', onclick: closeSprintForm }, 'Close sprint');
  wrap.append(sectionHead(
    isSet(sprint.name) ? `Sprint ${sprint.name}` : 'No sprint open',
    [show(sprint.goal), isSet(sprint.dates) ? sprint.dates : null,
     isSet(sprint.capacity) ? `capacity ${sprint.capacity} pts` : null].filter(Boolean).join(' · '),
    planBtn, isSet(sprint.name) ? closeBtn : null));

  if (!isSet(sprint.name)) {
    wrap.append(el('p', { class: 'empty', text: 'Run “Plan sprint” to pull Ready stories and triaged bugs onto the board.' }));
    return wrap;
  }

  const blockedIds = new Set(sprint.blocked.map((b) => b.id));
  const board = el('div', { class: 'board' });

  for (const column of state.workspace.vocabulary.board_columns) {
    const items = sprint.board[column].filter((i) => matchesPerson(i.assignee));
    const points = items.reduce((sum, i) => sum + num(i.points), 0);
    const node = el('div', { class: 'column', dataset: { column } },
      el('h3', {}, el('span', { text: column }),
        el('span', { class: 'n', text: `${items.length}${points ? ' · ' + points + 'p' : ''}` })));

    for (const item of items) {
      node.append(ticket(item, column, blockedIds.has(item.id)));
    }
    if (!items.length) node.append(el('p', { class: 'hint', style: 'text-align:center;padding:10px 0', text: '—' }));

    node.addEventListener('dragover', (e) => { e.preventDefault(); node.classList.add('drop'); });
    node.addEventListener('dragleave', () => node.classList.remove('drop'));
    node.addEventListener('drop', (e) => {
      e.preventDefault();
      node.classList.remove('drop');
      const id = e.dataTransfer.getData('text/plain');
      if (id) moveItem(id, column);
    });
    board.append(node);
  }
  wrap.append(board);

  if (sprint.blocked.length) {
    wrap.append(el('section', { class: 'section', style: 'margin-top:18px' },
      sectionHead(`🚧 Blocked (${sprint.blocked.length})`,
        'a flag, not a column — each item keeps its place on the board'),
      el('div', { class: 'stack' }, sprint.blocked.map((b) =>
        el('div', { class: 'blocked' },
          el('div', { class: 'grow' },
            el('div', { class: 'blocked-head' },
              el('button', { class: 'idlink', type: 'button',
                onclick: () => openItem(b.id) }, b.id),
              el('span', { class: 'blocked-title', text: show(b.title) })),
            el('div', { class: 'blocked-why' },
              el('span', { class: 'blocked-label' }, blockedMark()),
              prose(b.reason || b.text, 'span', { class: 'blocked-reason' }))),
          el('button', { class: 'btn small', type: 'button',
            onclick: () => act('set_blocked', { item_id: b.id, blocked: false }, 'Unblocked') },
            'Unblock'))))));
  }
  return wrap;
};

/** Story / bug ids as small clickable chips, so a long list still wraps. */
function idChips(ids) {
  if (!ids || !ids.length) return document.createTextNode(EMPTY);
  const wrap = el('span', { class: 'chips' });
  for (const id of ids) {
    wrap.append(el('button', { class: 'idlink', type: 'button',
      onclick: () => openItem(id) }, id));
  }
  return wrap;
}

function ticket(item, column, blocked) {
  const entity = item.id.startsWith('BUG') ? 'bug' : 'story';
  const node = el('div', { class: `ticket${blocked ? ' is-blocked' : ''}`,
      draggable: 'true', dataset: { id: item.id } },
    el('div', { class: 't-id' },
      // Shape = story or bug, fill = how far round the board it is. The column
      // heading above supplies the word, so this is never colour alone.
      el('span', { class: 'st st-motion', style: 'gap:5px',
        title: `${ledgerWord(entity, 'In Sprint')} · ${column}` },
        glyph(entity, 'In Sprint', column)),
      el('span', { text: item.id })),
    el('div', { class: 't-title', text: show(item.title) }),
    el('div', { class: 't-foot' },
      el('span', { text: isSet(item.assignee) ? item.assignee : 'unassigned' }),
      el('span', { class: 'chips' },
        blocked ? blockedMark() : null,
        isSet(item.points) ? badge(`${item.points} pts`) : null)));

  node.addEventListener('dragstart', (e) => {
    e.dataTransfer.setData('text/plain', item.id);
    node.classList.add('dragging');
  });
  node.addEventListener('dragend', () => node.classList.remove('dragging'));
  node.addEventListener('click', () => openItem(item.id));
  return node;
}

function moveItem(id, column) {
  if (column === 'Done') return completeForm(id);
  return act('move_board_item', { item_id: id, column });
}

VIEWS.ideas = () => {
  const repo = state.repo;
  const wrap = el('div', {});
  wrap.append(sectionHead('Idea inbox', 'raw captures, newest first',
    el('button', { class: 'btn primary', type: 'button', onclick: newIdeaForm }, 'New idea')));

  if (!repo.ideas.length) {
    wrap.append(el('p', { class: 'empty', text: 'The inbox is empty.' }));
  } else {
    wrap.append(el('div', { class: 'stack' }, repo.ideas.map((idea) =>
      el('div', { class: 'item' },
        el('span', { class: 'when', text: show(idea.date) }),
        prose(idea.text, 'div', { class: 'grow' }),
        el('div', { class: 'item-actions' },
          el('button', { class: 'btn small', type: 'button', onclick: () => triageToEpicForm(idea) }, '→ Epic'),
          el('button', { class: 'btn small', type: 'button', onclick: () => triageToStoryForm(idea) }, '→ Story'),
          el('button', { class: 'btn small', type: 'button', onclick: () => discardIdea(idea) }, 'Discard'))))));
  }

  wrap.append(el('section', { class: 'section', style: 'margin-top:22px' },
    sectionHead('Bug inbox', 'untriaged reports',
      el('button', { class: 'btn', type: 'button', onclick: newBugForm }, 'Report bug')),
    repo.bug_inbox.length
      ? el('div', { class: 'stack' }, repo.bug_inbox.map((bug) =>
          el('div', { class: 'item' },
            el('span', { class: 'when', text: show(bug.date) }),
            prose(bug.text, 'div', { class: 'grow' }),
            el('button', { class: 'btn small', type: 'button', onclick: () => triageBugForm(bug) }, 'Triage'))))
      : el('p', { class: 'empty', text: 'No untriaged bug reports.' })));
  return wrap;
};

VIEWS.epics = () => {
  const repo = state.repo;
  const wrap = el('div', {});
  wrap.append(sectionHead('Epics', `${repo.epics.length} epic(s) · status and totals are derived from the stories`,
    el('button', { class: 'btn', type: 'button', onclick: newEpicForm }, 'New epic')));

  if (!repo.epics.length) return (wrap.append(el('p', { class: 'empty', text: 'No epics yet.' })), wrap);

  for (const epic of repo.epics) {
    const roll = epic.rollup;
    const card = el('div', { class: 'epic' },
      el('div', { class: 'epic-head' },
        el('div', { class: 'grow' },
          el('div', { class: 'chips' },
            el('span', { class: 'id', text: epic.id }), stateChip('epic', epic.state),
            isSet(epic.target) ? badge(`target ${epic.target}`) : null,
            isSet(epic.area) ? badge(epic.area) : null),
          el('h3', { style: 'margin-top:6px', text: show(epic.title) }),
          isSet(epic.goal) ? prose(epic.goal, 'p', { class: 'goal' }) : null),
        el('div', { class: 'progress' },
          el('div', { class: 'hint', style: 'margin-bottom:3px', text: 'Stories' }),
          meter(roll.stories_done, roll.stories_total),
          el('div', { class: 'hint', style: 'margin:8px 0 3px', text: 'Points' }),
          meter(roll.points_done, roll.points_total))));

    const rows = epic.stories.filter((i) => matchesPerson(i.assignee));
    if (rows.length) {
      const table = el('table', { class: 'grid', style: 'margin-top:12px' },
        el('thead', {}, el('tr', {},
          ['ID', 'Title', 'State', 'Pri', 'Pts', 'Assignee', ''].map((h) => el('th', { text: h })))),
        el('tbody', {}, rows.map((item) => {
          const detailed = repo.stories.some((s) => s.id === item.id);
          return el('tr', { class: 'row-link' },
            el('td', { class: 'id', text: item.id }),
            el('td', { text: show(item.title) }),
            el('td', {}, stateChip('story', indexState(item.state),
              { column: boardColumn(item.id) })),
            el('td', {}, priorityMark(item.priority)),
            el('td', { class: 'num', text: show(item.points) }),
            el('td', { text: show(item.assignee) }),
            el('td', {}, detailed
              ? el('button', { class: 'btn small', type: 'button', onclick: () => openItem(item.id) }, 'Open')
              : el('button', { class: 'btn small primary', type: 'button', onclick: () => detailStoryForm(item, epic) }, 'Detail')));
        })));
      card.append(table);
    }

    if (epic.history && epic.history.length) {
      card.append(el('div', { class: 'detail-block', style: 'margin-top:12px' },
        el('h4', { text: 'History' }),
        el('ul', {}, epic.history.map((h) => prose(h, 'li')))));
    }
    wrap.append(card);
  }
  return wrap;
};

function storyTable(stories) {
  return el('table', { class: 'grid' },
    el('thead', {}, el('tr', {},
      ['ID', 'Title', 'State', 'Pri', 'Pts', 'Epic', 'Assignee'].map((h) => el('th', { text: h })))),
    el('tbody', {}, stories.map((story) =>
      el('tr', { class: 'row-link', onclick: () => openItem(story.id) },
        el('td', { class: 'id', text: story.id }),
        el('td', { text: show(story.title) }),
        el('td', {}, stateChip('story', story.state, { column: boardColumn(story.id) })),
        el('td', {}, priorityMark(story.priority)),
        el('td', { class: 'num', text: show(story.estimate) }),
        el('td', { class: 'id', text: show(story.parent) }),
        el('td', { text: show(story.assignee) })))));
}

VIEWS.stories = () => {
  const repo = state.repo;
  const wrap = el('div', {});
  const states = state.workspace.vocabulary.story_states;
  wrap.append(sectionHead('User stories', `${repo.stories.length} detailed · Draft stories live on their epic`));

  const drafts = repo.epics.flatMap((e) => e.stories.filter((i) => /Draft/.test(i.state || ''))
    .map((i) => ({ ...i, epic: e })));
  if (drafts.length) {
    wrap.append(el('section', { class: 'section' },
      sectionHead(stateHeading('story', 'Draft'),
        `${drafts.length} — triaged, not yet detailed`),
      el('div', { class: 'stack' }, drafts.map((d) =>
        el('div', { class: 'item' },
          el('span', { class: 'id', text: d.id }),
          stateChip('story', 'Draft'),
          el('div', { class: 'grow', text: show(d.title) }),
          badge(d.epic.id),
          el('button', { class: 'btn small primary', type: 'button',
            onclick: () => detailStoryForm(d, d.epic) }, 'Detail'))))));
  }

  for (const name of states) {
    const group = repo.stories.filter((s) => s.state === name && matchesPerson(s.assignee));
    if (!group.length) continue;
    const points = group.reduce((sum, s) => sum + num(s.estimate), 0);
    wrap.append(el('section', { class: 'section' },
      sectionHead(stateHeading('story', name), `${group.length} · ${points} pts`),
      storyTable(group)));
  }
  return wrap;
};

VIEWS.bugs = () => {
  const repo = state.repo;
  const wrap = el('div', {});
  wrap.append(sectionHead('Bugs', `${repo.bugs.length} registered · ${repo.bug_inbox.length} untriaged`,
    el('button', { class: 'btn', type: 'button', onclick: newBugForm }, 'Report bug')));

  for (const name of state.workspace.vocabulary.bug_states) {
    if (name === 'Inbox') continue;
    const group = repo.bugs.filter((b) => b.state === name && matchesPerson(b.assignee));
    if (!group.length) continue;
    wrap.append(el('section', { class: 'section' },
      sectionHead(stateHeading('bug', name), `${group.length}`),
      el('table', { class: 'grid' },
        el('thead', {}, el('tr', {},
          ['ID', 'Title', 'Sev', 'Pri', 'Relates to', 'Assignee'].map((h) => el('th', { text: h })))),
        el('tbody', {}, group.map((bug) =>
          el('tr', { class: 'row-link', onclick: () => openItem(bug.id) },
            el('td', { class: 'id', text: bug.id }),
            el('td', { text: show(bug.title) }),
            el('td', {}, severityPill(bug.severity)),
            el('td', {}, priorityMark(bug.priority)),
            el('td', { class: 'id', text: show(bug.relates_to) }),
            el('td', { text: show(bug.assignee) })))))));
  }
  if (!repo.bugs.length) wrap.append(el('p', { class: 'empty', text: 'No registered bugs.' }));
  return wrap;
};

VIEWS.sprints = () => {
  const repo = state.repo;
  const wrap = el('div', {});
  wrap.append(sectionHead('Sprint history', `rolling velocity ${show(repo.history.rolling_velocity)}`));
  wrap.append(velocityChart(repo.history.sprints));

  if (repo.history.sprints.length) {
    wrap.append(el('section', { class: 'section', style: 'margin-top:18px' },
      el('table', { class: 'grid sprints' },
        el('thead', {}, el('tr', {},
          [['Sprint', ''], ['Start', 'date'], ['End', 'date'], ['Goal', 'wide'],
           ['Committed', 'num'], ['Completed', 'num'], ['Velocity', 'num'],
           ['Delivered', 'ids'], ['Carried over', 'ids']]
            .map(([h, cls]) => el('th', { class: cls, text: h })))),
        el('tbody', {}, repo.history.sprints.map((s) =>
          el('tr', {},
            el('td', { class: 'id' },
              el('strong', { text: show(s.name) }),
              isSet(s.title) ? el('div', { class: 'hint', text: s.title }) : null),
            el('td', { class: 'date', text: show(s.start) }),
            el('td', { class: 'date', text: show(s.end) }),
            prose(s.goal, 'td', { class: 'wide' }),
            el('td', { class: 'num', text: show(s.committed) }),
            el('td', { class: 'num', text: show(s.completed) }),
            el('td', { class: 'num strong', text: show(s.velocity) }),
            el('td', { class: 'ids' }, idChips(s.delivered)),
            el('td', { class: 'ids' }, idChips(s.carried))))))));
  } else {
    wrap.append(el('p', { class: 'empty', text: 'No sprints closed yet.' }));
  }
  return wrap;
};

VIEWS.releases = () => {
  const repo = state.repo;
  const releases = repo.releases;
  const wrap = el('div', {});
  wrap.append(sectionHead('Increment', 'done, not yet released',
    el('button', { class: 'btn primary', type: 'button', onclick: cutReleaseForm,
      disabled: releases.increment.length ? null : true }, 'Cut release')));

  wrap.append(releases.increment.length
    ? el('div', { class: 'stack' }, releases.increment.map((i) =>
        el('div', { class: 'item' }, prose(i.text, 'div', { class: 'grow' }))))
    : el('p', { class: 'empty', text: 'Nothing waiting to be released.' }));

  wrap.append(el('section', { class: 'section', style: 'margin-top:22px' },
    sectionHead('Version history', 'newest first'),
    releases.versions.length
      ? el('div', { class: 'stack' }, releases.versions.map((v) =>
          el('div', { class: 'item' },
            el('div', { class: 'grow' },
              el('div', { class: 'chips' },
                el('strong', { text: v.version }),
                isSet(v.date) ? badge(v.date) : null),
              el('h3', { style: 'margin:5px 0 3px; font-size:14px', text: show(v.title) }),
              isSet(v.theme) ? prose(v.theme, 'p', { style: 'margin:0' }) : null,
              el('p', { class: 'hint', style: 'margin:6px 0 0',
                text: `Stories: ${v.stories.join(', ') || EMPTY}  ·  Epics: ${v.epics.join(', ') || EMPTY}` })))))
      : el('p', { class: 'empty', text: 'No releases cut yet.' })));
  return wrap;
};

/* The command sheet. Descriptions come from the shipped commands/*.md
 * frontmatter via /api/commands, so this list cannot drift from the plugin. */
const HERE_ACTIONS = {
  add_idea: newIdeaForm,
  add_bug: newBugForm,
  plan_sprint: planSprintForm,
  close_sprint: closeSprintForm,
  cut_release: cutReleaseForm,
  check: runCheck,
  commit: commitForm,
};

const ACTION_VIEW = {
  triage_idea_to_story: 'ideas', triage_bug: 'ideas',
  detail_story: 'stories', move_board_item: 'board', complete_item: 'board',
};

function copyCommand(text) {
  navigator.clipboard?.writeText(text).then(
    () => toast('ok', 'Copied', text),
    () => toast('warn', text, 'Copy it by hand — the clipboard is blocked.'));
}

VIEWS.commands = () => {
  const wrap = el('div', {});
  const sheet = state.commands;
  if (!sheet) {
    wrap.append(el('p', { class: 'empty', text: 'Loading the command sheet…' }));
    loadCommands();
    return wrap;
  }

  const here = sheet.groups.reduce((n, g) => n + g.commands.filter((c) => c.here).length, 0);
  const search = el('input', { type: 'text', placeholder: 'Filter commands…',
    'aria-label': 'Filter commands', style: 'min-width:200px' });
  wrap.append(sectionHead('Commands', `${sheet.total} commands · ${here} usable from this page`, search));
  wrap.append(el('p', { class: 'hint', style: 'margin:-4px 0 16px',
    text: 'Everything Agile-Ledger Pro can do. “Here” runs on this page; “In Claude Code” means type it in the session — those read your code or your git history, or need a judgement call.' }));

  const body = el('div', {});
  const draw = (needle) => {
    body.replaceChildren();
    for (const group of sheet.groups) {
      const rows = group.commands.filter((c) =>
        !needle || (`/${c.name} ${c.description} ${c.writes}`).toLowerCase().includes(needle));
      if (!rows.length) continue;

      body.append(el('section', { class: 'section' },
        sectionHead(group.group, group.blurb),
        el('table', { class: 'grid' },
          el('thead', {}, el('tr', {},
            ['Command', 'What it does', 'Writes', 'Where'].map((h) => el('th', { text: h })))),
          el('tbody', {}, rows.map((c) => {
            const full = `/${c.name}${c.args ? ' ' + c.args : ''}`;
            const run = HERE_ACTIONS[c.action];
            const view = c.view || ACTION_VIEW[c.action];
            return el('tr', {},
              el('td', {},
                el('button', { class: 'cmdbtn', type: 'button', title: 'Copy this command',
                  onclick: () => copyCommand(full) }, full)),
              el('td', {},
                el('div', { text: c.description || EMPTY }),
                c.note ? el('div', { class: 'hint', style: 'margin-top:3px', text: c.note }) : null),
              el('td', { class: 'id', text: c.writes }),
              el('td', {}, run
                ? el('button', { class: 'btn small primary', type: 'button', onclick: run }, 'Do it here')
                : view
                  ? el('button', { class: 'btn small', type: 'button', onclick: () => goTo(view) }, 'Open tab')
                  : badge('In Claude Code')));
          })))));
    }
    if (!body.children.length) {
      body.append(el('p', { class: 'empty', text: 'No command matches that.' }));
    }
  };

  search.addEventListener('input', () => draw(search.value.trim().toLowerCase()));
  draw('');
  wrap.append(body);

  if (sheet.source) {
    wrap.append(el('p', { class: 'hint', style: 'margin-top:14px',
      text: `Read from ${sheet.source} — this sheet is generated from the installed commands, so it always matches your version.` }));
  }
  return wrap;
};

async function loadCommands() {
  try {
    state.commands = await api('/api/commands');
    if (state.route && state.route.name === 'commands') render();
  } catch (error) {
    toast('err', 'Could not load the command sheet', error.message);
  }
}

VIEWS.files = () => {
  const wrap = el('div', {});
  wrap.append(sectionHead('Ledger files', 'the Markdown this page is built from',
    el('button', { class: 'btn', type: 'button', onclick: runCheck }, 'Run ledger check')));
  const pre = el('pre', { class: 'source', text: 'Pick a file…' });
  const wanted = state.route && state.route.param;
  const load = async (name) => {
    try {
      const data = await api(`/api/repo/${encodeURIComponent(state.slug)}/file/${encodeURIComponent(name)}`);
      pre.textContent = data.text;
    } catch (error) { pre.textContent = `Could not read ${name}: ${error.message}`; }
  };
  const picker = el('div', { class: 'chips', style: 'margin-bottom:12px' },
    state.workspace.vocabulary.files.map((name) =>
      el('button', { class: `btn small${name === wanted ? ' primary' : ''}`, type: 'button',
        onclick: () => { location.hash = `#/files/${encodeURIComponent(name)}`; } }, name)));
  wrap.append(picker, pre);
  // #/files/<name> is a real address, so a link to a file opens it.
  if (wanted) load(wanted);
  return wrap;
};

/* ------------------------------------------------------------- item drawer */

function openItem(id) {
  const repo = state.repo;
  const story = repo.stories.find((s) => s.id === id);
  const bug = repo.bugs.find((b) => b.id === id);
  if (!story && !bug) { toast('warn', 'No detail yet', `${id} has no full entry — detail it first.`); return; }

  const body = document.getElementById('drawer-body');
  document.getElementById('drawer-title').textContent = id;
  body.replaceChildren(story ? storyDetail(story) : bugDetail(bug));
  const drawer = document.getElementById('drawer');
  drawer.hidden = false;
  drawer.setAttribute('aria-hidden', 'false');
}

function closeDrawer() {
  const drawer = document.getElementById('drawer');
  drawer.hidden = true;
  drawer.setAttribute('aria-hidden', 'true');
}

function kvList(pairs) {
  const list = el('dl', { class: 'kv' });
  for (const [key, value] of pairs) {
    list.append(el('dt', { text: key }), el('dd', { text: show(value) }));
  }
  return list;
}

function storyDetail(story) {
  const wrap = el('div', {});
  wrap.append(el('div', { class: 'chips', style: 'margin-bottom:10px' },
    stateChip('story', story.state, { column: boardColumn(story.id) }),
    priorityMark(story.priority),
    isSet(story.parent) ? badge(story.parent) : null));
  wrap.append(el('h3', { style: 'margin-bottom:12px', text: show(story.title) }));

  wrap.append(el('div', { class: 'detail-block' },
    kvList([['Estimate', story.estimate], ['Area', story.area], ['Layer', story.layer],
            ['Assignee', story.assignee],
            ['Dependencies', story.dependencies.join(', ')],
            ['Delivered', story.delivered]])));

  if (isSet(story.story)) {
    wrap.append(el('div', { class: 'detail-block' },
      el('h4', { text: 'Story' }), prose(story.story)));
  }
  if (story.criteria_met) {
    wrap.append(el('div', { class: 'detail-block' },
      el('h4', { text: 'Acceptance criteria' }), el('p', { text: 'All met ✓' })));
  } else if (story.criteria.length) {
    wrap.append(el('div', { class: 'detail-block' },
      el('h4', { text: 'Acceptance criteria' }),
      el('ul', {}, story.criteria.map((c) => prose(c, 'li')))));
  }
  if (isSet(story.reason)) {
    wrap.append(el('div', { class: 'detail-block' }, el('h4', { text: 'Reason' }), prose(story.reason)));
  }
  if (isSet(story.notes)) {
    wrap.append(el('div', { class: 'detail-block' }, el('h4', { text: 'Notes' }), prose(story.notes)));
  }

  const actionsRow = el('div', { class: 'item-actions', style: 'margin-top:16px' },
    el('button', { class: 'btn primary', type: 'button', onclick: () => editStoryForm(story) }, 'Edit'),
    el('button', { class: 'btn', type: 'button', onclick: () => branchFor(story) }, 'Copy branch name'));
  for (const name of state.workspace.vocabulary.story_states) {
    if (name === story.state) continue;
    actionsRow.append(el('button', { class: 'btn small', type: 'button',
      onclick: () => changeStoryState(story, name) }, `→ ${name}`));
  }
  wrap.append(actionsRow);
  return wrap;
}

function bugDetail(bug) {
  const wrap = el('div', {});
  wrap.append(el('div', { class: 'chips', style: 'margin-bottom:10px' },
    stateChip('bug', bug.state, { column: boardColumn(bug.id) }),
    severityPill(bug.severity),
    priorityMark(bug.priority)));
  wrap.append(el('h3', { style: 'margin-bottom:12px', text: show(bug.title) }));
  wrap.append(el('div', { class: 'detail-block' },
    kvList([['Estimate', bug.estimate], ['Area', bug.area], ['Assignee', bug.assignee],
            ['Reported by', bug.reported_by], ['Relates to', bug.relates_to], ['Fixed', bug.fixed]])));

  for (const [label, value] of [['Symptom', bug.symptom], ['Expected', bug.expected],
                                ['Actual', bug.actual], ['Assessment', bug.assessment],
                                ['Notes', bug.notes]]) {
    if (isSet(value)) {
      wrap.append(el('div', { class: 'detail-block' }, el('h4', { text: label }), prose(value)));
    }
  }
  if (bug.steps.length) {
    wrap.append(el('div', { class: 'detail-block' },
      el('h4', { text: `Steps to reproduce (${bug.steps_confidence || 'unconfirmed'})` }),
      el('ol', {}, bug.steps.map((s) => prose(s, 'li')))));
  }

  const actionsRow = el('div', { class: 'item-actions', style: 'margin-top:16px' },
    el('button', { class: 'btn primary', type: 'button', onclick: () => editBugForm(bug) }, 'Edit'),
    el('button', { class: 'btn', type: 'button', onclick: () => branchFor(bug) }, 'Copy branch name'));
  for (const name of state.workspace.vocabulary.bug_states) {
    if (name === bug.state || name === 'Inbox') continue;
    actionsRow.append(el('button', { class: 'btn small', type: 'button',
      onclick: async () => { await act('set_bug_state', { bug_id: bug.id, state: name }); closeDrawer(); } },
      `→ ${name}`));
  }
  wrap.append(actionsRow);
  return wrap;
}

async function changeStoryState(story, name) {
  if (name === 'Paused' || name === 'Discarded') {
    openModal(`${story.id} → ${name}`,
      [field('Reason', textArea('reason', '', 'Why is it being set aside? Kept with the entry forever.'))],
      async (data) => { await act('set_story_state', { story_id: story.id, state: name, reason: data.reason }); closeDrawer(); },
      { submit: name });
    return;
  }
  await act('set_story_state', { story_id: story.id, state: name });
  closeDrawer();
}

function branchFor(item, justReturn) {
  const slug = String(item.title || '').toLowerCase().split(/\s+/)
    .map((w) => w.replace(/[^a-z0-9]/g, '')).filter(Boolean).slice(0, 5).join('-');
  const branch = `${item.id.toLowerCase()}-${slug || 'work'}`;
  if (justReturn) return branch;
  navigator.clipboard?.writeText(branch).then(
    () => toast('ok', 'Branch name copied', branch),
    () => toast('warn', 'Branch name', branch));
  return branch;
}

/* -------------------------------------------------------------- the forms */

function newIdeaForm() {
  openModal('Capture an idea',
    [field('Idea', textArea('text', '', 'Any language. Raw is fine — /triage shapes it later.', 3),
      'Appended to Ideas.md exactly as /idea would.')],
    (data) => act('add_idea', { text: data.text }), { submit: 'Capture' });
}

function newBugForm() {
  openModal('Report a bug',
    [field('What happened', textArea('text', '', 'The reporter’s words, as they said them.', 3),
      'Appended to the Bugs.md inbox, like /bug.')],
    (data) => act('add_bug', { text: data.text }), { submit: 'Report' });
}

function newEpicForm() {
  openModal('New epic', [
    field('Title', textInput('title', '', 'User onboarding')),
    field('Goal', textArea('goal', '', 'One line: the outcome this epic buys.', 2)),
    el('div', { class: 'form-grid' },
      field('Area', textInput('area', '', 'onboarding')),
      field('Target version', textInput('target', '', 'v2.0'))),
  ], (data) => act('triage_idea_to_epic', data), { submit: 'Create epic' });
}

function triageToEpicForm(idea) {
  openModal('Promote to an epic', [
    el('p', { class: 'hint', text: idea.text }),
    field('Title', textInput('title', idea.text.slice(0, 60))),
    field('Goal', textArea('goal', '', 'One line: the outcome this epic buys.', 2)),
    el('div', { class: 'form-grid' },
      field('Area', textInput('area', '')),
      field('Target version', textInput('target', ''))),
  ], (data) => act('triage_idea_to_epic', { ...data, idea_line: idea.line }),
     { submit: 'Create epic', note: 'The idea leaves the inbox.' });
}

function triageToStoryForm(idea) {
  const epics = state.repo.epics;
  if (!epics.length) { toast('warn', 'No epic yet', 'Create an epic first — a story needs a parent.'); return; }
  openModal('Promote to a story', [
    el('p', { class: 'hint', text: idea.text }),
    field('Title', textInput('title', idea.text.slice(0, 60))),
    el('div', { class: 'form-grid' },
      field('Parent epic', selectInput('epic_id', epics.map((e) => [e.id, `${e.id} — ${e.title}`]))),
      field('Priority', priorityInput(''))),
  ], (data) => act('triage_idea_to_story', { ...data, idea_line: idea.line }),
     { submit: 'Create story', note: 'Starts as 📝 Draft — an index line on its epic.' });
}

function discardIdea(idea) {
  openModal('Discard this idea?', [el('p', { text: idea.text })],
    () => act('discard_idea', { idea_line: idea.line }, 'Idea discarded'),
    { submit: 'Discard', note: 'It is removed from the inbox.' });
}

function triageBugForm(bug) {
  const vocab = state.workspace.vocabulary;
  openModal('Triage this report', [
    el('p', { class: 'hint', text: bug.text }),
    field('Title', textInput('title', bug.text.slice(0, 70))),
    el('div', { class: 'form-grid' },
      field('Severity', selectInput('severity', vocab.severities, 'minor'), 'impact'),
      field('Priority', priorityInput(''), 'when to fix'),
      field('Area', textInput('area', ''))),
    el('div', { class: 'form-grid' },
      field('Reported by', textInput('reported_by', '')),
      field('Relates to', textInput('relates_to', '', 'US-014'))),
  ], (data) => act('triage_bug', { ...data, symptom: bug.text, inbox_line: bug.line }),
     { submit: 'Register bug' });
}

function detailStoryForm(item, epic) {
  const vocab = state.workspace.vocabulary;
  openModal(`Detail ${item.id}`, [
    field('Title', textInput('title', item.title)),
    field('Story', textArea('story', '', 'As a <role>, I want <goal>, so that <benefit>.', 2)),
    field('Acceptance criteria', textArea('criteria', '',
      'One per line: Given <context>, when <action>, then <outcome>.', 4),
      'Given / When / Then — binary pass/fail so a developer can self-verify.'),
    el('div', { class: 'form-grid' },
      field('Priority', priorityInput(item.priority)),
      field('Estimate', selectInput('estimate', ['', ...vocab.fibonacci], item.points)),
      field('Layer', selectInput('layer', ['', ...vocab.layers], ''))),
    el('div', { class: 'form-grid' },
      field('Area', textInput('area', epic ? epic.area : '')),
      field('Assignee', textInput('assignee', item.assignee)),
      field('Dependencies', textInput('dependencies', '', 'US-009, US-012'))),
  ], (data) => act('detail_story', {
      story_id: item.id,
      title: data.title, story: data.story,
      criteria: linesOf(data.criteria),
      priority: data.priority, estimate: data.estimate, area: data.area,
      layer: data.layer, assignee: data.assignee,
      dependencies: String(data.dependencies || '').split(/[,\s]+/).filter(Boolean),
    }), { submit: 'Save as Ready', note: 'Definition of Ready gaps are reported, not blocked.' });
}

function editStoryForm(story) {
  const vocab = state.workspace.vocabulary;
  openModal(`Edit ${story.id}`, [
    field('Title', textInput('title', story.title)),
    field('Story', textArea('story', story.story, '', 2)),
    field('Acceptance criteria', textArea('criteria', story.criteria.join('\n'), '', 4)),
    el('div', { class: 'form-grid' },
      field('Priority', priorityInput(story.priority)),
      field('Estimate', selectInput('estimate', ['', ...vocab.fibonacci], story.estimate)),
      field('Layer', selectInput('layer', ['', ...vocab.layers], story.layer))),
    el('div', { class: 'form-grid' },
      field('Area', textInput('area', story.area)),
      field('Assignee', textInput('assignee', story.assignee)),
      field('Dependencies', textInput('dependencies', story.dependencies.join(', ')))),
    field('Notes', textArea('notes', story.notes, '', 2)),
  ], async (data) => {
      await act('update_story', {
        story_id: story.id, title: data.title, story: data.story,
        criteria: linesOf(data.criteria), priority: data.priority,
        estimate: data.estimate, area: data.area, layer: data.layer,
        assignee: data.assignee, notes: data.notes,
        dependencies: String(data.dependencies || '').split(/[,\s]+/).filter(Boolean),
      });
      closeDrawer();
    });
}

function editBugForm(bug) {
  const vocab = state.workspace.vocabulary;
  openModal(`Edit ${bug.id}`, [
    field('Title', textInput('title', bug.title)),
    el('div', { class: 'form-grid' },
      field('Severity', selectInput('severity', vocab.severities, bug.severity)),
      field('Priority', priorityInput(bug.priority)),
      field('Estimate', selectInput('estimate', ['', ...vocab.fibonacci], bug.estimate))),
    el('div', { class: 'form-grid' },
      field('Area', textInput('area', bug.area)),
      field('Assignee', textInput('assignee', bug.assignee)),
      field('Relates to', textInput('relates_to', bug.relates_to))),
    field('Symptom', textArea('symptom', bug.symptom, '', 2)),
    field('Steps to reproduce', textArea('steps', bug.steps.join('\n'), 'One per line', 3)),
    el('div', { class: 'form-grid' },
      field('Expected', textArea('expected', bug.expected, '', 2)),
      field('Actual', textArea('actual', bug.actual, '', 2))),
    field('Assessment', textArea('assessment', bug.assessment, 'Suspected root cause, and where.', 2)),
    field('Notes', textArea('notes', bug.notes, '', 2)),
  ], async (data) => {
      await act('update_bug', { bug_id: bug.id, ...data, steps: linesOf(data.steps) });
      closeDrawer();
    });
}

function planSprintForm() {
  const repo = state.repo;
  const candidates = [
    ...repo.stories.filter((s) => s.state === 'Ready')
      .map((s) => ({ id: s.id, label: `${s.id} — ${s.title}`, points: num(s.estimate), priority: s.priority })),
    ...repo.bugs.filter((b) => b.state === 'Triaged' || b.state === 'Confirmed')
      .map((b) => ({ id: b.id, label: `${b.id} — ${b.title}`, points: num(b.estimate), priority: b.priority })),
  ];
  if (!candidates.length) { toast('warn', 'Nothing pullable', 'No Ready stories or triaged bugs.'); return; }

  const total = el('span', { class: 'hint', text: '0 pts selected' });
  const recount = (root) => {
    const sum = [...root.querySelectorAll('input[name=items]:checked')]
      .reduce((n, box) => n + num(box.dataset.points), 0);
    total.textContent = `${sum} pts selected`;
  };
  const list = el('div', { class: 'stack' }, candidates.map((c) =>
    el('label', { class: 'item', style: 'cursor:pointer' },
      el('input', { type: 'checkbox', name: 'items', value: c.id, dataset: { points: c.points } }),
      el('span', { class: 'grow', text: c.label }),
      isSet(c.priority) ? badge(c.priority) : null,
      badge(`${c.points} pts`))));
  list.addEventListener('change', () => recount(list));

  const velocity = show(repo.history.rolling_velocity);
  openModal('Plan a sprint', [
    el('div', { class: 'form-grid' },
      field('Sprint', textInput('name', '', '2026-S05')),
      field('Dates', textInput('dates', '', '2026-04-06 → 2026-04-17')),
      field('Capacity (pts)', textInput('capacity', '', velocity), `rolling velocity ${velocity}`)),
    field('Sprint goal', textArea('goal', '', 'One sentence the whole sprint serves.', 2)),
    el('div', { class: 'section-head' }, el('h2', { text: 'Pull in' }), el('span', { class: 'grow' }), total),
    list,
  ], (data, form) => {
      const items = [...form.querySelectorAll('input[name=items]:checked')].map((b) => b.value);
      if (!items.length) { toast('warn', 'Nothing selected', 'Pick at least one item.'); throw new Error('empty'); }
      return act('plan_sprint', { name: data.name, goal: data.goal, dates: data.dates,
        capacity: data.capacity, items });
    }, { submit: 'Start sprint' });
}

function completeForm(id) {
  openModal(`${id} → Done`, [
    el('p', { class: 'hint', text: 'Gated by the Definition of Done and the acceptance criteria. Recorded into the Increment.' }),
    el('div', { class: 'form-grid' },
      field('PR', textInput('pr', '', '#142')),
      field('Commit', textInput('commit', '', 'a1b2c3d'))),
  ], (data) => act('complete_item', { item_id: id, pr: data.pr, commit: data.commit }),
     { submit: 'Mark done' });
}

function closeSprintForm() {
  const sprint = state.repo.sprint;
  const done = sprint.board.Done.length;
  const left = Object.entries(sprint.board)
    .filter(([col]) => col !== 'Done').reduce((n, [, items]) => n + items.length, 0);
  openModal(`Close ${show(sprint.name)}`, [
    el('p', { text: `${done} done, ${left} unfinished. Unfinished work goes back to the backlog; velocity is recorded.` }),
    field('Retro — kept', textInput('retro_kept', '', 'what worked')),
    field('Retro — try', textInput('retro_try', '', 'what to change')),
  ], (data) => act('close_sprint', data), { submit: 'Close sprint' });
}

function cutReleaseForm() {
  const releases = state.repo.releases;
  const latest = releases.versions[0];
  openModal('Cut a release', [
    el('p', { class: 'hint',
      text: `${releases.increment.length} item(s) in the Increment. Latest version: ${latest ? latest.version : 'none'}.` }),
    el('div', { class: 'form-grid' },
      field('Version', textInput('version', '', 'leave blank for the next minor'),
        'New capability ⇒ Major · increment ⇒ Minor'),
      field('Title', textInput('title', '', 'Frictionless sign-in'))),
    field('Theme', textArea('theme', '', 'One line for the release notes.', 2)),
  ], (data) => act('cut_release', data), { submit: 'Cut release' });
}

async function runCheck() {
  const result = await act('check', {}, 'Ledger check');
  state.drift = result.issues || [];
  render();
  if (state.drift.length) {
    toast('warn', `${state.drift.length} issue(s)`, 'Shown on Health', state.drift.slice(0, 4));
  }
}

function commitForm() {
  const git = state.workspace.git;
  if (!git.git) { toast('warn', 'Not a git repository', git.reason || ''); return; }
  if (!git.dirty) { toast('ok', 'Ledger is clean', 'Nothing to commit.'); return; }
  openModal('Commit the ledger', [
    el('p', { class: 'hint', text: `${git.changes.length} change(s) on ${git.branch}. Only ${state.slug}/ is staged, and nothing is pushed.` }),
    el('pre', { class: 'source', style: 'max-height:180px', text: git.changes.join('\n') }),
    field('Message', textInput('message', `ledger(${state.slug}): dashboard update`)),
  ], (data) => act('commit', { message: data.message }), { submit: 'Commit' });
}

/* ------------------------------------------------------------------ chrome */

/* ====================================================================== shell
 * Five jobs in a left rail, plus the ledger's own files one click away.
 * Routing is hash-based so every destination and every item has a URL that
 * back/forward, bookmarks and the ⌘K palette can all reach.
 */

const ITEM_RE = /^(US|BUG|EPIC|TASK)-\d+$/i;

const DESTINATIONS = [
  { route: 'today',    label: 'Today',    view: 'today',
    icon: 'M8 1.5v3M8 11.5v3M1.5 8h3M11.5 8h3M8 5.25A2.75 2.75 0 1 1 8 10.75 2.75 2.75 0 0 1 8 5.25Z',
    count: () => needsYou().length },
  { route: 'inbox',    label: 'Inbox',    view: 'ideas',
    icon: 'M2 9.5h3l1 2h4l1-2h3M2.75 9.5 4.5 3.5h7l1.75 6v3a1 1 0 0 1-1 1h-9a1 1 0 0 1-1-1Z',
    count: (r) => r.ideas.length + r.bug_inbox.length },
  { route: 'backlog',  label: 'Backlog',  view: 'backlog',
    icon: 'M3 4h10M3 8h10M3 12h6',
    count: (r) => r.stats.ready },
  { route: 'sprint',   label: 'Sprint',   view: 'board',
    icon: 'M3 2.5v11M3 3.5h9l-1.6 2.6L12 8.7H3Z',
    count: (r) => Object.values(r.sprint.board).reduce((n, i) => n + i.length, 0) },
  { route: 'ship',     label: 'Ship',     view: 'ship',
    icon: 'M2.5 11.5h11M4 11.5V6.5l4-4 4 4v5M6.5 11.5V8.5h3v3',
    count: (r) => r.releases.increment.length },
];

const LEDGER_DESTINATIONS = [
  { route: 'health',   label: 'Health',   view: 'health',
    icon: 'M8 13.5S2.5 10.2 2.5 6.4A2.9 2.9 0 0 1 8 5a2.9 2.9 0 0 1 5.5 1.4c0 3.8-5.5 7.1-5.5 7.1Z',
    warn: true, count: () => healthCount() },
  { route: 'files',    label: 'Files',    view: 'files',
    icon: 'M4 2.5h5l3 3v8h-8ZM9 2.5v3h3' },
  { route: 'commands', label: 'Commands', view: 'commands',
    icon: 'M4 6 6.5 8.5 4 11M8.5 11.5H12' },
];

const ALL_DESTINATIONS = [...DESTINATIONS, ...LEDGER_DESTINATIONS];

function navIcon(d) {
  return svg('svg', { class: 'glyph', width: 16, height: 16, viewBox: '0 0 16 16',
    'aria-hidden': 'true' },
    svg('path', { d: d.icon, fill: 'none', stroke: 'currentColor',
      'stroke-width': 1.5, 'stroke-linecap': 'round', 'stroke-linejoin': 'round' }));
}

/* ------------------------------------------------------------------ router */

function parseHash() {
  const raw = (location.hash || '').replace(/^#\/?/, '');
  if (!raw) return { name: 'today' };
  const [head, ...rest] = raw.split('/');
  if (ITEM_RE.test(head)) return { name: 'item', id: head.toUpperCase() };
  const dest = ALL_DESTINATIONS.find((d) => d.route === head);
  if (dest) return { name: dest.route, param: decodeURIComponent(rest.join('/') || '') };
  return { name: 'notfound', param: head };
}

/* The command sheet and older callers still name the file-shaped views; map
 * those onto the five jobs rather than 404 on them. */
const VIEW_ROUTE = {
  overview: 'today', today: 'today', ideas: 'inbox', inbox: 'inbox',
  epics: 'backlog', stories: 'backlog', bugs: 'backlog', backlog: 'backlog',
  board: 'sprint', sprint: 'sprint',
  releases: 'ship', sprints: 'ship', ship: 'ship',
  health: 'health', files: 'files', commands: 'commands',
};

function goTo(route) {
  location.hash = '#/' + (VIEW_ROUTE[route] || route);
}

function openItemPage(id) { location.hash = '#/' + id.toUpperCase(); }

/** Remember where each destination was scrolled to, and go back to it. */
const scrollMemory = new Map();

function onRoute() {
  const previous = state.route;
  if (previous) scrollMemory.set(routeKey(previous), window.scrollY);
  state.route = parseHash();
  render();
  const remembered = scrollMemory.get(routeKey(state.route));
  window.scrollTo(0, state.route.name === 'item' ? 0 : (remembered || 0));
}

const routeKey = (r) => r.name + (r.param ? '/' + r.param : '') + (r.id || '');

/* --------------------------------------------------------------- the rail */

function needsYou() {
  /* The rules that are pure derivations of the snapshot. Phase 3 builds the
   * Today screen on top of these; the rail needs the count now. */
  const repo = state.repo;
  if (!repo) return [];
  const out = [];
  const stories = Object.fromEntries(repo.stories.map((s) => [s.id, s]));

  for (const b of repo.sprint.blocked) {
    out.push({ kind: 'blocked', id: b.id, title: `${b.id} is blocked`, detail: b.reason });
  }
  const waiting = repo.ideas.length + repo.bug_inbox.length;
  if (waiting) {
    out.push({ kind: 'triage', title: `${waiting} to triage`,
      detail: `${repo.ideas.length} idea(s), ${repo.bug_inbox.length} bug report(s)` });
  }
  for (const s of repo.stories) {
    if (s.state !== 'Ready') continue;
    const missing = [];
    if (!isSet(s.story)) missing.push('story sentence');
    if (!s.criteria.length && !s.criteria_met) missing.push('acceptance criteria');
    if (!isSet(s.estimate)) missing.push('estimate');
    if (!isSet(s.priority)) missing.push('priority');
    if (missing.length) {
      out.push({ kind: 'dor', id: s.id, title: `${s.id} is not Ready`,
        detail: `missing ${missing.join(', ')}` });
    }
  }
  for (const s of repo.stories) {
    if (s.state !== 'In Sprint') continue;
    const unmet = (s.dependencies || []).filter(
      (d) => stories[d] && stories[d].state !== 'Delivered');
    if (unmet.length) {
      out.push({ kind: 'early', id: s.id,
        title: `${s.id} started before its dependency`,
        detail: `needs ${unmet.join(', ')}` });
    }
  }
  if (repo.releases.increment.length) {
    out.push({ kind: 'release',
      title: `${repo.releases.increment.length} delivered item(s) aren't in a release`,
      detail: 'the Increment is waiting for a version' });
  }
  const git = state.workspace && state.workspace.git;
  if (git && git.dirty) {
    out.push({ kind: 'commit', title: `${git.changes.length} uncommitted ledger file(s)`,
      detail: `on ${git.branch}` });
  }
  return out;
}

function healthCount() {
  const findings = needsYou().filter((f) => f.kind === 'dor' || f.kind === 'early');
  return findings.length + (state.drift ? state.drift.length : 0);
}

function renderRail() {
  const host = document.getElementById('rail-nav');
  const bar = document.getElementById('tabbar');
  if (!host) return;
  const repo = state.repo;
  host.replaceChildren();

  const link = (d) => {
    const here = state.route && state.route.name === d.route;
    const n = repo && d.count ? d.count(repo) : 0;
    const node = el('a', { class: 'nav', href: '#/' + d.route,
      'aria-current': here ? 'page' : null }, navIcon(d), el('span', { text: d.label }));
    if (n) node.append(el('span', { class: `n${d.warn ? ' n-w' : ''}`, text: String(n) }));
    return node;
  };

  for (const d of DESTINATIONS) host.append(link(d));
  host.append(el('div', { class: 'nav-label', text: 'Ledger' }));
  for (const d of LEDGER_DESTINATIONS) host.append(link(d));

  // Phone: the first four plus More (Ship + the ledger group).
  if (bar) {
    const phone = [...DESTINATIONS.slice(0, 4),
      { route: 'ship', label: 'More', view: 'ship', icon: 'M3 8h.01M8 8h.01M13 8h.01' }];
    bar.replaceChildren(...phone.map((d) => {
      const here = state.route && (state.route.name === d.route
        || (d.label === 'More' && LEDGER_DESTINATIONS.some((x) => x.route === state.route.name)));
      const n = repo && d.count ? d.count(repo) : 0;
      return el('button', { type: 'button', 'aria-current': here ? 'page' : null,
        onclick: () => goTo(d.route) },
        navIcon(d),
        el('span', { text: d.label }),
        n ? el('span', { class: 'n', text: String(n) }) : null);
    }));
  }
}

/* ---------------------------------------------------------- the trust line */

function renderTrust() {
  const host = document.getElementById('trust');
  if (!host || !state.workspace) return;
  const files = state.repo
    ? state.workspace.vocabulary.files.length - (state.repo.missing_files || []).length : 0;
  const since = state.syncedAt ? Math.max(0, Math.round((Date.now() - state.syncedAt) / 1000)) : null;
  const ago = since === null ? 'never'
    : since < 5 ? 'just now'
    : since < 90 ? `${since}s ago`
    : `${Math.round(since / 60)}m ago`;

  host.replaceChildren(
    el('div', { class: 'trust-line' },
      el('span', { class: `trust-dot${since !== null && since > 60 ? ' stale' : ''}` }),
      el('span', { text: `${files} files · synced ${ago}` })));

  const git = state.workspace.git;
  if (git && git.dirty) {
    host.append(el('div', { class: 'trust-line' },
      el('span', { text: `${git.changes.length} uncommitted · ` }),
      el('button', { type: 'button', onclick: commitForm }, 'Commit…')));
  }
  if (state.externalEdit) {
    host.classList.add('pulse');
    setTimeout(() => host.classList.remove('pulse'), 2400);
    state.externalEdit = false;
  }
}

/* ------------------------------------------------------------- the views */

VIEWS.today = () => {
  const wrap = el('div', {});
  const findings = needsYou();
  const sprint = state.repo.sprint;
  wrap.append(el('div', { class: 'page-head' },
    el('div', { class: 'grow' },
      el('h1', { class: 'page-title', text: greeting() }),
      el('p', { class: 'page-sub', text: [
        today(),
        isSet(sprint.name) ? `sprint ${sprint.name}` : 'no sprint open',
        findings.length ? `${findings.length} thing(s) need you` : 'nothing needs you',
      ].join(' · ') }))));
  // Phase 3 turns these into the full Needs-you queue; for now the existing
  // overview keeps every number reachable.
  wrap.append(VIEWS.overview());
  return wrap;
};

function greeting() {
  const h = new Date().getHours();
  return h < 12 ? 'Good morning' : h < 18 ? 'Good afternoon' : 'Good evening';
}
function today() {
  return new Date().toLocaleDateString(undefined,
    { weekday: 'long', day: 'numeric', month: 'long' });
}

/** Backlog gathers what used to be three tabs; Phase 4 makes it one outline. */
VIEWS.backlog = () => {
  const wrap = el('div', {});
  const groups = [['epics', 'Epics'], ['stories', 'Stories'], ['bugs', 'Bugs']];
  let current = remember('backlog.group') || 'epics';
  if (!groups.some(([k]) => k === current)) current = 'epics';

  const seg = el('div', { class: 'seg', role: 'group', 'aria-label': 'Backlog view' },
    groups.map(([key, label]) => el('button', { type: 'button',
      'aria-pressed': String(key === current),
      onclick: () => { remember('backlog.group', key); render(); } }, label)));

  wrap.append(el('div', { class: 'page-head' },
    el('div', { class: 'grow' },
      el('h1', { class: 'page-title', text: 'Backlog' }),
      el('p', { class: 'page-sub',
        text: `${state.repo.stats.ready} Ready · ${state.repo.stats.ready_points} pts` })),
    seg));
  wrap.append(VIEWS[current]());
  return wrap;
};

VIEWS.ship = () => {
  const wrap = el('div', {});
  wrap.append(el('div', { class: 'page-head' },
    el('div', { class: 'grow' },
      el('h1', { class: 'page-title', text: 'Ship' }),
      el('p', { class: 'page-sub',
        text: `${state.repo.releases.increment.length} waiting · rolling velocity ${show(state.repo.history.rolling_velocity)}` }))));
  wrap.append(VIEWS.releases());
  wrap.append(VIEWS.sprints());
  return wrap;
};

VIEWS.health = () => {
  const wrap = el('div', {});
  const findings = needsYou().filter((f) => f.kind === 'dor' || f.kind === 'early');
  wrap.append(el('div', { class: 'page-head' },
    el('div', { class: 'grow' },
      el('h1', { class: 'page-title', text: 'Health' }),
      el('p', { class: 'page-sub', text: 'what the ledger says is wrong with itself' })),
    el('button', { class: 'btn', type: 'button', onclick: runCheck }, 'Run ledger check')));

  const section = (title, rows, empty) => el('section', { class: 'section' },
    sectionHead(title, `${rows.length}`),
    rows.length
      ? el('div', { class: 'stack' }, rows.map((f) => el('div', { class: 'item' },
          el('div', { class: 'grow' },
            el('strong', { text: f.title || f }),
            f.detail ? el('div', { class: 'hint', text: f.detail }) : null),
          f.id ? el('button', { class: 'btn small', type: 'button',
            onclick: () => openItemPage(f.id) }, 'Open') : null)))
      : el('p', { class: 'empty', text: empty }));

  wrap.append(section('Fails Definition of Ready',
    findings.filter((f) => f.kind === 'dor'), 'Every Ready story has what it needs.'));
  wrap.append(section('Started before a dependency',
    findings.filter((f) => f.kind === 'early'), 'Nothing started early.'));
  wrap.append(section('Ledger drift',
    (state.drift || []).map((d) => ({ title: d })),
    state.drift ? 'No drift found.' : 'Run the ledger check to look for drift.'));

  const git = state.workspace && state.workspace.git;
  if (git && git.dirty) {
    wrap.append(el('section', { class: 'section' },
      sectionHead('Uncommitted', `${git.changes.length}`,
        el('button', { class: 'btn small', type: 'button', onclick: commitForm }, 'Commit…')),
      el('pre', { class: 'source', text: git.changes.join('\n') })));
  }
  return wrap;
};

VIEWS.notfound = () => el('div', {},
  el('h1', { class: 'page-title', text: 'Not in this ledger' }),
  el('p', { class: 'page-sub',
    text: `Nothing here matches “${show(state.route.param)}”.` }),
  el('div', { style: 'margin-top:14px' },
    el('button', { class: 'btn primary', type: 'button', onclick: openPalette }, 'Search…')));

/* ------------------------------------------------------------- item page */

VIEWS.item = () => {
  const id = state.route.id;
  const repo = state.repo;
  const story = repo.stories.find((s) => s.id === id);
  const bug = repo.bugs.find((b) => b.id === id);
  const epic = repo.epics.find((e) => e.id === id);
  if (!story && !bug && !epic) {
    const draft = repo.epics.flatMap((e) => (e.stories || [])
      .filter((i) => i.id === id).map((i) => ({ ...i, epic: e })))[0];
    if (draft) return draftPage(draft);
    return el('div', {},
      el('h1', { class: 'page-title', text: 'Not in this ledger' }),
      el('p', { class: 'page-sub', text: `${id} has no entry here.` }),
      el('div', { style: 'margin-top:14px' },
        el('button', { class: 'btn', type: 'button', onclick: openPalette }, 'Search…')));
  }
  if (epic) return epicPage(epic);
  return story ? itemPage(story, 'story') : itemPage(bug, 'bug');
};

function crumb(...parts) {
  const row = el('div', { class: 'crumb' });
  parts.forEach((p, i) => {
    if (i) row.append(el('span', { text: '/' }));
    row.append(p);
  });
  return row;
}

function copyLink(id) {
  const url = `${location.origin}${location.pathname}#/${id}`;
  navigator.clipboard?.writeText(url).then(
    () => toast('ok', 'Link copied', url),
    () => toast('warn', 'Link', url));
}

function sourceBlock(file, span) {
  const row = el('div', { class: 'source' });
  if (!span) return row;
  row.append(el('span', { text: `${file} : ${span[0] + 1}–${span[1]}` }));
  row.append(el('button', { class: 'btn small ghost', type: 'button',
    onclick: () => { location.hash = `#/files/${encodeURIComponent(file)}`; } }, 'Open in Files'));
  return row;
}

const STORY_TRACK = ['Draft', 'Ready', 'In Sprint', 'Delivered'];

function lifecycleTrack(stateName, column) {
  const at = STORY_TRACK.indexOf(stateName);
  const track = el('div', { class: 'track', role: 'img',
    'aria-label': `Lifecycle: ${stateName}${column ? ', ' + column : ''}` });
  STORY_TRACK.forEach((name, i) => {
    const now = name === stateName;
    const step = el('div', { class: `track-step${now ? ' now' : (at > i ? ' done' : '')}` },
      el('span', { text: name }));
    if (now && name === 'In Sprint') {
      const cols = el('span', { class: 'track-cols' });
      for (const c of state.workspace.vocabulary.board_columns) {
        cols.append(el('span', { class: `track-col${c === column ? ' now' : ''}`, text: c }));
      }
      step.append(cols);
    }
    track.append(step);
  });
  return track;
}

function itemPage(item, entity) {
  const repo = state.repo;
  const column = boardColumn(item.id);
  const isStory = entity === 'story';
  const wrap = el('div', {});

  wrap.append(crumb(
    el('button', { type: 'button', onclick: () => goTo('backlog') }, 'Backlog'),
    item.parent ? el('button', { type: 'button',
      onclick: () => openItemPage(item.parent) }, item.parent) : null,
    el('span', { class: 'mono', text: item.id })));

  wrap.append(el('div', { class: 'page-head' },
    el('div', { class: 'grow' },
      el('div', { class: 'chips', style: 'margin-bottom:8px' },
        stateChip(entity, item.state, { column }),
        priorityMark(item.priority),
        !isStory ? severityPill(item.severity) : null,
        isSet(item.estimate) ? badge(`${item.estimate} pts`) : null,
        isSet(item.assignee) ? badge(item.assignee) : null),
      el('h1', { class: 'page-title', text: show(item.title) }),
      el('p', { class: 'page-sub mono', text: item.id })),
    el('div', { class: 'chips' },
      el('button', { class: 'btn small', type: 'button',
        onclick: () => copyLink(item.id) }, 'Copy link'),
      el('button', { class: 'btn small primary', type: 'button',
        onclick: () => (isStory ? editStoryForm(item) : editBugForm(item)) }, 'Edit'))));

  if (isStory) wrap.append(lifecycleTrack(item.state, column));

  const main = el('div', {});
  if (isStory) {
    if (isSet(item.story)) main.append(prose(item.story, 'p', { class: 'lede' }));
    main.append(criteriaBlock(item));
  } else {
    for (const [label, value, note] of [
      ['Symptom', item.symptom, ''],
      ['Steps to reproduce', null, item.steps_confidence],
      ['Expected', item.expected, ''],
      ['Actual', item.actual, ''],
      ['Assessment', item.assessment, item.assessment_confidence],
    ]) {
      if (label === 'Steps to reproduce') {
        if (!item.steps.length) continue;
        main.append(el('div', { class: 'detail-block' },
          el('h4', { text: `${label}${note ? ` (${note})` : ''}` }),
          el('ol', {}, item.steps.map((s) => prose(s, 'li')))));
        continue;
      }
      if (!isSet(value)) continue;
      main.append(el('div', { class: 'detail-block' },
        el('h4', { text: `${label}${note ? ` (${note})` : ''}` }), prose(value)));
    }
  }
  if (isSet(item.notes)) {
    main.append(el('div', { class: 'detail-block' },
      el('h4', { text: 'Notes' }), prose(item.notes)));
  }
  main.append(el('div', { class: 'detail-block' },
    el('h4', { text: 'In the ledger' }),
    sourceBlock(isStory ? 'User-Stories.md' : 'Bugs.md', item.span)));

  const side = el('div', {});
  side.append(moveCard(item, entity, column));
  side.append(connectionsCard(item, entity));
  if (isStory) side.append(dodCard());

  wrap.append(el('div', { class: 'item-grid' }, main, side));
  return wrap;
}

function criteriaBlock(story) {
  if (story.criteria_met) {
    return el('div', { class: 'detail-block' },
      el('h4', { text: 'Acceptance criteria' }),
      el('p', { text: 'All met ✓' }));
  }
  if (!story.criteria.length) {
    return el('div', { class: 'detail-block' },
      el('h4', { text: 'Acceptance criteria' }),
      el('p', { class: 'hint', text: 'None written yet.' }));
  }
  return el('div', { class: 'detail-block' },
    el('h4', { text: `Acceptance criteria · ${story.criteria.length}` }),
    el('ul', { class: 'check-list' }, story.criteria.map((c) => {
      const li = el('li', {}, checkBox(false));
      const body = el('span', {});
      // Given / When / Then read as keywords, so the shape of a criterion is
      // visible before the words are.
      const parts = String(c).split(/\b(given|when|then)\b/i);
      for (const part of parts) {
        if (/^(given|when|then)$/i.test(part)) {
          body.append(el('span', { class: 'gwt', text: part.toUpperCase() }), ' ');
        } else if (part.trim()) {
          body.append(rich(part));
        }
      }
      li.append(body);
      return li;
    })));
}

function checkBox(met) {
  return svg('svg', { class: `check-box${met ? ' met' : ''}`, width: 14, height: 14,
    viewBox: '0 0 14 14', 'aria-hidden': 'true' },
    svg('rect', { x: 1.5, y: 1.5, width: 11, height: 11, rx: 3, fill: 'none',
      stroke: 'currentColor', 'stroke-width': 1.4 }),
    met ? svg('path', { d: 'M4.3 7.2 6.1 9 9.7 5.3', fill: 'none', stroke: 'currentColor',
      'stroke-width': 1.6, 'stroke-linecap': 'round', 'stroke-linejoin': 'round' }) : null);
}

function moveCard(item, entity, column) {
  const card = el('div', { class: 'side-card' }, el('h3', { text: 'Move it' }));
  const row = el('div', { class: 'chips' });
  const states = entity === 'story'
    ? state.workspace.vocabulary.story_states
    : state.workspace.vocabulary.bug_states.filter((s) => s !== 'Inbox');
  for (const name of states) {
    if (name === item.state) continue;
    row.append(el('button', { class: 'btn small', type: 'button',
      onclick: () => (entity === 'story'
        ? changeStoryState(item, name)
        : act('set_bug_state', { bug_id: item.id, state: name })) }, `→ ${name}`));
  }
  card.append(row);
  if (column) {
    card.append(el('h3', { style: 'margin-top:14px', text: 'Board' }));
    const cols = el('div', { class: 'chips' });
    for (const c of state.workspace.vocabulary.board_columns) {
      if (c === column) continue;
      cols.append(el('button', { class: 'btn small', type: 'button',
        onclick: () => moveItem(item.id, c) }, c));
    }
    card.append(cols);
  }
  card.append(el('h3', { style: 'margin-top:14px', text: 'Branch' }));
  card.append(el('div', { class: 'chips' },
    el('code', { text: branchFor(item, true) }),
    el('button', { class: 'btn small ghost', type: 'button',
      onclick: () => branchFor(item) }, 'Copy')));
  return card;
}

/** One hop out: the epic above, what it needs, what needs it, bugs about it. */
function connectionsCard(item, entity) {
  const repo = state.repo;
  const card = el('div', { class: 'side-card' }, el('h3', { text: 'Connections' }));
  const conn = el('div', { class: 'conn' });
  const stories = Object.fromEntries(repo.stories.map((s) => [s.id, s]));

  const group = (label, ids, decorate) => {
    if (!ids.length) return;
    const box = el('div', {});
    box.append(el('div', { class: 'conn-group', text: label }));
    const row = el('div', { class: 'conn-row' });
    for (const id of ids) {
      row.append(el('button', { class: 'idlink', type: 'button',
        onclick: () => openItemPage(id) }, id));
      const note = decorate && decorate(id);
      if (note) row.append(note);
    }
    box.append(row);
    conn.append(box);
  };

  if (item.parent) group('Epic', [item.parent]);
  if (entity === 'story') {
    group('Needs', item.dependencies || [], (id) => {
      const dep = stories[id];
      if (!dep) return null;
      const met = dep.state === 'Delivered';
      return el('span', { class: `dep ${met ? 'dep-met' : ''}`,
        text: met ? '✓' : dep.state });
    });
    const neededBy = repo.stories
      .filter((s) => (s.dependencies || []).includes(item.id)).map((s) => s.id);
    group('Needed by', neededBy);
    group('Bugs', repo.bugs.filter((b) => b.relates_to === item.id).map((b) => b.id));
  } else if (item.relates_to) {
    group('Relates to', [item.relates_to]);
  }
  if (!conn.children.length) conn.append(el('p', { class: 'hint', text: 'Nothing linked yet.' }));
  card.append(conn);
  return card;
}

function dodCard() {
  const list = (state.repo.definitions && state.repo.definitions.definition_of_done) || [];
  const card = el('div', { class: 'side-card' }, el('h3', { text: 'Before Done' }));
  if (!list.length) {
    card.append(el('p', { class: 'hint', text: 'No Definition of Done in Definitions.md.' }));
    return card;
  }
  card.append(el('ul', { class: 'check-list' },
    list.map((line) => el('li', {}, checkBox(false), el('span', {}, rich(line))))));
  return card;
}

function epicPage(epic) {
  const wrap = el('div', {});
  wrap.append(crumb(
    el('button', { type: 'button', onclick: () => goTo('backlog') }, 'Backlog'),
    el('span', { class: 'mono', text: epic.id })));
  wrap.append(el('div', { class: 'page-head' },
    el('div', { class: 'grow' },
      el('div', { class: 'chips', style: 'margin-bottom:8px' },
        stateChip('epic', epic.state),
        isSet(epic.target) ? badge(`target ${epic.target}`) : null,
        isSet(epic.area) ? badge(epic.area) : null),
      el('h1', { class: 'page-title', text: show(epic.title) }),
      el('p', { class: 'page-sub mono', text: epic.id })),
    el('button', { class: 'btn small', type: 'button',
      onclick: () => copyLink(epic.id) }, 'Copy link')));

  const main = el('div', {});
  if (isSet(epic.goal)) main.append(prose(epic.goal, 'p', { class: 'lede' }));
  main.append(el('div', { class: 'detail-block', style: 'margin-top:16px' },
    el('h4', { text: `Stories · ${(epic.stories || []).length}` }),
    el('div', { class: 'stack' }, (epic.stories || []).map((i) =>
      el('div', { class: 'item' },
        stateChip('story', indexState(i.state), { column: boardColumn(i.id) }),
        el('button', { class: 'idlink', type: 'button',
          onclick: () => openItemPage(i.id) }, i.id),
        el('div', { class: 'grow', text: show(i.title) }),
        isSet(i.points) ? badge(`${i.points} pts`) : null)))));
  if ((epic.history || []).length) {
    main.append(el('div', { class: 'detail-block' },
      el('h4', { text: 'History' }),
      el('ul', {}, epic.history.map((h) => prose(h, 'li')))));
  }
  main.append(el('div', { class: 'detail-block' },
    el('h4', { text: 'In the ledger' }), sourceBlock('Epic-Backlog.md', epic.span)));

  const side = el('div', {});
  const roll = epic.rollup || {};
  side.append(el('div', { class: 'side-card' },
    el('h3', { text: 'Progress' }),
    el('div', { class: 'hint', style: 'margin-bottom:3px', text: 'Stories' }),
    meter(roll.stories_done || 0, roll.stories_total || 0),
    el('div', { class: 'hint', style: 'margin:10px 0 3px', text: 'Points' }),
    meter(roll.points_done || 0, roll.points_total || 0)));
  wrap.append(el('div', { class: 'item-grid' }, main, side));
  return wrap;
}

function draftPage(draft) {
  const wrap = el('div', {});
  wrap.append(crumb(
    el('button', { type: 'button', onclick: () => goTo('backlog') }, 'Backlog'),
    el('button', { type: 'button',
      onclick: () => openItemPage(draft.epic.id) }, draft.epic.id),
    el('span', { class: 'mono', text: draft.id })));
  wrap.append(el('div', { class: 'page-head' },
    el('div', { class: 'grow' },
      el('div', { class: 'chips', style: 'margin-bottom:8px' },
        stateChip('story', 'Draft'), priorityMark(draft.priority)),
      el('h1', { class: 'page-title', text: show(draft.title) }),
      el('p', { class: 'page-sub mono', text: draft.id })),
    el('button', { class: 'btn primary', type: 'button',
      onclick: () => detailStoryForm(draft, draft.epic) }, 'Write it up')));
  wrap.append(lifecycleTrack('Draft', ''));
  wrap.append(el('p', { class: 'page-sub' },
    'A Draft lives only as an index line under its epic — there is no detail entry yet. '
    + 'Writing it up moves it to Ready.'));
  return wrap;
}

/* --------------------------------------------------------------- palette */

let paletteIndex = 0;
let paletteRows = [];

function openPalette() {
  const box = document.getElementById('palette');
  const input = document.getElementById('palette-q');
  box.hidden = false;
  box.setAttribute('aria-hidden', 'false');
  input.value = '';
  drawPalette('');
  setTimeout(() => input.focus(), 20);
}

function closePalette() {
  const box = document.getElementById('palette');
  box.hidden = true;
  box.setAttribute('aria-hidden', 'true');
}

function paletteCandidates(query) {
  const q = query.trim().toLowerCase();
  const repo = state.repo;
  const rows = [];
  if (repo) {
    const seen = new Set();
    const push = (entity, item, extra) => {
      if (seen.has(item.id)) return;
      seen.add(item.id);
      rows.push({ group: 'Items', id: item.id, label: show(item.title),
        entity, state: item.state, column: boardColumn(item.id), ...extra });
    };
    for (const s of repo.stories) push('story', s);
    for (const b of repo.bugs) push('bug', b);
    for (const e of repo.epics) {
      push('epic', e);
      for (const i of e.stories || []) {
        push('story', { id: i.id, title: i.title, state: indexState(i.state) });
      }
    }
  }
  const sheet = state.commands;
  if (sheet) {
    for (const group of sheet.groups) {
      for (const c of group.commands) {
        rows.push({ group: c.action || c.view ? 'Do it here' : 'In Claude Code',
          id: '/' + c.name, label: c.description || '', command: c });
      }
    }
  }
  if (!q) {
    return rows.filter((r) => r.group === 'Items').slice(0, 8)
      .concat(rows.filter((r) => r.group === 'Do it here').slice(0, 6));
  }
  const score = (r) => {
    const id = r.id.toLowerCase();
    const label = String(r.label).toLowerCase();
    if (id.startsWith(q) || id.replace('/', '').startsWith(q)) return 0;
    if (id.includes(q)) return 1;
    if (label.startsWith(q)) return 2;
    if (label.includes(q)) return 3;
    return 99;
  };
  return rows.map((r) => ({ r, s: score(r) })).filter((x) => x.s < 99)
    .sort((a, b) => a.s - b.s).slice(0, 30).map((x) => x.r);
}

function highlight(text, query) {
  const node = el('span', {});
  const q = query.trim();
  if (!q) { node.textContent = text; return node; }
  const at = String(text).toLowerCase().indexOf(q.toLowerCase());
  if (at < 0) { node.textContent = text; return node; }
  node.append(document.createTextNode(String(text).slice(0, at)));
  node.append(el('mark', { text: String(text).substr(at, q.length) }));
  node.append(document.createTextNode(String(text).slice(at + q.length)));
  return node;
}

function drawPalette(query) {
  const host = document.getElementById('palette-results');
  paletteRows = paletteCandidates(query);
  paletteIndex = 0;
  host.replaceChildren();
  let group = null;
  paletteRows.forEach((row, i) => {
    if (row.group !== group) {
      group = row.group;
      host.append(el('div', { class: 'grp', text: group }));
    }
    const node = el('button', { class: 'opt', type: 'button', role: 'option',
      'aria-selected': String(i === 0), dataset: { index: String(i) },
      onclick: (e) => runPaletteRow(row, e.shiftKey) },
      el('span', { class: 'opt-id' }, highlight(row.id, query)),
      el('span', { class: 'opt-main' }, highlight(row.label, query)));
    if (row.entity) {
      node.append(el('span', { class: 'opt-tail' },
        stateChip(row.entity, row.state, { column: row.column })));
    }
    host.append(node);
  });
  if (!paletteRows.length) {
    host.append(el('p', { class: 'empty', style: 'margin:14px', text: 'Nothing matches.' }));
  }
}

function movePalette(delta) {
  const options = [...document.getElementById('palette-results').querySelectorAll('.opt')];
  if (!options.length) return;
  paletteIndex = (paletteIndex + delta + options.length) % options.length;
  options.forEach((o, i) => o.setAttribute('aria-selected', String(i === paletteIndex)));
  options[paletteIndex].scrollIntoView({ block: 'nearest' });
}

function runPaletteRow(row, peek) {
  closePalette();
  if (row.entity) {
    if (peek) openItem(row.id);
    else openItemPage(row.id);
    return;
  }
  const c = row.command;
  if (!c) return;
  const run = HERE_ACTIONS[c.action];
  if (run) return run();
  const view = c.view || ACTION_VIEW[c.action];
  if (view) return goTo(view);
  copyCommand(`/${c.name}${c.args ? ' ' + c.args : ''}`);
}

/* ---------------------------------------------------------------- render */

/* A folder relocated from a pre-2.0 ledger is missing files this page reads.
 * Say that plainly and persistently — an empty backlog with no explanation
 * looks like data loss. */
function layoutBanner() {
  const layout = state.repo && state.repo.layout;
  if (!layout || !layout.message) return null;
  const legacy = layout.legacy;
  return el('div', { class: `notice${legacy ? ' critical' : ''}`, role: 'status' },
    el('strong', { text: legacy ? `Pre-2.0 ledger (${layout.era})` : 'Incomplete ledger folder' }),
    el('p', { text: layout.message }),
    layout.detail ? el('p', { class: 'hint', text: layout.detail }) : null,
    legacy ? el('button', { class: 'btn small', type: 'button',
      onclick: () => copyCommand('/migrate-ledger') }, 'Copy /migrate-ledger') : null);
}

function render() {
  if (!state.route) state.route = parseHash();
  renderRail();
  renderTrust();
  renderPeople();
  renderProject();

  const host = document.getElementById('main');
  const name = state.route.name;
  const dest = ALL_DESTINATIONS.find((d) => d.route === name);
  const viewName = name === 'item' ? 'item' : name === 'notfound' ? 'notfound'
    : (dest ? dest.view : 'today');

  document.title = (name === 'item' ? state.route.id
    : dest ? dest.label : 'Not found') + ' · Agile Ledger Pro';

  if (!state.repo && name !== 'notfound') {
    host.replaceChildren(el('p', { class: 'empty', text: 'No project selected.' }));
    return;
  }
  try {
    const panel = (VIEWS[viewName] || VIEWS.today)();
    host.replaceChildren(...[layoutBanner(), panel].filter(Boolean));
  } catch (error) {
    host.replaceChildren(el('p', { class: 'empty',
      text: `Could not render this view: ${error.message}` }));
    throw error;
  }
}

function renderProject() {
  const name = document.getElementById('proj-name');
  const sub = document.getElementById('proj-sub');
  if (!name || !state.workspace) return;
  name.textContent = state.slug || '—';
  const git = state.workspace.git;
  const placement = state.repo && state.repo.placement === 'in-repo' ? 'in repo' : 'ledger repo';
  sub.textContent = git && git.git ? `${placement} · ${git.branch}` : placement;
}

function renderPeople() {
  const picker = document.getElementById('person-picker');
  const repo = state.repo;
  if (!picker) return;
  const people = new Set();
  if (repo) {
    for (const s of repo.stories) if (isSet(s.assignee)) people.add(nameOf(s.assignee));
    for (const b of repo.bugs) if (isSet(b.assignee)) people.add(nameOf(b.assignee));
    const me = repo.definitions.config && repo.definitions.config.Me;
    if (me) people.add(me);
  }
  const previous = state.person;
  picker.replaceChildren(
    el('option', { value: '', text: 'Everyone' }),
    ...[...people].sort().map((p) => el('option', { value: p, text: p })));
  picker.value = previous;
  if (picker.value !== previous) state.person = picker.value;

  const label = document.getElementById('who-name');
  const initial = document.getElementById('who-initial');
  if (label) label.textContent = state.person || 'Everyone';
  if (initial) initial.textContent = (state.person || '·').charAt(0).toUpperCase();
}

/* ------------------------------------------------------------- lifecycle */

async function loadRepo(slug) {
  state.slug = slug;
  remember('repo', slug);
  state.repo = await api(`/api/repo/${encodeURIComponent(slug)}`);
  state.revision = state.repo.revision;
  state.syncedAt = Date.now();
  render();
}

async function refreshWorkspaceQuietly() {
  try { state.workspace = await api('/api/workspace'); renderTrust(); } catch { /* keep */ }
}

/* Claude edits the same files from the terminal. A revision bump that did not
 * follow one of our own writes is an external edit: pulse the trust line
 * rather than toast, so the page stays quiet while someone else works. */
async function poll() {
  if (!state.slug || document.hidden) return;
  try {
    const { revision } = await api(`/api/repo/${encodeURIComponent(state.slug)}/revision`);
    state.syncedAt = Date.now();
    if (revision && revision !== state.revision) {
      const ours = state.pendingOwnWrite;
      state.pendingOwnWrite = false;
      state.repo = await api(`/api/repo/${encodeURIComponent(state.slug)}`);
      state.revision = state.repo.revision;
      state.externalEdit = !ours;
      render();
    } else {
      renderTrust();
    }
  } catch { /* the server may be stopping; try again next tick */ }
}

function applyTheme(mode) {
  document.documentElement.setAttribute('data-theme', mode);
  remember('theme', mode);
  for (const b of document.querySelectorAll('[data-theme-set]')) {
    b.setAttribute('aria-pressed', String(b.dataset.themeSet === mode));
  }
}

/** localStorage, wrapped: a blocked or private store must not break the page. */
function remember(key, value) {
  const full = 'agile-ledger-pro.' + key;
  try {
    if (value === undefined) return localStorage.getItem(full);
    localStorage.setItem(full, value);
  } catch { /* private window, blocked storage — carry on without it */ }
  return value;
}

async function boot() {
  applyTheme(remember('theme') || 'auto');
  for (const b of document.querySelectorAll('[data-theme-set]')) {
    b.addEventListener('click', () => applyTheme(b.dataset.themeSet));
  }
  for (const node of document.querySelectorAll('[data-close]')) {
    node.addEventListener('click', () => { closeModal(); closeDrawer(); closePalette(); });
  }

  const projBtn = document.getElementById('proj');
  const picker = document.getElementById('repo-picker');
  if (projBtn && picker) projBtn.addEventListener('click', () => picker.focus());
  const whoBtn = document.getElementById('who');
  const person = document.getElementById('person-picker');
  if (whoBtn && person) whoBtn.addEventListener('click', () => person.focus());

  document.addEventListener('keydown', (event) => {
    const palette = document.getElementById('palette');
    const open = !palette.hidden;
    if ((event.key === 'k' || event.key === 'K') && (event.metaKey || event.ctrlKey)) {
      event.preventDefault();
      open ? closePalette() : openPalette();
      return;
    }
    if (event.key === 'Escape') { closeModal(); closeDrawer(); closePalette(); return; }
    if (!open) return;
    if (event.key === 'ArrowDown') { event.preventDefault(); movePalette(1); }
    else if (event.key === 'ArrowUp') { event.preventDefault(); movePalette(-1); }
    else if (event.key === 'Enter') {
      event.preventDefault();
      if (paletteRows[paletteIndex]) runPaletteRow(paletteRows[paletteIndex], event.shiftKey);
    }
  });
  const q = document.getElementById('palette-q');
  if (q) q.addEventListener('input', () => drawPalette(q.value));

  const drawerOpen = document.getElementById('drawer-open');
  if (drawerOpen) {
    drawerOpen.addEventListener('click', () => {
      const id = document.getElementById('drawer-title').textContent;
      closeDrawer();
      if (id) openItemPage(id);
    });
  }

  try {
    state.workspace = await api('/api/workspace');
  } catch (error) {
    document.getElementById('main').replaceChildren(
      el('p', { class: 'empty', text: `Could not reach the ledger: ${error.message}` }));
    return;
  }

  const present = state.workspace.repos.filter((r) => r.present);
  picker.replaceChildren(...present.map((r) => el('option', { value: r.slug, text: r.slug })));
  picker.addEventListener('change', () => loadRepo(picker.value));
  if (person) {
    person.addEventListener('change', (event) => { state.person = event.target.value; render(); });
  }

  if (!present.length) {
    document.getElementById('main').replaceChildren(el('p', { class: 'empty',
      text: 'This ledger has no repo folders yet. Run /register-repo in Claude Code.' }));
    return;
  }

  const remembered = remember('repo');
  const preferred = state.workspace.config.default_repo;
  const slug = present.some((r) => r.slug === remembered) ? remembered
    : present.some((r) => r.slug === preferred) ? preferred
    : present[0].slug;
  picker.value = slug;

  state.route = parseHash();
  window.addEventListener('hashchange', onRoute);

  await loadRepo(slug);
  loadCommands();
  setInterval(poll, 2500);
}

boot();
