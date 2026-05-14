(function () {
  const STORAGE_KEY = 'map4d_tools_action_logs_v1';

  const ACTION_LABELS = {
    import_poi: 'Import POI',
    delete_poi: 'Delete POI',
    geocode: 'Geocode địa chỉ',
    reverse_geocode: 'Reverse Geocode',
    nearby_search: 'Nearby Search',
    other: 'Khác'
  };

  function safeParse(raw, fallback) {
    try { return JSON.parse(raw); } catch { return fallback; }
  }

  function isAllowedAction(action) {
    return ['import_poi', 'delete_poi', 'geocode', 'reverse_geocode', 'nearby_search'].includes(action);
  }

  function readLogs() {
    const logs = safeParse(localStorage.getItem(STORAGE_KEY), []);
    if (!Array.isArray(logs)) return [];
    // Dashboard chỉ theo dõi 3 nhóm thao tác: Import POI, Delete POI và Geocode.
    return logs.filter(log => isAllowedAction(log?.action));
  }

  function writeLogs(logs) {
    const allowedLogs = Array.isArray(logs) ? logs.filter(log => isAllowedAction(log?.action)) : [];
    localStorage.setItem(STORAGE_KEY, JSON.stringify(allowedLogs.slice(0, 2000)));
  }

  function notifyLogUpdated(log) {
    try { window.dispatchEvent(new CustomEvent('map4d-log-updated', { detail: log || null })); } catch {}
    try { window.parent && window.parent.postMessage({ type: 'map4d-log-updated', detail: log || null }, '*'); } catch {}
    try {
      if (!window.__map4dLogBroadcastChannel) window.__map4dLogBroadcastChannel = new BroadcastChannel('map4d-tools-log-channel');
      window.__map4dLogBroadcastChannel.postMessage({ type: 'map4d-log-updated', detail: log || null });
    } catch {}
  }

  function uid() {
    return 'log_' + Date.now().toString(36) + '_' + Math.random().toString(36).slice(2, 9);
  }

  function normalizeText(value) {
    return String(value || '').trim();
  }

  function normalizeAreaSearchText(value) {
    return normalizeText(value)
      .toUpperCase()
      .normalize('NFD')
      .replace(/[\u0300-\u036f]/g, '')
      .replace(/Đ/g, 'D')
      .replace(/[^A-Z0-9]+/g, ' ')
      .replace(/\s+/g, ' ')
      .trim();
  }

  function getAreaRules() {
    return [
      { area: 'ĐN', patterns: ['DA NANG', 'TP DA NANG', 'THANH PHO DA NANG', 'DANANG', 'TPDN', 'DN'] },
      { area: 'QN', patterns: ['QUANG NAM', 'TINH QUANG NAM'] },
      { area: 'QNg', patterns: ['QUANG NGAI', 'TINH QUANG NGAI'] },
      { area: 'QNi', patterns: ['QUANG NINH', 'TINH QUANG NINH'] },
      { area: 'HCM', patterns: ['HO CHI MINH', 'TP HCM', 'TPHCM', 'THANH PHO HO CHI MINH', 'SAI GON', 'SAIGON'] },
      { area: 'HN', patterns: ['HA NOI', 'HANOI', 'THU DO HA NOI'] },
      { area: 'BD', patterns: ['BINH DUONG', 'TINH BINH DUONG'] },
      { area: 'DNai', patterns: ['DONG NAI', 'TINH DONG NAI'] },
      { area: 'CT', patterns: ['CAN THO', 'TP CAN THO', 'THANH PHO CAN THO'] },
      { area: 'HP', patterns: ['HAI PHONG', 'TP HAI PHONG'] },
      { area: 'HUE', patterns: ['THUA THIEN HUE', 'HUE'] },
      { area: 'KH', patterns: ['KHANH HOA', 'NHA TRANG'] },
      { area: 'BRVT', patterns: ['BA RIA VUNG TAU', 'VUNG TAU'] },
      { area: 'LA', patterns: ['LONG AN'] },
      { area: 'TG', patterns: ['TIEN GIANG'] },
      { area: 'AG', patterns: ['AN GIANG'] },
      { area: 'KG', patterns: ['KIEN GIANG'] },
      { area: 'LD', patterns: ['LAM DONG', 'DA LAT'] },
      { area: 'BTh', patterns: ['BINH THUAN'] },
      { area: 'BT', patterns: ['BEN TRE'] },
      { area: 'TN', patterns: ['TAY NINH'] },
      { area: 'NA', patterns: ['NGHE AN'] },
      { area: 'TH', patterns: ['THANH HOA'] },
      { area: 'HD', patterns: ['HAI DUONG'] },
      { area: 'HY', patterns: ['HUNG YEN'] },
      { area: 'VP', patterns: ['VINH PHUC'] },
      { area: 'BN', patterns: ['BAC NINH'] },
      { area: 'BG', patterns: ['BAC GIANG'] }
    ];
  }

  function inferAreaFromText(text) {
    const raw = normalizeText(text);
    if (!raw) return 'N/A';

    const target = ` ${normalizeAreaSearchText(raw)} `;
    for (const rule of getAreaRules()) {
      if (rule.patterns.some(pattern => target.includes(` ${normalizeAreaSearchText(pattern)} `))) return rule.area;
    }
    return 'Khác';
  }

  function getAddressTextFromRow(row) {
    const source = row && row.rowData ? row.rowData : row;
    if (!source || typeof source !== 'object') return '';

    const addressKeys = [];
    Object.keys(source).forEach(key => {
      const normalizedKey = String(key || '')
        .toLowerCase()
        .normalize('NFD')
        .replace(/[\u0300-\u036f]/g, '')
        .replace(/đ/g, 'd')
        .replace(/[^a-z0-9]/g, '');

      if (
        ['address', 'oldaddress', 'diachi', 'diachicu'].includes(normalizedKey) ||
        normalizedKey.includes('address') ||
        normalizedKey.includes('oldaddress') ||
        normalizedKey.includes('diachi')
      ) {
        addressKeys.push(key);
      }
    });

    return addressKeys
      .map(key => normalizeText(source[key]))
      .filter(Boolean)
      .join(' ');
  }

  function inferAreaFromRows(rows, maxRows = 200) {
    if (!Array.isArray(rows) || rows.length === 0) return 'N/A';

    const score = new Map();
    const limitedRows = rows.slice(0, maxRows);
    limitedRows.forEach(row => {
      const addressText = getAddressTextFromRow(row);
      if (!addressText) return;
      const area = inferAreaFromText(addressText);
      if (!area || area === 'N/A' || area === 'Khác') return;
      score.set(area, (score.get(area) || 0) + 1);
    });

    if (!score.size) return 'N/A';
    return [...score.entries()].sort((a, b) => b[1] - a[1])[0][0];
  }

  function inferAreaFromFileAndRows(fileName, rows) {
    const fileArea = inferAreaFromText(fileName);
    if (fileArea && fileArea !== 'N/A' && fileArea !== 'Khác') return fileArea;

    const rowArea = inferAreaFromRows(rows);
    if (rowArea && rowArea !== 'N/A' && rowArea !== 'Khác') return rowArea;

    return fileArea || rowArea || 'N/A';
  }

  function actionLabel(action) {
    return ACTION_LABELS[action] || ACTION_LABELS.other;
  }

  function addLog(input) {
    const now = new Date();
    const fileName = normalizeText(input.fileName);
    const message = normalizeText(input.message);
    const explicitArea = normalizeText(input.area);
    const areaFromRows = Array.isArray(input.rows) ? inferAreaFromFileAndRows(fileName, input.rows) : '';
    const area = explicitArea || (areaFromRows && areaFromRows !== 'N/A' && areaFromRows !== 'Khác' ? areaFromRows : inferAreaFromText(`${fileName} ${message}`));
    const poiCount = Number(input.poiCount ?? input.total ?? 0) || 0;
    const successCount = Number(input.successCount ?? input.success ?? 0) || 0;
    const errorCount = Number(input.errorCount ?? input.error ?? 0) || 0;
    const action = input.action || 'other';
    if (!isAllowedAction(action)) {
      console.info('Bỏ qua log không thuộc nhóm Import/Delete/Geocode:', action, input);
      return null;
    }

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
    notifyLogUpdated(log);
    return log;
  }

  function buildDefaultMessage(action, area, poiCount, successCount, errorCount) {
    const label = actionLabel(action);
    const count = poiCount ? `${poiCount.toLocaleString('vi-VN')} dòng` : '';
    const scope = area && area !== 'N/A' ? area : '';
    const result = successCount || errorCount ? ` · OK: ${successCount}, lỗi: ${errorCount}` : '';
    return [label, scope, count].filter(Boolean).join(' ') + result;
  }

  function clearLogs() {
    localStorage.removeItem(STORAGE_KEY);
    notifyLogUpdated(null);
  }

  function removeLog(id) {
    writeLogs(readLogs().filter(log => log.id !== id));
    notifyLogUpdated(null);
  }

  function addSampleLogs() {
    const today = new Date();
    const yesterday = new Date(Date.now() - 86400000);
    const twoDaysAgo = new Date(Date.now() - 2 * 86400000);
    const sample = [
      { createdAt: today.toISOString(), dateKey: today.toISOString().slice(0, 10), action: 'import_poi', actionLabel: 'Import POI', area: 'ĐN', poiCount: 1000, successCount: 995, errorCount: 5, fileName: 'mapped_categories_result (1).xlsx', message: 'Import file ĐN 1.000 POI' },
      { createdAt: today.toISOString(), dateKey: today.toISOString().slice(0, 10), action: 'delete_poi', actionLabel: 'Delete POI', area: 'QN', poiCount: 500, successCount: 498, errorCount: 2, fileName: 'mapped_categories_result (2).xlsx', message: 'Del POI QN 500 POI' },
      { createdAt: yesterday.toISOString(), dateKey: yesterday.toISOString().slice(0, 10), action: 'geocode', actionLabel: 'Geocode địa chỉ', area: 'ĐN', poiCount: 1000, successCount: 995, errorCount: 5, fileName: 'mapped_categories_result (1).xlsx', message: 'Geocode địa chỉ ĐN 1.000 dòng' },
      { createdAt: yesterday.toISOString(), dateKey: yesterday.toISOString().slice(0, 10), action: 'reverse_geocode', actionLabel: 'Reverse Geocode', area: 'QN', poiCount: 500, successCount: 498, errorCount: 2, fileName: 'reverse_input.xlsx', message: 'Reverse geocode QN 500 dòng' },
      { createdAt: twoDaysAgo.toISOString(), dateKey: twoDaysAgo.toISOString().slice(0, 10), action: 'nearby_search', actionLabel: 'Nearby Search', area: 'HCM', poiCount: 2350, successCount: 2350, errorCount: 0, fileName: 'nearby_search_hcm.xlsx', message: 'Tìm POI xung quanh HCM 2.350 dòng' }
    ];
    const existing = readLogs();
    const logs = sample.map(item => ({
      id: uid(),
      actionLabel: item.actionLabel || actionLabel(item.action),
      status: item.errorCount > 0 ? 'warning' : 'success',
      source: 'sample',
      meta: {},
      ...item
    })).concat(existing);
    writeLogs(logs);
    notifyLogUpdated(null);
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
    inferAreaFromRows,
    inferAreaFromFileAndRows,
    getAddressTextFromRow,
    actionLabel
  };
  window.recordMap4DLog = addLog;
})();
