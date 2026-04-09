/* ═══════════════════════════════════════════════
   VinLex AI — PDF Management UI
═══════════════════════════════════════════════ */

// ── Drag and drop ──────────────────────────────

const dropZone = document.getElementById('drop-zone');

dropZone.addEventListener('dragover', (e) => {
  e.preventDefault();
  dropZone.classList.add('drag-over');
});

dropZone.addEventListener('dragleave', () => {
  dropZone.classList.remove('drag-over');
});

dropZone.addEventListener('drop', (e) => {
  e.preventDefault();
  dropZone.classList.remove('drag-over');
  const files = e.dataTransfer.files;
  if (files.length > 0) {
    uploadFile(files[0]);
  }
});

function handleFileSelect(event) {
  const file = event.target.files[0];
  if (file) uploadFile(file);
  event.target.value = ''; // reset so same file can be re-uploaded
}

// ── Upload ─────────────────────────────────────

async function uploadFile(file) {
  if (!file.name.toLowerCase().endsWith('.pdf')) {
    showUploadStatus('❌ Chỉ chấp nhận file PDF.', 'error');
    return;
  }
  if (file.size > 50 * 1024 * 1024) {
    showUploadStatus('❌ File quá lớn. Tối đa 50MB.', 'error');
    return;
  }

  showUploadStatus(`⏳ Đang tải lên "${file.name}"...`, 'loading');

  const formData = new FormData();
  formData.append('file', file);

  try {
    const res = await fetch('/api/pdfs/upload', {
      method: 'POST',
      body: formData,
    });
    if (!res.ok) {
      const err = await res.json();
      showUploadStatus(`❌ Lỗi: ${err.error || 'Upload thất bại'}`, 'error');
      return;
    }
    const pdf = await res.json();
    showUploadStatus(`✅ Đã tải lên "${pdf.filename}". Đang xử lý...`, 'success');

    // Add row to table and start polling
    addPDFRow(pdf);
    pollStatus(pdf.id);

  } catch (e) {
    showUploadStatus('❌ Không thể kết nối đến máy chủ.', 'error');
    console.error('Upload error:', e);
  }
}

// ── Status polling ─────────────────────────────

function pollStatus(pdfId) {
  const interval = setInterval(async () => {
    try {
      const res = await fetch(`/api/pdfs/${pdfId}/status`);
      if (!res.ok) { clearInterval(interval); return; }
      const data = await res.json();

      if (data.status !== 'indexing') {
        clearInterval(interval);
        updateStatusBadge(pdfId, data.status);
        updatePDFCounts(pdfId);
        showUploadStatus('', '');
      }
    } catch (e) {
      clearInterval(interval);
    }
  }, 2000);
}

async function updatePDFCounts(pdfId) {
  // Refresh the full list to get updated chunk/page counts
  const res = await fetch('/api/pdfs');
  if (!res.ok) return;
  const pdfs = await res.json();
  const pdf = pdfs.find(p => p.id === pdfId);
  if (!pdf) return;

  const row = document.getElementById(`row-${pdfId}`);
  if (!row) return;
  const subline = row.querySelector('p.text-xs');
  if (subline) {
    subline.textContent = `${pdf.page_count} trang · ${pdf.chunk_count} đoạn`;
  }

  // Update count badge
  const count = pdfs.length;
  const countEl = document.getElementById('pdf-count');
  if (countEl) countEl.textContent = `(${count} tài liệu)`;
}

function updateStatusBadge(pdfId, status) {
  const cell = document.getElementById(`status-${pdfId}`);
  if (!cell) return;

  if (status === 'ready') {
    cell.innerHTML = `<span class="badge-ready"><span class="pulse-dot"></span> Sẵn sàng</span>`;
  } else if (status === 'error') {
    cell.innerHTML = `<span class="badge-error">⚠ Lỗi xử lý</span>`;
  }
}

// ── Add row to table ───────────────────────────

function addPDFRow(pdf) {
  const tbody = document.getElementById('pdf-tbody');

  // Remove empty state row if present
  const emptyRow = document.getElementById('empty-table-row');
  if (emptyRow) emptyRow.remove();

  const kb = Math.round(pdf.size_bytes / 1024);
  const date = pdf.uploaded_at ? pdf.uploaded_at.substring(0, 10) : '';

  const tr = document.createElement('tr');
  tr.id = `row-${pdf.id}`;
  tr.className = 'border-t border-gray-50 hover:bg-gray-50 transition-colors';
  tr.innerHTML = `
    <td class="px-6 py-4">
      <div class="flex items-center gap-2">
        <span class="text-lg">📄</span>
        <div>
          <p class="font-medium text-gray-800">${escapeHtml(pdf.filename)}</p>
          <p class="text-xs text-gray-400">0 trang · 0 đoạn</p>
        </div>
      </div>
    </td>
    <td class="px-6 py-4 text-gray-500">${kb} KB</td>
    <td class="px-6 py-4 text-gray-500">${date}</td>
    <td class="px-6 py-4" id="status-${pdf.id}">
      <span class="badge-indexing"><span class="pulse-dot"></span> Đang xử lý...</span>
    </td>
    <td class="px-6 py-4">
      <button onclick="deletePDF('${pdf.id}', '${escapeHtml(pdf.filename)}')"
              class="text-red-500 hover:text-red-700 text-sm font-medium hover:bg-red-50 px-3 py-1.5 rounded-lg transition-colors">
        Xóa
      </button>
    </td>
  `;

  tbody.insertBefore(tr, tbody.firstChild);
}

// ── Delete ─────────────────────────────────────

async function deletePDF(pdfId, filename) {
  if (!confirm(`Xóa tài liệu "${filename}"?\n\nHành động này không thể hoàn tác.`)) return;

  try {
    const res = await fetch(`/api/pdfs/${pdfId}`, { method: 'DELETE' });
    if (!res.ok) {
      alert('Không thể xóa tài liệu. Vui lòng thử lại.');
      return;
    }
    const row = document.getElementById(`row-${pdfId}`);
    if (row) row.remove();

    // Update count
    const tbody = document.getElementById('pdf-tbody');
    const count = tbody.querySelectorAll('tr[id^="row-"]').length;
    const countEl = document.getElementById('pdf-count');
    if (countEl) countEl.textContent = `(${count} tài liệu)`;

    // Show empty state if no PDFs
    if (count === 0) {
      const emptyTr = document.createElement('tr');
      emptyTr.id = 'empty-table-row';
      emptyTr.innerHTML = `
        <td colspan="5" class="px-6 py-12 text-center text-gray-400">
          <div class="text-3xl mb-2">📭</div>
          <p>Chưa có tài liệu nào được tải lên.</p>
        </td>
      `;
      tbody.appendChild(emptyTr);
    }

  } catch (e) {
    alert('Lỗi kết nối. Vui lòng thử lại.');
    console.error('Delete error:', e);
  }
}

// ── Load PDFs ──────────────────────────────────

async function loadPDFs() {
  try {
    const res = await fetch('/api/pdfs');
    if (!res.ok) return;
    const pdfs = await res.json();

    const tbody = document.getElementById('pdf-tbody');
    tbody.innerHTML = '';

    const countEl = document.getElementById('pdf-count');
    if (countEl) countEl.textContent = `(${pdfs.length} tài liệu)`;

    if (pdfs.length === 0) {
      tbody.innerHTML = `
        <tr id="empty-table-row">
          <td colspan="5" class="px-6 py-12 text-center text-gray-400">
            <div class="text-3xl mb-2">📭</div>
            <p>Chưa có tài liệu nào được tải lên.</p>
          </td>
        </tr>
      `;
      return;
    }

    pdfs.forEach(pdf => {
      const kb = Math.round(pdf.size_bytes / 1024);
      const date = pdf.uploaded_at ? pdf.uploaded_at.substring(0, 10) : '';
      let statusHtml = '';
      if (pdf.status === 'ready') {
        statusHtml = `<span class="badge-ready"><span class="pulse-dot"></span> Sẵn sàng</span>`;
      } else if (pdf.status === 'indexing') {
        statusHtml = `<span class="badge-indexing"><span class="pulse-dot"></span> Đang xử lý...</span>`;
        pollStatus(pdf.id);
      } else {
        statusHtml = `<span class="badge-error" title="${escapeHtml(pdf.error || '')}">⚠ Lỗi</span>`;
      }

      const tr = document.createElement('tr');
      tr.id = `row-${pdf.id}`;
      tr.className = 'border-t border-gray-50 hover:bg-gray-50 transition-colors';
      tr.innerHTML = `
        <td class="px-6 py-4">
          <div class="flex items-center gap-2">
            <span class="text-lg">📄</span>
            <div>
              <p class="font-medium text-gray-800">${escapeHtml(pdf.filename)}</p>
              <p class="text-xs text-gray-400">${pdf.page_count} trang · ${pdf.chunk_count} đoạn</p>
            </div>
          </div>
        </td>
        <td class="px-6 py-4 text-gray-500">${kb} KB</td>
        <td class="px-6 py-4 text-gray-500">${date}</td>
        <td class="px-6 py-4" id="status-${pdf.id}">${statusHtml}</td>
        <td class="px-6 py-4">
          <button onclick="deletePDF('${pdf.id}', '${escapeHtml(pdf.filename)}')"
                  class="text-red-500 hover:text-red-700 text-sm font-medium hover:bg-red-50 px-3 py-1.5 rounded-lg transition-colors">
            Xóa
          </button>
        </td>
      `;
      tbody.appendChild(tr);
    });
  } catch (e) {
    console.error('Failed to load PDFs:', e);
  }
}

// ── Upload status message ──────────────────────

function showUploadStatus(msg, type) {
  const el = document.getElementById('upload-status');
  if (!msg) { el.classList.add('hidden'); return; }
  el.classList.remove('hidden');
  const colors = {
    loading: 'text-blue-700 bg-blue-50 border-blue-100',
    success: 'text-green-700 bg-green-50 border-green-100',
    error:   'text-red-700 bg-red-50 border-red-100',
  };
  el.className = `mt-4 text-sm px-4 py-3 rounded-lg border ${colors[type] || ''}`;
  el.textContent = msg;
}

// ── Helpers ────────────────────────────────────

function escapeHtml(str) {
  return String(str)
    .replace(/&/g, '&amp;')
    .replace(/</g, '&lt;')
    .replace(/>/g, '&gt;')
    .replace(/"/g, '&quot;')
    .replace(/'/g, '&#39;');
}
