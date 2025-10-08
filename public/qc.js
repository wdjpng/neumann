(() => {
  const palette = ['#ef4444', '#f97316', '#fbbf24', '#22c55e', '#0ea5e9', '#6366f1', '#a855f7', '#ec4899', '#14b8a6', '#f59e0b'];

  const state = {
    base: null,
    letters: [],
    letterSummaries: new Map(),
    letter: null,
    pages: [],
    chunks: [],
    chunkCache: new Map(),
    pageReasonCache: new Map(),
    htmlCache: { full: null, translateDe: null, translateEn: null },
    finished: false,
    pdfUrl: null,
    currentPage: 0,
    currentChunk: 0,
    view: 'chunks',
    editingChunk: false,
    editingFull: false,
    editingTranslate: { de: false, en: false },
    translateFocus: 'de',
    drawMode: false,
    drawRects: [],
    drawStart: null,
    drawActiveEl: null,
    tasksTimer: null,
    tasksActive: false,
    allowShortcuts: true,
    lastPositions: {},
    taskStatusMap: new Map(),
  };

  const el = {};
  let statusTimer = null;
  let hintTimer = null;

  document.addEventListener('DOMContentLoaded', init);

  function init() {
    assignElements();
    attachHandlers();
    loadOverview();
  }

  function assignElements() {
    el.baseSelect = qs('#base-select');
    el.letterSelect = qs('#letter-select');
    el.statusBadge = qs('#status-badge');
    el.tasksButton = qs('#btn-tasks');
    el.tasksPanel = qs('#tasks-panel');
    el.tasksList = qs('#tasks-list');
    el.tasksCount = qs('#tasks-count');
    el.hintBanner = qs('#hint-banner');
    el.reasoningPanel = qs('#reasoning-panel');

    el.btnBatchRebuild = qs('#btn-batch-rebuild');
    el.btnTranslateCurrent = qs('#btn-translate-current');
    el.btnTranslateAll = qs('#btn-translate-all');

    el.btnViewBoxes = qs('#btn-view-boxes');
    el.btnViewChunks = qs('#btn-view-chunks');
    el.btnViewFull = qs('#btn-view-full');
    el.btnViewTranslate = qs('#btn-view-translate');

    // boxes view
    el.viewBoxes = qs('#view-boxes');
    el.pageImage = qs('#page-image');
    el.pageStage = qs('#page-stage');
    el.boxesLayer = qs('#boxes-layer');
    el.draftLayer = qs('#draft-layer');
    el.pagesList = qs('#pages-list');
    el.btnDrawToggle = qs('#btn-draw-toggle');
    el.btnBoxesApply = qs('#btn-boxes-apply');
    el.btnBoxesApplyRebuild = qs('#btn-boxes-apply-rebuild');
    el.btnBoxesRegenerate = qs('#btn-boxes-regenerate');

    // chunk view
    el.viewChunks = qs('#view-chunks');
    el.chunkImage = qs('#chunk-image');
    el.chunkEditor = qs('#chunk-editor');
    el.chunkPreview = qs('#chunk-preview');
    el.btnPrev = qs('#btn-prev');
    el.btnNext = qs('#btn-next');
    el.btnApprove = qs('#btn-approve');
    el.btnRetry = qs('#btn-retry');
    el.btnFeedback = qs('#btn-feedback');
    el.btnEdit = qs('#btn-edit');
    el.btnRender = qs('#btn-render');
    el.chunkMeta = qs('#chunk-meta');

    // full view
    el.viewFull = qs('#view-full');
    el.pdfFrame = qs('#pdf-frame');
    el.fullEditor = qs('#full-editor');
    el.fullPreview = qs('#full-preview');
    el.btnFullEdit = qs('#btn-full-edit');
    el.btnFullRender = qs('#btn-full-render');
    el.btnFullReload = qs('#btn-full-reload');
    el.btnFullReloadFeedback = qs('#btn-full-reload-feedback');
    el.btnFullFinished = qs('#btn-full-finished');
    el.btnFullDeep = qs('#btn-full-deep');

    // translate view
    el.viewTranslate = qs('#view-translate');
    el.btnTranslateRetry = qs('#btn-translate-retry');
    el.btnTranslateFeedback = qs('#btn-translate-feedback');
    el.btnTranslateEditDe = qs('#btn-translate-edit-de');
    el.btnTranslateRenderDe = qs('#btn-translate-render-de');
    el.btnTranslateEditEn = qs('#btn-translate-edit-en');
    el.btnTranslateRenderEn = qs('#btn-translate-render-en');
    el.translateEditorDe = qs('#translate-editor-de');
    el.translatePreviewDe = qs('#translate-preview-de');
    el.translateEditorEn = qs('#translate-editor-en');
    el.translatePreviewEn = qs('#translate-preview-en');

    updateDrawButtonLabel();
  }

  function attachHandlers() {
    el.baseSelect.addEventListener('change', () => {
      rememberPosition();
      loadOverview(el.baseSelect.value);
    });

    el.letterSelect.addEventListener('change', () => {
      rememberPosition();
      loadLetter(el.letterSelect.value, { restore: true });
    });

    el.tasksButton.addEventListener('click', () => {
      el.tasksPanel.classList.toggle('visible');
      if (el.tasksPanel.classList.contains('visible')) {
        fetchTasks();
      }
    });

    document.addEventListener('click', (evt) => {
      if (!el.tasksPanel.contains(evt.target) && evt.target !== el.tasksButton) {
        el.tasksPanel.classList.remove('visible');
      }
    });

    el.btnBatchRebuild.addEventListener('click', () => enqueueBatchRebuild());
    el.btnTranslateCurrent.addEventListener('click', () => translateCurrent());
    el.btnTranslateAll.addEventListener('click', () => enqueueTranslateAll());

    el.btnViewBoxes.addEventListener('click', () => setView('boxes'));
    el.btnViewChunks.addEventListener('click', () => setView('chunks'));
    el.btnViewFull.addEventListener('click', () => setView('full'));
    el.btnViewTranslate.addEventListener('click', () => setView('translate'));

    el.btnDrawToggle.addEventListener('click', toggleDrawMode);
    el.btnBoxesApply.addEventListener('click', () => applyDrawnBoxes(false));
    el.btnBoxesApplyRebuild.addEventListener('click', () => applyDrawnBoxes(true));
    el.btnBoxesRegenerate.addEventListener('click', () => regenerateBoxes());

    el.btnPrev.addEventListener('click', () => navigatePrev());
    el.btnNext.addEventListener('click', () => navigateNext());
    el.btnApprove.addEventListener('click', () => toggleChunkReviewed());
    el.btnRetry.addEventListener('click', () => retryCurrentChunk());
    el.btnFeedback.addEventListener('click', () => feedbackChunk());
    el.btnEdit.addEventListener('click', () => toggleChunkEdit(true));
    el.btnRender.addEventListener('click', () => exitChunkEdit());

    el.btnFullEdit.addEventListener('click', () => toggleFullEdit(true));
    el.btnFullRender.addEventListener('click', () => exitFullEdit());
    el.fullEditor.addEventListener('blur', () => saveFullHtml());
    el.btnFullReload.addEventListener('click', () => rebuildUnified());
    el.btnFullReloadFeedback.addEventListener('click', () => rebuildUnified(true));
    el.btnFullFinished.addEventListener('click', () => toggleFinished());
    el.btnFullDeep.addEventListener('click', () => deepReload());

    el.btnTranslateRetry.addEventListener('click', () => translateCurrent());
    el.btnTranslateFeedback.addEventListener('click', () => translateWithFeedback());
    el.btnTranslateEditDe.addEventListener('click', () => toggleTranslateEdit('de', true));
    el.btnTranslateRenderDe.addEventListener('click', () => exitTranslateEdit('de'));
    el.btnTranslateEditEn.addEventListener('click', () => toggleTranslateEdit('en', true));
    el.btnTranslateRenderEn.addEventListener('click', () => exitTranslateEdit('en'));
    el.translateEditorDe.addEventListener('blur', () => saveTranslate('de'));
    el.translateEditorEn.addEventListener('blur', () => saveTranslate('en'));

    [el.chunkEditor, el.fullEditor, el.translateEditorDe, el.translateEditorEn].forEach((textarea) => {
      textarea.addEventListener('focus', () => { state.allowShortcuts = false; });
      textarea.addEventListener('blur', () => { state.allowShortcuts = true; });
    });

    el.chunkEditor.addEventListener('blur', () => saveChunkHtml());

    el.translatePreviewDe.addEventListener('mouseenter', () => { state.translateFocus = 'de'; });
    el.translatePreviewEn.addEventListener('mouseenter', () => { state.translateFocus = 'en'; });
    el.translateEditorDe.addEventListener('focus', () => { state.translateFocus = 'de'; });
    el.translateEditorEn.addEventListener('focus', () => { state.translateFocus = 'en'; });

    el.pagesList.addEventListener('click', (evt) => {
      const li = evt.target.closest('li[data-index]');
      if (!li) return;
      const idx = Number(li.dataset.index);
      selectPage(idx);
      setView('boxes');
    });

    el.boxesLayer.addEventListener('click', (evt) => {
      const box = evt.target.closest('.qc-box');
      if (!box) return;
      const pageIdx = Number(box.dataset.page);
      const chunkIdx = Number(box.dataset.chunk);
      const globalIdx = state.chunks.findIndex((c) => c.page_index === pageIdx && c.chunk_index === chunkIdx);
      if (globalIdx >= 0) {
        state.currentChunk = globalIdx;
        state.currentPage = pageIdx;
        setView('chunks');
        renderChunkView();
      }
    });

    if (el.pageStage) {
      el.pageStage.addEventListener('mousedown', handlePageMouseDown);
    }

    window.addEventListener('resize', () => {
      if (state.view === 'boxes') {
        renderBoxesOverlay();
      }
    });

    document.addEventListener('keydown', handleKeyDown);
  }

  function qs(sel) {
    return document.querySelector(sel);
  }

  function withBase(path) {
    if (!state.base) return path;
    return path.includes('?')
      ? `${path}&base=${encodeURIComponent(state.base)}`
      : `${path}?base=${encodeURIComponent(state.base)}`;
  }

  async function fetchJSON(url, options) {
    const res = await fetch(url, options);
    if (!res.ok) {
      const text = await res.text();
      throw new Error(text || res.statusText || 'Request failed');
    }
    return res.json();
  }

  async function fetchText(url) {
    const res = await fetch(url);
    if (!res.ok) return '';
    return res.text();
  }

  function setStatus(message, type = 'info', persist = false) {
    if (!el.statusBadge) return;
    el.statusBadge.textContent = message || 'Idle';
    el.statusBadge.dataset.state = type;
    if (statusTimer) {
      clearTimeout(statusTimer);
      statusTimer = null;
    }
    if (!persist && message) {
      statusTimer = setTimeout(() => {
        el.statusBadge.textContent = 'Idle';
        el.statusBadge.dataset.state = '';
      }, 3500);
    }
  }

  function showHint(message) {
    if (!el.hintBanner) return;
    if (hintTimer) {
      clearTimeout(hintTimer);
    }
    el.hintBanner.textContent = message;
    el.hintBanner.classList.add('visible');
    hintTimer = setTimeout(() => {
      el.hintBanner.classList.remove('visible');
    }, 3200);
  }

  async function loadOverview(preferredBase = null) {
    const baseParam = preferredBase ? `?base=${encodeURIComponent(preferredBase)}` : '';
    try {
      const data = await fetchJSON(`/api/qc/overview${baseParam}`);
      populateBaseSelect(data.bases, data.base);
      state.base = data.base;
      state.letters = data.letters || [];
      state.letterSummaries = new Map(state.letters.map((l) => [l.id, l]));
      populateLetterSelect();
      const targetLetter = determineInitialLetter();
      if (targetLetter) {
        loadLetter(targetLetter, { restore: true });
      }
    } catch (err) {
      console.error(err);
      setStatus(`Failed to load overview: ${err.message}`, 'error', true);
    }
  }

  function determineInitialLetter() {
    const requested = el.letterSelect.value;
    if (requested && state.letterSummaries.has(requested)) {
      return requested;
    }
    if (state.letter && state.letterSummaries.has(state.letter)) {
      return state.letter;
    }
    return state.letters.length ? state.letters[0].id : null;
  }

  function populateBaseSelect(bases, active) {
    if (!el.baseSelect) return;
    el.baseSelect.innerHTML = '';
    (bases || []).forEach((name) => {
      const option = document.createElement('option');
      option.value = name;
      option.textContent = name;
      if (name === active) option.selected = true;
      el.baseSelect.appendChild(option);
    });
  }

  function populateLetterSelect() {
    if (!el.letterSelect) return;
    const current = state.letter;
    el.letterSelect.innerHTML = '';
    state.letters.forEach((letter) => {
      const option = document.createElement('option');
      option.value = letter.id;
      const flags = [];
      if (letter.finished) flags.push('✅');
      if (letter.needs_rebuild) flags.push('🧱');
      if (letter.needs_translate) flags.push('🌐');
      option.textContent = `${flags.join(' ')} ${letter.id}`.trim();
      if (letter.id === current) option.selected = true;
      el.letterSelect.appendChild(option);
    });
  }

  async function loadLetter(letterId, { restore = false } = {}) {
    if (!letterId) return;
    try {
      setStatus('Loading letter…', 'info', true);
      state.letter = letterId;
      if (el.letterSelect.value !== letterId) {
        el.letterSelect.value = letterId;
      }
      setDrawMode(false, { silent: true });
      state.chunkCache = new Map();
      state.pageReasonCache = new Map();
      state.htmlCache = { full: null, translateDe: null, translateEn: null };

      const data = await fetchJSON(withBase(`/api/qc/letter/${encodeURIComponent(letterId)}/context`));
      state.pages = data.pages || [];
      state.chunks = (data.chunks || []).sort((a, b) => (a.page_index - b.page_index) || (a.chunk_index - b.chunk_index));
      state.finished = !!data.finished;
      state.pdfUrl = data.pdf_url || null;
      updateLetterSummary(letterId, data);

      const saved = restore ? state.lastPositions[letterId] : null;
      if (saved) {
        state.view = saved.view || 'chunks';
        state.currentPage = clampPage(saved.pageIndex ?? 0);
        state.currentChunk = clampChunk(saved.chunkIndex ?? 0);
      } else {
        state.view = state.chunks.length ? 'chunks' : 'boxes';
        state.currentChunk = 0;
        state.currentPage = state.chunks.length ? state.chunks[0].page_index : (state.pages[0]?.index ?? 0);
      }

      reflectViewButtons();
      renderLetterMeta();
      renderCurrentView();
      setStatus('Letter loaded', 'success');
    } catch (err) {
      console.error(err);
      setStatus(`Failed to load letter: ${err.message}`, 'error', true);
    }
  }

  function updateLetterSummary(letterId, context) {
    const summary = state.letterSummaries.get(letterId) || { id: letterId };
    if (Object.prototype.hasOwnProperty.call(context, 'finished')) {
      summary.finished = !!context.finished;
    }
    if (Object.prototype.hasOwnProperty.call(context, 'pdf_url') && context.pdf_url) {
      summary.pdf_url = context.pdf_url;
    }
    state.letterSummaries.set(letterId, summary);
    const listIdx = state.letters.findIndex((entry) => entry.id === letterId);
    if (listIdx >= 0) {
      state.letters[listIdx] = { ...state.letters[listIdx], ...summary };
    }
    populateLetterSelect();
  }

  function updateDrawButtonLabel() {
    if (!el.btnDrawToggle) return;
    el.btnDrawToggle.textContent = state.drawMode ? 'Cancel Drawing (Esc)' : 'Draw Mode';
  }

  function renderLetterMeta() {
    if (!el.btnFullFinished) return;
    el.btnFullFinished.textContent = state.finished ? 'Unmark Reviewed (f)' : 'Mark Reviewed (f)';
  }

  function rememberPosition() {
    if (!state.letter) return;
    state.lastPositions[state.letter] = {
      view: state.view,
      pageIndex: state.currentPage,
      chunkIndex: state.currentChunk,
    };
  }

  function setView(view) {
    if (view === state.view) {
      renderCurrentView();
      return;
    }
    rememberPosition();
    if (state.view === 'boxes' && view !== 'boxes' && state.drawMode) {
      setDrawMode(false, { silent: true });
    }
    state.view = view;
    reflectViewButtons();
    renderCurrentView();
  }

  function reflectViewButtons() {
    const mapping = {
      boxes: el.btnViewBoxes,
      chunks: el.btnViewChunks,
      full: el.btnViewFull,
      translate: el.btnViewTranslate,
    };
    Object.entries(mapping).forEach(([key, btn]) => {
      if (!btn) return;
      if (key === state.view) {
        btn.classList.add('primary');
      } else {
        btn.classList.remove('primary');
      }
    });
  }

  function renderCurrentView() {
    document.querySelectorAll('.qc-view').forEach((v) => v.classList.remove('active'));
    switch (state.view) {
      case 'boxes':
        el.viewBoxes?.classList.add('active');
        renderBoxesView();
        break;
      case 'full':
        el.viewFull?.classList.add('active');
        renderFullView();
        break;
      case 'translate':
        el.viewTranslate?.classList.add('active');
        renderTranslateView();
        break;
      case 'chunks':
      default:
        el.viewChunks?.classList.add('active');
        renderChunkView();
        break;
    }
  }

  function clampPage(idx) {
    if (!state.pages.length) return 0;
    return Math.min(Math.max(idx, 0), state.pages.length - 1);
  }

  function clampChunk(idx) {
    if (!state.chunks.length) return 0;
    return Math.min(Math.max(idx, 0), state.chunks.length - 1);
  }

  function renderBoxesView() {
    const page = state.pages.find((p) => p.index === state.currentPage) || state.pages[0];
    if (!page) {
      el.pageImage.src = '';
      el.boxesLayer.innerHTML = '';
      updateReasoning('');
      return;
    }
    state.currentPage = page.index;
    el.pageImage.src = page.image_url || '';
    el.pageImage.onload = () => renderBoxesOverlay();
    renderBoxesOverlay();
    renderPagesList();
    loadPageReasoning(page.index);
  }

  function renderBoxesOverlay() {
    const page = state.pages.find((p) => p.index === state.currentPage);
    if (!page || !el.pageStage) return;
    if (state.drawMode) {
      el.boxesLayer.innerHTML = '';
      return;
    }
    const { width: stageWidth, height: stageHeight } = el.pageStage.getBoundingClientRect();
    if (!stageWidth || !stageHeight) return;
    const scaleX = stageWidth / (page.size?.width || stageWidth);
    const scaleY = stageHeight / (page.size?.height || stageHeight);

    el.boxesLayer.innerHTML = '';
    const coordByIndex = new Map((page.coords || []).map((c) => [c.chunk_index, c]));

    state.chunks.forEach((chunk, globalIdx) => {
      if (chunk.page_index !== page.index) return;
      const coord = coordByIndex.get(chunk.chunk_index);
      if (!coord) return;
      const box = document.createElement('div');
      box.className = 'qc-box';
      const color = palette[globalIdx % palette.length];
      box.style.borderColor = color;
      box.style.backgroundColor = rgbaFromHex(color, 0.16);
      box.style.left = `${coord.x1 * scaleX}px`;
      box.style.top = `${coord.y1 * scaleY}px`;
      box.style.width = `${Math.max(coord.x2 - coord.x1, 1) * scaleX}px`;
      box.style.height = `${Math.max(coord.y2 - coord.y1, 1) * scaleY}px`;
      box.textContent = `${chunk.chunk_index + 1}`;
      box.dataset.page = String(chunk.page_index);
      box.dataset.chunk = String(chunk.chunk_index);
      if (state.chunks[state.currentChunk]?.page_index === chunk.page_index &&
          state.chunks[state.currentChunk]?.chunk_index === chunk.chunk_index) {
        box.classList.add('selected');
      }
      el.boxesLayer.appendChild(box);
    });

    if (state.drawMode) {
      el.draftLayer.classList.add('drawing');
    } else {
      el.draftLayer.classList.remove('drawing');
    }
  }

  function renderPagesList() {
    if (!el.pagesList) return;
    el.pagesList.innerHTML = '';
    state.pages.forEach((page) => {
      const li = document.createElement('li');
      li.dataset.index = String(page.index);
      li.innerHTML = `<strong>Page</strong><span>${page.index + 1}</span><span>${page.chunk_count || 0} chunks</span>`;
      if (page.index === state.currentPage) {
        li.classList.add('active');
      }
      el.pagesList.appendChild(li);
    });
  }

  async function loadPageReasoning(pageIndex) {
    const cacheKey = `${state.letter}:${pageIndex}`;
    if (state.pageReasonCache.has(cacheKey)) {
      updateReasoning(state.pageReasonCache.get(cacheKey));
      return;
    }
    try {
      const data = await fetchJSON(withBase(`/api/qc/letter/${encodeURIComponent(state.letter)}/page/${pageIndex}/reasoning`));
      const text = data.reasoning || '';
      state.pageReasonCache.set(cacheKey, text);
      updateReasoning(text);
    } catch (err) {
      updateReasoning('');
    }
  }

  function handlePageMouseDown(evt) {
    if (state.view !== 'boxes') return;
    if (evt.button !== 0) return;
    if (state.drawMode) return;
    if (evt.target.closest('.qc-box')) return;
    evt.preventDefault();
    evt.stopPropagation();
    setDrawMode(true);
    if (el.draftLayer) {
      onDraftMouseDown(evt);
    }
  }

  function setDrawMode(enabled, { silent = false } = {}) {
    if (enabled) {
      if (state.drawMode) return;
      state.drawMode = true;
      state.drawRects = [];
      state.drawStart = null;
      state.drawActiveEl = null;
      if (el.draftLayer) {
        el.draftLayer.innerHTML = '';
      }
      if (el.boxesLayer) {
        el.boxesLayer.style.pointerEvents = 'none';
      }
      enableDraftEvents();
      updateDrawButtonLabel();
      renderBoxesOverlay();
      if (!silent) {
        setStatus('Draw mode enabled', 'info');
      }
    } else {
      if (!state.drawMode) return;
      state.drawMode = false;
      state.drawRects = [];
      state.drawStart = null;
      state.drawActiveEl = null;
      if (el.draftLayer) {
        el.draftLayer.innerHTML = '';
      }
      disableDraftEvents();
      if (el.boxesLayer) {
        el.boxesLayer.style.pointerEvents = 'auto';
      }
      updateDrawButtonLabel();
      renderBoxesOverlay();
      if (!silent) {
        setStatus('Draw mode disabled', 'info');
      }
    }
  }

  function toggleDrawMode() {
    setDrawMode(!state.drawMode);
  }

  function enableDraftEvents() {
    if (!el.draftLayer) return;
    el.draftLayer.classList.add('drawing');
    el.draftLayer.addEventListener('mousedown', onDraftMouseDown);
  }

  function disableDraftEvents() {
    if (!el.draftLayer) return;
    el.draftLayer.classList.remove('drawing');
    el.draftLayer.removeEventListener('mousedown', onDraftMouseDown);
    window.removeEventListener('mousemove', onDraftMouseMove);
    window.removeEventListener('mouseup', onDraftMouseUp);
  }

  function onDraftMouseDown(evt) {
    if (!state.drawMode || evt.button !== 0) return;
    const rect = el.pageStage.getBoundingClientRect();
    const x = evt.clientX - rect.left;
    const y = evt.clientY - rect.top;
    state.drawStart = { x, y };
    const elRect = document.createElement('div');
    elRect.className = 'draw-rect';
    el.draftLayer.appendChild(elRect);
    state.drawActiveEl = elRect;
    window.addEventListener('mousemove', onDraftMouseMove);
    window.addEventListener('mouseup', onDraftMouseUp);
  }

  function onDraftMouseMove(evt) {
    if (!state.drawStart || !state.drawActiveEl) return;
    const rect = el.pageStage.getBoundingClientRect();
    const currentX = evt.clientX - rect.left;
    const currentY = evt.clientY - rect.top;
    const left = Math.min(state.drawStart.x, currentX);
    const top = Math.min(state.drawStart.y, currentY);
    const width = Math.abs(currentX - state.drawStart.x);
    const height = Math.abs(currentY - state.drawStart.y);
    state.drawActiveEl.style.left = `${left}px`;
    state.drawActiveEl.style.top = `${top}px`;
    state.drawActiveEl.style.width = `${width}px`;
    state.drawActiveEl.style.height = `${height}px`;
  }

  function onDraftMouseUp() {
    window.removeEventListener('mousemove', onDraftMouseMove);
    window.removeEventListener('mouseup', onDraftMouseUp);
    if (!state.drawStart || !state.drawActiveEl) return;
    const rect = el.pageStage.getBoundingClientRect();
    const width = parseFloat(state.drawActiveEl.style.width) || 0;
    const height = parseFloat(state.drawActiveEl.style.height) || 0;
    if (width < 8 || height < 8) {
      state.drawActiveEl.remove();
      state.drawActiveEl = null;
      state.drawStart = null;
      return;
    }
    const left = parseFloat(state.drawActiveEl.style.left) || 0;
    const top = parseFloat(state.drawActiveEl.style.top) || 0;
    const page = state.pages.find((p) => p.index === state.currentPage);
    const scaleX = rect.width / (page?.size?.width || rect.width);
    const scaleY = rect.height / (page?.size?.height || rect.height);
    const x1 = Math.round(left / scaleX);
    const y1 = Math.round(top / scaleY);
    const x2 = Math.round((left + width) / scaleX);
    const y2 = Math.round((top + height) / scaleY);
    state.drawRects.push({ x1, y1, x2, y2 });
    state.drawActiveEl = null;
    state.drawStart = null;
    setStatus(`${state.drawRects.length} box(es) drawn`, 'info');
  }

  async function applyDrawnBoxes(rebuild) {
    if (!state.drawMode || !state.drawRects.length) {
      setStatus('No boxes drawn', 'warning');
      return;
    }
    const sorted = [...state.drawRects].sort((a, b) => {
      if (a.y1 !== b.y1) return a.y1 - b.y1;
      return a.x1 - b.x1;
    });
    const payload = sorted.map(({ x1, y1, x2, y2 }) => ({ x1, y1, x2, y2 }));
    const body = {
      coords: payload,
      rebuild,
    };
    if (rebuild) {
      const feedback = window.prompt('Optional feedback for rebuilding unified HTML:', '');
      if (typeof feedback === 'string' && feedback.trim()) {
        body.feedback = feedback.trim();
      }
    }
    try {
      setStatus('Applying boxes…', 'info', true);
      await fetchJSON(withBase(`/api/qc/letter/${encodeURIComponent(state.letter)}/pages/${state.currentPage}/update`), {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(body),
      });
      setStatus('Boxes update queued', 'success');
      setDrawMode(false, { silent: true });
      kickTasksPoll();
      await reloadLetterContext();
    } catch (err) {
      setStatus(`Failed to update boxes: ${err.message}`, 'error', true);
    }
  }

  async function regenerateBoxes() {
    try {
      setStatus('Regenerating boxes…', 'info', true);
      await fetchJSON(withBase(`/api/qc/letter/${encodeURIComponent(state.letter)}/pages/${state.currentPage}/regenerate`), {
        method: 'POST',
      });
      setStatus('Regeneration queued', 'success');
      kickTasksPoll();
      await reloadLetterContext();
    } catch (err) {
      setStatus(`Failed to regenerate: ${err.message}`, 'error', true);
    }
  }

  async function reloadLetterContext() {
    if (!state.letter) return;
    const saved = {
      view: state.view,
      pageIndex: state.currentPage,
      chunkIndex: state.currentChunk,
    };
    state.lastPositions[state.letter] = saved;
    await loadLetter(state.letter, { restore: true });
  }

  function rgbaFromHex(hex, alpha) {
    if (!hex || hex[0] !== '#') return `rgba(37, 99, 235, ${alpha})`;
    const value = hex.slice(1);
    const bigint = parseInt(value.length === 3 ? value.replace(/(.)/g, '$1$1') : value, 16);
    const r = (bigint >> 16) & 255;
    const g = (bigint >> 8) & 255;
    const b = bigint & 255;
    return `rgba(${r}, ${g}, ${b}, ${alpha})`;
  }

  async function renderChunkView() {
    if (!state.chunks.length) {
      el.chunkImage.src = '';
      el.chunkPreview.srcdoc = '';
      updateReasoning('');
      return;
    }
    state.currentChunk = clampChunk(state.currentChunk);
    const chunk = state.chunks[state.currentChunk];
    state.currentPage = chunk.page_index;
    el.chunkImage.src = chunk.image_url || '';
    updateChunkMeta(chunk);
    const detail = await getChunkDetail(chunk.page_index, chunk.chunk_index);
    renderChunkContent(detail);
    updateReasoning(detail.reasoning || '');
    renderBoxesOverlay();
    renderPagesList();
    updateApproveButtonUI();
  }

  function updateChunkMeta(chunk) {
    if (!el.chunkMeta) return;
    const detail = state.chunkCache.get(`${chunk.page_index}_${chunk.chunk_index}`);
    const approved = detail?.approved;
    const parts = [`Page ${chunk.page_index + 1}`, `Chunk ${chunk.chunk_index + 1}`];
    if (approved) parts.push('✅ Approved');
    el.chunkMeta.textContent = parts.join(' · ');
  }

  function currentChunkApproved() {
    const chunk = state.chunks[state.currentChunk];
    if (!chunk) return false;
    // Prefer cache detail if available, fall back to list entry
    const key = `${chunk.page_index}_${chunk.chunk_index}`;
    const detail = state.chunkCache.get(key);
    return typeof detail?.approved === 'boolean' ? !!detail.approved : !!chunk.approved;
  }

  function setCurrentChunkApproved(flag) {
    const chunk = state.chunks[state.currentChunk];
    if (!chunk) return;
    const key = `${chunk.page_index}_${chunk.chunk_index}`;
    const cached = state.chunkCache.get(key) || {};
    state.chunkCache.set(key, { ...cached, approved: !!flag });
    // Also mirror onto list item for skip logic
    state.chunks[state.currentChunk] = { ...chunk, approved: !!flag };
  }

  function updateApproveButtonUI() {
    if (!el.btnApprove) return;
    const approved = currentChunkApproved();
    el.btnApprove.textContent = approved ? 'Unapprove' : 'Approve';
    el.btnApprove.title = approved ? 'Mark chunk as not reviewed (t)' : 'Mark chunk as reviewed (t, Ctrl+Enter)';
  }

  async function getChunkDetail(pageIdx, chunkIdx) {
    const key = `${pageIdx}_${chunkIdx}`;
    if (state.chunkCache.has(key)) return state.chunkCache.get(key);
    const detail = await fetchJSON(withBase(`/api/qc/letter/${encodeURIComponent(state.letter)}/chunk/${pageIdx}/${chunkIdx}`));
    state.chunkCache.set(key, detail);
    return detail;
  }

  function renderChunkContent(detail) {
    if (state.editingChunk) {
      el.chunkEditor.value = detail.html || '';
      el.chunkEditor.style.display = 'block';
      el.chunkPreview.style.display = 'none';
      el.chunkEditor.focus();
    } else {
      el.chunkPreview.srcdoc = detail.html || '';
      el.chunkPreview.style.display = 'block';
      el.chunkEditor.style.display = 'none';
    }
    const chunk = state.chunks[state.currentChunk];
    if (chunk) {
      const key = `${chunk.page_index}_${chunk.chunk_index}`;
      state.chunkCache.set(key, { ...detail });
      updateChunkMeta(chunk);
    }
  }

  function toggleChunkEdit(flag) {
    if (flag) {
      state.editingChunk = true;
      renderChunkView();
      return Promise.resolve();
    }
    return exitChunkEdit();
  }

  async function exitChunkEdit() {
    if (!state.editingChunk) return;
    await saveChunkHtml();
    state.editingChunk = false;
    if (el.chunkEditor) {
      el.chunkEditor.blur();
    }
    renderChunkView();
  }

  async function saveChunkHtml() {
    if (!state.editingChunk) return;
    const chunk = state.chunks[state.currentChunk];
    if (!chunk) return;
    const html = el.chunkEditor.value;
    try {
      await fetchJSON(withBase(`/api/qc/letter/${encodeURIComponent(state.letter)}/chunk/${chunk.page_index}/${chunk.chunk_index}/save`), {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ html }),
      });
      const key = `${chunk.page_index}_${chunk.chunk_index}`;
      const cached = state.chunkCache.get(key) || {};
      state.chunkCache.set(key, { ...cached, html });
      setStatus('Chunk saved', 'success');
    } catch (err) {
      setStatus(`Failed to save chunk: ${err.message}`, 'error', true);
    }
  }

  async function approveChunk() {
    const chunk = state.chunks[state.currentChunk];
    if (!chunk) return;
    try {
      await fetchJSON(withBase(`/api/qc/letter/${encodeURIComponent(state.letter)}/chunk/${chunk.page_index}/${chunk.chunk_index}/approve`), {
        method: 'POST',
      });
      const key = `${chunk.page_index}_${chunk.chunk_index}`;
      const cached = state.chunkCache.get(key) || {};
      state.chunkCache.set(key, { ...cached, approved: true });
      state.chunks[state.currentChunk] = { ...chunk, approved: true };
      setStatus('Chunk approved', 'success');
      renderChunkView();
    } catch (err) {
      setStatus(`Approve failed: ${err.message}`, 'error', true);
    }
  }

  async function unapproveChunk() {
    const chunk = state.chunks[state.currentChunk];
    if (!chunk) return;
    try {
      await fetchJSON(withBase(`/api/qc/letter/${encodeURIComponent(state.letter)}/chunk/${chunk.page_index}/${chunk.chunk_index}/unapprove`), {
        method: 'POST',
      });
      setCurrentChunkApproved(false);
      setStatus('Chunk unapproved', 'success');
      renderChunkView();
    } catch (err) {
      setStatus(`Unapprove failed: ${err.message}`, 'error', true);
    }
  }

  function toggleChunkReviewed() {
    if (currentChunkApproved()) {
      void unapproveChunk();
    } else {
      void approveChunk();
    }
  }

  async function retryCurrentChunk(feedback = '') {
    const chunk = state.chunks[state.currentChunk];
    if (!chunk) return;
    try {
      await fetchJSON(withBase(`/api/qc/letter/${encodeURIComponent(state.letter)}/chunk/${chunk.page_index}/${chunk.chunk_index}/retry`), {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ feedback }),
      });
      setStatus('Retry queued', 'success');
      kickTasksPoll();
    } catch (err) {
      setStatus(`Retry failed: ${err.message}`, 'error', true);
    }
  }

  function feedbackChunk() {
    const note = window.prompt('Feedback for this chunk:');
    if (note === null) return;
    retryCurrentChunk(note);
  }

  async function renderFullView() {
    if (state.pdfUrl) {
      el.pdfFrame.src = state.pdfUrl;
    }
    if (!state.htmlCache.full) {
      try {
        state.htmlCache.full = await fetchJSON(withBase(`/api/qc/letter/${encodeURIComponent(state.letter)}/html/de`));
      } catch (err) {
        state.htmlCache.full = { html: '', mtime: 0 };
      }
    }
    if (state.editingFull) {
      el.fullEditor.value = state.htmlCache.full.html || '';
      el.fullEditor.style.display = 'block';
      el.fullPreview.style.display = 'none';
      el.fullEditor.focus();
    } else {
      el.fullEditor.style.display = 'none';
      el.fullPreview.style.display = 'block';
      el.fullPreview.srcdoc = state.htmlCache.full.html || '';
    }
    loadUnifiedReasoning();
  }

  function toggleFullEdit(flag) {
    if (flag) {
      state.editingFull = true;
      renderFullView();
      return Promise.resolve();
    }
    return exitFullEdit();
  }

  async function exitFullEdit() {
    if (!state.editingFull) return;
    await saveFullHtml();
    state.editingFull = false;
    if (el.fullEditor) {
      el.fullEditor.blur();
    }
    renderFullView();
  }

  async function saveFullHtml() {
    if (!state.editingFull) return;
    const html = el.fullEditor.value;
    try {
      const result = await fetchJSON(withBase(`/api/qc/letter/${encodeURIComponent(state.letter)}/html/de`), {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ html }),
      });
      state.htmlCache.full = { html, mtime: result.mtime };
      setStatus('Unified HTML saved', 'success');
    } catch (err) {
      setStatus(`Failed to save unified HTML: ${err.message}`, 'error', true);
    }
  }

  async function loadUnifiedReasoning() {
    try {
      const data = await fetchJSON(withBase(`/api/qc/letter/${encodeURIComponent(state.letter)}/reasoning`));
      updateReasoning(data.reasoning || '');
    } catch (err) {
      updateReasoning('');
    }
  }

  async function rebuildUnified(withFeedback = false) {
    const payload = {};
    if (withFeedback) {
      const message = window.prompt('Feedback to include in rebuild:');
      if (message && message.trim()) payload.feedback = message.trim();
    }
    try {
      await fetchJSON(withBase(`/api/qc/letter/${encodeURIComponent(state.letter)}/rebuild`), {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(payload),
      });
      setStatus('Rebuild queued', 'success');
      kickTasksPoll();
    } catch (err) {
      setStatus(`Rebuild failed: ${err.message}`, 'error', true);
    }
  }

  async function toggleFinished() {
    try {
      const res = await fetchJSON(withBase(`/api/qc/letter/${encodeURIComponent(state.letter)}/finished`), {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
      });
      state.finished = !!res.finished;
      updateLetterSummary(state.letter, { finished: state.finished });
      renderLetterMeta();
      setStatus(state.finished ? 'Marked finished' : 'Marked unfinished', 'success');
    } catch (err) {
      setStatus(`Failed to toggle finished: ${err.message}`, 'error', true);
    }
  }

  async function deepReload() {
    if (!window.confirm('Deep reload will reprocess the document. Continue?')) return;
    try {
      await fetchJSON(withBase(`/api/qc/letter/${encodeURIComponent(state.letter)}/deep_reload`), {
        method: 'POST',
      });
      setStatus('Deep reload queued', 'success');
      kickTasksPoll();
    } catch (err) {
      setStatus(`Deep reload failed: ${err.message}`, 'error', true);
    }
  }

  async function renderTranslateView() {
    if (!state.htmlCache.translateDe) {
      try {
        state.htmlCache.translateDe = await fetchJSON(withBase(`/api/qc/letter/${encodeURIComponent(state.letter)}/html/de`));
      } catch (err) {
        state.htmlCache.translateDe = { html: '', mtime: 0 };
      }
    }
    if (!state.htmlCache.translateEn) {
      try {
        state.htmlCache.translateEn = await fetchJSON(withBase(`/api/qc/letter/${encodeURIComponent(state.letter)}/html/en`));
      } catch (err) {
        state.htmlCache.translateEn = { html: '', mtime: 0 };
      }
    }

    if (state.editingTranslate.de) {
      el.translateEditorDe.value = state.htmlCache.translateDe.html || '';
      el.translateEditorDe.style.display = 'block';
      el.translatePreviewDe.style.display = 'none';
      el.translateEditorDe.focus();
    } else {
      el.translateEditorDe.style.display = 'none';
      el.translatePreviewDe.style.display = 'block';
      el.translatePreviewDe.srcdoc = state.htmlCache.translateDe.html || '';
    }

    if (state.editingTranslate.en) {
      el.translateEditorEn.value = state.htmlCache.translateEn.html || '';
      el.translateEditorEn.style.display = 'block';
      el.translatePreviewEn.style.display = 'none';
      el.translateEditorEn.focus();
    } else {
      el.translateEditorEn.style.display = 'none';
      el.translatePreviewEn.style.display = 'block';
      el.translatePreviewEn.srcdoc = state.htmlCache.translateEn.html || '';
    }
  }

  function toggleTranslateEdit(lang, flag) {
    if (flag) {
      state.editingTranslate[lang] = true;
      renderTranslateView();
      return Promise.resolve();
    }
    return exitTranslateEdit(lang);
  }

  async function saveTranslate(lang) {
    if (!state.editingTranslate[lang]) return;
    const editor = lang === 'de' ? el.translateEditorDe : el.translateEditorEn;
    const html = editor.value;
    try {
      const result = await fetchJSON(withBase(`/api/qc/letter/${encodeURIComponent(state.letter)}/html/${lang}`), {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ html }),
      });
      if (lang === 'de') {
        state.htmlCache.translateDe = { html, mtime: result.mtime };
      } else {
        state.htmlCache.translateEn = { html, mtime: result.mtime };
      }
      setStatus(`${lang.toUpperCase()} HTML saved`, 'success');
    } catch (err) {
      setStatus(`Failed to save ${lang.toUpperCase()}: ${err.message}`, 'error', true);
    }
  }

  async function exitTranslateEdit(lang) {
    if (!state.editingTranslate[lang]) return;
    await saveTranslate(lang);
    state.editingTranslate[lang] = false;
    const editor = lang === 'de' ? el.translateEditorDe : el.translateEditorEn;
    if (editor) editor.blur();
    renderTranslateView();
  }

  async function translateCurrent(feedback = '') {
    try {
      await fetchJSON(withBase(`/api/qc/letter/${encodeURIComponent(state.letter)}/translate`), {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(feedback ? { feedback } : {}),
      });
      setStatus('Translation queued', 'success');
      kickTasksPoll();
    } catch (err) {
      setStatus(`Translate failed: ${err.message}`, 'error', true);
    }
  }

  function translateWithFeedback() {
    const message = window.prompt('Feedback for translation:');
    if (message === null) return;
    translateCurrent(message.trim());
  }

  async function enqueueBatchRebuild() {
    try {
      await fetchJSON(withBase('/api/qc/batch/rebuild_changed'), { method: 'POST' });
      setStatus('Batch rebuild queued', 'success');
      kickTasksPoll();
    } catch (err) {
      setStatus(`Batch rebuild failed: ${err.message}`, 'error', true);
    }
  }

  async function enqueueTranslateAll() {
    try {
      await fetchJSON(withBase('/api/qc/batch/translate_all'), { method: 'POST' });
      setStatus('Batch translate queued', 'success');
      kickTasksPoll();
    } catch (err) {
      setStatus(`Batch translate failed: ${err.message}`, 'error', true);
    }
  }

  async function fetchTasks() {
    try {
      const data = await fetchJSON(withBase('/api/qc/tasks'));
      renderTasks(data.tasks || []);
      handleTaskTransitions(data.tasks || []);
      const active = (data.tasks || []).some((t) => t.status === 'queued' || t.status === 'running');
      el.tasksCount.textContent = String((data.tasks || []).filter((t) => t.status === 'queued' || t.status === 'running').length);
      if (active && !state.tasksTimer) {
        state.tasksTimer = setInterval(fetchTasks, 500);
      }
      if (!active && state.tasksTimer) {
        clearInterval(state.tasksTimer);
        state.tasksTimer = null;
      }
    } catch (err) {
      console.error(err);
    }
  }

  function renderTasks(tasks) {
    if (!el.tasksList) return;
    el.tasksList.innerHTML = '';
    tasks.slice(0, 25).forEach((task) => {
      const li = document.createElement('li');
      const left = document.createElement('div');
      left.className = 'task-label';
      const dot = document.createElement('span');
      dot.className = `task-dot dot-${task.status}`;
      const label = document.createElement('span');
      label.textContent = task.name;
      left.append(dot, label);
      const right = document.createElement('div');
      right.className = 'task-meta';
      const parts = [];
      if (task.meta?.letter) parts.push(task.meta.letter);
      if (task.meta?.page_index !== undefined) parts.push(`p${task.meta.page_index + 1}`);
      if (task.meta?.chunk_index !== undefined) parts.push(`c${task.meta.chunk_index + 1}`);
      right.textContent = parts.join(' · ');
      li.append(left, right);
      el.tasksList.appendChild(li);
    });
  }

  function handleTaskTransitions(tasks) {
    const currentIds = new Set();
    tasks.forEach((task) => {
      currentIds.add(task.id);
      const previous = state.taskStatusMap.get(task.id);
      if (previous !== task.status) {
        state.taskStatusMap.set(task.id, task.status);
        if (task.status === 'done' || task.status === 'error') {
          onTaskSettled(task);
        }
      }
    });
    Array.from(state.taskStatusMap.keys()).forEach((id) => {
      if (!currentIds.has(id)) {
        state.taskStatusMap.delete(id);
      }
    });
  }

  function onTaskSettled(task) {
    const { status, name = '', meta = {} } = task;
    if (meta.letter && meta.letter !== state.letter) {
      return;
    }
    if (status === 'error') {
      setStatus(`${name} failed`, 'error', true);
      return;
    }
    const normalized = name.toLowerCase();
    if (normalized.includes('rebuild html') ||
        normalized.includes('update chunks') ||
        normalized.includes('regenerate chunks') ||
        normalized.includes('deep reload')) {
      reloadLetterContext()
        .then(() => setStatus(`${name} complete`, 'success'))
        .catch((err) => console.error(err));
      return;
    }
    if (normalized.includes('translate')) {
      state.htmlCache.translateDe = null;
      state.htmlCache.translateEn = null;
      const refresh = state.view === 'translate'
        ? renderTranslateView()
        : Promise.resolve();
      Promise.resolve(refresh)
        .then(() => setStatus(`${name} complete`, 'success'))
        .catch((err) => console.error(err));
    }
  }

  function kickTasksPoll() {
    fetchTasks();
    setTimeout(fetchTasks, 600);
  }

  function updateReasoning(text) {
    if (!el.reasoningPanel) return;
    el.reasoningPanel.textContent = text || '';
  }

  function selectPage(index) {
    state.currentPage = clampPage(index);
    renderBoxesView();
  }

  function navigateNext() {
    switch (state.view) {
      case 'boxes':
        if (state.pages.length && state.currentPage < state.pages.length - 1) {
          state.currentPage += 1;
          renderBoxesView();
        } else if (state.chunks.length) {
          state.currentChunk = 0;
          setView('chunks');
        } else {
          setView('full');
        }
        break;
      case 'chunks':
        if (state.currentChunk < state.chunks.length - 1) {
          state.currentChunk += 1;
          renderChunkView();
        } else if (state.pages.length) {
          setView('full');
        } else {
          showHint('End reached ✨');
        }
        break;
      case 'full':
        setView('translate');
        break;
      case 'translate':
        showHint('End reached ✨');
        break;
    }
  }

  function navigatePrev() {
    switch (state.view) {
      case 'boxes':
        if (state.currentPage > 0) {
          state.currentPage -= 1;
          renderBoxesView();
        } else {
          showHint('Start reached ⏪');
        }
        break;
      case 'chunks':
        if (state.currentChunk > 0) {
          state.currentChunk -= 1;
          renderChunkView();
        } else if (state.pages.length) {
          setView('boxes');
          state.currentPage = state.pages.length - 1;
          renderBoxesView();
        }
        break;
      case 'full':
        if (state.chunks.length) {
          setView('chunks');
          state.currentChunk = state.chunks.length - 1;
          renderChunkView();
        } else {
          setView('boxes');
        }
        break;
      case 'translate':
        setView('full');
        break;
    }
  }

  function navigateNextUnreviewed() {
    if (state.view !== 'chunks' || !state.chunks.length) return;
    for (let i = state.currentChunk + 1; i < state.chunks.length; i++) {
      if (!state.chunks[i]?.approved) {
        state.currentChunk = i;
        renderChunkView();
        return;
      }
    }
    showHint('No next unreviewed chunk');
  }

  function navigatePrevUnreviewed() {
    if (state.view !== 'chunks' || !state.chunks.length) return;
    for (let i = state.currentChunk - 1; i >= 0; i--) {
      if (!state.chunks[i]?.approved) {
        state.currentChunk = i;
        renderChunkView();
        return;
      }
    }
    showHint('No previous unreviewed chunk');
  }

  function handleKeyDown(evt) {
    const key = evt.key;
    const code = evt.code || '';
    const ctrl = evt.ctrlKey || evt.metaKey;
    const isEditing = !!(state.editingChunk || state.editingFull || (state.editingTranslate && (state.editingTranslate.de || state.editingTranslate.en)));

    // In edit mode, only capture Ctrl+M to exit/edit toggle. Let everything else through to the editor
    if (isEditing) {
      if (ctrl && (key === 'm' || key === 'M')) {
        handleCtrlM();
        evt.preventDefault();
      }
      return;
    }
    if (!state.allowShortcuts) {
      if (ctrl && key === 'Enter') {
        handleCtrlEnter();
        evt.preventDefault();
      }
      if (ctrl && (key === 'm' || key === 'M')) {
        handleCtrlM();
        evt.preventDefault();
      }
      if (key === 'm' || key === 'M') {
        handleEditToggle();
        evt.preventDefault();
      }
      if (evt.shiftKey && (code === 'BracketLeft' || key === '{' || key === '[')) {
        if (state.view === 'chunks') {
          navigatePrevUnreviewed();
        } else {
          navigateLetter(-1);
        }
        evt.preventDefault();
      }
      if (evt.shiftKey && (code === 'BracketRight' || key === '}' || key === ']')) {
        if (state.view === 'chunks') {
          navigateNextUnreviewed();
        } else {
          navigateLetter(1);
        }
        evt.preventDefault();
      }
      return;
    }

    if (key === 'v' || key === 'V') {
      setView('boxes');
    } else if (key === 'c' || key === 'C') {
      setView('chunks');
    } else if (key === 'p' || key === 'P') {
      setView('full');
    } else if (key === 'r' || key === 'R') {
      handleRetryShortcut();
    } else if (key === '|') {
      handleFeedbackShortcut();
    } else if (key === 'm' || key === 'M') {
      handleEditToggle();
      evt.preventDefault();
    } else if (key === 'f' || key === 'F') {
      if (state.letter) {
        toggleFinished();
        evt.preventDefault();
      }
    } else if (key === 'd' || key === 'D') {
      if (state.view === 'full') {
        deepReload();
      }
    } else if (code === 'BracketLeft' || key === '[' || key === '{') {
      if (evt.shiftKey) {
        if (state.view === 'chunks') {
          navigatePrevUnreviewed();
        } else {
          navigateLetter(-1);
        }
      } else {
        navigatePrev();
      }
      evt.preventDefault();
    } else if (code === 'BracketRight' || key === ']' || key === '}') {
      if (evt.shiftKey) {
        if (state.view === 'chunks') {
          navigateNextUnreviewed();
        } else {
          navigateLetter(1);
        }
      } else {
        navigateNext();
      }
      evt.preventDefault();
    } else if (key === 't' || key === 'T') {
      if (state.view === 'chunks') {
        toggleChunkReviewed();
        evt.preventDefault();
      }
    } else if (key === 'Escape') {
      if (state.drawMode) {
        setDrawMode(false, { silent: true });
        setStatus('Draw mode cancelled', 'info');
      }
    } else if (key === 'Backspace') {
      if (state.drawMode && state.drawRects.length > 0) {
        state.drawRects.pop();
        if (el.draftLayer && el.draftLayer.lastChild) {
          el.draftLayer.lastChild.remove();
        }
        setStatus(`${state.drawRects.length} box(es) drawn`, 'info');
        evt.preventDefault();
      }
    } else if (ctrl && key === 'Enter') {
      handleCtrlEnter();
      evt.preventDefault();
    } else if (ctrl && (key === 'm' || key === 'M')) {
      handleCtrlM();
      evt.preventDefault();
    }
  }

  async function handleCtrlEnter() {
    if (state.view === 'boxes' && state.drawMode) {
      applyDrawnBoxes(false);
    } else if (state.view === 'chunks') {
      const wasApproved = currentChunkApproved();
      if (wasApproved) {
        await unapproveChunk();
      } else {
        await approveChunk();
        navigateNext();
      }
    } else if (state.view === 'full' && state.editingFull) {
      await exitFullEdit();
    } else if (state.view === 'translate') {
      if (state.editingTranslate.de) await exitTranslateEdit('de');
      if (state.editingTranslate.en) await exitTranslateEdit('en');
    }
  }

  function handleCtrlM() {
    if (state.view === 'chunks' && state.editingChunk) {
      exitChunkEdit();
    } else if (state.view === 'full' && state.editingFull) {
      exitFullEdit();
    } else if (state.view === 'translate') {
      if (state.editingTranslate[state.translateFocus]) {
        exitTranslateEdit(state.translateFocus);
      }
    }
  }

  function handleRetryShortcut() {
    switch (state.view) {
      case 'boxes':
        regenerateBoxes();
        break;
      case 'chunks':
        retryCurrentChunk();
        break;
      case 'translate':
        translateCurrent();
        break;
      case 'full':
        rebuildUnified();
        break;
    }
  }

  function handleFeedbackShortcut() {
    switch (state.view) {
      case 'chunks':
        feedbackChunk();
        break;
      case 'translate':
        translateWithFeedback();
        break;
      case 'boxes':
        showHint('Feedback shortcut not available in boxes view');
        break;
      case 'full':
        rebuildUnified(true);
        break;
    }
  }

  function handleEditToggle() {
    switch (state.view) {
      case 'chunks':
        if (state.editingChunk) {
          exitChunkEdit();
        } else {
          toggleChunkEdit(true);
        }
        break;
      case 'full':
        if (state.editingFull) {
          exitFullEdit();
        } else {
          toggleFullEdit(true);
        }
        break;
      case 'translate':
        if (state.editingTranslate[state.translateFocus]) {
          exitTranslateEdit(state.translateFocus);
        } else {
          toggleTranslateEdit(state.translateFocus, true);
        }
        break;
    }
  }

  function navigateLetter(direction) {
    if (!state.letters.length) return;
    const idx = state.letters.findIndex((l) => l.id === state.letter);
    const nextIdx = idx + direction;
    if (nextIdx < 0 || nextIdx >= state.letters.length) {
      showHint(direction > 0 ? 'All PDFs finished ✅' : 'Start reached ⏪');
      return;
    }
    rememberPosition();
    const nextLetter = state.letters[nextIdx].id;
    loadLetter(nextLetter, { restore: true });
  }
})();
