(function initThemeEarly(){
  try {
    const stored = localStorage.getItem('theme');
    if (stored) document.documentElement.setAttribute('data-bs-theme', stored);
  } catch {}
})();

const csrfToken = document.querySelector('meta[name="csrf-token"]').getAttribute('content') || '';

async function api(method, url, body, isForm = false) {
  const headers = isForm ? { 'X-CSRFToken': csrfToken } : { 'Content-Type': 'application/json', 'X-CSRFToken': csrfToken };
  const opts = { method, headers };
  if (body && !isForm) opts.body = JSON.stringify(body);
  if (body && isForm) opts.body = body;
  const res = await fetch(url, opts);
  if (!res.ok) throw new Error(await res.text());
  try { return await res.json(); } catch { return {}; }
}

function splitList(str) { return (str || '').split(',').map(s => s.trim()).filter(Boolean); }
function joinList(list) { return (list || []).join(', '); }

let currentGroupId = null;
let tagMode = 'OR'; // OR | AND
let orderKey = 'noteOrder';

function getOrder() { try { return JSON.parse(localStorage.getItem(orderKey) || '[]'); } catch { return []; } }
function setOrder(ids) { try { localStorage.setItem(orderKey, JSON.stringify(ids)); } catch {} }
function applyOrder(list) {
  const order = getOrder();
  if (!order.length) return list;
  const map = new Map(list.map(n => [n.id, n]));
  const ordered = order.map(id => map.get(id)).filter(Boolean);
  const rest = list.filter(n => !order.includes(n.id));
  return [...ordered, ...rest];
}

function getPinned() { try { return new Set(JSON.parse(localStorage.getItem('pinnedNotes') || '[]')); } catch { return new Set(); } }
function setPinned(set) { try { localStorage.setItem('pinnedNotes', JSON.stringify(Array.from(set))); } catch {}
}

async function loadGroups() {
  const groups = await api('GET', '/api/groups');
  const list = document.getElementById('groupList');
  if (!list) return;
  list.innerHTML = '';
  const allItem = document.createElement('li');
  allItem.className = 'list-group-item bg-transparent d-flex justify-content-between align-items-center';
  allItem.textContent = 'Все'
  allItem.style.cursor = 'pointer';
  allItem.onclick = () => { currentGroupId = null; loadNotes(); };
  list.appendChild(allItem);
  (groups || []).forEach(g => {
    const li = document.createElement('li');
    li.className = 'list-group-item bg-transparent d-flex justify-content-between align-items-center gap-2';
    const nameBtn = document.createElement('span');
    nameBtn.textContent = g.name;
    nameBtn.style.cursor = 'pointer';
    nameBtn.onclick = () => { currentGroupId = g.id; loadNotes(); };
    const actions = document.createElement('div');
    actions.className = 'btn-group btn-group-sm';
    const rename = document.createElement('button');
    rename.className = 'btn btn-outline-secondary';
    rename.textContent = '✎';
    rename.title = 'Переименовать';
    rename.onclick = async (e) => {
      e.stopPropagation();
      const newName = prompt('Новое имя группы', g.name);
      if (!newName || newName.trim() === g.name) return;
      await api('PATCH', `/api/groups/${g.id}`, { name: newName.trim() });
      await loadGroups();
    };
    const del = document.createElement('button');
    del.className = 'btn btn-outline-danger';
    del.textContent = '✕';
    del.title = 'Удалить группу';
    del.onclick = async (e) => {
      e.stopPropagation();
      if (!confirm('Удалить группу? Заметки останутся, просто уберется связь.')) return;
      await api('DELETE', `/api/groups/${g.id}`);
      if (currentGroupId === g.id) currentGroupId = null;
      await loadGroups();
      await loadNotes();
    };
    actions.appendChild(rename);
    actions.appendChild(del);
    li.appendChild(nameBtn);
    li.appendChild(actions);
    list.appendChild(li);
  });
}

async function addGroupPrompt() {
  const name = prompt('Название группы');
  if (!name) return;
  await api('POST', '/api/groups', { name });
  await loadGroups();
}

function ensurePreviewModal() {
  let modal = document.getElementById('previewModal');
  if (!modal) {
    modal = document.createElement('div');
    modal.id = 'previewModal';
    modal.className = 'modal fade';
    modal.innerHTML = `
<div class="modal-dialog modal-xl modal-dialog-centered">
  <div class="modal-content bg-dark">
    <div class="modal-header border-0">
      <h5 class="modal-title">Предпросмотр</h5>
      <button type="button" class="btn-close btn-close-white" data-bs-dismiss="modal" aria-label="Close"></button>
    </div>
    <div class="modal-body">
      <div id="previewContainer" class="w-100" style="min-height:60vh;">
        <img id="previewImg" src="" class="img-fluid rounded d-none" />
        <iframe id="previewFrame" src="" class="w-100 d-none" style="height:70vh;border:none;"></iframe>
      </div>
    </div>
  </div>
</div>`;
    document.body.appendChild(modal);
  }
}

function openPreview(att) {
  ensurePreviewModal();
  const isImg = /image\//.test(att.mime_type || '') || /\.(png|jpg|jpeg|gif|webp|bmp)$/i.test(att.filename || '');
  const isPdf = /pdf$/i.test(att.mime_type || '') || /\.pdf$/i.test(att.filename || '');
  const isVideo = /video\//.test(att.mime_type || '') || /\.(mp4|mov|webm)$/i.test(att.filename || '');
  const isAudio = /audio\//.test(att.mime_type || '') || /\.(mp3|wav|ogg)$/i.test(att.filename || '');
  const modal = document.getElementById('previewModal');
  const img = modal.querySelector('#previewImg');
  const frame = modal.querySelector('#previewFrame');
  let media = modal.querySelector('#previewMedia');
  if (!media) {
    media = document.createElement('video');
    media.id = 'previewMedia';
    media.className = 'w-100 d-none';
    media.controls = true;
    modal.querySelector('#previewContainer').appendChild(media);
  }
  img.classList.add('d-none');
  frame.classList.add('d-none');
  media.classList.add('d-none');
  if (isImg) {
    img.src = `/api/attachments/${att.id}`;
    img.classList.remove('d-none');
  } else if (isPdf) {
    frame.src = `/api/attachments/${att.id}`;
    frame.classList.remove('d-none');
  } else if (isVideo || isAudio) {
    media.src = `/api/attachments/${att.id}`;
    media.classList.remove('d-none');
  } else {
    window.open(`/api/attachments/${att.id}`, '_blank');
    return;
  }
  const bsModal = new bootstrap.Modal(modal);
  bsModal.show();
}

function buildAttachmentNode(att) {
  const wrap = document.createElement('div');
  wrap.className = 'd-flex align-items-center gap-2 mt-1';
  const link = document.createElement('a');
  link.href = `/api/attachments/${att.id}`;
  link.target = '_blank';
  link.textContent = att.filename || 'file';
  const preview = document.createElement('button');
  preview.className = 'btn btn-sm btn-outline-light';
  preview.textContent = '👁';
  preview.onclick = (e) => openPreview(att);
  const del = document.createElement('button');
  del.className = 'btn btn-sm btn-outline-danger';
  del.textContent = '✕';
  del.onclick = async () => {
    await api('DELETE', `/api/attachments/${att.id}`);
    await loadNotes();
  };
  wrap.appendChild(link);
  wrap.appendChild(preview);
  wrap.appendChild(del);
  return wrap;
}

async function loadNotes() {
  try {
    const q = document.getElementById('search')?.value || '';
    const date = document.getElementById('dateFilter')?.value || '';
    const tags = splitList(document.getElementById('tags')?.value || '');
    const url = new URL('/api/notes', window.location.origin);
    if (q) url.searchParams.set('q', q);
    if (currentGroupId) url.searchParams.set('group_id', currentGroupId);
    if (date) url.searchParams.set('date', date);
    const list = await api('GET', url.pathname + url.search);

    const container = document.getElementById('notes');
    if (!container) return;
    container.innerHTML = '';
    const tpl = document.getElementById('noteCardTpl');

    const tagMatch = (noteTags) => {
      if (!tags.length) return true;
      const set = new Set(noteTags || []);
      return tagMode === 'AND' ? tags.every(t => set.has(t)) : tags.some(t => set.has(t));
    };

    const filtered = (list || []).filter(n => tagMatch(n.tags));
    const pinSet = getPinned();
    const notes = applyOrder(filtered).sort((a, b) => (pinSet.has(b.id) - pinSet.has(a.id)));

    notes.forEach(n => {
      const node = tpl.content.cloneNode(true);
      const col = node.querySelector('.col-12');
      if (col) col.dataset.noteId = n.id;
      const card = node.querySelector('.note-card');
      if (card) card.dataset.noteId = n.id;
      if (card) {
        const toggleFullscreen = () => {
          card.classList.toggle('enlarged');
          let ov = document.querySelector('.notes-overlay');
          const open = card.classList.contains('enlarged');
          if (open) {
            if (!ov) { ov = document.createElement('div'); ov.className = 'notes-overlay'; document.body.appendChild(ov); }
            document.documentElement.classList.add('note-fullscreen-open');
            ov.onclick = () => { toggleFullscreen(); };
          } else {
            ov && ov.remove();
            document.documentElement.classList.remove('note-fullscreen-open');
          }
        };
        card.addEventListener('dblclick', toggleFullscreen);
        if (pinSet.has(n.id)) card.classList.add('pinned');
      }

      const title = node.querySelector('.title');
      const ql = node.querySelector('.quill-editor');
      const tagInput = node.querySelector('.tagInput');
      const groupInput = node.querySelector('.groupInput');
      const fileInput = node.querySelector('.fileInput');
      const attachments = node.querySelector('.attachments');
      const saveBtn = node.querySelector('.save');
      const delBtn = node.querySelector('.delete');
      const expandBtn = node.querySelector('.expand');
      const pinBtn = document.createElement('button');
      pinBtn.className = 'btn btn-sm btn-outline-warning';
      pinBtn.textContent = 'Pin';

      if (title) title.value = n.title || '';
      if (tagInput) tagInput.value = joinList(n.tags);
      if (groupInput) groupInput.value = joinList((n.groups||[]).map(g => g.name));

      // Init Quill safely
      let quill = null;
      if (window.Quill && ql) {
        quill = new Quill(ql, {
          theme: 'snow',
          modules: { toolbar: [[{ 'font': [] }],[{ 'size': ['small', false, 'large', 'huge'] }],['bold','italic','underline','strike'],[{ 'color': [] }, { 'background': [] }],[{ 'script': 'sub'},{ 'script': 'super' }],[{ 'header': [1,2,3,4,5,6,false] }],[{ 'list': 'ordered'},{ 'list': 'bullet' }],[{ 'indent': '-1'},{ 'indent': '+1' }],[{ 'direction': 'rtl' }],[{ 'align': [] }],['link','blockquote','code-block','clean']] }
        });
        quill.root.innerHTML = n.content || '';
      } else if (ql) {
        // Fallback to contenteditable div
        ql.setAttribute('contenteditable', 'true');
        ql.innerHTML = n.content || '';
      }

      const getContent = () => quill ? quill.root.innerHTML : (ql ? ql.innerHTML : '');

      const debouncedSave = debounce(async () => {
        await api('PATCH', `/api/notes/${n.id}`, {
          title: title ? title.value : n.title,
          content: getContent(),
          tags: splitList(tagInput ? tagInput.value : ''),
          groups: splitList(groupInput ? groupInput.value : '')
        });
      }, 600);

      title && title.addEventListener('input', debouncedSave);
      quill && quill.on('text-change', debouncedSave);
      if (!quill && ql) ql.addEventListener('input', debouncedSave);
      tagInput && tagInput.addEventListener('input', debouncedSave);
      groupInput && groupInput.addEventListener('input', debouncedSave);

      saveBtn && saveBtn.addEventListener('click', async () => {
        await api('PATCH', `/api/notes/${n.id}`, {
          title: title ? title.value : n.title,
          content: getContent(),
          tags: splitList(tagInput ? tagInput.value : ''),
          groups: splitList(groupInput ? groupInput.value : '')
        });
        await loadNotes();
      });

      delBtn && delBtn.addEventListener('click', async () => {
        if (!confirm('Удалить заметку?')) return;
        await api('DELETE', `/api/notes/${n.id}`);
        await loadNotes();
      });

      expandBtn && expandBtn.addEventListener('click', () => {
        if (!card) return;
        card.dispatchEvent(new Event('dblclick'));
      });

      // Pin toggle
      pinBtn.addEventListener('click', () => {
        const s = getPinned();
        if (s.has(n.id)) s.delete(n.id); else s.add(n.id);
        setPinned(s);
        loadNotes();
      });

      // Context menu
      if (card) {
        card.addEventListener('contextmenu', (e) => {
          e.preventDefault();
          document.querySelectorAll('.note-context').forEach(el => el.remove());
          const m = document.createElement('div');
          m.className = 'note-context';
          m.style.left = e.pageX + 'px';
          m.style.top = e.pageY + 'px';
          const items = [
            { label: 'Закрепить/Открепить', action: () => pinBtn.click() },
            { label: 'Дублировать', action: async () => { await api('POST', '/api/notes', { title: (title ? title.value : n.title) + ' (копия)', content: getContent(), tags: splitList(tagInput ? tagInput.value : ''), groups: splitList(groupInput ? groupInput.value : '') }); loadNotes(); } },
            { label: 'Развернуть', action: () => expandBtn && expandBtn.click() },
            { label: 'Удалить', action: () => delBtn && delBtn.click() },
          ];
          items.forEach(it => { const d = document.createElement('div'); d.className = 'item'; d.textContent = it.label; d.onclick = () => { it.action(); m.remove(); }; m.appendChild(d); });
          document.body.appendChild(m);
          const close = () => { m.remove(); document.removeEventListener('click', close); };
          setTimeout(() => document.addEventListener('click', close), 0);
        });
      }

      if (fileInput) fileInput.addEventListener('change', async (e) => {
        const files = Array.from(e.target.files || []);
        for (const f of files) {
          const fd = new FormData();
          fd.append('file', f);
          await api('POST', `/api/notes/${n.id}/attachments`, fd, true);
        }
        await loadNotes();
      });

      // Drag & Drop
      if (card) {
        card.addEventListener('dragstart', (e) => {
          e.dataTransfer.effectAllowed = 'move';
          e.dataTransfer.setData('text/plain', String(n.id));
          card.classList.add('opacity-50');
        });
        card.addEventListener('dragend', () => card.classList.remove('opacity-50'));
        card.addEventListener('dragover', (e) => { e.preventDefault(); });
        card.addEventListener('drop', (e) => {
          e.preventDefault();
          const draggedId = Number(e.dataTransfer.getData('text/plain'));
          const targetId = n.id;
          if (!draggedId || draggedId === targetId) return;
          const ids = Array.from(container.querySelectorAll('.note-card')).map(el => Number(el.dataset.noteId));
          const from = ids.indexOf(draggedId);
          const to = ids.indexOf(targetId);
          if (from === -1 || to === -1) return;
          ids.splice(to, 0, ids.splice(from, 1)[0]);
          setOrder(ids);
          loadNotes();
        });
      }

      // attachments render
      (n.attachments || []).forEach(att => attachments && attachments.appendChild(buildAttachmentNode(att)));

      const head = node.querySelector('.note-card-head .d-flex.align-items-center.gap-2');
      if (head) head.prepend(pinBtn);
      container.appendChild(node);
    });
  } catch (err) {
    console.error('Failed to load notes', err);
  }
}

function debounce(fn, ms) { let t; return function(...args) { clearTimeout(t); t = setTimeout(() => fn.apply(this, args), ms); }; }

async function createNote() {
  await api('POST', '/api/notes', { title: 'Новая заметка', content: '', tags: [] });
  await loadNotes();
}

function initThemeToggle() {
  const toggle = document.getElementById('themeToggle');
  const apply = (theme) => { document.documentElement.setAttribute('data-bs-theme', theme); try { localStorage.setItem('theme', theme); } catch {} };
  const stored = (function(){ try { return localStorage.getItem('theme'); } catch { return null; } })() || 'dark';
  apply(stored);
  if (toggle) {
    toggle.checked = stored === 'dark';
    toggle.addEventListener('change', () => apply(toggle.checked ? 'dark' : 'light'));
  }
}

function initTagControls() {
  const input = document.getElementById('tags');
  const modeBtn = document.getElementById('tagMode');
  if (modeBtn) {
    modeBtn.addEventListener('click', () => {
      tagMode = tagMode === 'OR' ? 'AND' : 'OR';
      modeBtn.textContent = tagMode;
      loadNotes();
    });
  }
  input && input.addEventListener('input', () => loadNotes());
}

function initHotkeys() {
  document.addEventListener('keydown', (e) => {
    if ((e.ctrlKey || e.metaKey) && e.key.toLowerCase() === 's') {
      e.preventDefault();
      const firstSave = document.querySelector('.save');
      if (firstSave) firstSave.click();
    }
    if ((e.ctrlKey || e.metaKey) && e.key.toLowerCase() === 'n') {
      e.preventDefault();
      const btn = document.getElementById('newNote');
      if (btn) btn.click();
    }
  });
}

window.addEventListener('DOMContentLoaded', () => {
  const newBtn = document.getElementById('newNote');
  const dateFilter = document.getElementById('dateFilter');
  const addGroup = document.getElementById('addGroup');
  if (newBtn) newBtn.addEventListener('click', () => createNote());
  if (dateFilter) dateFilter.addEventListener('change', () => loadNotes());
  if (addGroup) addGroup.addEventListener('click', () => addGroupPrompt());
  if (document.getElementById('notes')) {
    initThemeToggle();
    initTagControls();
    initHotkeys();
    loadGroups().then(loadNotes);
  }
});
