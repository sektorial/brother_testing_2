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
  const LS_KEY = "bt2-progress-v1";
  const KEYS_KEY = "bt2-keys-v1";
  const AUTH_KEY = "bt2-auth-v1";
  const AUTH_USER = "bt2-user-v1";

  const el = {
    homeBtn: document.getElementById("btn-home"),
    title: document.getElementById("title"),
    timer: document.getElementById("timer"),
    version: document.getElementById("app-version"),
    login: document.getElementById("screen-login"),
    home: document.getElementById("screen-home"),
    pools: document.getElementById("screen-pools"),
    archive: document.getElementById("screen-archive"),
    break: document.getElementById("screen-break"),
    quiz: document.getElementById("screen-quiz"),
    summary: document.getElementById("screen-summary"),
    sourceList: document.getElementById("source-list"),
    loadError: document.getElementById("load-error"),
    poolsLead: document.getElementById("pools-lead"),
    poolList: document.getElementById("pool-list"),
    archiveLead: document.getElementById("archive-lead"),
    archiveError: document.getElementById("archive-error"),
    themeList: document.getElementById("theme-list"),
    themeName: document.getElementById("theme-name"),
    makeTheme: document.getElementById("btn-make-theme"),
    themeAdd: document.getElementById("theme-add"),
    archiveList: document.getElementById("archive-list"),
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
    keyEditor: document.getElementById("key-editor"),
    keyToggle: document.getElementById("btn-key"),
    keyPanel: document.getElementById("key-panel"),
    keyHint: document.getElementById("key-hint"),
    keyOptions: document.getElementById("key-options"),
    keySave: document.getElementById("btn-key-save"),
    keyReset: document.getElementById("btn-key-reset"),
    confirm: document.getElementById("btn-confirm"),
    prev: document.getElementById("btn-prev"),
    next: document.getElementById("btn-next"),
    toArchive: document.getElementById("btn-archive"),
    finish: document.getElementById("btn-finish"),
    summaryText: document.getElementById("summary-text"),
    review: document.getElementById("btn-review"),
    wrong: document.getElementById("btn-wrong"),
    toBreak: document.getElementById("btn-break"),
    retry: document.getElementById("btn-retry"),
    summaryPools: document.getElementById("btn-summary-pools"),
    logout: document.getElementById("btn-logout"),
    loginForm: document.getElementById("login-form"),
    loginUser: document.getElementById("login-user"),
    loginPass: document.getElementById("login-pass"),
    loginError: document.getElementById("login-error"),
  };

  /** @type {any[]} */
  let questions = [];
  /** @type {{ libraryId: string | null, sourceId: string | null, themeId: string | null, poolIndex: number, index: number, reviewing: boolean, drill: { kind: string, items: any[] } | null } | null} */
  let session = null;
  let tickId = 0;

  function loadStore() {
    try {
      const raw = JSON.parse(localStorage.getItem(LS_KEY) || "{}");
      const themes = Array.isArray(raw.themes) ? raw.themes : [];
      return {
        answers: raw.answers || {},
        timers: raw.timers || {},
        marks: raw.marks || {},
        archive: Array.isArray(raw.archive) ? raw.archive.filter((id) => typeof id === "string") : [],
        themes: themes
          .filter((theme) => theme && typeof theme.id === "string")
          .map((theme) => ({
            id: theme.id,
            title: String(theme.title || "Тема"),
            questionIds: Array.isArray(theme.questionIds)
              ? theme.questionIds.filter((id) => typeof id === "string")
              : [],
          })),
      };
    } catch {
      return { answers: {}, timers: {}, marks: {}, archive: [], themes: [] };
    }
  }
  function saveStore(store) {
    localStorage.setItem(LS_KEY, JSON.stringify(store));
  }
  function loadKeys() {
    try {
      const raw = JSON.parse(localStorage.getItem(KEYS_KEY) || "{}");
      return raw && typeof raw === "object" ? raw : {};
    } catch {
      return {};
    }
  }
  function saveKeys(keys) {
    localStorage.setItem(KEYS_KEY, JSON.stringify(keys));
  }

  function libraryById(id) {
    return LIBRARIES.find((library) => library.id === id);
  }
  function libraryOrdinal(libraryId) {
    const index = LIBRARIES.findIndex((library) => library.id === libraryId);
    return index < 0 ? 0 : index + 1;
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
  function questionById(id) {
    return questions.find((question) => question.id === id) || null;
  }
  function questionCode(question) {
    if (!question) return "";
    const index = sourceQuestions(question.library, question.source).findIndex((item) => item.id === question.id);
    if (index < 0) return "";
    const pool = Math.floor(index / POOL_SIZE) + 1;
    const position = (index % POOL_SIZE) + 1;
    return `${libraryOrdinal(question.library)}.${pool}.${position}`;
  }
  function poolRangeLabel(libraryId, pool) {
    return `${libraryOrdinal(libraryId)}.${pool.index + 1}.1–${pool.items.length}`;
  }
  function themePoolLabel(pool) {
    return `${pool.index + 1}.1–${pool.items.length}`;
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
  function themeById(id) {
    return loadStore().themes.find((theme) => theme.id === id) || null;
  }
  function themeQuestions(theme) {
    if (!theme) return [];
    return theme.questionIds.map(questionById).filter(Boolean);
  }
  function themePools(theme) {
    const list = themeQuestions(theme);
    const pools = [];
    for (let start = 0; start < list.length; start += POOL_SIZE) {
      const items = list.slice(start, start + POOL_SIZE);
      if (!items.length) continue;
      pools.push({ index: pools.length, items });
    }
    return pools;
  }
  function sessionPools() {
    if (session?.themeId) {
      const theme = themeById(session.themeId);
      return theme ? themePools(theme) : [];
    }
    if (!session?.sourceId) return [];
    return buildPools(session.libraryId, session.sourceId);
  }
  function describePool(pool) {
    if (session?.themeId) return themePoolLabel(pool);
    return poolRangeLabel(session.libraryId, pool);
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
  function activeTimerKey() {
    if (session?.themeId) return `archive:${session.themeId}:${session.poolIndex}`;
    return timerStorageKey(session.libraryId, session.sourceId, session.poolIndex);
  }
  function currentPool() {
    if (!session) return null;
    if (session.themeId) {
      const theme = themeById(session.themeId);
      return theme ? themePools(theme)[session.poolIndex] || null : null;
    }
    if (!session.sourceId) return null;
    return buildPools(session.libraryId, session.sourceId)[session.poolIndex] || null;
  }
  function activeItems() {
    if (session?.drill) return session.drill.items;
    return currentPool()?.items || [];
  }
  function limitMs(source) {
    return (categoryById(source.block)?.minutes || 20) * 60 * 1000;
  }
  function poolLimitMs(items) {
    const blocks = new Set(items.map((question) => question.block).filter(Boolean));
    if (blocks.size === 1) return (categoryById([...blocks][0])?.minutes || 20) * 60 * 1000;
    return 20 * 60 * 1000;
  }
  function activeLimitMs() {
    if (session?.themeId) {
      const pool = currentPool();
      return pool ? poolLimitMs(pool.items) : 20 * 60 * 1000;
    }
    const source = sourceById(session.libraryId, session.sourceId);
    return source ? limitMs(source) : 20 * 60 * 1000;
  }

  function show(name) {
    el.login.hidden = name !== "login";
    el.home.hidden = name !== "libraries";
    el.pools.hidden = name !== "pools";
    el.archive.hidden = name !== "archive";
    el.break.hidden = name !== "break";
    el.quiz.hidden = name !== "quiz";
    el.summary.hidden = name !== "summary";
    el.homeBtn.hidden = name === "libraries" || name === "login";
    el.homeBtn.textContent = name === "pools" || name === "archive" ? "← Бібліотеки" : "← Меню";
    const timed = (name === "quiz" || name === "summary") && !(session && session.drill);
    el.timer.hidden = !timed;
    if (name === "libraries") el.title.textContent = "Тренажер";
    if (name === "archive") el.title.textContent = "Архів питань";
  }

  function formatClock(ms) {
    const total = Math.max(0, Math.ceil(ms / 1000));
    const minutes = Math.floor(total / 60);
    const seconds = total % 60;
    return `${String(minutes).padStart(2, "0")}:${String(seconds).padStart(2, "0")}`;
  }
  function timerStateByKey(key, limit) {
    const timer = loadStore().timers[key];
    if (!timer) return { started: false, left: limit, closed: false };
    if (timer.closed) return { started: true, left: timer.left, closed: true };
    return { started: true, left: timer.deadline - Date.now(), closed: false };
  }
  function ensureTimerKey(key, limit) {
    const store = loadStore();
    if (!store.timers[key]) {
      store.timers[key] = { deadline: Date.now() + limit };
      saveStore(store);
    }
  }
  function closeTimerKey(key) {
    const store = loadStore();
    const timer = store.timers[key];
    if (!timer || timer.closed) return;
    store.timers[key] = { closed: true, left: Math.max(0, timer.deadline - Date.now()) };
    saveStore(store);
  }
  function clearTimerKey(key) {
    const store = loadStore();
    delete store.timers[key];
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
    const parts = (question.correct || []).map((id) => {
      const option = (question.options || []).find((item) => String(item.id) === String(id));
      if (option?.text) return option.text;
      if (option?.image) return `Фігура ${id}`;
      return String(id);
    });
    if (question.interaction === "single" && parts.length > 1) return parts.join(" або ");
    return parts.join(", ");
  }
  function hasKey(question) {
    return (question.correct || []).length > 0 && !(question.issues || []).includes("key-missing");
  }
  function grade(question, picked) {
    const correct = (question.correct || []).map(String);
    const answers = picked || [];
    if (isTyped(question)) {
      return correct.some((item) =>
        question.interaction === "expression" ? exprEqual(answers[0] || "", item) : numsEqual(answers[0] || "", item)
      );
    }
    if (question.interaction === "single") return answers.length === 1 && correct.includes(String(answers[0]));
    const chosen = new Set(answers.map(String));
    if (chosen.size !== correct.length) return false;
    return correct.every((item) => chosen.has(item));
  }
  function judged(question, saved) {
    if (!saved) return null;
    if (!hasKey(question)) return { picked: saved.picked || [], unscored: true, ok: null };
    return { picked: saved.picked || [], unscored: false, ok: grade(question, saved.picked || []) };
  }
  function savedAnswer(id) {
    return loadStore().answers[id] || null;
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
      const saved = judged(question, savedAnswer(question.id));
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
  function makeTimerPoolButton(pool, label, timerKey, limit, onClick) {
    const stats = poolStats(pool);
    const button = document.createElement("button");
    button.type = "button";
    button.className = "choice" + (stats.answered ? " selected" : "");
    button.dataset.timerKey = timerKey;
    button.dataset.limit = String(limit);
    const text = document.createElement("span");
    text.textContent = label;
    const sub = document.createElement("span");
    sub.className = "sub";
    const score = document.createElement("span");
    score.className = "score";
    score.textContent = `${stats.correct}/${stats.total}`;
    const clock = document.createElement("span");
    clock.className = "clock";
    sub.append(score, clock);
    paintClock(clock, timerStateByKey(timerKey, limit));
    button.append(text, sub);
    button.addEventListener("click", onClick);
    return button;
  }
  function makePoolButton(libraryId, sourceId, pool) {
    const source = sourceById(libraryId, sourceId);
    return makeTimerPoolButton(
      pool,
      poolRangeLabel(libraryId, pool),
      timerStorageKey(libraryId, sourceId, pool.index),
      source ? limitMs(source) : 0,
      () => {
        session.sourceId = sourceId;
        session.themeId = null;
        session.poolIndex = pool.index;
        session.drill = null;
        session.reviewing = false;
        openPool(pool.index);
      }
    );
  }
  function makeThemePoolButton(theme, pool) {
    const key = `archive:${theme.id}:${pool.index}`;
    return makeTimerPoolButton(pool, themePoolLabel(pool), key, poolLimitMs(pool.items), () => openTheme(theme.id, pool.index));
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
      label.textContent = `${libraryOrdinal(library.id)} · ${library.title}`;
      const sub = document.createElement("span");
      sub.className = "sub";
      sub.textContent = count ? `${count} питань` : "немає питань";
      button.append(label, sub);
      button.addEventListener("click", () => openLibrary(library.id));
      el.sourceList.append(button);
    }
    const store = loadStore();
    const archiveButton = document.createElement("button");
    archiveButton.type = "button";
    archiveButton.className = "choice";
    const archiveLabel = document.createElement("span");
    archiveLabel.textContent = "Архів питань";
    const archiveSub = document.createElement("span");
    archiveSub.className = "sub";
    archiveSub.textContent = store.themes.length
      ? `${store.archive.length} питань · тем ${store.themes.length}`
      : `${store.archive.length} питань`;
    archiveButton.append(archiveLabel, archiveSub);
    archiveButton.addEventListener("click", renderArchive);
    el.sourceList.append(archiveButton);
  }

  function openLibrary(libraryId) {
    session = {
      libraryId,
      sourceId: null,
      themeId: null,
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

  function snippet(text) {
    const clean = String(text || "").replace(/\s+/g, " ").trim();
    if (clean.length <= 120) return clean;
    return `${clean.slice(0, 117)}…`;
  }
  function showArchiveError(message) {
    el.archiveError.hidden = false;
    el.archiveError.textContent = message;
  }
  function selectedArchiveIds() {
    const checked = new Set(
      [...el.archiveList.querySelectorAll('input[type="checkbox"]:checked')].map((node) => node.value)
    );
    return loadStore().archive.filter((id) => checked.has(id) && questionById(id));
  }
  function archiveRow(question, themeNames) {
    const row = document.createElement("div");
    row.className = "archive-item";
    const label = document.createElement("label");
    const box = document.createElement("input");
    box.type = "checkbox";
    box.value = question.id;
    const copy = document.createElement("span");
    copy.className = "archive-copy";
    const title = document.createElement("span");
    title.textContent = questionCode(question);
    const detail = document.createElement("span");
    detail.className = "sub";
    const source = sourceById(question.library, question.source);
    const library = libraryById(question.library);
    const bits = [[library?.title, source?.title].filter(Boolean).join(" · "), snippet(question.prompt)];
    if (themeNames.length) bits.push(themeNames.join(", "));
    detail.textContent = bits.filter(Boolean).join(" · ");
    copy.append(title, detail);
    label.append(box, copy);
    const remove = document.createElement("button");
    remove.type = "button";
    remove.className = "ghost";
    remove.textContent = "Прибрати";
    remove.addEventListener("click", () => {
      const store = loadStore();
      store.archive = store.archive.filter((id) => id !== question.id);
      saveStore(store);
      renderArchive();
    });
    row.append(label, remove);
    return row;
  }
  function deleteTheme(themeId) {
    const store = loadStore();
    const theme = store.themes.find((item) => item.id === themeId);
    const pools = theme ? Math.ceil((theme.questionIds || []).length / POOL_SIZE) : 0;
    store.themes = store.themes.filter((item) => item.id !== themeId);
    for (let index = 0; index < pools; index += 1) delete store.timers[`archive:${themeId}:${index}`];
    saveStore(store);
    renderArchive();
  }
  function addToTheme(themeId, ids) {
    const store = loadStore();
    const theme = store.themes.find((item) => item.id === themeId);
    if (!theme) return;
    const have = new Set(theme.questionIds);
    for (const id of ids) {
      if (have.has(id)) continue;
      theme.questionIds.push(id);
      have.add(id);
    }
    saveStore(store);
  }
  function renderArchive() {
    session = null;
    show("archive");
    const store = loadStore();
    el.archiveLead.textContent = store.archive.length
      ? "Оберіть питання і зберіть тему. Тема ділиться на пули по 30 і тренується як звичайний пул."
      : "Архів порожній. На екрані питання натисніть «В архів».";
    el.archiveError.hidden = true;
    el.themeList.replaceChildren();
    for (const theme of store.themes) {
      const section = document.createElement("section");
      section.className = "block";
      const head = document.createElement("div");
      head.className = "theme-head";
      const heading = document.createElement("h2");
      heading.textContent = theme.title;
      const remove = document.createElement("button");
      remove.type = "button";
      remove.className = "ghost";
      remove.textContent = "Видалити тему";
      remove.addEventListener("click", () => deleteTheme(theme.id));
      head.append(heading, remove);
      section.append(head);
      const pools = themePools(theme);
      if (!pools.length) {
        const empty = document.createElement("p");
        empty.className = "note";
        empty.textContent = "У темі немає доступних питань.";
        section.append(empty);
      } else {
        const stack = document.createElement("div");
        stack.className = "stack";
        for (const pool of pools) stack.append(makeThemePoolButton(theme, pool));
        section.append(stack);
      }
      el.themeList.append(section);
    }
    el.themeAdd.replaceChildren();
    for (const theme of store.themes) {
      const button = document.createElement("button");
      button.type = "button";
      button.className = "secondary";
      button.textContent = `Додати обрані до «${theme.title}»`;
      button.addEventListener("click", () => {
        const ids = selectedArchiveIds();
        if (!ids.length) {
          showArchiveError("Оберіть питання з архіву.");
          return;
        }
        addToTheme(theme.id, ids);
        renderArchive();
      });
      el.themeAdd.append(button);
    }
    el.archiveList.replaceChildren();
    const known = store.archive.map(questionById).filter(Boolean);
    if (!known.length) {
      const empty = document.createElement("p");
      empty.className = "note";
      empty.textContent = "Поки що тут немає питань.";
      el.archiveList.append(empty);
      return;
    }
    const themeNames = new Map();
    for (const theme of store.themes) {
      for (const id of theme.questionIds) {
        const names = themeNames.get(id) || [];
        names.push(theme.title);
        themeNames.set(id, names);
      }
    }
    for (const question of known) el.archiveList.append(archiveRow(question, themeNames.get(question.id) || []));
  }

  function openPool(poolIndex) {
    session.poolIndex = poolIndex;
    session.reviewing = false;
    session.drill = null;
    session.index = 0;
    const key = activeTimerKey();
    const limit = activeLimitMs();
    ensureTimerKey(key, limit);
    const state = timerStateByKey(key, limit);
    if (state.left <= 0) {
      closeTimerKey(key);
      showSummary(true);
      return;
    }
    if (state.closed) {
      showSummary(false);
      return;
    }
    const pool = currentPool();
    const firstOpen = pool.items.findIndex((question) => !savedAnswer(question.id));
    session.index = firstOpen === -1 ? 0 : firstOpen;
    show("quiz");
    renderQuestion();
  }
  function openTheme(themeId, poolIndex) {
    session = {
      libraryId: null,
      sourceId: null,
      themeId,
      poolIndex: 0,
      index: 0,
      reviewing: false,
      drill: null,
    };
    openPool(poolIndex);
  }

  function wrongItems(pool) {
    return pool.items.filter((question) => {
      const saved = judged(question, savedAnswer(question.id));
      return Boolean(saved) && saved.ok === false;
    });
  }
  function openDrill() {
    const pool = currentPool();
    const items = wrongItems(pool);
    if (!items.length) return;
    const store = loadStore();
    for (const question of items) delete store.answers[question.id];
    saveStore(store);
    session.drill = { kind: "wrong", items };
    session.reviewing = false;
    session.index = 0;
    show("quiz");
    renderQuestion();
  }

  function renderQuestion() {
    const pool = currentPool();
    const items = activeItems();
    const question = items[session.index];
    if (!pool || !question) return;
    const stored = savedAnswer(question.id);
    const saved = judged(question, stored);
    const closed = !session.drill && timerStateByKey(activeTimerKey(), activeLimitMs()).closed;
    const locked = Boolean(stored) || closed;
    const source = session.themeId ? null : sourceById(session.libraryId, session.sourceId);
    const theme = session.themeId ? themeById(session.themeId) : null;
    const prefix = session.drill?.kind === "wrong" ? "Помилки · " : "";
    const heading = theme ? theme.title : source?.title || "";
    el.title.textContent = `${prefix}${heading} · пул ${pool.index + 1}`;
    el.quizMeta.textContent = `Питання ${session.index + 1} з ${items.length} · ${questionCode(question)}`;
    paintArchiveButton(question.id);
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
    if (closed && !stored && keyed) {
      el.verdict.hidden = false;
      el.verdict.className = "verdict bad";
      el.verdict.textContent = `Без відповіді. Відповідь: ${keyText(question)}`;
      const text = (question.explanation || "").trim();
      el.explanation.hidden = !text;
      el.explanation.textContent = text;
    }
    el.keyEditor.hidden = !canEditKeys();
    el.keyPanel.hidden = true;
    el.confirm.hidden = locked;
    el.confirm.disabled = true;
    el.prev.disabled = session.index === 0;
    el.next.textContent = session.index === items.length - 1 ? "До результату" : "Далі";
    el.finish.textContent = session.drill ? "До результату" : "Завершити пул";
    if (!locked && typed) syncTypedConfirm();
    if (!locked && !typed) syncChoiceConfirm(question);
  }

  function paintArchiveButton(questionId) {
    const archived = loadStore().archive.includes(questionId);
    el.toArchive.setAttribute("aria-pressed", archived ? "true" : "false");
    el.toArchive.textContent = archived ? "В архіві" : "В архів";
  }
  function toggleArchive(questionId) {
    const store = loadStore();
    const index = store.archive.indexOf(questionId);
    if (index === -1) store.archive.push(questionId);
    else store.archive.splice(index, 1);
    saveStore(store);
  }

  function optionLabel(question, id) {
    const option = (question.options || []).find((item) => String(item.id) === String(id));
    if (option?.text) return option.text;
    if (option?.image) return `Фігура ${id}`;
    return String(id);
  }
  function typedKeyRow(value) {
    const row = document.createElement("div");
    row.className = "key-row";
    const input = document.createElement("input");
    input.type = "text";
    input.dataset.key = "1";
    input.value = value;
    const remove = document.createElement("button");
    remove.type = "button";
    remove.className = "ghost";
    remove.textContent = "Прибрати";
    remove.addEventListener("click", () => {
      row.remove();
      if (!el.keyOptions.querySelector("input[data-key]")) {
        const add = el.keyOptions.querySelector("button");
        el.keyOptions.insertBefore(typedKeyRow(""), add);
      }
    });
    row.append(input, remove);
    return row;
  }
  function paintKeyPanel() {
    const question = activeItems()[session?.index];
    if (!question) return;
    el.keyOptions.replaceChildren();
    const typed = isTyped(question);
    el.keyHint.textContent = typed
      ? "Кожен рядок — окремий прийнятний варіант."
      : question.interaction === "single"
        ? "Позначте варіанти, які зараховувати. Достатньо одного."
        : "Позначте всі варіанти, які треба обрати разом.";
    if (typed) {
      const values = (question.correct || []).map(String);
      if (!values.length) values.push("");
      for (const value of values) el.keyOptions.append(typedKeyRow(value));
      const add = document.createElement("button");
      add.type = "button";
      add.className = "secondary";
      add.textContent = "Додати варіант";
      add.addEventListener("click", () => el.keyOptions.insertBefore(typedKeyRow(""), add));
      el.keyOptions.append(add);
      return;
    }
    const accepted = new Set((question.correct || []).map(String));
    for (const option of question.options || []) {
      const label = document.createElement("label");
      label.className = "key-row";
      const box = document.createElement("input");
      box.type = "checkbox";
      box.value = String(option.id);
      box.checked = accepted.has(String(option.id));
      const text = document.createElement("span");
      text.textContent = optionLabel(question, option.id);
      label.append(box, text);
      el.keyOptions.append(label);
    }
  }
  function readKeyDraft() {
    const question = activeItems()[session.index];
    if (!question) return [];
    if (isTyped(question)) {
      return [...el.keyOptions.querySelectorAll("input[data-key]")].map((input) => input.value.trim()).filter(Boolean);
    }
    return [...el.keyOptions.querySelectorAll('input[type="checkbox"]:checked')].map((input) => input.value);
  }
  function canEditKeys() {
    return sessionStorage.getItem(AUTH_USER) === "ivoln";
  }

  function selectionFromDom() {
    return [...el.choices.querySelectorAll(".option.selected")].map((node) => node.dataset.id);
  }
  function neededCount(question) {
    if (isTyped(question) || question.interaction === "single") return 1;
    const keys = (question.correct || []).length;
    if (question.interaction === "pair") return keys || 2;
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
    if (savedAnswer(question.id) || (!session.drill && timerStateByKey(activeTimerKey(), activeLimitMs()).closed)) return;
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

  function sessionTitle() {
    if (session?.themeId) return themeById(session.themeId)?.title || "Архів";
    return sourceById(session.libraryId, session.sourceId)?.title || "";
  }
  function showSummary(expired) {
    session.drill = null;
    session.reviewing = false;
    const pool = currentPool();
    const stats = poolStats(pool);
    const limit = activeLimitMs();
    const left = Math.max(0, timerStateByKey(activeTimerKey(), limit).left);
    const used = limit - left;
    show("summary");
    el.title.textContent = `${sessionTitle()} · пул ${pool.index + 1}`;
    el.timer.textContent = formatClock(left);
    el.timer.classList.toggle("low", left <= 0);
    const timeNote = expired ? "Час вичерпано. " : `Витрачено ${formatClock(used)}. `;
    const missing = stats.unscored ? ` Без ключа ${stats.unscored}.` : "";
    el.summaryText.textContent = `${timeNote}Правильно ${stats.correct} з ${stats.total}. Без відповіді ${stats.total - stats.answered}.${missing}`;
    const hasNext = pool.index + 1 < sessionPools().length;
    el.toBreak.hidden = !hasNext;
    const wrong = wrongItems(pool);
    el.wrong.hidden = wrong.length === 0;
    el.wrong.textContent = `Пройти питання з неправильною відповіддю (${wrong.length})`;
    el.summaryPools.textContent = session.themeId ? "До архіву" : "До списку пулів";
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
    closeTimerKey(activeTimerKey());
    showSummary(timerStateByKey(activeTimerKey(), activeLimitMs()).left <= 0);
  }
  function backToList() {
    if (session?.themeId) renderArchive();
    else if (session?.libraryId) openLibrary(session.libraryId);
    else renderLibraries();
  }

  function refreshClocks(root) {
    for (const button of root.querySelectorAll("button[data-timer-key]")) {
      const clock = button.querySelector(".clock");
      if (!clock) continue;
      paintClock(clock, timerStateByKey(button.dataset.timerKey, Number(button.dataset.limit)));
    }
  }

  function tick() {
    if (!el.home.hidden) return;
    if (!el.archive.hidden) {
      refreshClocks(el.themeList);
      return;
    }
    if (!session || (el.quiz.hidden && el.summary.hidden && el.pools.hidden && el.break.hidden)) return;
    if (!el.pools.hidden) {
      refreshClocks(el.poolList);
      return;
    }
    if (session.drill || (!session.sourceId && !session.themeId)) return;
    const limit = activeLimitMs();
    const state = timerStateByKey(activeTimerKey(), limit);
    const left = Math.max(0, state.left);
    if (!el.quiz.hidden || !el.summary.hidden) {
      el.timer.textContent = formatClock(left);
      el.timer.classList.toggle("low", left < 60 * 1000);
    }
    if (!el.quiz.hidden && !session.drill && !state.closed && state.left <= 0) {
      closeTimerKey(activeTimerKey());
      showSummary(true);
    }
  }

  el.homeBtn.addEventListener("click", () => {
    if (!el.archive.hidden) {
      renderLibraries();
      return;
    }
    if (session?.themeId) {
      renderArchive();
      return;
    }
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
  el.toArchive.addEventListener("click", () => {
    const question = activeItems()[session?.index];
    if (!question) return;
    toggleArchive(question.id);
    paintArchiveButton(question.id);
  });
  el.finish.addEventListener("click", () => {
    if (session.drill) {
      showSummary(false);
      return;
    }
    closeTimerKey(activeTimerKey());
    showSummary(timerStateByKey(activeTimerKey(), activeLimitMs()).left <= 0);
  });
  el.review.addEventListener("click", () => {
    session.reviewing = true;
    session.drill = null;
    session.index = 0;
    show("quiz");
    renderQuestion();
  });
  el.wrong.addEventListener("click", openDrill);
  el.toBreak.addEventListener("click", () => {
    const next = sessionPools()[session.poolIndex + 1];
    show("break");
    el.timer.hidden = true;
    el.title.textContent = "Перерва";
    el.breakPools.textContent = session.themeId ? "До архіву" : "До списку пулів";
    el.breakText.textContent = `Наступний пул ${describePool(next)}. Таймер почнеться, коли відкриєте його.`;
  });
  el.nextPool.addEventListener("click", () => openPool(session.poolIndex + 1));
  el.breakPools.addEventListener("click", backToList);
  el.summaryPools.addEventListener("click", backToList);
  el.retry.addEventListener("click", () => {
    const pool = currentPool();
    const store = loadStore();
    for (const question of pool.items) delete store.answers[question.id];
    saveStore(store);
    if (session.themeId) clearTimerKey(`archive:${session.themeId}:${pool.index}`);
    else clearTimer(session.libraryId, session.sourceId, pool.index);
    openPool(pool.index);
  });
  el.makeTheme.addEventListener("click", () => {
    const title = el.themeName.value.trim();
    const ids = selectedArchiveIds();
    if (!title) {
      showArchiveError("Вкажіть назву теми.");
      return;
    }
    if (!ids.length) {
      showArchiveError("Оберіть питання з архіву.");
      return;
    }
    const store = loadStore();
    store.themes.push({ id: `theme-${Date.now()}`, title, questionIds: ids });
    saveStore(store);
    el.themeName.value = "";
    renderArchive();
  });
  el.themeName.addEventListener("keydown", (event) => {
    if (event.key === "Enter") {
      event.preventDefault();
      el.makeTheme.click();
    }
  });
  el.keyToggle.addEventListener("click", () => {
    if (!canEditKeys()) return;
    el.keyPanel.hidden = !el.keyPanel.hidden;
    if (!el.keyPanel.hidden) paintKeyPanel();
  });
  el.keySave.addEventListener("click", () => {
    const question = activeItems()[session?.index];
    if (!question || !canEditKeys()) return;
    const accept = readKeyDraft();
    if (!accept.length) {
      el.keyHint.textContent = "Потрібен хоча б один варіант.";
      return;
    }
    const keys = loadKeys();
    keys[question.id] = { accept };
    saveKeys(keys);
    applyKeyOverrides();
    el.keyPanel.hidden = true;
    renderQuestion();
  });
  el.keyReset.addEventListener("click", () => {
    const question = activeItems()[session?.index];
    if (!question || !canEditKeys()) return;
    const keys = loadKeys();
    delete keys[question.id];
    saveKeys(keys);
    applyKeyOverrides();
    el.keyPanel.hidden = true;
    renderQuestion();
  });

  if (el.version) el.version.textContent = `Версія ${window.APP_VERSION || "1.2.0"}`;

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

  function rememberBank() {
    for (const question of questions) {
      question.bankCorrect = (question.correct || []).slice();
      question.bankIssues = (question.issues || []).slice();
    }
  }
  function applyKeyOverrides() {
    const overrides = loadKeys();
    for (const question of questions) {
      const over = overrides[question.id];
      if (!over || !Array.isArray(over.accept)) {
        question.correct = (question.bankCorrect || []).slice();
        question.issues = (question.bankIssues || []).slice();
        continue;
      }
      question.correct = over.accept.map(String);
      question.issues = (question.bankIssues || []).filter((issue) => issue !== "key-missing");
    }
  }

  function startApp() {
    fetch("data/questions.json")
      .then((response) => {
        if (!response.ok) throw new Error(String(response.status));
        return response.json();
      })
      .then((data) => {
        questions = data;
        rememberBank();
        applyKeyOverrides();
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
        sessionStorage.setItem(AUTH_USER, auth.name || "");
        el.loginPass.value = "";
        el.logout.hidden = false;
        startApp();
      });
    });
  }

  el.logout.addEventListener("click", () => {
    sessionStorage.removeItem(AUTH_KEY);
    sessionStorage.removeItem(AUTH_USER);
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
    if (!sessionStorage.getItem(AUTH_USER) && window.APP_AUTH.name) {
      sessionStorage.setItem(AUTH_USER, window.APP_AUTH.name);
    }
    el.logout.hidden = false;
    startApp();
  } else {
    showLogin();
  }
})();
