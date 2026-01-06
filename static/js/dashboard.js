(function () {
  const config = window.DASHBOARD_CONFIG || {};
  let rows = [];
  let searchInput = null;
  const insightSubline = document.getElementById('insightSubline');
  const deleteModal = document.getElementById('deleteModal');
  const cancelDelete = document.getElementById('cancelDelete');
  const confirmDeleteForm = document.getElementById('confirmDeleteForm');
  const deleteRecordDate = document.getElementById('deleteRecordDate');
  let chartHandlersBound = false;
  let recordsHandlersBound = false;

  const parseDate = (value) => {
    if (!value) return null;
    const parts = value.split('-');
    if (parts.length === 3) {
      return new Date(Number(parts[0]), Number(parts[1]) - 1, Number(parts[2]));
    }
    const parsed = new Date(value);
    return Number.isNaN(parsed.getTime()) ? null : parsed;
  };

  const getLatestDate = () => {
    let latest = null;
    rows.forEach((row) => {
      const rowDate = parseDate(row.dataset.date);
      if (rowDate && (!latest || rowDate > latest)) {
        latest = rowDate;
      }
    });
    return latest;
  };

  const formatSteps = (value) => new Intl.NumberFormat('en-US', { maximumFractionDigits: 0 }).format(value);
  const formatSleep = (value) => Number(value).toFixed(1);

  const applyFilters = () => {
    const query = (searchInput?.value || '').trim().toLowerCase();
    rows.forEach((row) => {
      const searchText = (row.dataset.search || '').toLowerCase();
      const matchesSearch = !query || searchText.includes(query);
      row.style.display = matchesSearch ? '' : 'none';
    });
  };

  const computeInsight = () => {
    if (!insightSubline || rows.length === 0) return;
    const latestDate = getLatestDate();
    if (!latestDate) return;

    const inWindow = (rowDate, start, end) => rowDate && rowDate >= start && rowDate <= end;
    const endCurrent = new Date(latestDate);
    const startCurrent = new Date(latestDate);
    startCurrent.setDate(startCurrent.getDate() - 6);
    const endPrevious = new Date(startCurrent);
    endPrevious.setDate(endPrevious.getDate() - 1);
    const startPrevious = new Date(endPrevious);
    startPrevious.setDate(startPrevious.getDate() - 6);

    const totals = (start, end) => {
      let steps = 0;
      let sleep = 0;
      let count = 0;
      const days = new Set();
      rows.forEach((row) => {
        const rowDate = parseDate(row.dataset.date);
        if (inWindow(rowDate, start, end)) {
          steps += Number(row.dataset.steps || 0);
          sleep += Number(row.dataset.sleep || 0);
          count += 1;
          if (row.dataset.date) {
            days.add(row.dataset.date);
          }
        }
      });
      return { steps, sleep, count, dayCount: days.size };
    };

    const current = totals(startCurrent, endCurrent);
    const previous = totals(startPrevious, endPrevious);
    if (current.dayCount < 3 || previous.dayCount < 3) {
      insightSubline.textContent = 'Compared to last week: not enough data yet.';
      return;
    }

    const currentStepsAvg = current.steps / current.count;
    const previousStepsAvg = previous.steps / previous.count;
    const currentSleepAvg = current.sleep / current.count;
    const previousSleepAvg = previous.sleep / previous.count;
    const deltaSteps = Math.round(currentStepsAvg - previousStepsAvg);
    const deltaSleep = currentSleepAvg - previousSleepAvg;
    const stepSign = deltaSteps >= 0 ? '+' : '-';
    const sleepSign = deltaSleep >= 0 ? '+' : '-';

    insightSubline.textContent = `Compared to last week: ${stepSign}${formatSteps(Math.abs(deltaSteps))} steps/day, sleep ${sleepSign}${formatSleep(Math.abs(deltaSleep))} hrs`;
  };

  const openDeleteModal = (url, recordDate) => {
    if (!deleteModal) return;
    if (confirmDeleteForm) {
      confirmDeleteForm.setAttribute('action', url);
    }
    if (deleteRecordDate) {
      deleteRecordDate.textContent = recordDate || 'this date';
    }
    deleteModal.classList.add('is-visible');
    deleteModal.setAttribute('aria-hidden', 'false');
  };

  const closeDeleteModal = () => {
    if (!deleteModal) return;
    deleteModal.classList.remove('is-visible');
    deleteModal.setAttribute('aria-hidden', 'true');
    if (confirmDeleteForm) {
      confirmDeleteForm.setAttribute('action', '#');
    }
  };

  const showRecordsLoading = (show) => {
    const container = document.querySelector('[data-records-container]');
    if (!container) return;
    const overlay = container.querySelector('.records-overlay');
    if (overlay) {
      overlay.hidden = !show;
    }
  };

  const showRecordsError = (show) => {
    const container = document.querySelector('[data-records-container]');
    if (!container) return;
    const error = container.querySelector('.records-error');
    if (error) {
      error.hidden = !show;
    }
  };

  const updateRecordsUrl = (tableRange) => {
    const url = new URL(window.location.href);
    url.searchParams.set('table_range', tableRange);
    window.history.replaceState({}, '', url.toString());
  };

  const rebindRecentRecords = () => {
    rows = Array.from(document.querySelectorAll('.record-row'));
    searchInput = document.getElementById('recordSearch');
    applyFilters();
    computeInsight();
  };

  const updateRecentRecords = (requestUrl, tableRange) => {
    const container = document.querySelector('[data-records-container]');
    if (!container) return;
    const prevInput = container.querySelector('#recordSearch');
    const prevValue = prevInput ? prevInput.value : '';
    const hadFocus = document.activeElement === prevInput;
    const scrollY = window.scrollY;

    showRecordsError(false);
    showRecordsLoading(true);
    fetch(requestUrl, { headers: { 'X-Requested-With': 'XMLHttpRequest' } })
      .then((response) => response.text())
      .then((html) => {
        container.innerHTML = html;
        const newOverlay = container.querySelector('.records-overlay');
        if (newOverlay) {
          newOverlay.hidden = true;
        }
        const newInput = container.querySelector('#recordSearch');
        if (newInput) {
          newInput.value = prevValue;
          if (hadFocus) {
            newInput.focus();
            newInput.setSelectionRange(prevValue.length, prevValue.length);
          }
        }
        updateRecordsUrl(tableRange);
        rebindRecentRecords();
        window.scrollTo({ top: scrollY });
      })
      .catch(() => {
        showRecordsLoading(false);
        showRecordsError(true);
      });
  };

  const initRecentRecords = () => {
    const container = document.querySelector('[data-records-container]');
    if (!container || recordsHandlersBound) return;
    recordsHandlersBound = true;

    container.addEventListener('click', (event) => {
      const rangeButton = event.target.closest('[data-table-range]');
      if (rangeButton) {
        if (!window.fetch || !config.recordsEndpoint) return;
        event.preventDefault();
        const tableRange = rangeButton.dataset.tableRange;
        const url = new URL(config.recordsEndpoint, window.location.origin);
        const params = new URLSearchParams(window.location.search);
        params.set('table_range', tableRange);
        url.search = params.toString();
        updateRecentRecords(url.toString(), tableRange);
        return;
      }

      const deleteButton = event.target.closest('.action-btn-danger');
      if (deleteButton) {
        event.preventDefault();
        openDeleteModal(deleteButton.dataset.deleteUrl, deleteButton.dataset.recordDate);
      }
    });

    container.addEventListener('input', (event) => {
      if (event.target && event.target.id === 'recordSearch') {
        searchInput = event.target;
        applyFilters();
      }
    });

    if (cancelDelete) {
      cancelDelete.addEventListener('click', closeDeleteModal);
    }

    if (deleteModal) {
      deleteModal.addEventListener('click', (event) => {
        if (event.target === deleteModal) {
          closeDeleteModal();
        }
      });
    }

    document.addEventListener('keydown', (event) => {
      if (event.key === 'Escape' && deleteModal?.classList.contains('is-visible')) {
        closeDeleteModal();
      }
    });

    rebindRecentRecords();
  };

  const buildLayout = (title, yTitle) => ({
    title: title,
    xaxis: { title: 'Date', tickfont: { size: 11, color: '#6b778a' }, gridcolor: 'rgba(15,23,42,0.06)' },
    yaxis: { title: yTitle, tickfont: { size: 11, color: '#6b778a' }, gridcolor: 'rgba(15,23,42,0.06)' },
    paper_bgcolor: 'rgba(0,0,0,0)',
    plot_bgcolor: 'rgba(0,0,0,0)',
    font: { color: '#1b3352' }
  });

  const buildTrace = (chartKey, chartConfig, data) => {
    const trace = {
      x: data.dates || [],
      y: data.values || [],
      type: chartConfig.type,
      name: chartKey === 'sleep' ? 'Sleep Hours' : 'Heart Rate'
    };
    if (chartConfig.type === 'bar') {
      trace.marker = { color: chartConfig.color };
    } else {
      trace.mode = chartConfig.mode || 'lines+markers';
      trace.line = { color: chartConfig.color };
    }
    return trace;
  };

  const setActiveRange = (chartKey, rangeValue) => {
    document.querySelectorAll(`.range-btn[data-chart="${chartKey}"]`).forEach((btn) => {
      if (btn.dataset.range === String(rangeValue)) {
        btn.classList.add('active');
      } else {
        btn.classList.remove('active');
      }
    });
  };

  const updateUrlParam = (key, value) => {
    const url = new URL(window.location.href);
    url.searchParams.set(key, value);
    window.history.replaceState({}, '', url.toString());
  };

  const updateChart = (chartKey, rangeValue) => {
    if (!config.chartEndpoint || !window.fetch) return;
    const chartConfig = config.charts?.[chartKey];
    if (!chartConfig) return;
    const requestUrl = `${config.chartEndpoint}?chart=${chartKey}&range=${rangeValue}`;
    fetch(requestUrl, { headers: { 'X-Requested-With': 'XMLHttpRequest' } })
      .then((response) => response.json())
      .then((payload) => {
        if (!payload || !payload.data) return;
        const trace = buildTrace(chartKey, chartConfig, payload.data);
        Plotly.react(chartConfig.elementId, [trace], buildLayout(chartConfig.title, chartConfig.yTitle));
        setActiveRange(chartKey, rangeValue);
        const paramKey = chartKey === 'hr' ? 'hr_range' : 'sleep_range';
        updateUrlParam(paramKey, rangeValue);
      })
      .catch(() => {});
  };

  const initCharts = () => {
    if (!window.Plotly || !config.charts) return;
    Object.entries(config.charts).forEach(([key, chartConfig]) => {
      const trace = buildTrace(key, chartConfig, chartConfig.data || {});
      Plotly.newPlot(chartConfig.elementId, [trace], buildLayout(chartConfig.title, chartConfig.yTitle));
    });

    if (chartHandlersBound) return;
    chartHandlersBound = true;
    document.addEventListener('click', (event) => {
      const button = event.target.closest('.range-btn[data-chart]');
      if (!button) return;
      if (!window.fetch) return;
      event.preventDefault();
      updateChart(button.dataset.chart, button.dataset.range);
    });
  };

  window.initCharts = initCharts;
  window.initRecentRecords = initRecentRecords;
  window.rebindRecentRecords = rebindRecentRecords;

  if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', () => {
      initCharts();
      initRecentRecords();
    });
  } else {
    initCharts();
    initRecentRecords();
  }
})();
