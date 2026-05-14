const $ = id => document.getElementById(id);

function formatNumber(value) {
  return Number(value || 0).toLocaleString('vi-VN');
}

function formatDate(dateKey) {
  const d = new Date(`${dateKey}T00:00:00`);
  if (Number.isNaN(d.getTime())) return dateKey;
  return d.toLocaleDateString('vi-VN', { weekday: 'long', year: 'numeric', month: '2-digit', day: '2-digit' });
}

function formatTime(iso) {
  const d = new Date(iso);
  if (Number.isNaN(d.getTime())) return '--:--';
  return d.toLocaleTimeString('vi-VN', { hour: '2-digit', minute: '2-digit', second: '2-digit' });
}

function getFilters() {
  return {
    from: $('filterFrom').value,
    to: $('filterTo').value,
    action: $('filterAction').value,
    keyword: $('filterKeyword').value.trim().toLowerCase()
  };
}

function applyFilters(logs) {
  const f = getFilters();
  return logs.filter(log => {
    if (f.from && log.dateKey < f.from) return false;
    if (f.to && log.dateKey > f.to) return false;
    if (f.action !== 'all' && log.action !== f.action) return false;
    if (f.keyword) {
      const haystack = [log.actionLabel, log.area, log.fileName, log.message, log.status].join(' ').toLowerCase();
      if (!haystack.includes(f.keyword)) return false;
    }
    return true;
  });
}

function groupByDate(logs) {
  return logs.reduce((acc, log) => {
    const key = log.dateKey || String(log.createdAt || '').slice(0, 10) || 'unknown';
    if (!acc[key]) acc[key] = [];
    acc[key].push(log);
    return acc;
  }, {});
}

function renderStats(logs) {
  $('statTotalLogs').textContent = formatNumber(logs.length);
  $('statTotalPoi').textContent = formatNumber(logs.reduce((sum, log) => sum + Number(log.poiCount || 0), 0));
  $('statImportPoi').textContent = formatNumber(logs.filter(log => log.action === 'import_poi').reduce((sum, log) => sum + Number(log.poiCount || 0), 0));
  $('statDeletePoi').textContent = formatNumber(logs.filter(log => log.action === 'delete_poi').reduce((sum, log) => sum + Number(log.poiCount || 0), 0));
}

function escapeHtml(value) {
  return String(value ?? '').replace(/[&<>'"]/g, ch => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', "'": '&#39;', '"': '&quot;' }[ch]));
}

function renderTimeline(logs) {
  const container = $('logTimeline');
  $('resultSummary').textContent = `Đang hiển thị ${formatNumber(logs.length)} log phù hợp bộ lọc.`;
  if (!logs.length) {
    container.innerHTML = '<div class="empty">Chưa có log. Bạn có thể bấm “Tạo log mẫu” hoặc chạy Import/Delete POI để tự ghi log.</div>';
    return;
  }

  const grouped = groupByDate(logs);
  const days = Object.keys(grouped).sort((a, b) => b.localeCompare(a));
  container.innerHTML = days.map(day => {
    const items = grouped[day].sort((a, b) => String(b.createdAt).localeCompare(String(a.createdAt)));
    const totalPoi = items.reduce((sum, log) => sum + Number(log.poiCount || 0), 0);
    return `
      <article class="day-group">
        <header class="day-header">
          <h3>${escapeHtml(formatDate(day))}</h3>
          <span>${formatNumber(items.length)} log · ${formatNumber(totalPoi)} POI</span>
        </header>
        <div class="log-list">
          ${items.map(log => `
            <div class="log-row">
              <div class="log-time">${escapeHtml(formatTime(log.createdAt))}</div>
              <div><span class="pill ${escapeHtml(log.action)}">${escapeHtml(log.actionLabel || log.action)}</span></div>
              <div class="area">${escapeHtml(log.area || 'N/A')}</div>
              <div class="count">${formatNumber(log.poiCount)} POI</div>
              <div class="msg">
                <strong>${escapeHtml(log.message || '')}</strong>
                <small>${escapeHtml(log.fileName || '')} · OK: ${formatNumber(log.successCount)} · Lỗi: ${formatNumber(log.errorCount)} · <span class="status ${escapeHtml(log.status)}">${escapeHtml(log.status)}</span></small>
              </div>
              <button class="delete-log" data-id="${escapeHtml(log.id)}" title="Xóa log này">×</button>
            </div>
          `).join('')}
        </div>
      </article>`;
  }).join('');

  container.querySelectorAll('.delete-log').forEach(btn => {
    btn.addEventListener('click', () => {
      if (confirm('Xóa log này?')) {
        Map4DLogStore.removeLog(btn.dataset.id);
        render();
      }
    });
  });
}

function render() {
  const allLogs = Map4DLogStore.readLogs();
  const logs = applyFilters(allLogs);
  renderStats(logs);
  renderTimeline(logs);
}

function downloadCsv() {
  const logs = applyFilters(Map4DLogStore.readLogs());
  const blob = new Blob([Map4DLogStore.exportCSV(logs)], { type: 'text/csv;charset=utf-8;' });
  const url = URL.createObjectURL(blob);
  const a = document.createElement('a');
  a.href = url;
  a.download = `map4d_action_logs_${new Date().toISOString().slice(0, 10)}.csv`;
  document.body.appendChild(a);
  a.click();
  document.body.removeChild(a);
  URL.revokeObjectURL(url);
}

function addManualLog() {
  const action = $('manualAction').value;
  const area = $('manualArea').value.trim();
  const poiCount = Number($('manualPoiCount').value || 0);
  const fileName = $('manualFileName').value.trim();
  const message = $('manualMessage').value.trim() || `${Map4DLogStore.actionLabel(action)} ${area} ${poiCount} POI`;
  Map4DLogStore.addLog({ action, area, poiCount, successCount: poiCount, errorCount: 0, fileName, message, source: 'manual' });
  $('manualMessage').value = '';
  render();
}

function initDefaultDateRange() {
  const today = new Date();
  const sevenDaysAgo = new Date(Date.now() - 6 * 86400000);
  $('filterTo').value = today.toISOString().slice(0, 10);
  $('filterFrom').value = sevenDaysAgo.toISOString().slice(0, 10);
}

document.addEventListener('DOMContentLoaded', () => {
  initDefaultDateRange();
  ['filterFrom', 'filterTo', 'filterAction', 'filterKeyword'].forEach(id => {
    $(id).addEventListener(id === 'filterKeyword' ? 'input' : 'change', render);
  });
  $('btnSeedSample').addEventListener('click', () => { Map4DLogStore.addSampleLogs(); render(); });
  $('btnExportCsv').addEventListener('click', downloadCsv);
  $('btnClearLogs').addEventListener('click', () => { if (confirm('Xóa toàn bộ log trên trình duyệt này?')) { Map4DLogStore.clearLogs(); render(); } });
  $('btnAddManualLog').addEventListener('click', addManualLog);
  window.addEventListener('map4d-log-updated', render);
  render();
});
