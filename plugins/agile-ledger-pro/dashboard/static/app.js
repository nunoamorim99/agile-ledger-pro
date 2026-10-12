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
  tab: 'overview',
  revision: 0,
};

/* ------------------------------------------------------------------ utils */

function el(tag, attrs, ...children) {
  const node = document.createElement(tag);
  for (const [key, value] of Object.entries(attrs || {})) {
    if (value === null || value === undefined || value === false) continue;
    if (key === 'class') node.className = value;
    else if (key === 'text') node.textContent = value;
    else if (key === 'html') node.innerHTML = value;          // literals only
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
    if (result.repo) {
      state.repo = result.repo;
      state.revision = result.repo.revision;
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
    .map((s) => ({ name: s.name, value: num(s.velocity) }));
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
    const tip = make('title', {});
    tip.textContent = `${d.name}: ${d.value} points`;
    hit.append(tip);
    // The hit area precedes its bar so the `.bar-hit:hover + .bar` rule lights it up.
    svg.append(hit, bar);

    const label = make('text', { x: x + barW / 2, y: padT + plotH + 15,
      'text-anchor': 'middle', class: 'cat' });
    label.textContent = d.name;
    svg.append(label);

    if (i === data.length - 1 || (d.value === best && best > 0)) {
      const value = make('text', { x: x + barW / 2, y: top - 6,
        'text-anchor': 'middle', class: 'direct' });
      value.textContent = String(d.value);
      svg.append(value);
    }
  });

  return el('figure', { class: 'chart', style: 'margin:0' },
    el('figcaption', { text: 'Completed story points per closed sprint, oldest first. Hover a bar for its value.' }),
    svg);
}

/* ------------------------------------------------------------------ parts */

function badge(text, tone) {
  return el('span', { class: `badge${tone ? ' ' + tone : ''}`, text });
}

function stateBadge(value) {
  const text = show(value);
  const tone = /Delivered|Fixed|Done/.test(text) ? 'good'
    : /Blocked|Discarded|Won/.test(text) ? 'critical'
    : /Sprint|Progress|Confirmed/.test(text) ? 'accent'
    : '';
  return badge(text, tone);
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
  return el('div', { class: 'section-head' },
    el('h2', { text: title }),
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

  wrap.append(el('section', { class: 'section' },
    sectionHead('At a glance', repo.slug),
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
        el('p', { style: 'margin:0 0 10px', text: show(sprint.goal) }),
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
      sectionHead('Blocked', 'a flag, not a column — the item keeps its place'),
      el('div', { class: 'stack' }, sprint.blocked.map((b) =>
        el('div', { class: 'item' },
          el('div', { class: 'grow' },
            el('strong', { text: b.id }), ' ', el('span', { text: b.text })),
          el('button', { class: 'btn small', type: 'button',
            onclick: () => act('set_blocked', { item_id: b.id, blocked: false }, 'Unblocked') }, 'Unblock'))))));
  }
  return wrap;
};

function ticket(item, column, blocked) {
  const node = el('div', { class: 'ticket', draggable: 'true', dataset: { id: item.id } },
    el('div', { class: 't-id', text: item.id }),
    el('div', { class: 't-title', text: show(item.title) }),
    el('div', { class: 't-foot' },
      el('span', { text: isSet(item.assignee) ? item.assignee : 'unassigned' }),
      el('span', { class: 'chips' },
        blocked ? badge('🚧 Blocked', 'critical') : null,
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
        el('div', { class: 'grow', text: idea.text }),
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
            el('div', { class: 'grow', text: bug.text }),
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
            el('strong', { text: epic.id }), stateBadge(epic.state),
            isSet(epic.target) ? badge(`target ${epic.target}`) : null,
            isSet(epic.area) ? badge(epic.area) : null),
          el('h3', { style: 'margin-top:6px', text: show(epic.title) }),
          isSet(epic.goal) ? el('p', { class: 'goal', text: epic.goal }) : null),
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
            el('td', {}, stateBadge(item.state)),
            el('td', { text: show(item.priority) }),
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
        el('ul', {}, epic.history.map((h) => el('li', { text: h })))));
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
        el('td', {}, stateBadge(story.state)),
        el('td', { text: show(story.priority) }),
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
      sectionHead('📝 Draft', `${drafts.length} — triaged, not yet detailed`),
      el('div', { class: 'stack' }, drafts.map((d) =>
        el('div', { class: 'item' },
          el('span', { class: 'id', text: d.id }),
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
      sectionHead(name, `${group.length} · ${points} pts`),
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
      sectionHead(name, `${group.length}`),
      el('table', { class: 'grid' },
        el('thead', {}, el('tr', {},
          ['ID', 'Title', 'Sev', 'Pri', 'Relates to', 'Assignee'].map((h) => el('th', { text: h })))),
        el('tbody', {}, group.map((bug) =>
          el('tr', { class: 'row-link', onclick: () => openItem(bug.id) },
            el('td', { class: 'id', text: bug.id }),
            el('td', { text: show(bug.title) }),
            el('td', { text: show(bug.severity) }),
            el('td', { text: show(bug.priority) }),
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
      el('table', { class: 'grid' },
        el('thead', {}, el('tr', {},
          ['Sprint', 'Dates', 'Goal', 'Committed', 'Completed', 'Velocity', 'Delivered', 'Carried over']
            .map((h) => el('th', { text: h })))),
        el('tbody', {}, repo.history.sprints.map((s) =>
          el('tr', {},
            el('td', { class: 'id', text: show(s.name) }),
            el('td', { text: show(s.dates) }),
            el('td', { text: show(s.goal) }),
            el('td', { class: 'num', text: show(s.committed) }),
            el('td', { class: 'num', text: show(s.completed) }),
            el('td', { class: 'num', text: show(s.velocity) }),
            el('td', { class: 'id', text: s.delivered.join(', ') || EMPTY }),
            el('td', { class: 'id', text: s.carried.join(', ') || EMPTY })))))));
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
        el('div', { class: 'item' }, el('div', { class: 'grow', text: i.text }))))
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
              isSet(v.theme) ? el('p', { style: 'margin:0', text: v.theme }) : null,
              el('p', { class: 'hint', style: 'margin:6px 0 0',
                text: `Stories: ${v.stories.join(', ') || EMPTY}  ·  Epics: ${v.epics.join(', ') || EMPTY}` })))))
      : el('p', { class: 'empty', text: 'No releases cut yet.' })));
  return wrap;
};

VIEWS.files = () => {
  const wrap = el('div', {});
  wrap.append(sectionHead('Ledger files', 'the Markdown this page is built from',
    el('button', { class: 'btn', type: 'button', onclick: runCheck }, 'Run ledger check')));
  const pre = el('pre', { class: 'source', text: 'Pick a file…' });
  const picker = el('div', { class: 'chips', style: 'margin-bottom:12px' },
    state.workspace.vocabulary.files.map((name) =>
      el('button', { class: 'btn small', type: 'button', onclick: async () => {
        try {
          const data = await api(`/api/repo/${encodeURIComponent(state.slug)}/file/${encodeURIComponent(name)}`);
          pre.textContent = data.text;
        } catch (error) { pre.textContent = `Could not read ${name}: ${error.message}`; }
      } }, name)));
  wrap.append(picker, pre);
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
    stateBadge(story.state),
    isSet(story.priority) ? badge(story.priority) : null,
    isSet(story.parent) ? badge(story.parent) : null));
  wrap.append(el('h3', { style: 'margin-bottom:12px', text: show(story.title) }));

  wrap.append(el('div', { class: 'detail-block' },
    kvList([['Estimate', story.estimate], ['Area', story.area], ['Layer', story.layer],
            ['Assignee', story.assignee],
            ['Dependencies', story.dependencies.join(', ')],
            ['Delivered', story.delivered]])));

  if (isSet(story.story)) {
    wrap.append(el('div', { class: 'detail-block' },
      el('h4', { text: 'Story' }), el('p', { text: story.story })));
  }
  if (story.criteria_met) {
    wrap.append(el('div', { class: 'detail-block' },
      el('h4', { text: 'Acceptance criteria' }), el('p', { text: 'All met ✓' })));
  } else if (story.criteria.length) {
    wrap.append(el('div', { class: 'detail-block' },
      el('h4', { text: 'Acceptance criteria' }),
      el('ul', {}, story.criteria.map((c) => el('li', { text: c })))));
  }
  if (isSet(story.reason)) {
    wrap.append(el('div', { class: 'detail-block' }, el('h4', { text: 'Reason' }), el('p', { text: story.reason })));
  }
  if (isSet(story.notes)) {
    wrap.append(el('div', { class: 'detail-block' }, el('h4', { text: 'Notes' }), el('p', { text: story.notes })));
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
    stateBadge(bug.state),
    isSet(bug.severity) ? badge(`severity ${bug.severity}`) : null,
    isSet(bug.priority) ? badge(bug.priority) : null));
  wrap.append(el('h3', { style: 'margin-bottom:12px', text: show(bug.title) }));
  wrap.append(el('div', { class: 'detail-block' },
    kvList([['Estimate', bug.estimate], ['Area', bug.area], ['Assignee', bug.assignee],
            ['Reported by', bug.reported_by], ['Relates to', bug.relates_to], ['Fixed', bug.fixed]])));

  for (const [label, value] of [['Symptom', bug.symptom], ['Expected', bug.expected],
                                ['Actual', bug.actual], ['Assessment', bug.assessment],
                                ['Notes', bug.notes]]) {
    if (isSet(value)) {
      wrap.append(el('div', { class: 'detail-block' }, el('h4', { text: label }), el('p', { text: value })));
    }
  }
  if (bug.steps.length) {
    wrap.append(el('div', { class: 'detail-block' },
      el('h4', { text: `Steps to reproduce (${bug.steps_confidence || 'unconfirmed'})` }),
      el('ol', {}, bug.steps.map((s) => el('li', { text: s })))));
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

function branchFor(item) {
  const slug = String(item.title || '').toLowerCase().split(/\s+/)
    .map((w) => w.replace(/[^a-z0-9]/g, '')).filter(Boolean).slice(0, 5).join('-');
  const branch = `${item.id.toLowerCase()}-${slug || 'work'}`;
  navigator.clipboard?.writeText(branch).then(
    () => toast('ok', 'Branch name copied', branch),
    () => toast('warn', 'Branch name', branch));
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
  if (result.issues && result.issues.length) {
    toast('warn', `${result.issues.length} issue(s)`, null, result.issues);
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

const TABS = [
  ['overview', 'Overview'], ['board', 'Board'], ['ideas', 'Inbox'],
  ['epics', 'Epics'], ['stories', 'Stories'], ['bugs', 'Bugs'],
  ['sprints', 'Sprints'], ['releases', 'Releases'], ['files', 'Files'],
];

function counts() {
  const repo = state.repo;
  if (!repo) return {};
  return {
    ideas: repo.ideas.length + repo.bug_inbox.length,
    epics: repo.epics.length,
    stories: repo.stories.length,
    bugs: repo.stats.open_bugs,
    board: Object.values(repo.sprint.board).reduce((n, items) => n + items.length, 0),
    releases: repo.releases.increment.length,
  };
}

function renderTabs() {
  const bar = document.getElementById('tabs');
  const n = counts();
  bar.replaceChildren(...TABS.map(([id, label]) => {
    const node = el('button', { class: 'tab', type: 'button', role: 'tab',
      'aria-selected': String(id === state.tab),
      onclick: () => { state.tab = id; location.hash = id; render(); } },
      label);
    if (n[id]) node.append(el('span', { class: 'count', text: String(n[id]) }));
    return node;
  }));
}

function renderPeople() {
  const picker = document.getElementById('person-picker');
  const repo = state.repo;
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
}

function render() {
  renderTabs();
  renderPeople();
  const view = document.getElementById('view');
  if (!state.repo) {
    view.replaceChildren(el('p', { class: 'empty', text: 'No project selected.' }));
    return;
  }
  if (state.repo.missing_files && state.repo.missing_files.length) {
    toast('warn', 'Missing ledger files', state.repo.missing_files.join(', '));
  }
  try {
    view.replaceChildren((VIEWS[state.tab] || VIEWS.overview)());
  } catch (error) {
    view.replaceChildren(el('p', { class: 'empty', text: `Could not render this view: ${error.message}` }));
    throw error;
  }
}

async function loadRepo(slug) {
  state.slug = slug;
  localStorage.setItem('agile-ledger-pro.repo', slug);
  state.repo = await api(`/api/repo/${encodeURIComponent(slug)}`);
  state.revision = state.repo.revision;
  render();
}

async function refreshWorkspaceQuietly() {
  try { state.workspace = await api('/api/workspace'); } catch { /* keep the old copy */ }
}

/* Claude edits the same files from the terminal, so poll the folder's mtime and
 * pull a fresh copy when something changed underneath us. */
async function poll() {
  if (!state.slug || document.hidden) return;
  try {
    const { revision } = await api(`/api/repo/${encodeURIComponent(state.slug)}/revision`);
    if (revision && revision !== state.revision) {
      state.repo = await api(`/api/repo/${encodeURIComponent(state.slug)}`);
      state.revision = state.repo.revision;
      render();
      toast('ok', 'Ledger reloaded', 'The files changed on disk.');
    }
  } catch { /* the server may be stopping; try again next tick */ }
}

function applyTheme(mode) {
  document.documentElement.setAttribute('data-theme', mode);
  localStorage.setItem('agile-ledger-pro.theme', mode);
}

async function boot() {
  applyTheme(localStorage.getItem('agile-ledger-pro.theme') || 'auto');
  document.getElementById('theme-btn').addEventListener('click', () => {
    const order = ['auto', 'light', 'dark'];
    const now = document.documentElement.getAttribute('data-theme') || 'auto';
    applyTheme(order[(order.indexOf(now) + 1) % order.length]);
  });
  document.getElementById('commit-btn').addEventListener('click', commitForm);

  for (const node of document.querySelectorAll('[data-close]')) {
    node.addEventListener('click', () => { closeModal(); closeDrawer(); });
  }
  document.addEventListener('keydown', (event) => {
    if (event.key === 'Escape') { closeModal(); closeDrawer(); }
  });

  try {
    state.workspace = await api('/api/workspace');
  } catch (error) {
    document.getElementById('view').replaceChildren(
      el('p', { class: 'empty', text: `Could not reach the ledger: ${error.message}` }));
    return;
  }

  const path = document.getElementById('ledger-path');
  path.textContent = state.workspace.root;
  path.title = state.workspace.root;

  const present = state.workspace.repos.filter((r) => r.present);
  const picker = document.getElementById('repo-picker');
  picker.replaceChildren(...present.map((r) => el('option', { value: r.slug, text: r.slug })));
  picker.addEventListener('change', () => loadRepo(picker.value));

  if (!present.length) {
    document.getElementById('view').replaceChildren(el('p', { class: 'empty',
      text: 'This ledger has no repo folders yet. Run /register-repo in Claude Code.' }));
    return;
  }

  const remembered = localStorage.getItem('agile-ledger-pro.repo');
  const preferred = state.workspace.config.default_repo;
  const slug = present.some((r) => r.slug === remembered) ? remembered
    : present.some((r) => r.slug === preferred) ? preferred
    : present[0].slug;
  picker.value = slug;

  const hash = location.hash.replace('#', '');
  if (TABS.some(([id]) => id === hash)) state.tab = hash;

  document.getElementById('person-picker').addEventListener('change', (event) => {
    state.person = event.target.value;
    render();
  });

  await loadRepo(slug);
  setInterval(poll, 2500);
}

boot();
