'use strict';

async function loadPrompt() {
  const res = await fetch('chat_prompt.json', { cache: 'no-cache' });
  if (!res.ok) throw new Error('Failed to load chat_prompt.json');
  return res.json();
}

function posRankBadge(pos, ranks) {
  const color = pos === 'QB' ? '#8ab4ff' : pos === 'RB' ? '#95ffa3' : pos === 'WR' ? '#ffd48b' : pos === 'TE' ? '#ff9ad1' : pos === 'K' ? '#b8b8ff' : '#9fe3ff';
  return `<span class="badge" style="border-color:${color}66;color:${color}">${pos}: ${ranks.join(', ')}</span>`;
}

function tierChip(idx, total) {
  const p = (idx + 1) / total;
  if (p <= 0.33) return '<span class="chip chip-good">Top</span>';
  if (p <= 0.66) return '<span class="chip chip-mid">Mid</span>';
  return '<span class="chip chip-bad">Bottom</span>';
}

function render(league) {
  const leagueName = document.getElementById('league-name');
  const week = document.getElementById('context-week');
  const list = document.getElementById('rankings');
  const teams = league.teams || [];
  leagueName.textContent = league.league ? league.league : 'League';
  week.textContent = `Week ${league.week ?? ''}`;
  list.innerHTML = '';

  if (!Array.isArray(teams) || teams.length === 0) {
    list.innerHTML = '<li class="card"><div class="rank">–</div><div class="card-body"><h2 class="team-name">No rankings available</h2><div class="sub">Ensure chat_prompt.json exists and is accessible</div></div></li>';
    return;
  }

  teams.forEach((t, idx) => {
    const summary = (t.ai_summary_html || '').trim();
    const info = `${t.record || ''} • PF ${t.points_for ?? '-'}${t.stars && t.stars.length ? ` • ⭐ ${t.stars.join(', ')}` : ''}`;

    const li = document.createElement('li');
    const rankNum = idx + 1;
    let tier = 'tier-mid';
    // Top 6 => green, 7-9 => yellow, bottom 3 => red
    if (rankNum <= 6) tier = 'tier-good';
    else if (rankNum <= 9) tier = 'tier-mid';
    else tier = 'tier-bad';
    li.className = `card ${tier}`;
    li.innerHTML = `
      <div class="rank">${rankNum}</div>
      <div class="card-body">
        <div class="card-top">
          <h2 class="team-name">${t.team_name}</h2>
        </div>
        <div class="sub">${info}</div>
        <div class="summary">${summary || ''}</div>
      </div>
    `;
    list.appendChild(li);
  });
}

async function main() {
  try {
    if (location.protocol === 'file:') {
      console.warn('Serving over file:// can block fetch of chat_prompt.json. Start a local server, e.g. `python -m http.server 8000`.');
      const list = document.getElementById('rankings');
      list.innerHTML = '<li class="card"><div class="rank">!</div><div class="card-body"><h2 class="team-name">Cannot load data</h2><div class="sub">Open this site via http://localhost (not file://). Try: <code>python -m http.server 8000</code></div></div></li>';
    }
    const data = await loadPrompt();
    render(data);
  } catch (e) {
    console.error(e);
    const list = document.getElementById('rankings');
    list.innerHTML = '<li class="card"><div class="rank">!</div><div class="card-body"><h2 class="team-name">Failed to load chat_prompt.json</h2><div class="sub">Check that the file exists and you are serving this folder over HTTP</div></div></li>';
  }
}

document.getElementById('refresh-btn').addEventListener('click', main);

main();