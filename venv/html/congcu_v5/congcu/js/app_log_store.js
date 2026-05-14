(function () {
  const STORAGE_KEY = 'map4d_tools_action_logs_v1';

  const ACTION_LABELS = {
    import_poi: 'Import POI',
    delete_poi: 'Delete POI',
    geocode: 'Geocode',
    route_simulation: 'Route Simulation',
    other: 'Khác'
  };

  function safeParse(raw, fallback) {
    try { return JSON.parse(raw); } catch { return fallback; }
  }

  function readLogs() {
    const logs = safeParse(localStorage.getItem(STORAGE_KEY), []);
    return Array.isArray(logs) ? logs : [];
  }

  function writeLogs(logs) {
    localStorage.setItem(STORAGE_KEY, JSON.stringify(logs.slice(0, 2000)));
  }

  function uid() {
    return 'log_' + Date.now().toString(36) + '_' + Math.random().toString(36).slice(2, 9);
  }

  function normalizeText(value) {
    return String(value || '').trim();
  }

  function inferAreaFromText(text) {
    const raw = normalizeText(text);
    const upper = raw.toUpperCase()
      .normalize('NFD')
      .replace(/[\u0300-\u036f]/g, '')
      .replace(/Đ/g, 'D');

    const rules = [
      { area: 'ĐN', patterns: [' DA NANG', 'DANANG', 'DN_', '_DN', '-DN', ' DN ', 'ĐN', 'TPDN'] },
      { area: 'QN', patterns: [' QUANG NAM', 'QUANGNAM', 'QN_', '_QN', '-QN', ' QN '] },
      { area: 'HCM', patterns: [' HO CHI MINH', 'HCM', 'TPHCM', 'SAI GON', 'SAIGON'] },
      { area: 'HN', patterns: [' HA NOI', 'HANOI', 'HN_', '_HN', '-HN', ' HN '] },
      { area: 'BD', patterns: [' BINH DUONG', 'BINHDUONG', 'BD_', '_BD', '-BD', ' BD '] },
      { area: 'DNai', patterns: [' DONG NAI', 'DONGNAI', 'DNAI'] },
      { area: 'CT', patterns: [' CAN THO', 'CANTHO', 'CT_', '_CT', '-CT', ' CT '] }
    ];

    const target = ` ${upper} `;
    for (const rule of rules) {
      if (rule.patterns.some(p => target.includes(p))) return rule.area;
    }
    return raw ? 'Khác' : 'N/A';
  }

  function actionLabel(action) {
    return ACTION_LABELS[action] || ACTION_LABELS.other;
  }

  function addLog(input) {
    const now = new Date();
    const fileName = normalizeText(input.fileName);
    const message = normalizeText(input.message);
    const area = normalizeText(input.area) || inferAreaFromText(`${fileName} ${message}`);
    const poiCount = Number(input.poiCount ?? input.total ?? 0) || 0;
    const successCount = Number(input.successCount ?? input.success ?? 0) || 0;
    const errorCount = Number(input.errorCount ?? input.error ?? 0) || 0;
    const action = input.action || 'other';

    const log = {
      id: uid(),
      createdAt: input.createdAt || now.toISOString(),
      dateKey: input.dateKey || now.toISOString().slice(0, 10),
      action,
      actionLabel: input.actionLabel || actionLabel(action),
      area,
      poiCount,
      successCount,
      errorCount,
      status: input.status || (errorCount > 0 ? 'warning' : 'success'),
      fileName,
      source: input.source || 'client',
      message: message || buildDefaultMessage(action, area, poiCount, successCount, errorCount),
      meta: input.meta || {}
    };

    const logs = readLogs();
    logs.unshift(log);
    writeLogs(logs);
    window.dispatchEvent(new CustomEvent('map4d-log-updated', { detail: log }));
    return log;
  }

  function buildDefaultMessage(action, area, poiCount, successCount, errorCount) {
    const label = actionLabel(action);
    const count = poiCount ? `${poiCount.toLocaleString('vi-VN')} POI` : '';
    const scope = area && area !== 'N/A' ? area : '';
    const result = successCount || errorCount ? ` · OK: ${successCount}, lỗi: ${errorCount}` : '';
    return [label, scope, count].filter(Boolean).join(' ') + result;
  }

  function clearLogs() {
    localStorage.removeItem(STORAGE_KEY);
    window.dispatchEvent(new CustomEvent('map4d-log-updated'));
  }

  function removeLog(id) {
    writeLogs(readLogs().filter(log => log.id !== id));
    window.dispatchEvent(new CustomEvent('map4d-log-updated'));
  }

  function addSampleLogs() {
    const today = new Date();
    const yesterday = new Date(Date.now() - 86400000);
    const twoDaysAgo = new Date(Date.now() - 2 * 86400000);
    const sample = [
      { createdAt: today.toISOString(), dateKey: today.toISOString().slice(0, 10), action: 'import_poi', area: 'ĐN', poiCount: 1000, successCount: 995, errorCount: 5, fileName: 'DN_import_1000_POI.xlsx', message: 'Import file ĐN 1000 POI' },
      { createdAt: today.toISOString(), dateKey: today.toISOString().slice(0, 10), action: 'delete_poi', area: 'QN', poiCount: 500, successCount: 498, errorCount: 2, fileName: 'QN_delete_500_POI.xlsx', message: 'Del POI QN 500 POI' },
      { createdAt: yesterday.toISOString(), dateKey: yesterday.toISOString().slice(0, 10), action: 'import_poi', area: 'HCM', poiCount: 2350, successCount: 2350, errorCount: 0, fileName: 'HCM_batch_POI.xlsx', message: 'Import POI HCM 2350 POI' },
      { createdAt: twoDaysAgo.toISOString(), dateKey: twoDaysAgo.toISOString().slice(0, 10), action: 'delete_poi', area: 'ĐN', poiCount: 120, successCount: 120, errorCount: 0, fileName: 'DN_remove_old_POI.xlsx', message: 'Del POI ĐN 120 POI' }
    ];
    const existing = readLogs();
    const logs = sample.map(item => ({
      id: uid(),
      actionLabel: actionLabel(item.action),
      status: item.errorCount > 0 ? 'warning' : 'success',
      source: 'sample',
      meta: {},
      ...item
    })).concat(existing);
    writeLogs(logs);
    window.dispatchEvent(new CustomEvent('map4d-log-updated'));
  }

  function exportCSV(logs = readLogs()) {
    const headers = ['createdAt', 'actionLabel', 'area', 'poiCount', 'successCount', 'errorCount', 'status', 'fileName', 'message'];
    const escapeCell = (value) => {
      const str = String(value ?? '');
      if (/[",\n]/.test(str)) return '"' + str.replace(/"/g, '""') + '"';
      return str;
    };
    return '\uFEFF' + [headers.join(','), ...logs.map(log => headers.map(h => escapeCell(log[h])).join(','))].join('\n');
  }

  window.Map4DLogStore = {
    STORAGE_KEY,
    readLogs,
    writeLogs,
    addLog,
    clearLogs,
    removeLog,
    addSampleLogs,
    exportCSV,
    inferAreaFromText,
    actionLabel
  };
  window.recordMap4DLog = addLog;
})();
