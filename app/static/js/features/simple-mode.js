/** Simple Mode Create UI */
const AMBIENT_ROTATION_MS = 5 * 60 * 1000;
const MAX_REFERENCE_SIZE = 20 * 1024 * 1024;

const state = {
  profiles: [], profileId: 'realism', ratio: '1:1', quality: 'standard', batch: 1,
  improve: true, referenceData: null, referenceUrl: null, ambient: [], ambientLayer: 'a',
  ambientTimer: null, runId: null, pollTimer: null, lastOutput: null, assistantHistory: []
};
const el = {};

const PROFILE_UI = {
  realism: {
    title: 'Realism', subtitle: 'Фотореализм, портреты и кинематографичный свет',
    strengths: ['Люди и естественная кожа', 'Фотооптика и глубина резкости', 'Архитектура и свет'],
    glyph: '<svg viewBox="0 0 48 48" class="model-glyph" aria-hidden="true"><path d="M11 15.5h7l3-4h6l3 4h7a4 4 0 0 1 4 4V34a4 4 0 0 1-4 4H11a4 4 0 0 1-4-4V19.5a4 4 0 0 1 4-4Z"/><circle cx="24" cy="27" r="7.5"/><path d="M24 22.5a4.5 4.5 0 0 1 4.5 4.5"/></svg>'
  },
  anime: {
    title: 'Anime', subtitle: 'Персонажи, иллюстрация и выразительная стилизация',
    strengths: ['Лица и эмоции', 'Чистый рисунок и цвет', 'Динамичные персонажи'],
    glyph: '<svg viewBox="0 0 48 48" class="model-glyph" aria-hidden="true"><path d="M12 29c2.7-8.2 8-12.3 16-12.3 3.7 0 6.8.8 9.4 2.3-2.1 10.2-7.8 15.3-17.1 15.3-3.3 0-6.1-.8-8.3-2.3"/><path d="M14.2 17.5 11 9l8.4 4.4M31.8 14.4 38 9l-1.3 8.7M19.3 25.5h.1M29 24.8h.1M20.5 30.2c2.2 1.5 4.7 1.7 7.2.6M38 12.5h5M40.5 10v5"/></svg>'
  },
  universal: {
    title: 'Universal', subtitle: 'Сложные сцены, текст в кадре и свободные идеи',
    strengths: ['Понимание длинных запросов', 'Несколько объектов в сцене', 'Текст и разные стили'],
    glyph: '<svg viewBox="0 0 48 48" class="model-glyph" aria-hidden="true"><path d="m24 7 13 8v18l-13 8-13-8V15l13-8Z"/><path d="m11 15 13 8 13-8M24 23v18m-6.8-21.8 13.6 8.3M30.8 19.2l-13.6 8.3"/></svg>'
  }
};

function bind() {
  const ids = [
    'studio-layout','prompt-input','prompt-box-container','prompt-clear-btn','ai-improve-checkbox','ai-improve-control',
    'reference-file-input','reference-preview-container','reference-preview-img','reference-filename','remove-reference-btn',
    'model-cards-container','aspect-ratio-selector','quality-selector','batch-selector','create-button','create-progress-fill',
    'create-progress-text','generation-error-banner','error-title','error-message','error-tech-text','error-tech-details','error-dismiss-btn',
    'canvas-surface','canvas-generating-state','canvas-generating-status','canvas-result-state','canvas-result-img',
    'btn-action-download','btn-action-remix','btn-action-copy-prompt','ambient-layer-a','ambient-layer-b',
    'ai-assistant-toggle','ai-assistant-backdrop','ai-assistant-drawer','assistant-close-btn','assistant-new-chat-btn',
    'assistant-messages-container','assistant-chat-form','assistant-chat-input','assistant-send-btn'
  ];
  ids.forEach(id => { el[id.replaceAll('-', '_')] = document.getElementById(id); });
}
const E = name => el[name.replaceAll('-', '_')];

async function init() {
  bind(); restore(); wire(); assistantWelcome(); resizePrompt();
  try {
    const r = await fetch('/api/simple/bootstrap');
    if (!r.ok) throw new Error(String(r.status));
    const data = await r.json();
    state.profiles = Array.isArray(data.profiles) ? data.profiles : [];
    state.ambient = Array.isArray(data.ambient_candidates) ? data.ambient_candidates : [];
    const def = data.default_profile_id;
    if (def && state.profiles.some(p => p.id === def)) state.profileId = def;
    else if (!state.profiles.some(p => p.id === state.profileId) && state.profiles[0]) state.profileId = state.profiles[0].id;
    renderModels(); syncRatios(); syncQuality(); syncAi(data.ai_status || {}); startAmbient();
  } catch (err) {
    console.error(err);
    showError('Не удалось открыть создание', 'Профили генерации не загрузились. Обновите страницу или проверьте настройки приложения.');
  }
}

function restore() {
  try {
    const v = localStorage.getItem('cmv_simple_ai_improve'); if (v !== null) state.improve = v === 'true';
    const q = localStorage.getItem('cmv_simple_quality'); if (q) state.quality = q;
    const b = Number(localStorage.getItem('cmv_simple_batch')); if (b >= 1 && b <= 4) state.batch = b;
    const r = localStorage.getItem('cmv_simple_ratio'); if (r) state.ratio = r;
  } catch (_) {}
  if (E('ai-improve-checkbox')) E('ai-improve-checkbox').checked = state.improve;
}
function save(k,v){ try { localStorage.setItem(k,String(v)); } catch (_) {} }
function profile(){ return state.profiles.find(p => p.id === state.profileId) || null; }

function syncAi(status) {
  const available = Boolean(status.available && status.has_text);
  E('ai-improve-control')?.classList.toggle('is-unavailable', !available);
  if (E('ai-improve-checkbox')) {
    E('ai-improve-checkbox').disabled = !available;
    E('ai-improve-checkbox').checked = available && state.improve;
  }
  if (E('ai-improve-control')) E('ai-improve-control').title = available
    ? 'Автоматически адаптировать запрос под выбранную модель'
    : 'Текстовый ИИ-профиль не настроен. Запрос будет отправлен без AI-улучшения.';
}

function startAmbient() {
  if (!state.ambient.length) return;
  const pick = () => state.ambient[Math.floor(Math.random() * state.ambient.length)];
  setAmbient(pick());
  if (state.ambient.length > 1) state.ambientTimer = setInterval(() => setAmbient(pick()), AMBIENT_ROTATION_MS);
}
function setAmbient(item) {
  const url = typeof item === 'string' ? item : item?.preview_url || item?.thumbnail_url;
  if (!url || !E('ambient-layer-a') || !E('ambient-layer-b')) return;
  const img = new Image();
  img.onload = () => {
    const next = state.ambientLayer === 'a' ? E('ambient-layer-b') : E('ambient-layer-a');
    const prev = state.ambientLayer === 'a' ? E('ambient-layer-a') : E('ambient-layer-b');
    next.style.backgroundImage = `url("${String(url).replaceAll('"','%22')}")`;
    next.classList.add('active'); prev.classList.remove('active');
    state.ambientLayer = state.ambientLayer === 'a' ? 'b' : 'a';
  };
  img.src = url;
}

function renderModels() {
  const root = E('model-cards-container'); if (!root) return; root.replaceChildren();
  state.profiles.forEach(p => {
    const ui = PROFILE_UI[p.id] || {title:p.name || p.id, subtitle:p.tagline || p.description || '', strengths:(p.strengths || []).slice(0,3), glyph:fallbackGlyph()};
    const ready = p.health?.status === 'ready';
    const card = document.createElement('button');
    card.type='button'; card.className='model-card'; card.dataset.profileId=p.id; card.setAttribute('role','radio');
    card.classList.toggle('active', p.id === state.profileId); card.setAttribute('aria-checked', String(p.id === state.profileId));
    const strengths=(ui.strengths || []).slice(0,3).map(x=>`<li>${esc(x)}</li>`).join('');
    const vram=p.vram_rec_gb ? `комфортно от ${esc(p.vram_rec_gb)} GB VRAM` : '';
    card.innerHTML=`<span class="model-card-art">${ui.glyph}</span><span class="model-card-copy"><span class="model-card-title-row"><strong class="model-card-name">${esc(ui.title)}</strong><span class="model-health ${ready?'is-ready':'needs-setup'}">${ready?'Готова':'Нужна настройка'}</span></span><span class="model-card-subtitle">${esc(ui.subtitle)}</span>${vram?`<span class="model-card-vram">${vram}</span>`:''}</span><span class="model-card-details" aria-hidden="true"><span class="model-details-kicker">Подходит для</span><ul>${strengths}</ul>${p.technical_model?`<span class="model-technical-name">${esc(p.technical_model)}</span>`:''}</span>`;
    card.addEventListener('click',()=>selectModel(p.id)); root.appendChild(card);
  });
}
function fallbackGlyph(){ return '<svg viewBox="0 0 48 48" class="model-glyph" aria-hidden="true"><path d="M24 7 38 15v18L24 41 10 33V15l14-8Z"/><circle cx="24" cy="24" r="6"/></svg>'; }
function selectModel(id){ state.profileId=id; document.querySelectorAll('.model-card').forEach(c=>{const a=c.dataset.profileId===id;c.classList.toggle('active',a);c.setAttribute('aria-checked',String(a));}); syncRatios(); syncQuality(); }

function syncRatios() {
  const allowed=new Set((profile()?.aspect_ratios || []).map(x=>x.ratio));
  if (allowed.size && !allowed.has(state.ratio)) state.ratio=profile().aspect_ratios[0].ratio;
  E('aspect-ratio-selector')?.querySelectorAll('[data-ratio]').forEach(b=>{const ok=!allowed.size||allowed.has(b.dataset.ratio);const a=ok&&b.dataset.ratio===state.ratio;b.disabled=!ok;b.classList.toggle('active',a);b.setAttribute('aria-checked',String(a));});
}
function syncQuality() {
  const presets=profile()?.quality_presets || {};
  const keys=Object.keys(presets); if(keys.length && !presets[state.quality]) state.quality=presets.standard?'standard':keys[0];
  E('quality-selector')?.querySelectorAll('[data-quality]').forEach(b=>{const q=b.dataset.quality,ok=!keys.length||Boolean(presets[q]),a=ok&&q===state.quality;b.disabled=!ok;b.classList.toggle('active',a);b.setAttribute('aria-checked',String(a));const m=b.querySelector('.quality-meta');if(m&&presets[q]?.steps)m.textContent=`${presets[q].steps} шагов`;});
}

function wire() {
  E('create-button')?.addEventListener('click', create);
  E('error-dismiss-btn')?.addEventListener('click', dismissError);
  E('prompt-input')?.addEventListener('input',()=>{resizePrompt(); if(E('prompt-clear-btn'))E('prompt-clear-btn').hidden=!E('prompt-input').value.trim();});
  E('prompt-clear-btn')?.addEventListener('click',()=>{E('prompt-input').value='';E('prompt-input').dispatchEvent(new Event('input'));E('prompt-input').focus();});
  E('ai-improve-checkbox')?.addEventListener('change',e=>{state.improve=e.target.checked;save('cmv_simple_ai_improve',state.improve);});
  E('aspect-ratio-selector')?.querySelectorAll('[data-ratio]').forEach(b=>b.addEventListener('click',()=>{if(b.disabled)return;state.ratio=b.dataset.ratio;save('cmv_simple_ratio',state.ratio);syncRatios();}));
  E('quality-selector')?.querySelectorAll('[data-quality]').forEach(b=>b.addEventListener('click',()=>{if(b.disabled)return;state.quality=b.dataset.quality;save('cmv_simple_quality',state.quality);syncQuality();}));
  E('batch-selector')?.querySelectorAll('[data-batch]').forEach(b=>{const n=Number(b.dataset.batch);setBatchState(b,n===state.batch);b.addEventListener('click',()=>{state.batch=n;save('cmv_simple_batch',n);E('batch-selector').querySelectorAll('[data-batch]').forEach(x=>setBatchState(x,Number(x.dataset.batch)===n));});});
  E('reference-file-input')?.addEventListener('change',e=>{const f=e.target.files?.[0];if(f)addReference(f);});
  wireDrop(); E('remove-reference-btn')?.addEventListener('click',clearReference);
  E('btn-action-download')?.addEventListener('click',download); E('btn-action-copy-prompt')?.addEventListener('click',copyPrompt); E('btn-action-remix')?.addEventListener('click',()=>{canvas('idle');E('prompt-input')?.focus();});
  E('ai-assistant-toggle')?.addEventListener('click',openAssistant); E('ai-assistant-backdrop')?.addEventListener('click',closeAssistant); E('assistant-close-btn')?.addEventListener('click',closeAssistant); E('assistant-new-chat-btn')?.addEventListener('click',resetAssistant); E('assistant-chat-form')?.addEventListener('submit',assistantSend);
  E('assistant-chat-input')?.addEventListener('input',resizeAssistant); E('assistant-chat-input')?.addEventListener('keydown',e=>{if(e.key==='Enter'&&!e.shiftKey){e.preventDefault();E('assistant-chat-form')?.requestSubmit();}});
  window.addEventListener('keydown',e=>{if((e.ctrlKey||e.metaKey)&&e.key==='Enter'){e.preventDefault();create();}else if(e.key==='Escape'&&!E('ai-assistant-drawer')?.hidden)closeAssistant();});
}
function setBatchState(b,a){b.classList.toggle('active',a);b.setAttribute('aria-checked',String(a));}
function resizePrompt(){const t=E('prompt-input');if(!t)return;t.style.height='auto';t.style.height=`${Math.max(112,Math.min(t.scrollHeight,240))}px`;t.style.overflowY=t.scrollHeight>240?'auto':'hidden';}
function resizeAssistant(){const t=E('assistant-chat-input');if(!t)return;t.style.height='auto';t.style.height=`${Math.min(t.scrollHeight,132)}px`;}

function wireDrop(){const box=E('prompt-box-container');if(!box)return;['dragenter','dragover'].forEach(n=>box.addEventListener(n,e=>{e.preventDefault();box.classList.add('is-dragging-reference');}));['dragleave','drop'].forEach(n=>box.addEventListener(n,e=>{e.preventDefault();box.classList.remove('is-dragging-reference');}));box.addEventListener('drop',e=>{const f=[...(e.dataTransfer?.files||[])].find(x=>x.type.startsWith('image/'));if(f)addReference(f);});}
function addReference(file){
  if(!file.type.startsWith('image/'))return showError('Не получилось добавить изображение','Выберите PNG, JPEG, WebP или другой формат изображения.');
  if(file.size>MAX_REFERENCE_SIZE)return showError('Изображение слишком большое','Для референса выберите файл меньше 20 МБ.');
  dismissError(); const reader=new FileReader();
  reader.onerror=()=>showError('Не получилось прочитать изображение','Попробуйте другой файл.');
  reader.onload=()=>{if(typeof reader.result!=='string')return;clearReference(false);state.referenceUrl=URL.createObjectURL(file);state.referenceData=reader.result;E('reference-filename').textContent=file.name;const img=E('reference-preview-img');img.onload=()=>{E('reference-preview-container').hidden=false;};img.onerror=()=>{showError('Не получилось показать изображение','Браузер не смог открыть превью этого файла.');clearReference();};img.src=state.referenceUrl;}; reader.readAsDataURL(file);
}
function clearReference(clearInput=true){state.referenceData=null;if(state.referenceUrl){URL.revokeObjectURL(state.referenceUrl);state.referenceUrl=null;}E('reference-preview-img')?.removeAttribute('src');if(E('reference-preview-container'))E('reference-preview-container').hidden=true;if(clearInput&&E('reference-file-input'))E('reference-file-input').value='';}

async function create(){
  if(state.runId)return; const prompt=E('prompt-input')?.value.trim()||'';
  if(!prompt&&!state.referenceData){showError('Нечего создавать','Напишите идею или добавьте изображение-ориентир.');E('prompt-input')?.focus();return;}
  dismissError(); canvas('generating','Подготавливаем запрос…'); button(true,4,'Запуск…');
  try{
    const r=await fetch('/api/simple/generate',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({profile_id:state.profileId,prompt,improve_with_ai:state.improve,aspect_ratio:state.ratio,quality:state.quality,batch_size:state.batch,reference_image:state.referenceData})});
    const data=await r.json().catch(()=>({})); if(!r.ok)throw new Error(data.suggestion||data.error||'Запуск генерации не удался.'); state.runId=data.run_id;if(!state.runId)throw new Error('Сервер не вернул идентификатор генерации.'); poll();
  }catch(err){console.error(err);state.runId=null;button(false);canvas('idle');showError('Не удалось начать генерацию',err.message||'Проверьте настройки генерации.');}
}
function poll(){
  if(state.pollTimer)clearInterval(state.pollTimer);let progress=10;const stages=['Собираем композицию…','Прорабатываем основные формы…','Добавляем свет и детали…','Финальная обработка…'];
  state.pollTimer=setInterval(async()=>{try{const r=await fetch(`/api/simple/runs/${encodeURIComponent(state.runId)}`);if(!r.ok)return;const d=await r.json();if(d.status==='running'||d.status==='queued'){progress=Math.min(progress+6,92);button(true,progress,`${progress}%`);E('canvas-generating-status').textContent=stages[Math.min(stages.length-1,Math.floor(progress/100*stages.length))];return;}if(d.status==='completed'||d.is_complete){stopPoll();button(false);success(d.outputs||[]);return;}if(d.status==='failed'||d.status==='cancelled'){stopPoll();button(false);canvas('idle');showError('Генерация остановилась',d.run?.error||'Процесс был прерван.');}}catch(err){console.warn(err);}},900);
}
function stopPoll(){if(state.pollTimer){clearInterval(state.pollTimer);state.pollTimer=null;}state.runId=null;}
function success(outputs){if(!outputs.length){canvas('idle');return showError('Готово, но результат не найден','Генерация завершилась без доступного изображения.');}const out=outputs[0],url=out.preview_url||out.thumbnail_url;if(!url){canvas('idle');return showError('Результат недоступен','Сервер не вернул ссылку на изображение.');}state.lastOutput=out;E('canvas-result-img').src=url;canvas('result');setAmbient(url);}
function canvas(mode,text=''){E('studio-layout').dataset.view=mode;if(mode==='generating'){E('canvas-generating-state').hidden=false;E('canvas-result-state').hidden=true;E('canvas-generating-status').textContent=text||'Создаём изображение…';E('canvas-surface').classList.remove('has-result');}else if(mode==='result'){E('canvas-generating-state').hidden=true;E('canvas-result-state').hidden=false;E('canvas-surface').classList.add('has-result');}else{E('canvas-generating-state').hidden=true;E('canvas-result-state').hidden=true;E('canvas-surface').classList.remove('has-result');}}
function button(running,percent=0,text='Создание…'){const b=E('create-button');if(!b)return;b.classList.toggle('running',running);b.disabled=running;E('create-progress-fill').style.width=`${running?percent:0}%`;E('create-progress-text').textContent=running?text:'Создание…';}
function download(){const o=state.lastOutput,u=o?.preview_url||o?.thumbnail_url;if(!u)return;const a=document.createElement('a');a.href=u;a.download=o.filename||`creation-${Date.now()}.png`;document.body.appendChild(a);a.click();a.remove();}
async function copyPrompt(){const p=E('prompt-input')?.value.trim();if(!p)return;try{await navigator.clipboard.writeText(p);E('btn-action-copy-prompt')?.classList.add('is-copied');setTimeout(()=>E('btn-action-copy-prompt')?.classList.remove('is-copied'),1200);}catch(_) {}}

function openAssistant(){E('ai-assistant-backdrop').hidden=false;E('ai-assistant-drawer').hidden=false;document.body.classList.add('assistant-open');setTimeout(()=>E('assistant-chat-input')?.focus(),30);}
function closeAssistant(){E('ai-assistant-backdrop').hidden=true;E('ai-assistant-drawer').hidden=true;document.body.classList.remove('assistant-open');}
function resetAssistant(){state.assistantHistory=[];assistantWelcome();E('assistant-chat-input')?.focus();}
function assistantWelcome(){const root=E('assistant-messages-container');if(!root)return;root.innerHTML='<div class="assistant-message assistant-message-system assistant-welcome-card"><span class="assistant-welcome-mark" aria-hidden="true">✦</span><div><strong>Помогу довести идею до хорошего промпта</strong><p>Уточним композицию, свет, настроение или адаптируем идею под референс.</p></div></div><div class="assistant-starter-row"><button type="button" class="assistant-starter" data-starter="Сделай мой текущий запрос более кинематографичным, но не перегружай деталями">Кинематографичнее</button><button type="button" class="assistant-starter" data-starter="Помоги уточнить композицию и свет для моего текущего запроса">Композиция и свет</button><button type="button" class="assistant-starter" data-starter="Сократи мой текущий запрос, сохранив важные детали">Сделать точнее</button></div>';root.querySelectorAll('[data-starter]').forEach(b=>b.addEventListener('click',()=>{E('assistant-chat-input').value=b.dataset.starter;resizeAssistant();E('assistant-chat-input').focus();}));}
async function assistantSend(e){e?.preventDefault();const input=E('assistant-chat-input'),send=E('assistant-send-btn');const text=input?.value.trim();if(!text||!send)return;input.value='';resizeAssistant();appendMessage('user',text);const id=appendMessage('assistant','Думаю…',true);send.disabled=true;try{const r=await fetch('/api/simple/assistant/chat',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({message:text,current_prompt:E('prompt-input')?.value||'',profile_id:state.profileId,history:state.assistantHistory})});const d=await r.json().catch(()=>({}));const msg=document.getElementById(id);if(!r.ok||!d.reply){if(msg)msg.textContent=d.error||'Не удалось получить ответ.';return;}msg?.classList.remove('is-loading');if(msg)msg.textContent=d.reply;state.assistantHistory.push({role:'user',content:text},{role:'assistant',content:d.reply});if(d.suggested_prompt&&msg){const b=document.createElement('button');b.type='button';b.className='assistant-apply-btn';b.textContent='Перенести в поле запроса';b.onclick=()=>{E('prompt-input').value=d.suggested_prompt;E('prompt-input').dispatchEvent(new Event('input'));closeAssistant();E('prompt-input').focus();};msg.appendChild(b);}}catch(_){const msg=document.getElementById(id);if(msg){msg.classList.remove('is-loading');msg.textContent='Связь с ИИ-помощником прервалась.';}}finally{send.disabled=false;}}
function appendMessage(role,text,loading=false){const root=E('assistant-messages-container');if(!root)return'';const d=document.createElement('div'),id=`assistant-message-${Date.now()}-${Math.random().toString(36).slice(2,6)}`;d.id=id;d.className=`assistant-message assistant-message-${role}${loading?' is-loading':''}`;d.textContent=text;root.appendChild(d);root.scrollTop=root.scrollHeight;return id;}

function showError(title,message,tech=''){if(!E('generation-error-banner'))return;E('error-title').textContent=title;E('error-message').textContent=message;E('error-tech-text').textContent=tech;E('error-tech-details').hidden=!tech;E('generation-error-banner').hidden=false;}
function dismissError(){if(E('generation-error-banner'))E('generation-error-banner').hidden=true;}
function esc(v){return String(v??'').replaceAll('&','&amp;').replaceAll('<','&lt;').replaceAll('>','&gt;').replaceAll('"','&quot;').replaceAll("'",'&#039;');}

document.readyState==='loading' ? document.addEventListener('DOMContentLoaded',init) : init();
