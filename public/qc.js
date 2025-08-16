(function(){
	const qs = sel => document.querySelector(sel);
	const qsa = sel => Array.from(document.querySelectorAll(sel));
	const state = {
		letter: null,
		chunks: [],
		idx: 0,
		modeEdit: false,
		allowShortcuts: true,
		view: 2,
		editDE: false,
		editEN: false,
		fullEdit: false,
		pages: [],
		pageCoords: {},
		originalPageCoords: {},
		currentPage: null,
		drawMode: false,
		drawRects: [],
		drawStart: null,
		scale: 1,
		base: null,
		tasksTimer: null,
		tasksOpen: false,
		lettersStatus: {},
		lastPositions: {}, // { [letter]: { pageIndex, chunkIndex, view } }
		shiftNavRestore: false,
		highlightBoxIndex: null
	};

	function baseQS(){ return state.base ? `?base=${encodeURIComponent(state.base)}` : ''; }

	function setStatus(t){ qs('#qc-status').textContent = t || ''; }
	function setReasoning(t){ qs('#qc-reasoning-bottom').textContent = t || ''; }

	function rememberPosition(){
		if(!state.letter) return;
		state.lastPositions[state.letter] = {
			pageIndex: state.currentPage,
			chunkIndex: state.idx,
			view: state.view
		};
	}

	function getUncompletedLetters(){
		const sel = qs('#qc-letters');
		const letters = Array.from(sel.options).map(o => o.value);
		return letters.filter(l => !(state.lettersStatus && state.lettersStatus[l] && state.lettersStatus[l].approved_pdf));
	}

	async function gotoAdjacentUncompleted(forward){
		await refreshLetterStatus();
		const uncompleted = getUncompletedLetters();
		if(!uncompleted.length){ showEndHint('all'); return; }
		const sel = qs('#qc-letters');
		const letters = Array.from(sel.options).map(o => o.value);
		let i = letters.indexOf(state.letter);
		let nextIdx = -1;
		if(forward){
			for(let k=i+1; k<letters.length; k++){
				if(uncompleted.includes(letters[k])){ nextIdx = k; break; }
			}
			if(nextIdx === -1){ showEndHint('end'); return; }
		}else{
			for(let k=i-1; k>=0; k--){
				if(uncompleted.includes(letters[k])){ nextIdx = k; break; }
			}
			if(nextIdx === -1){ showEndHint('start'); return; }
		}
		const nextLetter = letters[nextIdx];
		rememberPosition();
		state.shiftNavRestore = true;
		sel.value = nextLetter;
		await loadLetter(nextLetter, { restore: true });
	}

	async function fetchJSON(url, opts){
		const res = await fetch(url, opts);
		if(!res.ok) throw new Error(await res.text());
		return res.json();
	}

	async function pollTasks(){
		try{
			// aggregate over all letters in base
			const params = new URLSearchParams();
			if(state.base) params.set('base', state.base);
			const data = await fetchJSON(`/api/qc/tasks?${params.toString()}`);
			const tasks = data.tasks||[];
			renderTasks(tasks);
			const active = tasks.filter(t => t.status==='queued' || t.status==='running');
			qs('#tasks-count').textContent = String(active.length);
			const anyActive = active.length>0;
			if(anyActive){ if(!state.tasksTimer){ state.tasksTimer = setInterval(pollTasks, 2000); } }
			else { if(state.tasksTimer){ clearInterval(state.tasksTimer); state.tasksTimer = null; } }
		}catch(e){ /* ignore */ }
	}

	function kickPoll(){ pollTasks(); setTimeout(pollTasks, 300); setTimeout(pollTasks, 1000); }

	function renderTasks(tasks){
		const ul = qs('#tasks-list');
		ul.innerHTML = '';
		tasks.slice(0,20).forEach(t => {
			const li = document.createElement('li');
			const left = document.createElement('div'); left.style.display = 'flex'; left.style.alignItems = 'center'; left.style.gap = '8px';
			const dot = document.createElement('span'); dot.className = 'task-dot ' + (t.status==='queued'?'dot-queued': t.status==='running'?'dot-running': t.status==='done'?'dot-done':'dot-error');
			const label = document.createElement('span'); label.textContent = t.name;
			left.appendChild(dot); left.appendChild(label);
			const right = document.createElement('div'); right.className = 'task-meta';
			const parts = [];
			if(t.meta && t.meta.letter) parts.push(`letter: ${t.meta.letter}`);
			if(t.meta && t.meta.page_index!=null) parts.push(`page: ${t.meta.page_index+1}`);
			if(t.meta && t.meta.chunk_index!=null) parts.push(`chunk: ${t.meta.chunk_index+1}`);
			right.textContent = parts.join(' · ');
			li.appendChild(left); li.appendChild(right);
			ul.appendChild(li);
		});
		qs('#tasks-panel').classList.toggle('qc-hidden', !state.tasksOpen);
	}

	function toggleTasksPanel(){ state.tasksOpen = !state.tasksOpen; qs('#tasks-panel').classList.toggle('qc-hidden', !state.tasksOpen); }

	function switchView(v){
		// preserve relative position when switching
		if(v===1 && state.view===2){
			const c = state.chunks[state.idx];
			if(c){ state.currentPage = c.page_index; state.highlightBoxIndex = c.chunk_index; }
		}
		
		rememberPosition();
		state.view = v;
		qsa('#qc-views > div').forEach(d => d.classList.add('qc-hidden'));
		qs(`#view-${v}`).classList.remove('qc-hidden');
		if(v===1){ if(state.currentPage==null && state.pages.length){ selectPage(state.pages[0].index); } else if(state.currentPage!=null){ selectPage(state.currentPage); } renderBoxesView(); }
		if(v===2) renderChunkView();
		if(v===3) renderFullView();
		if(v===4) renderTranslateView();
	}

	function renderChunkView(){
		const c = state.chunks[state.idx]; if(!c) return;
		qs('#chunk-image').src = c.image_url;
		qs('#chunk-approved').textContent = c.approved ? 'Approved' : '';
		fetchJSON(`/api/qc/${state.letter}/chunk/${c.page_index}/${c.chunk_index}${baseQS()}`).then(d => {
			const iframe = qs('#chunk-render'); const editor = qs('#chunk-editor');
			if(state.modeEdit){ editor.classList.remove('qc-hidden'); iframe.classList.add('qc-hidden'); editor.value = d.html || ''; editor.focus(); }
			else { editor.classList.add('qc-hidden'); iframe.classList.remove('qc-hidden'); iframe.srcdoc = d.html || ''; }
			setReasoning(d.reasoning || ''); qs('#chunk-approved').textContent = d.approved ? 'Approved' : '';
			rememberPosition();
		}).catch(e => setStatus(e.message));
	}

	function bindChunkNav(){
		qs('#btn-prev').onclick = ()=> goPrev();
		qs('#btn-next').onclick = ()=> goNext();
		qs('#btn-approve').onclick = approveChunk;
		qs('#btn-retry').onclick = retryChunk;
		qs('#btn-feedback').onclick = feedbackChunk;
		qs('#btn-edit').onclick = toggleEdit;
		qs('#btn-render').onclick = ()=>{ state.modeEdit=false; renderChunkView(); };
	}

	function showEndHint(type){
		let el = qs('#end-hint');
		if(!el){
			el = document.createElement('div');
			el.id = 'end-hint';
			el.style.position = 'fixed';
			el.style.left = '50%';
			el.style.top = '12%';
			el.style.transform = 'translateX(-50%)';
			el.style.padding = '10px 14px';
			el.style.background = 'rgba(0,0,0,0.75)';
			el.style.color = '#fff';
			el.style.borderRadius = '12px';
			el.style.fontSize = '14px';
			el.style.boxShadow = '0 8px 24px rgba(0,0,0,0.2)';
			el.style.zIndex = '9999';
			document.body.appendChild(el);
		}
		el.textContent = type==='end' ? 'End reached ✨ — Press Ctrl+Enter to save/approve' : (type==='all' ? 'All PDFs are finished ✅' : 'At beginning ⏪');
		el.style.opacity = '0';
		el.style.transition = 'opacity 150ms ease, transform 250ms ease';
		requestAnimationFrame(()=>{
			el.style.opacity = '1';
			el.style.transform = 'translateX(-50%) scale(1.02)';
			setTimeout(()=>{ el.style.opacity='0'; el.style.transform='translateX(-50%) scale(1)'; }, 1600);
		});
	}

	function goPrev(){
		if(state.view===1){
			if(state.pages.length && state.currentPage!=null){
				const idx = state.pages.findIndex(p=>p.index===state.currentPage);
				if(idx>0){ selectPage(state.pages[idx-1].index); }
				else { showEndHint('start'); }
			}
			return;
		}
		if(state.view===2){
			if(state.idx>0){ state.idx--; renderChunkView(); }
			else {
				// at beginning of chunks → go to last page in boxing view
				if(state.pages.length>0){ 
					state.idx = state.chunks.length - 1;
					switchView(1); 
				}
				else { showEndHint('start'); }
			}
			return;
		}
		if(state.view===3){
			// at beginning of full → go to last chunk if available
			if(state.chunks.length>0){ state.idx = state.chunks.length - 1; switchView(2); }
			else if(state.pages.length>0){ state.currentPage = state.pages[state.pages.length-1].index; switchView(1); }
			else { showEndHint('start'); }
			return;
		}
		if(state.view===4){ showEndHint('start'); return; }
	}
	function goNext(){
		if(state.view===1){
			if(state.pages.length && state.currentPage!=null){
				const idx = state.pages.findIndex(p=>p.index===state.currentPage);
				console.log(`In view 1: currentPage=${state.currentPage}, pageIdx=${idx}, totalPages=${state.pages.length}`);
				if(idx>=0 && idx<state.pages.length-1){ 
					console.log(`Going to next page`);
					selectPage(state.pages[idx+1].index); 
				}
				else {
					console.log(`At end of pages, switching to chunks`);
					// at end of pages → go to 0_chunk_1.png (page 0, chunk 0)
					if(state.chunks.length>0) {
						// Find chunk with page_index=0 and chunk_index=0
						let targetIdx = -1;
						for(let i = 0; i < state.chunks.length; i++) {
							const chunk = state.chunks[i];
							if(chunk.page_index === 0 && chunk.chunk_index === 0) {
								targetIdx = i;
								break;
							}
						}
						
						// If not found, just use the first chunk in the array
						if(targetIdx === -1) {
							targetIdx = 0;
							console.log(`0_chunk_1.png not found, using first chunk in array: page ${state.chunks[0].page_index}, chunk ${state.chunks[0].chunk_index}`);
						} else {
							console.log(`Found 0_chunk_1.png at array index ${targetIdx}`);
						}
						
						state.idx = targetIdx;
						switchView(2);
					}
				}
			}
			return;
		}
		if(state.view===2){
			if(state.chunks.length===0){ switchView(3); return; }
			if(state.idx<state.chunks.length-1){ state.idx++; renderChunkView(); }
			else { switchView(3); }
			return;
		}
		if(state.view===3){ showEndHint('end'); return; }
		if(state.view===4){ showEndHint('end'); return; }
	}

	function approvePDF(){ fetch(`/api/qc/${state.letter}/approve_pdf${baseQS()}`, {method:'POST'}).then(refreshLetterStatus).then(renderLetterTitle).catch(()=>{}); }

	async function refreshLetterStatus(){ const status = await fetchJSON(`/api/qc/letters_status${baseQS()}`); state.lettersStatus = status || {}; }

	function renderLetterTitle(){ const sel = qs('#qc-letters'); const letter = state.letter; const approved = !!(state.lettersStatus && state.lettersStatus[letter] && state.lettersStatus[letter].approved_pdf); const opt = Array.from(sel.options).find(o => o.value===letter); if(opt){ opt.textContent = approved ? `${letter} ✅` : letter; } }

	function approveChunk(){ const c = state.chunks[state.idx]; if(!c) return; c.approved = true; renderChunkView(); fetch(`/api/qc/${state.letter}/chunk/${c.page_index}/${c.chunk_index}/approve${baseQS()}`, {method:'POST'}).catch(()=>{}); }

	function retryChunk(){ if(state.view===1){ // retry drawing chunks for current page
		if(state.currentPage==null) return; 
		
		const pageIndex = state.currentPage; setStatus('Regenerating chunks on page...'); fetch(`/api/qc/${state.letter}/page/${pageIndex}/regenerate_chunks${baseQS()}`, {method:'POST'}).then(()=>{ kickPoll(); }).catch(()=>{}); setStatus('Queued'); return; }

		if(state.view===3){ // retry uniting all HTML chunks in full document view
			rebuildUnified(); return; }
			
		const c = state.chunks[state.idx]; setStatus('Retrying...'); fetch(`/api/qc/${state.letter}/chunk/${c.page_index}/${c.chunk_index}/retry${baseQS()}`, {method:'POST', headers:{'Content-Type':'application/json'}, body: JSON.stringify({feedback:''})}).then(()=>{ kickPoll(); }).catch(()=>{}); setStatus('Queued'); state.modeEdit = false; renderChunkView(); }

	function feedbackChunk(){ const fb = prompt('Feedback for retry:'); if(fb==null) return; const c = state.chunks[state.idx]; setStatus('Retrying with feedback...'); fetch(`/api/qc/${state.letter}/chunk/${c.page_index}/${c.chunk_index}/retry${baseQS()}`, {method:'POST', headers:{'Content-Type':'application/json'}, body: JSON.stringify({feedback: fb})}).then(()=>{ kickPoll(); }).catch(()=>{}); setStatus('Queued'); state.modeEdit = false; renderChunkView(); }

	function saveEdit(){ const c = state.chunks[state.idx]; const html = qs('#chunk-editor').value; fetch(`/api/qc/${state.letter}/chunk/${c.page_index}/${c.chunk_index}/save${baseQS()}`, {method:'POST', headers:{'Content-Type':'application/json'}, body: JSON.stringify({html})}).then(()=>approveChunk()).catch(()=>{}); }

	function exitChunkEditAndSave(){
		if(state.view===2 && state.modeEdit){
			saveEdit();
			state.modeEdit = false;
			renderChunkView();
		}
	}

	function exitFullEditAndSave(){
		if(state.view===3 && state.fullEdit){
			saveFullDE();
			state.fullEdit = false;
			renderFullView();
		}
	}

	function exitTranslateEditAndSave(){
		if(state.view===4 && (state.editDE || state.editEN)){
			if(state.editDE) saveDE();
			if(state.editEN) saveEN();
			state.editDE = false;
			state.editEN = false;
			renderTranslateView();
		}
	}

	function toggleEdit(){ state.modeEdit ? (()=>{ saveEdit(); state.modeEdit=false; renderChunkView(); })() : (state.modeEdit=true, renderChunkView()); }

	function bindGlobalKeys(){
		document.addEventListener('keydown', async (e)=>{
			if(!state.allowShortcuts) return;
			const tag = (document.activeElement && document.activeElement.tagName || '').toLowerCase();
			const typing = tag === 'textarea' || tag === 'input';
			// Let browser search (Ctrl/Cmd+F) always pass through
			if((e.ctrlKey || e.metaKey) && (e.key.toLowerCase() === 'f')){ return; }
			// Do not intercept other Ctrl/Cmd shortcuts except Enter and M
			if((e.ctrlKey || e.metaKey) && !(e.key === 'Enter' || e.key.toLowerCase() === 'm')){ return; }
			if(typing && !(e.ctrlKey && (e.key === 'Enter' || e.key.toLowerCase() === 'm'))){ return; }
			// Shift+]/[ for unfinished PDFs navigation (no wrap)
			if(e.shiftKey && e.key===']'){ e.preventDefault(); await gotoAdjacentUncompleted(true); return; }
			if(e.shiftKey && e.key==='['){ e.preventDefault(); await gotoAdjacentUncompleted(false); return; }
			// Navigation between unfinished PDFs
			if(e.key.toLowerCase()==='n'){ e.preventDefault(); await gotoAdjacentUncompleted(true); return; }
			if(e.key.toLowerCase()==='b'){ e.preventDefault(); await gotoAdjacentUncompleted(false); return; }
			// View switching
			if(e.key.toLowerCase()==='v'){ e.preventDefault(); switchView(1); return; }
			if(e.key.toLowerCase()==='c'){ e.preventDefault(); switchView(2); return; }
			if(e.key.toLowerCase()==='p'){ e.preventDefault(); switchView(3); return; }
			// Toggle PDF finished
			if(e.key.toLowerCase()==='f'){ e.preventDefault(); approvePDF(); return; }
			// Navigation with brackets
			if(e.key===']'){ e.preventDefault(); goNext(); return; }
			if(e.key==='['){ e.preventDefault(); goPrev(); return; }
			if(e.key === 'Escape'){ if(state.view===1){ state.drawMode = false; state.drawRects = []; if(state.currentPage!=null){ state.pageCoords[state.currentPage] = JSON.parse(JSON.stringify(state.originalPageCoords[state.currentPage]||[])); renderBoxes(); } } return; }
			if(e.key.toLowerCase()==='r' && !(e.ctrlKey && e.shiftKey)){ e.preventDefault(); retryChunk(); return; }
			if(e.ctrlKey && e.key.toLowerCase()==='m'){
				e.preventDefault();
				await exitChunkEditAndSave();
				await exitFullEditAndSave();
				await exitTranslateEditAndSave();
				return;
			}
			if(e.ctrlKey && e.key === 'Enter'){ e.preventDefault(); if(state.view===1 && state.drawMode){ applyDrawnBoxes(); } else if(state.view===2){ approveChunk(); } else if(state.view===3){ saveFullDE(); } else if(state.view===4){ saveDE(); } }
			else if(!e.ctrlKey && e.key==='|'){ e.preventDefault(); if(state.view===2) feedbackChunk(); else if(state.view===4) feedbackDE(); }
			else if(!e.ctrlKey && e.key==='m'){
				e.preventDefault();
				if(state.view===2) toggleEdit();
				else if(state.view===3) toggleFullEdit();
				else if(state.view===4) toggleEditDE();
			}
			else if(e.ctrlKey && (e.key==='m' || e.key==='M')){ e.preventDefault(); if(state.view===2){ state.fullEdit=false; const ed = qs('#chunk-editor'); ed && ed.focus(); } else if(state.view===3){ state.fullEdit=false; renderFullView(); const ed = qs('#full-de-editor'); ed && ed.focus(); } else if(state.view===4){ state.editDE=false; state.editEN=false; renderTranslateView(); const ed = qs('#de-editor'); ed && ed.focus(); } }
			else if(!e.ctrlKey && e.key==='d'){ e.preventDefault(); deepReload(); }
		});
	}

	function deepReload(){ if(!state.letter) return; setStatus('Deep reloading...'); fetch(`/api/qc/${state.letter}/deep_reload${baseQS()}`, {method:'POST'}).catch(()=>{}); setStatus('Queued'); pollTasks(); }

	function rebuildUnified(){ if(!state.letter) return; setStatus('Rebuilding unified html...'); fetch(`/api/qc/${state.letter}/rebuild_html${baseQS()}`, {method:'POST', headers:{'Content-Type':'application/json'}, body: JSON.stringify({feedback:''})}).catch(()=>{}); setStatus('Queued'); pollTasks(); }

	function rebuildUnifiedAll(){ setStatus('Rebuilding all pending...'); fetch(`/api/qc/all/rebuild_html${baseQS()}`, {method:'POST'}).catch(()=>{}); setStatus('Queued'); pollTasks(); }

	function translateEN(){ if(!state.letter) return; setStatus('Translating...'); fetch(`/api/qc/${state.letter}/translate${baseQS()}`, {method:'POST'}).catch(()=>{}); setStatus('Queued'); pollTasks(); }
	function translateAll(){ setStatus('Translating all pending...'); fetch(`/api/qc/all/translate${baseQS()}`, {method:'POST'}).catch(()=>{}); setStatus('Queued'); pollTasks(); }

	async function loadLetter(letter, opts){
		const restore = !!(opts && opts.restore);
		state.letter = letter;
		// reset page image to avoid showing previous PDF when switching
		const img = qs('#page-image'); if(img){ img.src = ''; }
		const canvas = qs('#page-canvas'); if(canvas){ canvas.width = 0; canvas.height = 0; }
		const resp = await fetchJSON(`/api/qc/${letter}/chunks${baseQS()}`); state.chunks = resp.chunks || []; state.idx = 0; state.modeEdit = false;
		state.pages = await fetchJSON(`/api/qc/${letter}/pages${baseQS()}`);
		const list = qs('#page-list'); list.innerHTML = '';
		state.pages.forEach(p => { const li = document.createElement('li'); li.textContent = `Page ${p.index+1}`; li.onclick = ()=> selectPage(p.index); list.appendChild(li); });
		await refreshLetterStatus(); renderLetterTitle();
		if(restore && state.lastPositions[letter]){
			const lp = state.lastPositions[letter];
			state.currentPage = (lp.pageIndex!=null ? lp.pageIndex : null);
			state.idx = (lp.chunkIndex!=null ? lp.chunkIndex : 0);
			if(state.view===1 && state.currentPage!=null) selectPage(state.currentPage); else if(state.view===2) renderChunkView();
		}else{
			state.currentPage = null;
			if(state.view===2) renderChunkView();
			if(state.view===1 && state.pages.length) selectPage(state.pages[0].index);
		}
		renderFullView(); renderTranslateView(); pollTasks();
	}

	async function selectPage(pageIndex){
		state.currentPage = pageIndex; const img = qs('#page-image'); img.onload = ()=> setupCanvas(); img.src = `${state.pages.find(p=>p.index===pageIndex).image}`;
		const coords = await fetchJSON(`/api/qc/${state.letter}/page/${pageIndex}/coords${baseQS()}`); state.pageCoords[pageIndex] = coords.coords || []; state.originalPageCoords[pageIndex] = JSON.parse(JSON.stringify(state.pageCoords[pageIndex])); state.drawMode = false; renderBoxes(); fetchJSON(`/api/qc/${state.letter}/page/${pageIndex}/reasoning${baseQS()}`).then(r => setReasoning(r.reasoning || ''));
	}

	function setupCanvas(){ const img = qs('#page-image'); const canvas = qs('#page-canvas'); canvas.width = img.clientWidth; canvas.height = img.clientHeight; canvas.style.width = img.clientWidth + 'px'; canvas.style.height = img.clientHeight + 'px'; state.scale = img.clientWidth / img.naturalWidth; bindCanvasEvents(); renderBoxes(); }
	function getCoord(b, keyIndex){ const keys = ['x1','y1','x2','y2']; const k = keys[keyIndex]; return (b && (b[k] !== undefined)) ? b[k] : (Array.isArray(b) ? b[keyIndex] : undefined); }
	function renderBoxes(){ const canvas = qs('#page-canvas'); const ctx = canvas.getContext('2d'); ctx.clearRect(0,0,canvas.width,canvas.height); const boxes = state.drawMode ? state.drawRects : (state.pageCoords[state.currentPage]||[]); const colors = ['red','blue','green','orange','purple','yellow','cyan','magenta','lime','pink','brown','gray','navy','olive','maroon','teal','silver','gold']; boxes.forEach((b, i)=>{ const color = colors[i % colors.length]; const x1 = Math.round(getCoord(b,0) * state.scale); const y1 = Math.round(getCoord(b,1) * state.scale); const x2 = Math.round(getCoord(b,2) * state.scale); const y2 = Math.round(getCoord(b,3) * state.scale); if([x1,y1,x2,y2].every(n => Number.isFinite(n))){ ctx.strokeStyle = color; ctx.lineWidth = 2; ctx.strokeRect(x1, y1, x2 - x1, y2 - y1); if(state.highlightBoxIndex===i){ ctx.save(); ctx.strokeStyle = '#ff0'; ctx.lineWidth = 4; ctx.strokeRect(x1-2, y1-2, (x2 - x1)+4, (y2 - y1)+4); ctx.restore(); const pane = qs('#view-1 .qc-pane'); if(pane){ pane.scrollTop = Math.max(0, y1 - 40); } setTimeout(()=>{ state.highlightBoxIndex = null; }, 800); } } }); }
	function bindCanvasEvents(){ const canvas = qs('#page-canvas'); canvas.onmousedown = (e)=>{ const rect = canvas.getBoundingClientRect(); const x = (e.clientX - rect.left) / state.scale; const y = (e.clientY - rect.top) / state.scale; if(!state.drawMode){ state.drawMode = true; state.drawRects = []; setStatus('Draw mode: hold mouse to drag a box; Ctrl+Enter to apply; ESC to cancel; Backspace to undo last'); } state.drawStart = {x, y}; state.drawRects.push({x1: x, y1: y, x2: x, y2: y, temp:true}); renderBoxes(); }; canvas.onmousemove = (e)=>{ if(!state.drawMode || !state.drawStart) return; const rect = canvas.getBoundingClientRect(); const x = (e.clientX - rect.left) / state.scale; const y = (e.clientY - rect.top) / state.scale; const x1 = Math.round(Math.min(state.drawStart.x, x)); const y1 = Math.round(Math.min(state.drawStart.y, y)); const x2 = Math.round(Math.max(state.drawStart.x, x)); const y2 = Math.round(Math.max(state.drawStart.y, y)); if(state.drawRects.length){ state.drawRects[state.drawRects.length-1] = {x1,y1,x2,y2, temp:true}; } renderBoxes(); }; canvas.onmouseup = (e)=>{ if(!state.drawMode || !state.drawStart) return; const rect = canvas.getBoundingClientRect(); const x = (e.clientX - rect.left) / state.scale; const y = (e.clientY - rect.top) / state.scale; const x1 = Math.round(Math.min(state.drawStart.x, x)); const y1 = Math.round(Math.min(state.drawStart.y, y)); const x2 = Math.round(Math.max(state.drawStart.x, x)); const y2 = Math.round(Math.max(state.drawStart.y, y)); state.drawStart = null; if(state.drawRects.length){ state.drawRects[state.drawRects.length-1] = {x1,y1,x2,y2}; } renderBoxes(); }; canvas.onclick = (e)=>{ if(state.drawMode) return; const rect = canvas.getBoundingClientRect(); const x = (e.clientX - rect.left) / state.scale; const y = (e.clientY - rect.top) / state.scale; const boxes = state.pageCoords[state.currentPage]||[]; for(let j=0;j<boxes.length;j++){ const bx1 = getCoord(boxes[j],0), by1 = getCoord(boxes[j],1), bx2 = getCoord(boxes[j],2), by2 = getCoord(boxes[j],3); if(x>=bx1 && x<=bx2 && y>=by1 && y<=by2){ const idx = state.chunks.findIndex(ch => ch.page_index===state.currentPage && ch.chunk_index===j); if(idx>=0){ state.idx = idx; switchView(2); } return; } } }; }

	function applyDrawnBoxes(){ if(state.currentPage==null || !state.drawMode || !state.drawRects.length) return; setStatus('Updating chunks for page...'); const coords = state.drawRects.map(b => [b.x1,b.y1,b.x2,b.y2]); fetch(`/api/qc/${state.letter}/page/${state.currentPage}/update_chunks${baseQS()}`, {method:'POST', headers:{'Content-Type':'application/json'}, body: JSON.stringify({coords})}).then(()=>{ kickPoll(); }).catch(()=>{}); setStatus('Queued'); state.drawMode = false; state.drawRects = []; }

	function renderFullView(){ if(!state.letter) return; qs('#full-pdf').src = `/samples/${state.letter}.pdf`; const iframe = qs('#full-html-de'); const editor = qs('#full-de-editor'); fetchJSON(`/api/qc/${state.letter}/html_de${baseQS()}`).then(d => { if(state.fullEdit){ editor.classList.remove('qc-hidden'); iframe.classList.add('qc-hidden'); editor.value = d.html || ''; editor.focus(); } else { editor.classList.add('qc-hidden'); iframe.classList.remove('qc-hidden'); iframe.srcdoc = d.html || ''; } }); }
	function toggleFullEdit(){ state.fullEdit = !state.fullEdit; renderFullView(); }
	function saveFullDE(){ const html = qs('#full-de-editor').value; fetch(`/api/qc/${state.letter}/html_de/save${baseQS()}`, {method:'POST', headers:{'Content-Type':'application/json'}, body: JSON.stringify({html})}).then(()=>renderFullView()).catch(()=>{}); }
	async function renderTranslateView(){ if(!state.letter) return; const de = await fetchJSON(`/api/qc/${state.letter}/html_de${baseQS()}`); const en = await fetchJSON(`/api/qc/${state.letter}/html_en${baseQS()}`); const deEditor = qs('#de-editor'); const deRender = qs('#de-render'); const enEditor = qs('#en-editor'); const enRender = qs('#en-render'); if(state.editDE){ deEditor.classList.remove('qc-hidden'); deRender.classList.add('qc-hidden'); deEditor.value = de.html || ''; deEditor.focus(); } else { deEditor.classList.add('qc-hidden'); deRender.classList.remove('qc-hidden'); deRender.srcdoc = de.html || ''; } if(state.editEN){ enEditor.classList.remove('qc-hidden'); enRender.classList.add('qc-hidden'); enEditor.value = en.html || ''; enEditor.focus(); } else { enEditor.classList.add('qc-hidden'); enRender.classList.remove('qc-hidden'); enRender.srcdoc = en.html || ''; } }
	function saveDE(){ const html = qs('#de-editor').value; fetch(`/api/qc/${state.letter}/html_de/save${baseQS()}`, {method:'POST', headers:{'Content-Type':'application/json'}, body: JSON.stringify({html})}).then(()=>renderTranslateView()).catch(()=>{}); }
	function saveEN(){ const html = qs('#en-editor').value; fetch(`/api/qc/${state.letter}/html_en/save${baseQS()}`, {method:'POST', headers:{'Content-Type':'application/json'}, body: JSON.stringify({html})}).then(()=>renderTranslateView()).catch(()=>{}); }
	function toggleEditDE(){ state.editDE = !state.editDE; renderTranslateView(); }
	function toggleEditEN(){ state.editEN = !state.editEN; renderTranslateView(); }
	function retryDE(){ setStatus('Retranslating...'); fetch(`/api/qc/${state.letter}/translate${baseQS()}`, {method:'POST'}).catch(()=>{}); setStatus('Queued'); pollTasks(); renderTranslateView(); }
	function feedbackDE(){ const fb = prompt('Feedback for translate:'); if(fb==null) return; setStatus('Retranslating with feedback...'); fetch(`/api/qc/${state.letter}/translate${baseQS()}`, {method:'POST', headers:{'Content-Type':'application/json'}, body: JSON.stringify({feedback: fb})}).catch(()=>{}); setStatus('Queued'); pollTasks(); renderTranslateView(); }

	function reloadFull(feedback){
		setStatus(feedback ? 'Rebuilding with comment...' : 'Rebuilding...');
		fetch(`/api/qc/${state.letter}/rebuild_html${baseQS()}`, {
			method: 'POST',
			headers: {'Content-Type':'application/json'},
			body: JSON.stringify({feedback: feedback || ''})
		}).catch(()=>{});
		setStatus('Queued');
		pollTasks();
	}

	async function init(){
		qsa('[id^=view-btn-]').forEach(btn => { btn.onclick = ()=> switchView(parseInt(btn.id.split('-').pop(),10)); });
		bindGlobalKeys(); bindChunkNav();
		qs('#qc-rebuild').onclick = rebuildUnifiedAll; qs('#qc-translate').onclick = translateEN;
		const translateAllBtn = document.createElement('button'); translateAllBtn.textContent = 'Translate ALL'; translateAllBtn.className = 'small-btn'; translateAllBtn.onclick = translateAll; qs('.qc-toolbar').insertBefore(translateAllBtn, qs('#qc-status'));
		qs('#tasks-button').onclick = toggleTasksPanel;
		document.addEventListener('click', (e)=>{ const btn = qs('#tasks-button'); const panel = qs('#tasks-panel'); if(!panel.contains(e.target) && e.target !== btn && !btn.contains(e.target)){ state.tasksOpen = false; panel.classList.add('qc-hidden'); } });
		const baseSel = qs('#qc-bases'); const bases = await fetchJSON('/api/qc/bases'); baseSel.innerHTML = ''; bases.forEach(b => { const o = document.createElement('option'); o.value = b; o.textContent = b; baseSel.appendChild(o); }); state.base = (bases.includes('outputs_gpt-5') ? 'outputs_gpt-5' : (bases[0] || null)); if(state.base) baseSel.value = state.base; baseSel.onchange = async ()=>{ state.base = baseSel.value || null; await refreshLetters(); pollTasks(); };
		await refreshLetters();
		qs('#chunk-editor').addEventListener('blur', ()=>{ if(state.modeEdit) saveEdit(); });
		qs('#de-editor').addEventListener('blur', ()=>{ if(state.editDE) saveDE(); });
		qs('#en-editor').addEventListener('blur', ()=>{ if(state.editEN) saveEN(); });
		qs('#btn-edit-de').onclick = toggleEditDE;
		qs('#btn-retry-de').onclick = retryDE;
		qs('#btn-feedback-de').onclick = feedbackDE;
		qs('#btn-edit-en').onclick = toggleEditEN;
		qs('#btn-full-edit').onclick = toggleFullEdit;
		qs('#btn-full-render').onclick = ()=>{ state.fullEdit=false; renderFullView(); };
		// Approve PDF button click
		const approveBtn = qs('#btn-approve-pdf'); if(approveBtn){ approveBtn.onclick = approvePDF; }
		const btnReload = qs('#btn-full-reload'); if(btnReload){ btnReload.onclick = ()=> reloadFull(''); }
		const btnReloadComment = qs('#btn-full-reload-comment'); if(btnReloadComment){ btnReloadComment.onclick = ()=>{ const fb = prompt('Comment for rebuild:') || ''; reloadFull(fb); }; }
		pollTasks();
	}

	async function refreshLetters(){ const sel = qs('#qc-letters'); const letters = await fetchJSON(`/api/qc/letters${baseQS()}`); sel.innerHTML = ''; letters.forEach(l => { const o = document.createElement('option'); o.value = l; o.textContent = l; sel.appendChild(o); }); if(letters.length){ sel.value = letters[0]; await loadLetter(letters[0]); } sel.onchange = ()=> loadLetter(sel.value); }
	function renderBoxesView(){ if(state.currentPage==null && state.pages.length){ selectPage(state.pages[0].index); } }
	init();
})(); 