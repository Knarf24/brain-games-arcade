// Page code: drawing, taps, swipes and saving stats. All game rules live in Python (arcade.py).
"use strict";

const $ = (id) => document.getElementById(id);
const GAMES = ["2048", "mastermind", "hangman", "cowsbulls"];
const NAMES = { "2048": "2048", mastermind: "Mastermind", hangman: "Hangman", cowsbulls: "Cows & Bulls" };
const ICONS = { "2048": "🔢", mastermind: "🎯", hangman: "🔤", cowsbulls: "🐮" };
const SITE = "https://knarf24.github.io/brain-games-arcade/";

let py = null;
let tab = "2048";
const mode = { "2048": "daily", mastermind: "daily", hangman: "daily", cowsbulls: "daily" };
const state = {};          // last state from Python, per game
const recorded = {};       // has this game instance been saved to stats?
let stats = loadStats();

// ------------------------------------------------------------ storage (safe if blocked)
function loadStats() {
  try { return JSON.parse(localStorage.getItem("bga-stats")) || null; } catch { return null; }
}
function saveStats() {
  try { localStorage.setItem("bga-stats", JSON.stringify(stats)); } catch { /* private mode */ }
}
function today() {
  const d = new Date();
  return `${d.getFullYear()}-${String(d.getMonth() + 1).padStart(2, "0")}-${String(d.getDate()).padStart(2, "0")}`;
}

// ------------------------------------------------------------ Python bridge
function call(cmd) {
  const out = JSON.parse(py.globals.get("call")(JSON.stringify(cmd)));
  if (out && out.error) throw new Error(out.error);
  return out;
}

async function start() {
  try {
    py = await loadPyodide({ indexURL: new URL("pyodide/", location.href).href });
    $("loadText").textContent = "Loading the games…";
    const code = await fetch("arcade.py").then((r) => { if (!r.ok) throw new Error("arcade.py missing"); return r.text(); });
    py.FS.writeFile("/home/pyodide/arcade.py", code);
    py.runPython("from arcade import call");
  } catch (e) {
    $("loadText").textContent = "Couldn't start Python: " + e.message + ". Please reload.";
    return;
  }
  $("loading").hidden = true;
  $("app").hidden = false;
  buildStatic();
  const wanted = (location.hash || "").slice(1);
  showTab(GAMES.includes(wanted) || wanted === "stats" ? wanted : "2048");
  updateStreak();
  if ("serviceWorker" in navigator && location.protocol === "https:") {
    navigator.serviceWorker.register("sw.js").catch(() => {});
  }
}

// ------------------------------------------------------------ tabs, modes, messages
function showTab(name) {
  tab = name;
  document.querySelectorAll("#tabs button").forEach((b) => b.setAttribute("aria-selected", String(b.dataset.game === name)));
  document.querySelectorAll(".game").forEach((s) => { s.hidden = s.id !== "g-" + name; });
  $("modebar").hidden = name === "stats";
  history.replaceState(null, "", "#" + name);
  say("");
  if (name === "stats") return drawStats();
  syncModeButtons();
  if (!state[name]) newGame(name);
  else draw(name);
  if (name === "2048") $("board").focus({ preventScroll: true });
}

function syncModeButtons() {
  document.querySelectorAll("#modebar [data-mode]").forEach((b) => b.classList.toggle("on", b.dataset.mode === mode[tab]));
  $("mmRepeatsWrap").hidden = mode.mastermind === "daily";
  $("hmCat").parentElement.hidden = mode.hangman === "daily";
}

function say(text, kind = "") {
  const m = $("msg");
  m.textContent = text;
  m.className = "msg " + kind;
}

function dailyDone(game) {
  return stats && stats.daily && stats.daily[today()] && stats.daily[today()][game];
}

function newGame(game) {
  const daily = mode[game] === "daily";
  const cmd = { op: "new", game };
  if (daily) cmd.day = today();
  if (!daily && game === "mastermind") cmd.repeats = $("mmRepeats").checked;
  if (!daily && game === "hangman" && $("hmCat").value) cmd.category = $("hmCat").value;
  state[game] = call(cmd);
  recorded[game] = false;
  if (game === "mastermind") mmCurrent = [];
  if (game === "cowsbulls") cbCurrent = "";
  draw(game);
  const done = daily && dailyDone(game);
  if (done) {
    say(`You already played today's ${NAMES[game]} (${done.won ? "won" : "not solved"}, ${done.score} points). Replays don't count. A new puzzle comes tomorrow, or switch to Free play.`, "info");
  } else if (daily) {
    say(`Today's ${NAMES[game]}: everyone gets the same puzzle today.`);
  } else {
    say("");
  }
}

function act(game, action, value) {
  try {
    const s = call({ op: "act", game, action, value });
    state[game] = s;
    draw(game);
    afterMove(game, s);
    return s;
  } catch (e) {
    say(e.message, "bad");
    buzz();
    return null;
  }
}

function afterMove(game, s) {
  if (!s.finished || recorded[game]) return;
  recorded[game] = true;
  const day = s.daily && !dailyDone(game) ? s.daily : null;
  stats = call({ op: "record", stats, game, won: s.win, score: s.points, day });
  saveStats();
  updateStreak();
  setTimeout(() => finishDialog(game, s, !!day), game === "2048" ? 350 : 500);
}

function buzz() { try { navigator.vibrate && navigator.vibrate(40); } catch { /* ignore */ } }

// ------------------------------------------------------------ end-of-game dialog
function resultLine(game, s) {
  if (game === "2048") return s.won ? `reached 2048 with ${s.score} points` : `scored ${s.score} (best tile ${s.best_tile})`;
  if (game === "hangman") return s.solved ? `guessed "${s.word.toUpperCase()}" with ${s.lives} lives left` : `missed "${s.word.toUpperCase()}"`;
  const used = s.guesses.length;
  return s.solved ? `cracked the code in ${used}/${s.max_tries}` : `ran out of tries`;
}

function finishDialog(game, s, countedDaily) {
  const won = s.win;
  $("ovEmoji").textContent = won ? "🎉" : "🧩";
  $("ovTitle").textContent = won ? "Well done!" : (game === "2048" ? "No more moves" : "So close!");
  let text = `You ${resultLine(game, s)}. ${s.points} points.`;
  if (game === "mastermind" && !s.solved) text += " The code is shown on the board.";
  if (game === "cowsbulls" && !s.solved) text += ` The number was ${s.secret}.`;
  if (countedDaily) text += ` Daily streak: ${currentStreak()} 🔥`;
  $("ovText").textContent = text;
  $("ovNext").textContent = s.daily ? "Try Free play" : "Play again";
  $("ovNext").onclick = () => {
    closeDialog();
    if (s.daily) { mode[game] = "free"; syncModeButtons(); }
    newGame(game);
  };
  $("ovShare").onclick = () => share(game, s);
  $("ovShare").textContent = "📋 Copy result";
  if (game === "2048" && s.won && !s.over) {
    $("ovNext").textContent = "Keep going";
    $("ovNext").onclick = () => { closeDialog(); act("2048", "continue"); };
  }
  $("overlay").hidden = false;
  $("ovNext").focus();
}
function closeDialog() { $("overlay").hidden = true; }

function share(game, s) {
  let rows = "";
  if (game === "mastermind") rows = "\n" + s.guesses.map((g) => "⚫".repeat(g.exact) + "⚪".repeat(g.near) + "·".repeat(s.pegs - g.exact - g.near)).join("\n");
  if (game === "cowsbulls") rows = "\n" + s.guesses.map((g) => "🐂".repeat(g.bulls) + "🐄".repeat(g.cows) + "▫️".repeat(4 - g.bulls - g.cows)).join("\n");
  const head = `🧠 Brain Games Arcade ${s.daily ? "daily " + s.daily : "free play"}\n${ICONS[game]} ${NAMES[game]}: I ${resultLine(game, s)}`;
  const text = `${head}${rows}\n${SITE}`;
  const done = () => { $("ovShare").textContent = "✓ Copied"; };
  if (navigator.clipboard) navigator.clipboard.writeText(text).then(done, () => prompt("Copy this:", text));
}

// ------------------------------------------------------------ drawing
function draw(game) {
  const s = state[game];
  if (!s) return;
  ({ "2048": draw2048, mastermind: drawMM, hangman: drawHM, cowsbulls: drawCB })[game](s);
}

// 2048 -------------------------------------------------------
function draw2048(s) {
  $("s2048").textContent = s.score;
  $("t2048").textContent = s.best_tile;
  $("m2048").textContent = s.moves;
  $("undo2048").disabled = !s.can_undo || s.finished;
  const board = $("board");
  board.innerHTML = "";
  s.grid.forEach((row, r) => row.forEach((v, c) => {
    const cell = document.createElement("div");
    cell.className = "cell";
    if (v) {
      cell.textContent = v;
      cell.dataset.v = v > 2048 ? "big" : v;
      if (s.new && s.new[0] === r && s.new[1] === c) cell.classList.add("pop");
      if (s.merged.some((m) => m[0] === r && m[1] === c)) cell.classList.add("merge");
      if (v >= 1024) cell.classList.add("small");
    }
    board.appendChild(cell);
  }));
}

function move2048(dir) {
  if (tab !== "2048" || !$("overlay").hidden) return;
  const before = state["2048"];
  if (before.finished) return;
  const s = act("2048", "move", dir);
  if (s && s.moves === before.moves) buzz();
}

// Mastermind -------------------------------------------------
let mmCurrent = [];
function pegHTML(c, s, cls = "") {
  return `<i class="peg ${cls}" style="--c: var(--${s.colours[c]})" title="${s.colours[c]}"></i>`;
}
function drawMM(s) {
  const rows = $("mmRows");
  let html = "";
  for (let i = 0; i < s.max_tries; i++) {
    const g = s.guesses[i];
    const active = !s.finished && i === s.guesses.length;
    html += `<div class="mm-row ${active ? "active" : ""} ${g ? "" : "empty"}"><span class="n">${i + 1}</span><span class="pegs">`;
    for (let p = 0; p < s.pegs; p++) html += g ? pegHTML(g.code[p], s) : `<i class="peg hole"></i>`;
    html += `</span><span class="keys">`;
    if (g) {
      for (let k = 0; k < g.exact; k++) html += `<i class="k exact"></i>`;
      for (let k = 0; k < g.near; k++) html += `<i class="k near"></i>`;
      for (let k = g.exact + g.near; k < s.pegs; k++) html += `<i class="k"></i>`;
    }
    html += `</span></div>`;
  }
  if (s.finished) {
    html += `<div class="mm-row secret"><span class="n">🔓</span><span class="pegs">${s.secret.map((c) => pegHTML(c, s)).join("")}</span><span class="keys">the code</span></div>`;
  }
  rows.innerHTML = html;
  drawMMCurrent(s);
  $("mmPossible").textContent = s.finished ? "" : `${s.possible.toLocaleString()} code${s.possible === 1 ? "" : "s"} still fit your clues`;
  $("mmHint").disabled = s.finished;
}
function drawMMCurrent(s) {
  const slots = $("mmSlots");
  slots.innerHTML = "";
  for (let p = 0; p < s.pegs; p++) {
    const b = document.createElement("button");
    b.className = "slot";
    b.setAttribute("aria-label", mmCurrent[p] === undefined ? `Empty slot ${p + 1}` : `Slot ${p + 1}: ${s.colours[mmCurrent[p]]}, tap to clear`);
    if (mmCurrent[p] !== undefined) b.innerHTML = pegHTML(mmCurrent[p], s);
    b.onclick = () => { if (mmCurrent[p] !== undefined) { mmCurrent.splice(p, 1); drawMMCurrent(s); } };
    b.disabled = s.finished;
    slots.appendChild(b);
  }
  $("mmCheck").disabled = s.finished || mmCurrent.length !== s.pegs;
  document.querySelectorAll("#mmPalette button").forEach((b) => { b.disabled = s.finished || mmCurrent.length >= s.pegs; });
}
function mmPick(c) {
  const s = state.mastermind;
  if (s.finished || mmCurrent.length >= s.pegs) return;
  if (!s.repeats && mmCurrent.includes(c)) { say("Each colour only once in this mode.", "bad"); buzz(); return; }
  mmCurrent.push(c);
  say("");
  drawMMCurrent(s);
}
function mmCheck() {
  const s = state.mastermind;
  if (mmCurrent.length !== s.pegs) return;
  const guess = mmCurrent.slice();
  mmCurrent = [];
  const out = act("mastermind", "check", guess);
  if (out && !out.finished) {
    const g = out.guesses[out.guesses.length - 1];
    say(g.exact + g.near === 0 ? "None of those colours are in the code." : `${g.exact} right place, ${g.near} wrong place.`);
  }
}

// Hangman ----------------------------------------------------
function drawHM(s) {
  $("hmCatShow").textContent = s.category;
  $("hmWord").style.setProperty("--n", s.length);
  $("hmWord").innerHTML = (s.word || "").length
    ? s.word.split("").map((ch) => `<span class="${s.guessed.includes(ch) ? "" : "missed"}">${ch.toUpperCase()}</span>`).join("")
    : s.pattern.split(" ").map((ch) => `<span>${ch === "_" ? "&nbsp;" : ch.toUpperCase()}</span>`).join("");
  $("hmLives").innerHTML = "❤️".repeat(s.lives) + "<span class='lost'>" + "🤍".repeat(s.max_lives - s.lives) + "</span>";
  $("hmClue").textContent = s.clue ? "💡 " + s.clue : "";
  $("hmClueBtn").hidden = !s.can_clue;
  const lost = s.max_lives - s.lives;
  document.querySelectorAll("#gallows .part").forEach((p, i) => p.classList.toggle("on", i < lost));
  document.querySelectorAll("#hmKeys button").forEach((b) => {
    const l = b.dataset.l;
    b.className = s.guessed.includes(l) ? "hit" : s.wrong.includes(l) ? "miss" : "";
    b.disabled = s.finished || s.guessed.includes(l) || s.wrong.includes(l);
  });
}
function hmGuess(l) {
  const s = state.hangman;
  if (s.finished || s.guessed.includes(l) || s.wrong.includes(l)) return;
  const out = act("hangman", "guess", l);
  if (out && !out.finished) say(out.guessed.includes(l) ? `Yes, there is ${/[aeiou]/.test(l) ? "an" : "a"} ${l.toUpperCase()}!` : `No ${l.toUpperCase()}.`, out.guessed.includes(l) ? "good" : "");
}

// Cows and Bulls ---------------------------------------------
let cbCurrent = "";
function drawCB(s) {
  drawCBEntry(s);
  $("cbLog").innerHTML = s.guesses.slice().reverse().map((g, i) =>
    `<tr><td>${s.guesses.length - i}</td><td class="code">${g.code}</td><td>${"🐂".repeat(g.bulls) || "0"}</td><td>${"🐄".repeat(g.cows) || "0"}</td></tr>`).join("");
  $("cbPossible").textContent = s.finished ? (s.solved ? "" : `The number was ${s.secret}.`)
    : `${s.possible.toLocaleString()} number${s.possible === 1 ? "" : "s"} still fit your clues · ${s.tries_left} tries left`;
  $("cbHint").disabled = s.finished;
}
function drawCBEntry(s) {
  const box = $("cbDigits");
  box.innerHTML = "";
  for (let i = 0; i < s.digits; i++) {
    const d = document.createElement("span");
    d.className = "digit" + (i === cbCurrent.length && !s.finished ? " cursor" : "");
    d.textContent = cbCurrent[i] || "";
    box.appendChild(d);
  }
  $("cbCheck").disabled = s.finished || cbCurrent.length !== s.digits;
  document.querySelectorAll("#cbPad button[data-d]").forEach((b) => {
    const d = b.dataset.d;
    b.disabled = s.finished || cbCurrent.includes(d) || cbCurrent.length >= s.digits || (d === "0" && cbCurrent.length === 0);
  });
}
function cbType(d) {
  const s = state.cowsbulls;
  if (s.finished) return;
  if (d === "del") cbCurrent = cbCurrent.slice(0, -1);
  else if (cbCurrent.length < s.digits && !cbCurrent.includes(d) && !(d === "0" && !cbCurrent)) cbCurrent += d;
  else buzz();
  drawCBEntry(s);
}
function cbCheck() {
  const s = state.cowsbulls;
  if (cbCurrent.length !== s.digits) return;
  const guess = cbCurrent;
  cbCurrent = "";
  const out = act("cowsbulls", "check", guess);
  if (out && !out.finished) {
    const g = out.guesses[out.guesses.length - 1];
    say(`${guess}: ${g.bulls} bull${g.bulls === 1 ? "" : "s"}, ${g.cows} cow${g.cows === 1 ? "" : "s"}.`);
  }
}

// Coach (both code games) -------------------------------------
function coach(game) {
  const s = act(game, "hint");
  if (!s) return;
  const h = s.hint;
  if (game === "cowsbulls") {
    cbCurrent = h.suggest;
    drawCBEntry(s);
    say(`Coach: ${h.possible.toLocaleString()} numbers still fit. Try ${h.suggest}, it narrows things down the most. (Each hint costs 25 points.)`, "info");
  } else {
    mmCurrent = h.suggest.slice();
    drawMMCurrent(s);
    say(`Coach: ${h.possible.toLocaleString()} codes still fit. The suggested guess splits them best. (Each hint costs 25 points.)`, "info");
  }
}

// Stats --------------------------------------------------------
function currentStreak() {
  if (!stats) return 0;
  return call({ op: "streak", stats, today: today() }).streak;
}
function updateStreak() {
  const n = currentStreak();
  $("streak").innerHTML = `🔥 <b>${n}</b> day streak`;
  $("streak").classList.toggle("hot", n > 0);
}
function drawStats() {
  const st = stats || { games: {}, daily: {}, best_streak: 0 };
  const g = st.games || {};
  const played = Object.values(g).reduce((a, x) => a + x.played, 0);
  const won = Object.values(g).reduce((a, x) => a + x.won, 0);
  const cards = [
    ["🔥", currentStreak(), "day streak"],
    ["🏆", st.best_streak || 0, "best streak"],
    ["🎮", played, "games played"],
    ["✅", played ? Math.round((100 * won) / played) + "%" : "–", "won"],
  ];
  $("statCards").innerHTML = cards.map(([e, v, l]) => `<div class="stat"><span>${e}</span><b>${v}</b><small>${l}</small></div>`).join("");
  const t = (st.daily || {})[today()] || {};
  $("today").innerHTML = GAMES.map((k) => {
    const r = t[k];
    return `<button class="today-item ${r ? (r.won ? "won" : "done") : ""}" data-go="${k}">${ICONS[k]} ${NAMES[k]}<small>${r ? (r.won ? "✓ " : "✗ ") + r.score + " pts" : "Not played yet"}</small></button>`;
  }).join("");
  document.querySelectorAll("#today [data-go]").forEach((b) => { b.onclick = () => { mode[b.dataset.go] = "daily"; state[b.dataset.go] = null; showTab(b.dataset.go); }; });
  $("statRows").innerHTML = GAMES.map((k) => {
    const x = g[k] || { played: 0, won: 0, best: 0 };
    return `<tr><td>${ICONS[k]} ${NAMES[k]}</td><td>${x.played}</td><td>${x.won}</td><td>${x.best}</td></tr>`;
  }).join("");
}

// ------------------------------------------------------------ one-time setup
function buildStatic() {
  document.querySelectorAll("#tabs button").forEach((b) => { b.onclick = () => showTab(b.dataset.game); });
  document.querySelectorAll("#modebar [data-mode]").forEach((b) => {
    b.onclick = () => { if (mode[tab] === b.dataset.mode) return; mode[tab] = b.dataset.mode; syncModeButtons(); newGame(tab); };
  });
  $("newBtn").onclick = () => newGame(tab);

  // 2048: keys, swipe, buttons
  document.addEventListener("keydown", (e) => {
    if (!$("overlay").hidden) { if (e.key === "Escape") closeDialog(); return; }
    if (e.target.tagName === "SELECT" || e.target.tagName === "INPUT") return;
    const k = e.key;
    if (tab === "2048") {
      const map = { ArrowUp: "up", ArrowDown: "down", ArrowLeft: "left", ArrowRight: "right", w: "up", s: "down", a: "left", d: "right" };
      if (map[k]) { e.preventDefault(); move2048(map[k]); }
      if (k === "z" || k === "u") act("2048", "undo");
    } else if (tab === "hangman" && /^[a-z]$/i.test(k) && !e.ctrlKey && !e.metaKey) {
      hmGuess(k.toLowerCase());
    } else if (tab === "cowsbulls") {
      if (/^[0-9]$/.test(k)) cbType(k);
      else if (k === "Backspace") cbType("del");
      else if (k === "Enter") cbCheck();
    } else if (tab === "mastermind") {
      if (/^[1-6]$/.test(k)) mmPick(Number(k) - 1);
      else if (k === "Backspace") { mmCurrent.pop(); drawMMCurrent(state.mastermind); }
      else if (k === "Enter") mmCheck();
    }
  });
  const board = $("board");
  let t0 = null;
  board.addEventListener("touchstart", (e) => { t0 = [e.touches[0].clientX, e.touches[0].clientY]; }, { passive: true });
  board.addEventListener("touchmove", (e) => { if (t0) e.preventDefault(); }, { passive: false });
  board.addEventListener("touchend", (e) => {
    if (!t0) return;
    const dx = e.changedTouches[0].clientX - t0[0];
    const dy = e.changedTouches[0].clientY - t0[1];
    t0 = null;
    if (Math.max(Math.abs(dx), Math.abs(dy)) < 24) return;
    move2048(Math.abs(dx) > Math.abs(dy) ? (dx > 0 ? "right" : "left") : (dy > 0 ? "down" : "up"));
  });
  document.querySelectorAll(".arrows [data-dir]").forEach((b) => { b.onclick = () => move2048(b.dataset.dir); });
  $("undo2048").onclick = () => act("2048", "undo");

  // Mastermind palette
  const colours = ["red", "blue", "green", "yellow", "purple", "orange"];
  $("mmPalette").innerHTML = colours.map((c, i) => `<button data-c="${i}" aria-label="${c}" title="${c} (key ${i + 1})"><i class="peg" style="--c: var(--${c})"></i></button>`).join("");
  document.querySelectorAll("#mmPalette button").forEach((b) => { b.onclick = () => mmPick(Number(b.dataset.c)); });
  $("mmCheck").onclick = mmCheck;
  $("mmHint").onclick = () => coach("mastermind");
  $("mmRepeats").onchange = () => { if (mode.mastermind === "free") newGame("mastermind"); };

  // Hangman keyboard and topics
  $("hmKeys").innerHTML = ["qwertyuiop", "asdfghjkl", "zxcvbnm"].map((row) =>
    `<div>${row.split("").map((l) => `<button data-l="${l}">${l.toUpperCase()}</button>`).join("")}</div>`).join("");
  document.querySelectorAll("#hmKeys button").forEach((b) => { b.onclick = () => hmGuess(b.dataset.l); });
  const cats = call({ op: "categories" }).categories;
  $("hmCat").innerHTML = `<option value="">Any topic</option>` + cats.map((c) => `<option>${c}</option>`).join("");
  $("hmCat").onchange = () => newGame("hangman");
  $("hmClueBtn").onclick = () => act("hangman", "clue");

  // Cows and Bulls keypad
  $("cbPad").innerHTML = "1234567890".split("").map((d) => `<button data-d="${d}">${d}</button>`).join("") + `<button data-del class="del" aria-label="Delete">⌫</button>`;
  document.querySelectorAll("#cbPad button").forEach((b) => { b.onclick = () => cbType(b.dataset.d || "del"); });
  $("cbCheck").onclick = cbCheck;
  $("cbHint").onclick = () => coach("cowsbulls");

  // Dialog and stats
  $("ovClose").onclick = closeDialog;
  $("overlay").onclick = (e) => { if (e.target.id === "overlay") closeDialog(); };
  $("resetStats").onclick = () => {
    if (!confirm("Delete all your stats and your streak on this device?")) return;
    stats = null;
    try { localStorage.removeItem("bga-stats"); } catch { /* ignore */ }
    updateStreak();
    drawStats();
  };
}

start();
