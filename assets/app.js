(() => {
  "use strict";

  const POOL_SIZE = 30;
  const LIBRARIES = [
    { id: "2025", title: "САП 2025" },
    { id: "femida-2022", title: "FEMIDA 2022" },
    { id: "psymetrics-2021", title: "Psymetrics 2021" },
    { id: "psymetrics-2022", title: "Psymetrics test 2022" },
    { id: "startexam-2022", title: "StartExam 2022" },
  ];
  const CATEGORIES = [
    { id: "verbal", title: "Вербальний блок", minutes: 8 },
    { id: "abstract", title: "Абстрактно-логічний блок", minutes: 20 },
    { id: "math", title: "Математичний блок", minutes: 20 },
  ];
  const LEGACY_SOURCES = {
    "verbal-gold": { title: "Вербальний GOLD", block: "verbal", order: 0 },
    "verbal-standart": { title: "Вербальний STANDART", block: "verbal", order: 1 },
    abstract: { title: "Абстрактно-логічний", block: "abstract", order: 0 },
    math: { title: "Математичний", block: "math", order: 0 },
  };
  const MARKS = [
    { id: "flag", label: "Прапорець" },
    { id: "heart", label: "Серце" },
    { id: "star", label: "Зірка" },
  ];
  const LS_KEY = "bt2-progress-v1";
  const AUTH_KEY = "bt2-auth-v1";

  const el = {
    homeBtn: document.getElementById("btn-home"),
    title: document.getElementById("title"),
    timer: document.getElementById("timer"),
    version: document.getElementById("app-version"),
    login: document.getElementById("screen-login"),
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
    wrong: document.getElementById("btn-wrong"),
    markRetries: document.getElementById("mark-retries"),
    toBreak: document.getElementById("btn-break"),
    retry: document.getElementById("btn-retry"),
    summaryPools: document.getElementById("btn-summary-pools"),
    logout: document.getElementById("btn-logout"),
    loginForm: document.getElementById("login-form"),
    loginUser: document.getElementById("login-user"),
    loginPass: document.getElementById("login-pass"),
    loginError: document.getElementById("login-error"),
    markButtons: [...document.querySelectorAll(".mark")],
  };

  /** @type {any[]} */
  let questions = [];
  /** @type {{ libraryId: string, sourceId: string | null, poolIndex: number, index: number, reviewing: boolean, drill: { kind: string, mark: string | null, items: any[] } | null } | null} */
  let session = null;
  let tickId = 0;

  function loadStore() {
    try {
      const raw = JSON.parse(localStorage.getItem(LS_KEY) || "{}");
      return { answers: raw.answers || {}, timers: raw.timers || {}, marks: raw.marks || {} };
    } catch {
      return { answers: {}, timers: {}, marks: {} };
    }
  }
  function saveStore(store) {
    localStorage.setItem(LS_KEY, JSON.stringify(store));
  }

  function libraryById(id) {
    return LIBRARIES.find((library) => library.id === id);
  }
  function categoryById(id) {
    return CATEGORIES.find((category) => category.id === id);
  }
  function sourcesFor(libraryId) {
    const map = new Map();
    questions.forEach((question, index) => {
      if (question.library !== libraryId || map.has(question.source)) return;
      const legacy = LEGACY_SOURCES[question.source];
      map.set(question.source, {
        id: question.source,
        title: question.source_title || legacy?.title || question.source,
        block: question.block || legacy?.block || "verbal",
        order: question.source_order ?? legacy?.order ?? index,
      });
    });
    return [...map.values()].sort((a, b) => a.order - b.order || a.title.localeCompare(b.title, "uk"));
  }
  function sourceById(libraryId, sourceId) {
    return sourcesFor(libraryId).find((source) => source.id === sourceId) || null;
  }
  function sourceQuestions(libraryId, sourceId) {
    return questions
      .filter((item) => item.library === libraryId && item.source === sourceId)
      .sort((a, b) => a.number - b.number);
  }
  function buildPools(libraryId, sourceId) {
    const list = sourceQuestions(libraryId, sourceId);
    const pools = [];
    for (let start = 0; start < list.length; start += POOL_SIZE) {
      const items = list.slice(start, start + POOL_SIZE);
      if (!items.length) continue;
      pools.push({
        index: pools.length,
        items,
        from: items[0].number,
        to: items[items.length - 1].number,
      });
    }
    return pools;
  }
  function timerStorageKey(libraryId, sourceId, poolIndex) {
    const next = `${libraryId}:${sourceId}:${poolIndex}`;
    if (libraryId === "2025") {
      const legacy = `${sourceId}:${poolIndex}`;
      const timers = loadStore().timers;
      if (timers[legacy] && !timers[next]) return legacy;
    }
    return next;
  }
  function currentPool() {
    if (!session?.sourceId) return null;
    return buildPools(session.libraryId, session.sourceId)[session.poolIndex] || null;
  }
  function activeItems() {
    if (session?.drill) return session.drill.items;
    return currentPool()?.items || [];
  }
  function limitMs(source) {
    return (categoryById(source.block)?.minutes || 20) * 60 * 1000;
  }

  function show(name) {
    el.login.hidden = name !== "login";
    el.home.hidden = name !== "libraries";
    el.pools.hidden = name !== "pools";
    el.break.hidden = name !== "break";
    el.quiz.hidden = name !== "quiz";
    el.summary.hidden = name !== "summary";
    el.homeBtn.hidden = name === "libraries" || name === "login";
    el.homeBtn.textContent = name === "pools" ? "← Бібліотеки" : "← Меню";
    const timed = (name === "quiz" || name === "summary") && !(session && session.drill);
    el.timer.hidden = !timed;
    if (name === "libraries") el.title.textContent = "Тренажер";
  }

  function formatClock(ms) {
    const total = Math.max(0, Math.ceil(ms / 1000));
    const minutes = Math.floor(total / 60);
    const seconds = total % 60;
    return `${String(minutes).padStart(2, "0")}:${String(seconds).padStart(2, "0")}`;
  }
  function timerState(libraryId, sourceId, poolIndex) {
    const source = sourceById(libraryId, sourceId);
    const limit = source ? limitMs(source) : 0;
    const timer = loadStore().timers[timerStorageKey(libraryId, sourceId, poolIndex)];
    if (!timer) return { started: false, left: limit, closed: false };
    if (timer.closed) return { started: true, left: timer.left, closed: true };
    return { started: true, left: timer.deadline - Date.now(), closed: false };
  }
  function ensureTimer(libraryId, sourceId, poolIndex) {
    const store = loadStore();
    const key = timerStorageKey(libraryId, sourceId, poolIndex);
    if (!store.timers[key]) {
      const source = sourceById(libraryId, sourceId);
      store.timers[key] = { deadline: Date.now() + limitMs(source) };
      saveStore(store);
    }
  }
  function closeTimer(libraryId, sourceId, poolIndex) {
    const store = loadStore();
    const key = timerStorageKey(libraryId, sourceId, poolIndex);
    const timer = store.timers[key];
    if (!timer || timer.closed) return;
    store.timers[key] = { closed: true, left: Math.max(0, timer.deadline - Date.now()) };
    saveStore(store);
  }
  function clearTimer(libraryId, sourceId, poolIndex) {
    const store = loadStore();
    delete store.timers[timerStorageKey(libraryId, sourceId, poolIndex)];
    delete store.timers[`${libraryId}:${sourceId}:${poolIndex}`];
    delete store.timers[`${sourceId}:${poolIndex}`];
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
  function splitEq(value) {
    const index = value.indexOf("=");
    if (index === -1) return [value, ""];
    return [value.slice(0, index), value.slice(index + 1)];
  }
  function exprEqual(given, expected) {
    const left = normExpr(given);
    const right = normExpr(expected);
    if (left === right) return true;
    const [givenLeft, givenRight] = splitEq(left);
    const [expectedLeft, expectedRight] = splitEq(right);
    if (!givenLeft || givenLeft !== expectedLeft) return false;
    if (!givenRight || !expectedRight) return true;
    return numsEqual(givenRight, expectedRight);
  }
  function keyText(question) {
    return (question.correct || []).map((id) => {
      const option = (question.options || []).find((item) => String(item.id) === String(id));
      if (option?.text) return option.text;
      if (option?.image) return `Фігура ${id}`;
      return String(id);
    }).join(", ");
  }
  function hasKey(question) {
    return (question.correct || []).length > 0 && !(question.issues || []).includes("key-missing");
  }
  function grade(question, picked) {
    const correct = (question.correct || []).map(String);
    if (isTyped(question)) {
      return correct.some((item) =>
        question.interaction === "expression" ? exprEqual(picked[0] || "", item) : numsEqual(picked[0] || "", item)
      );
    }
    const chosen = new Set(picked.map(String));
    if (chosen.size !== correct.length) return false;
    return correct.every((item) => chosen.has(item));
  }
  function savedAnswer(id) {
    return loadStore().answers[id] || null;
  }
  function savedMark(id) {
    return loadStore().marks[id] || null;
  }
  function poolStats(pool) {
    let correct = 0;
    let answered = 0;
    let total = 0;
    let unscored = 0;
    for (const question of pool.items) {
      if (!hasKey(question)) {
        unscored += 1;
        continue;
      }
      total += 1;
      const saved = savedAnswer(question.id);
      if (!saved || saved.unscored) continue;
      answered += 1;
      if (saved.ok) correct += 1;
    }
    return { correct, answered, total, unscored };
  }

  function paintClock(node, state) {
    if (!state.started) {
      node.textContent = "";
      return;
    }
    if (state.left <= 0) node.textContent = " · час вийшов";
    else node.textContent = ` · ${formatClock(state.left)}`;
  }
  function makePoolButton(libraryId, sourceId, pool) {
    const stats = poolStats(pool);
    const state = timerState(libraryId, sourceId, pool.index);
    const button = document.createElement("button");
    button.type = "button";
    button.className = "choice" + (stats.answered ? " selected" : "");
    button.dataset.library = libraryId;
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
      session.sourceId = sourceId;
      session.poolIndex = pool.index;
      session.drill = null;
      session.reviewing = false;
      openPool(pool.index);
    });
    return button;
  }

  function renderLibraries() {
    session = null;
    show("libraries");
    el.sourceList.replaceChildren();
    for (const library of LIBRARIES) {
      const count = questions.filter((item) => item.library === library.id).length;
      const button = document.createElement("button");
      button.type = "button";
      button.className = "choice";
      const label = document.createElement("span");
      label.textContent = library.title;
      const sub = document.createElement("span");
      sub.className = "sub";
      sub.textContent = count ? `${count} питань` : "немає питань";
      button.append(label, sub);
      button.addEventListener("click", () => openLibrary(library.id));
      el.sourceList.append(button);
    }
  }

  function openLibrary(libraryId) {
    session = {
      libraryId,
      sourceId: null,
      poolIndex: 0,
      index: 0,
      reviewing: false,
      drill: null,
    };
    show("pools");
    const library = libraryById(libraryId);
    el.title.textContent = library.title;
    const sources = sourcesFor(libraryId);
    el.poolsLead.textContent = sources.length
      ? "Пули по 30 питань у порядку файлу. Таймер блоку стартує з першого відкриття пулу і не зупиняється в меню."
      : "У цій бібліотеці ще немає питань.";
    paintPools();
  }

  function paintPools() {
    if (!session) return;
    const sources = sourcesFor(session.libraryId);
    el.poolList.replaceChildren();
    for (const category of CATEGORIES) {
      const grouped = sources.filter((source) => source.block === category.id);
      if (!grouped.length) continue;
      const section = document.createElement("section");
      section.className = "block";
      const heading = document.createElement("h2");
      heading.textContent = `${category.title} · ${category.minutes} хв`;
      section.append(heading);
      for (const source of grouped) {
        const title = document.createElement("h3");
        const count = sourceQuestions(session.libraryId, source.id).length;
        title.textContent = `${source.title} · ${count}`;
        const stack = document.createElement("div");
        stack.className = "stack";
        for (const pool of buildPools(session.libraryId, source.id)) {
          stack.append(makePoolButton(session.libraryId, source.id, pool));
        }
        section.append(title, stack);
      }
      el.poolList.append(section);
    }
  }

  function openPool(poolIndex) {
    session.poolIndex = poolIndex;
    session.reviewing = false;
    session.drill = null;
    session.index = 0;
    ensureTimer(session.libraryId, session.sourceId, poolIndex);
    if (timerState(session.libraryId, session.sourceId, poolIndex).left <= 0) {
      closeTimer(session.libraryId, session.sourceId, poolIndex);
      showSummary(true);
      return;
    }
    if (timerState(session.libraryId, session.sourceId, poolIndex).closed) {
      showSummary(false);
      return;
    }
    const pool = currentPool();
    const firstOpen = pool.items.findIndex((question) => !savedAnswer(question.id));
    session.index = firstOpen === -1 ? 0 : firstOpen;
    show("quiz");
    renderQuestion();
  }

  function wrongItems(pool) {
    return pool.items.filter((question) => {
      const saved = savedAnswer(question.id);
      return Boolean(saved) && saved.ok === false;
    });
  }
  function markedItems(pool, mark) {
    return pool.items.filter((question) => savedMark(question.id) === mark);
  }
  function openDrill(kind, mark) {
    const pool = currentPool();
    const items = kind === "wrong" ? wrongItems(pool) : markedItems(pool, mark);
    if (!items.length) return;
    const store = loadStore();
    for (const question of items) delete store.answers[question.id];
    saveStore(store);
    session.drill = { kind, mark: mark || null, items };
    session.reviewing = false;
    session.index = 0;
    show("quiz");
    renderQuestion();
  }

  function renderQuestion() {
    const pool = currentPool();
    const items = activeItems();
    const question = items[session.index];
    let saved = savedAnswer(question.id);
    if (saved && !saved.ok && !saved.unscored && question.interaction === "expression" && grade(question, saved.picked)) {
      const store = loadStore();
      store.answers[question.id].ok = true;
      saveStore(store);
      saved = store.answers[question.id];
    }
    const closed = !session.drill && timerState(session.libraryId, session.sourceId, session.poolIndex).closed;
    const locked = Boolean(saved) || closed;
    const source = sourceById(session.libraryId, session.sourceId);
    let prefix = "";
    if (session.drill?.kind === "wrong") prefix = "Помилки · ";
    else if (session.drill?.kind === "mark") {
      const mark = MARKS.find((item) => item.id === session.drill.mark);
      prefix = `${mark ? mark.label : "Позначка"} · `;
    }
    el.title.textContent = `${prefix}${source.title} · пул ${pool.index + 1}`;
    el.quizMeta.textContent = `Питання ${session.index + 1} з ${items.length} · № ${question.number}`;
    paintMarks(question.id);
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

    const picked = new Set(locked && saved ? saved.picked.map(String) : []);
    const keyed = hasKey(question);
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
          caption.textContent = option.text || `Фігура ${option.id}`;
          button.append(image, caption);
        } else {
          button.textContent = option.text || option.id;
        }
        if (locked) {
          const correct = new Set((question.correct || []).map(String));
          const chosen = picked.has(String(option.id));
          if (keyed && saved) {
            button.classList.toggle("good", correct.has(String(option.id)));
            button.classList.toggle("bad", chosen && !correct.has(String(option.id)));
          } else if (chosen) button.classList.add("selected");
          button.disabled = true;
        } else if (picked.has(String(option.id))) {
          button.classList.add("selected");
        }
        button.addEventListener("click", () => toggleOption(question, String(option.id)));
        el.choices.append(button);
      }
    } else {
      el.answerHint.textContent = question.interaction === "expression"
        ? "Впишіть дії між числами. Результат після знака рівності можна не повторювати."
        : "Впишіть число. Кома і крапка рівнозначні.";
      el.answerInput.value = locked && saved ? (saved.picked[0] || "") : "";
      el.answerInput.disabled = locked;
    }

    const issues = question.issues || [];
    const notes = [];
    if (issues.includes("key-missing")) notes.push("Ключ у цьому експорті не збережено.");
    if (question.confidence === "low" || issues.includes("buttons-illegible")) {
      notes.push("Ключ неповний: частину кнопок на скані не вдалося прочитати.");
    }
    if (issues.includes("explanation-cropped")) notes.push("Пояснення на скані обрізане.");
    el.note.hidden = notes.length === 0;
    el.note.textContent = notes.join(" ");

    paintVerdict(question, saved);
    if (closed && !saved && keyed) {
      el.verdict.hidden = false;
      el.verdict.className = "verdict bad";
      el.verdict.textContent = `Без відповіді. Відповідь: ${keyText(question)}`;
      const text = (question.explanation || "").trim();
      el.explanation.hidden = !text;
      el.explanation.textContent = text;
    }
    el.confirm.hidden = locked;
    el.confirm.disabled = true;
    el.prev.disabled = session.index === 0;
    el.next.textContent = session.index === items.length - 1 ? "До результату" : "Далі";
    el.finish.textContent = session.drill ? "До результату" : "Завершити пул";
    if (!locked && typed) syncTypedConfirm();
    if (!locked && !typed) syncChoiceConfirm(question);
  }

  function paintMarks(questionId) {
    const current = savedMark(questionId);
    for (const button of el.markButtons) {
      button.setAttribute("aria-pressed", button.dataset.mark === current ? "true" : "false");
    }
  }
  function setMark(questionId, markId) {
    const store = loadStore();
    if (store.marks[questionId] === markId) delete store.marks[questionId];
    else store.marks[questionId] = markId;
    saveStore(store);
    paintMarks(questionId);
  }

  function selectionFromDom() {
    return [...el.choices.querySelectorAll(".option.selected")].map((node) => node.dataset.id);
  }
  function neededCount(question) {
    if (isTyped(question)) return 1;
    const keys = (question.correct || []).length;
    if (question.interaction === "pair") return 2;
    if (keys > 1) return keys;
    return 1;
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
    if (saved.unscored || !hasKey(question)) {
      el.verdict.hidden = false;
      el.verdict.className = "verdict";
      el.verdict.textContent = "Відповідь збережено. Ключ для цього питання відсутній, тож воно не входить у рахунок.";
      el.explanation.hidden = true;
      return;
    }
    el.verdict.hidden = false;
    el.verdict.className = "verdict " + (saved.ok ? "good" : "bad");
    const key = keyText(question);
    el.verdict.textContent = saved.ok ? "Правильно" : `Неправильно. Відповідь: ${key}`;
    const text = (question.explanation || "").trim();
    el.explanation.hidden = !text;
    el.explanation.textContent = text;
  }

  function commitAnswer() {
    const items = activeItems();
    const question = items[session.index];
    if (savedAnswer(question.id) || (!session.drill && timerState(session.libraryId, session.sourceId, session.poolIndex).closed)) return;
    const picked = isTyped(question) ? [el.answerInput.value.trim()] : selectionFromDom();
    if (!picked.length || (isTyped(question) && !picked[0])) return;
    if (!isTyped(question) && picked.length !== neededCount(question)) return;
    const store = loadStore();
    store.answers[question.id] = hasKey(question)
      ? { ok: grade(question, picked), picked }
      : { ok: null, picked, unscored: true };
    saveStore(store);
    renderQuestion();
  }

  function showSummary(expired) {
    session.drill = null;
    session.reviewing = false;
    const pool = currentPool();
    const stats = poolStats(pool);
    const source = sourceById(session.libraryId, session.sourceId);
    const left = Math.max(0, timerState(session.libraryId, session.sourceId, pool.index).left);
    const used = limitMs(source) - left;
    show("summary");
    el.title.textContent = `${source.title} · пул ${pool.index + 1}`;
    el.timer.textContent = formatClock(left);
    el.timer.classList.toggle("low", left <= 0);
    const timeNote = expired ? "Час вичерпано. " : `Витрачено ${formatClock(used)}. `;
    const missing = stats.unscored ? ` Без ключа ${stats.unscored}.` : "";
    el.summaryText.textContent = `${timeNote}Правильно ${stats.correct} з ${stats.total}. Без відповіді ${stats.total - stats.answered}.${missing}`;
    const hasNext = pool.index + 1 < buildPools(session.libraryId, session.sourceId).length;
    el.toBreak.hidden = !hasNext;
    const wrong = wrongItems(pool);
    el.wrong.hidden = wrong.length === 0;
    el.wrong.textContent = `Пройти питання з неправильною відповіддю (${wrong.length})`;
    el.markRetries.replaceChildren();
    for (const mark of MARKS) {
      const count = markedItems(pool, mark.id).length;
      if (!count) continue;
      const button = document.createElement("button");
      button.type = "button";
      button.className = "secondary";
      button.textContent = `Повторити позначені: ${mark.label} (${count})`;
      button.addEventListener("click", () => openDrill("mark", mark.id));
      el.markRetries.append(button);
    }
  }

  function goNext() {
    const items = activeItems();
    if (session.index < items.length - 1) {
      session.index += 1;
      renderQuestion();
      return;
    }
    if (session.drill) {
      showSummary(false);
      return;
    }
    closeTimer(session.libraryId, session.sourceId, session.poolIndex);
    showSummary(timerState(session.libraryId, session.sourceId, session.poolIndex).left <= 0);
  }

  function refreshClocks(root) {
    for (const button of root.querySelectorAll("button[data-pool]")) {
      const clock = button.querySelector(".clock");
      if (!clock) continue;
      paintClock(clock, timerState(button.dataset.library, button.dataset.source, Number(button.dataset.pool)));
    }
  }

  function tick() {
    if (!el.home.hidden) return;
    if (!session || (el.quiz.hidden && el.summary.hidden && el.pools.hidden && el.break.hidden)) return;
    if (!el.pools.hidden) {
      refreshClocks(el.poolList);
      return;
    }
    if (session.drill || !session.sourceId) return;
    const state = timerState(session.libraryId, session.sourceId, session.poolIndex);
    const left = Math.max(0, state.left);
    if (!el.quiz.hidden || !el.summary.hidden) {
      el.timer.textContent = formatClock(left);
      el.timer.classList.toggle("low", left < 60 * 1000);
    }
    if (!el.quiz.hidden && !session.drill && !state.closed && state.left <= 0) {
      closeTimer(session.libraryId, session.sourceId, session.poolIndex);
      showSummary(true);
    }
  }

  el.homeBtn.addEventListener("click", () => {
    if (!el.pools.hidden || !session?.libraryId) renderLibraries();
    else openLibrary(session.libraryId);
  });
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
    if (session.drill) {
      showSummary(false);
      return;
    }
    closeTimer(session.libraryId, session.sourceId, session.poolIndex);
    showSummary(timerState(session.libraryId, session.sourceId, session.poolIndex).left <= 0);
  });
  el.review.addEventListener("click", () => {
    session.reviewing = true;
    session.drill = null;
    session.index = 0;
    show("quiz");
    renderQuestion();
  });
  el.wrong.addEventListener("click", () => openDrill("wrong", null));
  for (const button of el.markButtons) {
    button.addEventListener("click", () => {
      const question = activeItems()[session.index];
      if (!question) return;
      setMark(question.id, button.dataset.mark);
    });
  }
  el.toBreak.addEventListener("click", () => {
    const next = buildPools(session.libraryId, session.sourceId)[session.poolIndex + 1];
    show("break");
    el.timer.hidden = true;
    el.title.textContent = "Перерва";
    el.breakText.textContent = `Наступний пул ${session.poolIndex + 2}: питання № ${next.from}–${next.to}. Таймер почнеться, коли відкриєте його.`;
  });
  el.nextPool.addEventListener("click", () => openPool(session.poolIndex + 1));
  el.breakPools.addEventListener("click", () => openLibrary(session.libraryId));
  el.summaryPools.addEventListener("click", () => openLibrary(session.libraryId));
  el.retry.addEventListener("click", () => {
    const pool = currentPool();
    const store = loadStore();
    for (const question of pool.items) delete store.answers[question.id];
    saveStore(store);
    clearTimer(session.libraryId, session.sourceId, session.poolIndex);
    openPool(pool.index);
  });

  if (el.version) el.version.textContent = `Версія ${window.APP_VERSION || "1.1.0"}`;

  tickId = setInterval(tick, 250);

  function sameSecret(given, expected) {
    const left = String(given);
    const right = String(expected);
    let diff = left.length ^ right.length;
    const length = Math.max(left.length, right.length);
    for (let i = 0; i < length; i += 1) {
      diff |= (left.charCodeAt(i) || 0) ^ (right.charCodeAt(i) || 0);
    }
    return diff === 0;
  }

  function startApp() {
    fetch("data/questions.json")
      .then((response) => {
        if (!response.ok) throw new Error(String(response.status));
        return response.json();
      })
      .then((data) => {
        questions = data;
        renderLibraries();
      })
      .catch(() => {
        show("libraries");
        el.loadError.hidden = false;
        el.loadError.textContent = "Не вдалося завантажити банк питань.";
      });
  }

  function sha256(value) {
    const bytes = new TextEncoder().encode(String(value));
    return crypto.subtle.digest("SHA-256", bytes).then((digest) => (
      [...new Uint8Array(digest)].map((byte) => byte.toString(16).padStart(2, "0")).join("")
    ));
  }

  function showLogin() {
    show("login");
    el.title.textContent = "Тренажер";
    el.logout.hidden = true;
    el.loginForm.addEventListener("submit", (event) => {
      event.preventDefault();
      Promise.all([sha256(el.loginUser.value), sha256(el.loginPass.value)]).then(([userHash, passwordHash]) => {
        const auth = window.APP_AUTH || {};
        const ok = sameSecret(userHash, auth.userHash || "") && sameSecret(passwordHash, auth.passwordHash || "");
        el.loginError.hidden = ok;
        if (!ok) return;
        sessionStorage.setItem(AUTH_KEY, "1");
        el.loginPass.value = "";
        el.logout.hidden = false;
        startApp();
      });
    });
  }

  el.logout.addEventListener("click", () => {
    sessionStorage.removeItem(AUTH_KEY);
    session = null;
    el.logout.hidden = true;
    el.loginPass.value = "";
    el.loginError.hidden = true;
    el.title.textContent = "Тренажер";
    show("login");
  });

  if (!window.APP_AUTH) {
    el.logout.hidden = true;
    startApp();
  } else if (sessionStorage.getItem(AUTH_KEY) === "1") {
    el.logout.hidden = false;
    startApp();
  } else {
    showLogin();
  }
})();
