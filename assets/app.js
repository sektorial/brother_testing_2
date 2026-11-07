(() => {
  "use strict";

  const LIBRARY = "2025";
  const POOL_SIZE = 30;
  const SOURCES = [
    { id: "verbal-gold", title: "Вербальний GOLD", minutes: 8 },
    { id: "verbal-standart", title: "Вербальний STANDART", minutes: 8 },
    { id: "abstract", title: "Абстрактно-логічний", minutes: 20 },
    { id: "math", title: "Математичний", minutes: 20 },
  ];
  const LS_KEY = "bt2-progress-v1";

  const el = {
    homeBtn: document.getElementById("btn-home"),
    title: document.getElementById("title"),
    timer: document.getElementById("timer"),
    version: document.getElementById("app-version"),
    home: document.getElementById("screen-home"),
    pools: document.getElementById("screen-pools"),
    break: document.getElementById("screen-break"),
    quiz: document.getElementById("screen-quiz"),
    summary: document.getElementById("screen-summary"),
    sourceList: document.getElementById("source-list"),
    loadError: document.getElementById("load-error"),
    poolsLead: document.getElementById("pools-lead"),
    poolList: document.getElementById("pool-list"),
    breakText: document.getElementById("break-text"),
    nextPool: document.getElementById("btn-next-pool"),
    breakPools: document.getElementById("btn-break-pools"),
    quizMeta: document.getElementById("quiz-meta"),
    prompt: document.getElementById("prompt"),
    stimulus: document.getElementById("stimulus"),
    choices: document.getElementById("choices"),
    answerLabel: document.getElementById("answer-label"),
    answerHint: document.getElementById("answer-hint"),
    answerInput: document.getElementById("answer-input"),
    note: document.getElementById("note"),
    verdict: document.getElementById("verdict"),
    explanation: document.getElementById("explanation"),
    confirm: document.getElementById("btn-confirm"),
    prev: document.getElementById("btn-prev"),
    next: document.getElementById("btn-next"),
    finish: document.getElementById("btn-finish"),
    summaryText: document.getElementById("summary-text"),
    review: document.getElementById("btn-review"),
    toBreak: document.getElementById("btn-break"),
    retry: document.getElementById("btn-retry"),
    summaryPools: document.getElementById("btn-summary-pools"),
  };

  /** @type {any[]} */
  let questions = [];
  /** @type {{ sourceId: string, poolIndex: number, index: number } | null} */
  let session = null;
  let tickId = 0;

  function loadStore() {
    try {
      const raw = JSON.parse(localStorage.getItem(LS_KEY) || "{}");
      return { answers: raw.answers || {}, timers: raw.timers || {} };
    } catch {
      return { answers: {}, timers: {} };
    }
  }
  function saveStore(store) {
    localStorage.setItem(LS_KEY, JSON.stringify(store));
  }

  function sourceById(id) {
    return SOURCES.find((source) => source.id === id);
  }
  function sourceQuestions(sourceId) {
    return questions
      .filter((item) => item.library === LIBRARY && item.source === sourceId)
      .sort((a, b) => a.number - b.number);
  }
  function buildPools(sourceId) {
    const list = sourceQuestions(sourceId);
    const pools = [];
    for (let start = 0; start < list.length; start += POOL_SIZE) {
      const items = list.slice(start, start + POOL_SIZE);
      pools.push({
        index: pools.length,
        items,
        from: items[0].number,
        to: items[items.length - 1].number,
      });
    }
    return pools;
  }
  function poolKey(sourceId, poolIndex) {
    return `${sourceId}:${poolIndex}`;
  }
  function currentPool() {
    if (!session) return null;
    return buildPools(session.sourceId)[session.poolIndex] || null;
  }

  function show(name) {
    el.home.hidden = name !== "home";
    el.pools.hidden = name !== "pools";
    el.break.hidden = name !== "break";
    el.quiz.hidden = name !== "quiz";
    el.summary.hidden = name !== "summary";
    el.homeBtn.hidden = name === "home";
    const timed = name === "quiz" || name === "summary";
    el.timer.hidden = !timed;
    if (name === "home") el.title.textContent = "Тренажер";
  }

  function formatClock(ms) {
    const total = Math.max(0, Math.ceil(ms / 1000));
    const minutes = Math.floor(total / 60);
    const seconds = total % 60;
    return `${String(minutes).padStart(2, "0")}:${String(seconds).padStart(2, "0")}`;
  }
  function limitMs(sourceId) {
    return sourceById(sourceId).minutes * 60 * 1000;
  }
  function timerState(sourceId, poolIndex) {
    const timer = loadStore().timers[poolKey(sourceId, poolIndex)];
    if (!timer) return { started: false, left: limitMs(sourceId), closed: false };
    if (timer.closed) return { started: true, left: timer.left, closed: true };
    return { started: true, left: timer.deadline - Date.now(), closed: false };
  }
  function ensureTimer(sourceId, poolIndex) {
    const store = loadStore();
    const key = poolKey(sourceId, poolIndex);
    if (!store.timers[key]) {
      store.timers[key] = { deadline: Date.now() + limitMs(sourceId) };
      saveStore(store);
    }
  }
  function closeTimer(sourceId, poolIndex) {
    const store = loadStore();
    const key = poolKey(sourceId, poolIndex);
    const timer = store.timers[key];
    if (!timer || timer.closed) return;
    store.timers[key] = { closed: true, left: Math.max(0, timer.deadline - Date.now()) };
    saveStore(store);
  }

  function normExpr(value) {
    return String(value)
      .trim()
      .toLowerCase()
      .replace(/\s+/g, "")
      .replace(/×/g, "*")
      .replace(/÷/g, "/")
      .replace(/[−–—]/g, "-")
      .replace(/,/g, ".");
  }
  function numsEqual(given, expected) {
    const left = normExpr(given);
    const right = normExpr(expected);
    if (left === right) return true;
    const a = Number(left);
    const b = Number(right);
    return Number.isFinite(a) && Number.isFinite(b) && Math.abs(a - b) < 1e-9;
  }
  function isTyped(question) {
    return question.interaction === "numeric" || question.interaction === "expression";
  }
  function grade(question, picked) {
    const correct = (question.correct || []).map(String);
    if (isTyped(question)) {
      return correct.some((item) =>
        question.interaction === "expression" ? normExpr(picked[0] || "") === normExpr(item) : numsEqual(picked[0] || "", item)
      );
    }
    const chosen = new Set(picked.map(String));
    if (chosen.size !== correct.length) return false;
    return correct.every((item) => chosen.has(item));
  }
  function savedAnswer(id) {
    return loadStore().answers[id] || null;
  }
  function poolStats(pool) {
    let correct = 0;
    let answered = 0;
    for (const question of pool.items) {
      const saved = savedAnswer(question.id);
      if (!saved) continue;
      answered += 1;
      if (saved.ok) correct += 1;
    }
    return { correct, answered, total: pool.items.length };
  }

  function makePoolButton(sourceId, pool) {
    const stats = poolStats(pool);
    const state = timerState(sourceId, pool.index);
    const button = document.createElement("button");
    button.type = "button";
    button.className = "choice" + (stats.answered ? " selected" : "");
    button.dataset.source = sourceId;
    button.dataset.pool = String(pool.index);
    const label = document.createElement("span");
    label.textContent = `Пул ${pool.index + 1} · № ${pool.from}–${pool.to}`;
    const sub = document.createElement("span");
    sub.className = "sub";
    const score = document.createElement("span");
    score.className = "score";
    score.textContent = `${stats.correct}/${stats.total}`;
    const clock = document.createElement("span");
    clock.className = "clock";
    sub.append(score, clock);
    paintClock(clock, state);
    button.append(label, sub);
    button.addEventListener("click", () => {
      session = { sourceId, poolIndex: pool.index, index: 0 };
      openPool(pool.index);
    });
    return button;
  }

  function renderHome() {
    session = null;
    show("home");
    el.sourceList.replaceChildren();
    for (const source of SOURCES) {
      const section = document.createElement("section");
      section.className = "block";
      const heading = document.createElement("h2");
      const count = sourceQuestions(source.id).length;
      heading.textContent = `${source.title} · ${count} · ${source.minutes} хв`;
      const stack = document.createElement("div");
      stack.className = "stack";
      for (const pool of buildPools(source.id)) stack.append(makePoolButton(source.id, pool));
      section.append(heading, stack);
      el.sourceList.append(section);
    }
  }

  function openPools(sourceId) {
    session = { sourceId, poolIndex: 0, index: 0 };
    show("pools");
    const source = sourceById(sourceId);
    el.title.textContent = source.title;
    const pools = buildPools(sourceId);
    el.poolsLead.textContent = `${pools.length} пулів по порядку файлу. Таймер ${source.minutes} хв на пул починається з першого відкриття і не зупиняється в меню.`;
    paintPools();
  }

  function paintPools() {
    if (!session) return;
    const pools = buildPools(session.sourceId);
    el.poolList.replaceChildren();
    for (const pool of pools) el.poolList.append(makePoolButton(session.sourceId, pool));
  }

  function paintClock(node, state) {
    if (!state.started) {
      node.textContent = "";
      return;
    }
    if (state.left <= 0) node.textContent = " · час вийшов";
    else node.textContent = ` · ${formatClock(state.left)}`;
  }

  function openPool(poolIndex) {
    session.poolIndex = poolIndex;
    session.reviewing = false;
    session.index = 0;
    ensureTimer(session.sourceId, poolIndex);
    if (timerState(session.sourceId, poolIndex).left <= 0) {
      closeTimer(session.sourceId, poolIndex);
      showSummary(true);
      return;
    }
    if (timerState(session.sourceId, poolIndex).closed) {
      showSummary(false);
      return;
    }
    const pool = currentPool();
    const firstOpen = pool.items.findIndex((question) => !savedAnswer(question.id));
    session.index = firstOpen === -1 ? 0 : firstOpen;
    show("quiz");
    renderQuestion();
  }

  function renderQuestion() {
    const pool = currentPool();
    const question = pool.items[session.index];
    const saved = savedAnswer(question.id);
    const closed = timerState(session.sourceId, session.poolIndex).closed;
    const locked = Boolean(saved) || closed;
    const source = sourceById(session.sourceId);
    el.title.textContent = `${source.title} · пул ${session.poolIndex + 1}`;
    el.quizMeta.textContent = `Питання ${session.index + 1} з ${pool.items.length} · № ${question.number}`;
    el.prompt.textContent = question.prompt || "";

    el.stimulus.replaceChildren();
    for (const path of question.stimulus_images || []) {
      const image = document.createElement("img");
      image.src = path;
      image.alt = "Схема до умови";
      el.stimulus.append(image);
    }

    const typed = isTyped(question);
    el.choices.hidden = typed;
    el.answerLabel.hidden = !typed;
    el.choices.replaceChildren();
    el.choices.classList.toggle("figures", !typed && (question.options || []).some((option) => option.image));

    const picked = new Set(locked ? saved.picked.map(String) : []);
    if (!typed) {
      for (const option of question.options || []) {
        const button = document.createElement("button");
        button.type = "button";
        button.className = "option";
        button.dataset.id = String(option.id);
        if (option.image) {
          const image = document.createElement("img");
          image.src = option.image;
          image.alt = `Фігура ${option.id}`;
          const caption = document.createElement("span");
          caption.className = "caption";
          caption.textContent = `Фігура ${option.id}`;
          button.append(image, caption);
        } else {
          button.textContent = option.text || option.id;
        }
        if (locked) {
          const correct = new Set((question.correct || []).map(String));
          const chosen = picked.has(String(option.id));
          button.classList.toggle("good", correct.has(String(option.id)));
          button.classList.toggle("bad", chosen && !correct.has(String(option.id)));
          button.disabled = true;
        } else if (picked.has(String(option.id))) {
          button.classList.add("selected");
        }
        button.addEventListener("click", () => toggleOption(question, String(option.id)));
        el.choices.append(button);
      }
    } else {
      el.answerHint.textContent = question.interaction === "expression"
        ? "Впишіть вираз із діями і результатом. Пробіли не враховуються."
        : "Впишіть число. Кома і крапка рівнозначні.";
      el.answerInput.value = locked ? (saved.picked[0] || "") : "";
      el.answerInput.disabled = locked;
    }

    const issues = question.issues || [];
    const notes = [];
    if (question.confidence === "low" || issues.includes("buttons-illegible")) {
      notes.push("Ключ неповний: частину кнопок на скані не вдалося прочитати.");
    }
    if (issues.includes("explanation-cropped")) {
      notes.push("Пояснення на скані обрізане.");
    }
    el.note.hidden = notes.length === 0;
    el.note.textContent = notes.join(" ");

    paintVerdict(question, saved);
    if (closed && !saved) {
      el.verdict.hidden = false;
      el.verdict.className = "verdict bad";
      el.verdict.textContent = `Без відповіді. Відповідь: ${(question.correct || []).join(", ")}`;
      const text = (question.explanation || "").trim();
      el.explanation.hidden = !text;
      el.explanation.textContent = text;
    }
    el.confirm.hidden = locked;
    el.confirm.disabled = true;
    el.prev.disabled = session.index === 0;
    el.next.textContent = session.index === pool.items.length - 1 ? "До результату" : "Далі";
    if (!locked && typed) syncTypedConfirm();
    if (!locked && !typed) syncChoiceConfirm(question);
  }

  function selectionFromDom() {
    return [...el.choices.querySelectorAll(".option.selected")].map((node) => node.dataset.id);
  }
  function neededCount(question) {
    return question.interaction === "pair" ? 2 : 1;
  }
  function syncChoiceConfirm(question) {
    el.confirm.disabled = selectionFromDom().length !== neededCount(question);
  }
  function syncTypedConfirm() {
    el.confirm.disabled = el.answerInput.value.trim().length === 0;
  }
  function toggleOption(question, id) {
    if (savedAnswer(question.id)) return;
    const need = neededCount(question);
    const selected = new Set(selectionFromDom());
    if (selected.has(id)) selected.delete(id);
    else if (need === 1) {
      selected.clear();
      selected.add(id);
    } else if (selected.size < need) selected.add(id);
    for (const button of el.choices.querySelectorAll(".option")) {
      button.classList.toggle("selected", selected.has(button.dataset.id));
    }
    syncChoiceConfirm(question);
  }

  function paintVerdict(question, saved) {
    if (!saved) {
      el.verdict.hidden = true;
      el.explanation.hidden = true;
      return;
    }
    el.verdict.hidden = false;
    el.verdict.className = "verdict " + (saved.ok ? "good" : "bad");
    const key = (question.correct || []).join(", ");
    el.verdict.textContent = saved.ok ? "Правильно" : `Неправильно. Відповідь: ${key}`;
    const text = (question.explanation || "").trim();
    el.explanation.hidden = !text;
    el.explanation.textContent = text;
  }

  function commitAnswer() {
    const pool = currentPool();
    const question = pool.items[session.index];
    if (savedAnswer(question.id) || timerState(session.sourceId, session.poolIndex).closed) return;
    const picked = isTyped(question) ? [el.answerInput.value.trim()] : selectionFromDom();
    if (!picked.length || (isTyped(question) && !picked[0])) return;
    if (!isTyped(question) && picked.length !== neededCount(question)) return;
    const store = loadStore();
    store.answers[question.id] = { ok: grade(question, picked), picked };
    saveStore(store);
    renderQuestion();
  }

  function showSummary(expired) {
    const pool = currentPool();
    const stats = poolStats(pool);
    const source = sourceById(session.sourceId);
    const left = Math.max(0, timerState(session.sourceId, pool.index).left);
    const used = limitMs(session.sourceId) - left;
    show("summary");
    el.title.textContent = `${source.title} · пул ${pool.index + 1}`;
    el.timer.textContent = formatClock(left);
    el.timer.classList.toggle("low", left <= 0);
    const timeNote = expired ? "Час вичерпано. " : `Витрачено ${formatClock(used)}. `;
    el.summaryText.textContent = `${timeNote}Правильно ${stats.correct} з ${stats.total}. Без відповіді ${stats.total - stats.answered}.`;
    const hasNext = pool.index + 1 < buildPools(session.sourceId).length;
    el.toBreak.hidden = !hasNext;
  }

  function goNext() {
    const pool = currentPool();
    if (session.index < pool.items.length - 1) {
      session.index += 1;
      renderQuestion();
      return;
    }
    closeTimer(session.sourceId, pool.index);
    showSummary(timerState(session.sourceId, pool.index).left <= 0);
  }

  function refreshClocks(root) {
    for (const button of root.querySelectorAll("button[data-pool]")) {
      const clock = button.querySelector(".clock");
      if (!clock) continue;
      paintClock(clock, timerState(button.dataset.source, Number(button.dataset.pool)));
    }
  }

  function tick() {
    if (!el.home.hidden) {
      refreshClocks(el.sourceList);
      return;
    }
    if (!session || (el.quiz.hidden && el.summary.hidden && el.pools.hidden)) return;
    if (!el.pools.hidden) {
      refreshClocks(el.poolList);
      return;
    }
    const state = timerState(session.sourceId, session.poolIndex);
    const left = Math.max(0, state.left);
    el.timer.textContent = formatClock(left);
    el.timer.classList.toggle("low", left < 60 * 1000);
    if (!el.quiz.hidden && !state.closed && state.left <= 0) {
      closeTimer(session.sourceId, session.poolIndex);
      showSummary(true);
    }
  }

  el.homeBtn.addEventListener("click", renderHome);
  el.confirm.addEventListener("click", commitAnswer);
  el.answerInput.addEventListener("input", syncTypedConfirm);
  el.answerInput.addEventListener("keydown", (event) => {
    if (event.key === "Enter" && !el.confirm.disabled) commitAnswer();
  });
  el.prev.addEventListener("click", () => {
    if (session.index > 0) {
      session.index -= 1;
      renderQuestion();
    }
  });
  el.next.addEventListener("click", goNext);
  el.finish.addEventListener("click", () => {
    closeTimer(session.sourceId, session.poolIndex);
    showSummary(timerState(session.sourceId, session.poolIndex).left <= 0);
  });
  el.review.addEventListener("click", () => {
    session.reviewing = true;
    session.index = 0;
    show("quiz");
    renderQuestion();
  });
  el.toBreak.addEventListener("click", () => {
    const next = buildPools(session.sourceId)[session.poolIndex + 1];
    show("break");
    el.timer.hidden = true;
    el.title.textContent = "Перерва";
    el.breakText.textContent = `Наступний пул ${session.poolIndex + 2}: питання № ${next.from}–${next.to}. Таймер почнеться, коли відкриєте його.`;
  });
  el.nextPool.addEventListener("click", () => openPool(session.poolIndex + 1));
  el.breakPools.addEventListener("click", () => openPools(session.sourceId));
  el.summaryPools.addEventListener("click", () => openPools(session.sourceId));
  el.retry.addEventListener("click", () => {
    const pool = currentPool();
    const store = loadStore();
    for (const question of pool.items) delete store.answers[question.id];
    delete store.timers[poolKey(session.sourceId, session.poolIndex)];
    saveStore(store);
    openPool(pool.index);
  });

  if (el.version) el.version.textContent = `Версія ${window.APP_VERSION || "1.0.0"}`;

  tickId = setInterval(tick, 250);

  fetch("data/questions.json")
    .then((response) => {
      if (!response.ok) throw new Error(String(response.status));
      return response.json();
    })
    .then((data) => {
      questions = data;
      renderHome();
    })
    .catch(() => {
      el.loadError.hidden = false;
      el.loadError.textContent = "Не вдалося завантажити банк питань.";
    });
})();
