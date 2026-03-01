/**
 * 股票分析平台 - 主应用逻辑
 * 股票搜索、状态管理、页面路由
 */

// ============================================================
// 全局状态
// ============================================================
const AppState = {
    currentStock: null,    // { code, name, name_en, market, product, counter_id, currency }
    currentPeriod: 'daily', // 当前K线周期
    searchTimer: null,
    watchlist: [],         // 自选股列表
};

// ============================================================
// 初始化
// ============================================================
document.addEventListener('DOMContentLoaded', () => {
    initTheme();
    initSearch();
    initKeyboardShortcuts();
    loadWatchlist();
    initMarketTicker();
    initCompanyTooltip();
    initColorScheme();
});

// ============================================================
// 搜索功能（长桥接口）
// ============================================================
function initSearch() {
    const input = document.getElementById('stockSearch');
    const results = document.getElementById('searchResults');

    input.addEventListener('input', (e) => {
        const q = e.target.value.trim();
        clearTimeout(AppState.searchTimer);

        if (!q) {
            results.classList.remove('active');
            return;
        }

        AppState.searchTimer = setTimeout(() => {
            searchStock(q);
        }, 300);
    });

    input.addEventListener('focus', () => {
        if (input.value.trim() && results.children.length > 0) {
            results.classList.add('active');
        }
    });

    // 点击外部关闭
    document.addEventListener('click', (e) => {
        if (!e.target.closest('.search-container')) {
            results.classList.remove('active');
        }
    });
}

async function searchStock(keyword) {
    const results = document.getElementById('searchResults');

    try {
        const resp = await fetch(`/api/stock/search?q=${encodeURIComponent(keyword)}`);
        const json = await resp.json();
        const data = json.data || [];

        if (data.length === 0) {
            results.innerHTML = '<div class="search-result-item"><span class="result-name" style="color:var(--text-tertiary)">未找到相关股票</span></div>';
            results.classList.add('active');
            return;
        }

        results.innerHTML = data.map(item => {
            const inWl = isInWatchlist(item.code, item.market);
            const itemJson = JSON.stringify(item).replace(/'/g, "&#39;").replace(/"/g, '&quot;');
            return `
            <div class="search-result-item">
                <span class="result-code" onclick='selectStock(JSON.parse(this.parentElement.dataset.stock))' style="cursor:pointer">${item.code}</span>
                <span class="result-name" onclick='selectStock(JSON.parse(this.parentElement.dataset.stock))' style="cursor:pointer">${item.name}</span>
                ${item.product ? `<span class="result-product">${item.product}</span>` : ''}
                <span class="result-market">${item.market}</span>
                <button class="result-add-btn ${inWl ? 'added' : ''}" onclick="event.stopPropagation(); addToWatchlistFromSearch(this, ${itemJson.replace(/"/g, "&quot;")})" title="${inWl ? '已在自选' : '加入自选'}">${inWl ? '✓' : '+'}</button>
            </div>
        `;
        }).join('');

        // 给每条设置 data-stock
        results.querySelectorAll('.search-result-item').forEach((el, i) => {
            el.dataset.stock = JSON.stringify(data[i]);
        });

        results.classList.add('active');
    } catch (err) {
        console.error('搜索失败:', err);
    }
}

// ============================================================
// 选中股票
// ============================================================
function selectStock(stock) {
    AppState.currentStock = stock;

    // 关闭搜索结果
    document.getElementById('searchResults').classList.remove('active');
    document.getElementById('stockSearch').value = '';

    // 更新顶部信息
    document.getElementById('headerStockName').textContent = stock.name || stock.code;
    document.getElementById('headerStockCode').textContent = `${stock.market}:${stock.code}`;

    // 重置价格显示
    document.getElementById('headerStockPrice').textContent = '--';
    document.getElementById('headerStockChange').textContent = '--';
    document.getElementById('headerStockChange').className = 'stock-change';

    // 切换到分析视图
    document.getElementById('welcomeScreen').style.display = 'none';
    document.getElementById('analysisWorkspace').style.display = 'grid';

    // 更新聊天窗口股票信息
    document.getElementById('chatStockName').textContent = `${stock.code}`;

    // 高亮自选股栏当前项
    renderWatchlist();

    // 清空所有面板
    _clearAllPanels();

    // 加载所有数据
    loadAllData(stock.code);
}

function _clearAllPanels() {
    const loading = (icon, text) => `<div class="empty-state"><span class="empty-icon">${icon}</span><p>${text}</p></div>`;

    // 压力/支撑
    const srEl = document.getElementById('srContent');
    if (srEl) srEl.innerHTML = loading('📐', '加载压力/支撑数据...');

    // 估值
    const valGrid = document.querySelector('#tab-valuation .valuation-grid');
    if (valGrid) valGrid.innerHTML = loading('💰', '加载估值数据...');

    // 新闻
    const newsEl = document.getElementById('newsList');
    if (newsEl) newsEl.innerHTML = loading('📰', '加载资讯数据...');

    // 财报
    const finEl = document.getElementById('financialOverview');
    if (finEl) finEl.innerHTML = loading('📑', '加载财报数据...');

    // 形态预警
    const patEl = document.getElementById('patternsContent');
    if (patEl) patEl.innerHTML = loading('🔮', '加载形态数据...');
    const patSumEl = document.getElementById('patternsSummary');
    if (patSumEl) patSumEl.innerHTML = '';

    // 日程
    const actEl = document.getElementById('actionsTimeline');
    if (actEl) actEl.innerHTML = loading('📅', '加载日程数据...');
}

async function loadAllData(code) {
    // 并行加载
    return Promise.all([
        loadKlineData(code),
        loadStockDetail(code),
        loadAnalysisData(code),
        loadValuationData(code),
        loadNewsData(code),
        loadFinancialData(code),
        loadPatternsData(code),
        loadCompanyInfo(code),
        loadActionsData(code),
    ]).catch(err => console.error('加载数据出错:', err));
}

// ============================================================
// 加载K线数据
// ============================================================
async function loadKlineData(code, period) {
    try {
        const stock = AppState.currentStock || {};
        const market = stock.market || 'US';
        const product = stock.product || 'ST';
        const p = period || AppState.currentPeriod || 'daily';

        const resp = await fetch(`/api/stock/${code}/kline?period=${p}&market=${market}&product=${product}&kline_session=${AppState.klineSession || 101}`);
        const json = await resp.json();
        const data = json.data || [];

        if (data.length > 0) {
            // 更新价格显示
            const latest = data[data.length - 1];
            document.getElementById('headerStockPrice').textContent = latest.close.toFixed(2);

            const changePct = latest.change_pct || 0;
            const changeEl = document.getElementById('headerStockChange');
            changeEl.textContent = `${changePct >= 0 ? '+' : ''}${changePct.toFixed(2)}%`;
            changeEl.className = `stock-change ${changePct >= 0 ? 'up' : 'down'}`;
        }

        // 渲染K线图
        if (typeof renderKlineChart === 'function') {
            renderKlineChart(data, p);
        }
    } catch (err) {
        console.error('加载K线数据失败:', err);
    }
}

// ============================================================
// 加载股票详情（长桥实时行情）
// ============================================================
async function loadStockDetail(code) {
    try {
        const stock = AppState.currentStock || {};
        const market = stock.market || 'US';
        const product = stock.product || 'ST';

        const resp = await fetch(`/api/stock/${code}/detail?market=${market}&product=${product}`);
        const json = await resp.json();
        const d = json.data || {};

        // 头部价格
        if (d.last_done) {
            document.getElementById('headerStockPrice').textContent = d.last_done.toFixed(2);
        }
        if (d.change_pct !== undefined) {
            const changeEl = document.getElementById('headerStockChange');
            const sign = d.change_pct >= 0 ? '+' : '';
            changeEl.textContent = `${sign}${d.change.toFixed(2)} (${sign}${d.change_pct.toFixed(2)}%)`;
            changeEl.className = `stock-change ${d.change_pct >= 0 ? 'up' : 'down'}`;
        }
        if (d.status_desc) {
            const codeEl = document.getElementById('headerStockCode');
            if (codeEl) {
                codeEl.textContent = `${stock.code || code} · ${d.status_desc}`;
            }
        }

        // 填充详情面板
        const _v = (v, decimals = 2) => {
            if (v === null || v === undefined || v === '--' || v === '') return '--';
            const n = Number(v);
            return isNaN(n) ? String(v) : n.toFixed(decimals);
        };
        const _vol = (v) => {
            const n = Number(v);
            if (isNaN(n) || !n) return '--';
            if (n >= 1e8) return (n / 1e8).toFixed(2) + '亿';
            if (n >= 1e4) return (n / 1e4).toFixed(2) + '万';
            return n.toFixed(0);
        };
        const _amt = (v) => {
            const n = Number(v);
            if (isNaN(n) || !n) return '--';
            if (n >= 1e12) return (n / 1e12).toFixed(2) + '万亿';
            if (n >= 1e8) return (n / 1e8).toFixed(2) + '亿';
            if (n >= 1e4) return (n / 1e4).toFixed(0) + '万';
            return n.toFixed(0);
        };

        const _set = (id, val) => {
            const el = document.getElementById(id);
            if (el) el.textContent = val;
        };

        _set('detailOpen', _v(d.open));
        _set('detailHigh', _v(d.high));
        _set('detailLow', _v(d.low));
        _set('detailPrevClose', _v(d.prev_close));
        _set('detailVolume', _vol(d.volume) + '股');
        _set('detailTurnover', _amt(d.turnover));
        _set('detailVolumeRate', d.volume_rate || '--');

        // 振幅 = (最高 - 最低) / 昨收 * 100
        if (d.high && d.low && d.prev_close) {
            const amp = ((d.high - d.low) / d.prev_close * 100).toFixed(2);
            _set('detailAmplitude', amp + '%');
        }

        _set('detailYearHigh', _v(d.year_high));
        _set('detailYearLow', _v(d.year_low));
        _set('detailMarketCap', _amt(d.market_cap) + (d.currency || ''));
        _set('detailDividend', d.dividend_yield && d.dividend_yield !== '--' ? d.dividend_yield + '%' : '--');

        // 显示面板
        const panel = document.getElementById('stockDetailPanel');
        if (panel) panel.style.display = '';

        // 存储详情到全局状态
        AppState.stockDetail = d;
    } catch (err) {
        console.error('加载股票详情失败:', err);
    }
}

// ============================================================
// 鼠标悬浮加载公司简介
// ============================================================
let _companyInfoCache = {};

function initCompanyTooltip() {
    // 标题旁刷新按钮 — 刷新全部数据
    const refreshBtn = document.getElementById('btnRefreshHeader');
    if (refreshBtn) {
        refreshBtn.addEventListener('click', (e) => {
            e.stopPropagation();
            const code = AppState.currentStock?.code;
            if (!code) return;
            refreshBtn.textContent = '⏳';
            // 清除公司信息缓存以重新加载
            delete _companyInfoCache[code];
            loadAllData(code).finally(() => refreshBtn.textContent = '🔄');
        });
    }
}

async function loadCompanyInfo(code) {
    if (!code) return;
    const stock = AppState.currentStock || {};
    const market = stock.market || 'US';
    const product = stock.product || 'ST';

    // 已缓存则直接填充
    if (_companyInfoCache[code]) {
        _fillTooltip(_companyInfoCache[code]);
        return;
    }

    try {
        const resp = await fetch(`/api/stock/${code}/company-info?market=${market}&product=${product}`);
        const json = await resp.json();
        const info = json.data || {};
        _companyInfoCache[code] = info;
        _fillTooltip(info);
    } catch (e) {
        console.error('加载公司信息失败:', e);
    }
}

function _fillTooltip(info) {
    const logo = document.getElementById('tooltipLogo');
    const name = document.getElementById('tooltipName');
    const industry = document.getElementById('tooltipIndustry');
    const intro = document.getElementById('tooltipIntro');
    const profile = document.getElementById('tooltipProfile');
    const webpage = document.getElementById('tooltipWebpage');

    if (logo) {
        logo.src = info.logo || info.icon || '';
        logo.style.display = logo.src ? '' : 'none';
    }
    if (name) name.textContent = info.company_name || info.name || '--';
    if (industry) industry.textContent = info.industry_name || '';
    if (intro) intro.textContent = info.intro || '';
    if (profile) profile.textContent = info.profile || '';
    if (webpage && info.webpage) {
        const url = info.webpage.startsWith('http') ? info.webpage : `https://${info.webpage}`;
        webpage.innerHTML = `🌐 <a href="${url}" target="_blank">${info.webpage}</a>`;
    }
}

// ============================================================
// 加载分析数据
// ============================================================
async function loadAnalysisData(code, period) {
    try {
        const p = period || AppState.klinePeriod || 'daily';
        const stock = AppState.currentStock || {};
        const market = stock.market || 'US';
        const product = stock.product || 'ST';
        const resp = await fetch(`/api/stock/${code}/analysis?period=${p}&market=${market}&product=${product}`);
        const json = await resp.json();
        const data = json.data || {};

        if (typeof renderAnalysisPanel === 'function') {
            renderAnalysisPanel(data);
        }
    } catch (err) {
        console.error('加载分析数据失败:', err);
    }
}

// ============================================================
// 加载估值数据
// ============================================================
async function loadValuationData(code) {
    try {
        const stock = AppState.currentStock || {};
        const market = stock.market || 'US';
        const product = stock.product || 'ST';
        const resp = await fetch(`/api/stock/${code}/valuation?market=${market}&product=${product}`);
        const json = await resp.json();
        const data = json.data || {};

        if (typeof renderValuationPanel === 'function') {
            renderValuationPanel(data);
        }
    } catch (err) {
        console.error('加载估值数据失败:', err);
    }
}

// ============================================================
// 加载资讯数据
// ============================================================
async function loadNewsData(code) {
    try {
        const stock = AppState.currentStock || {};
        const market = stock.market || 'US';
        const product = stock.product || 'ST';

        // 刷新按钮loading
        const btnRefresh = document.getElementById('btnRefreshNews');
        if (btnRefresh) {
            btnRefresh.disabled = true;
            btnRefresh.textContent = '⏳';
        }

        const resp = await fetch(`/api/stock/${code}/news?limit=50&market=${market}&product=${product}`);
        const json = await resp.json();
        const data = json.data || [];

        if (typeof renderNewsPanel === 'function') {
            renderNewsPanel(data);
        }

        // 更新资讯数量
        const countEl = document.getElementById('newsCount');
        if (countEl) countEl.textContent = `${data.length} 条`;

        // 恢复刷新按钮
        if (btnRefresh) {
            btnRefresh.disabled = false;
            btnRefresh.textContent = '🔄';
        }
    } catch (err) {
        console.error('加载资讯数据失败:', err);
        const btnRefresh = document.getElementById('btnRefreshNews');
        if (btnRefresh) {
            btnRefresh.disabled = false;
            btnRefresh.textContent = '🔄';
        }
    }
}

// ============================================================
// 加载财报数据
// ============================================================
async function loadFinancialData(code) {
    try {
        const stock = AppState.currentStock || {};
        const market = stock.market || 'US';
        const product = stock.product || 'ST';
        const resp = await fetch(`/api/stock/${code}/financial?market=${market}&product=${product}`);
        const json = await resp.json();
        const data = json.data || {};

        if (typeof renderFinancialPanel === 'function') {
            renderFinancialPanel(data);
        }
    } catch (err) {
        console.error('加载财报数据失败:', err);
    }
}

// ============================================================
// 加载K线形态分析
// ============================================================
async function loadPatternsData(code, period) {
    try {
        const p = period || AppState.klinePeriod || 'daily';
        const stock = AppState.currentStock || {};
        const market = stock.market || 'US';
        const product = stock.product || 'ST';
        const resp = await fetch(`/api/stock/${code}/patterns?period=${p}&market=${market}&product=${product}`);
        const json = await resp.json();
        const data = json.data || {};

        if (typeof renderPatternsPanel === 'function') {
            renderPatternsPanel(data);
        }
    } catch (err) {
        console.error('加载K线形态数据失败:', err);
    }
}

// ============================================================
// 加载日程/公告数据
// ============================================================
async function loadActionsData(code) {
    try {
        const stock = AppState.currentStock || {};
        const market = stock.market || 'US';
        const product = stock.product || 'ST';
        const resp = await fetch(`/api/stock/${code}/actions?market=${market}&product=${product}`);
        const json = await resp.json();
        const data = json.data || [];

        if (typeof renderActionsPanel === 'function') {
            renderActionsPanel(data);
        }
    } catch (err) {
        console.error('加载日程数据失败:', err);
    }
}

// ============================================================
// 分析 Tab 切换
// ============================================================
document.querySelectorAll('.analysis-tab').forEach(tab => {
    tab.addEventListener('click', () => {
        // 切换 tab 按钮
        document.querySelectorAll('.analysis-tab').forEach(t => t.classList.remove('active'));
        tab.classList.add('active');

        // 切换内容
        const tabName = tab.dataset.tab;
        document.querySelectorAll('.tab-content').forEach(c => c.classList.remove('active'));
        document.getElementById(`tab-${tabName}`).classList.add('active');
    });
});

// ============================================================
// 指标 Tab 切换
// ============================================================
document.querySelectorAll('.ind-tab').forEach(tab => {
    tab.addEventListener('click', () => {
        document.querySelectorAll('.ind-tab').forEach(t => t.classList.remove('active'));
        tab.classList.add('active');

        if (typeof switchIndicator === 'function') {
            switchIndicator(tab.dataset.ind);
        }
    });
});

// ============================================================
// 周期切换（含下拉菜单）
// ============================================================
AppState.klineSession = 101; // 默认全部 (101=全部)
const SESSION_MAP = { night: 104, pre: 102, mid: 100, post: 103, all: 101 };

// 清除所有 period 高亮
function clearPeriodActive() {
    document.querySelectorAll('.period-selector > .period-btn').forEach(b => b.classList.remove('active'));
    document.querySelectorAll('.dropdown-trigger').forEach(b => b.classList.remove('active'));
}

// 普通按钮（5日/日K/周K/月K/年K）
document.querySelectorAll('.period-selector > .period-btn[data-period]').forEach(btn => {
    btn.addEventListener('click', () => {
        clearPeriodActive();
        btn.classList.add('active');
        AppState.currentPeriod = btn.dataset.period;
        if (AppState.currentStock) {
            loadKlineData(AppState.currentStock.code, btn.dataset.period);
            // 切换周期时重新加载分析
            loadAnalysisData(AppState.currentStock.code);
            loadPatternsData(AppState.currentStock.code);
        }
    });
});

// 下拉菜单通用逻辑
function initDropdown(dropdownId, onSelect) {
    const dropdown = document.getElementById(dropdownId);
    if (!dropdown) return;
    const trigger = dropdown.querySelector('.dropdown-trigger');
    const menu = dropdown.querySelector('.dropdown-menu');

    trigger.addEventListener('click', (e) => {
        e.stopPropagation();
        // 关闭其他下拉
        document.querySelectorAll('.period-dropdown.open').forEach(d => {
            if (d !== dropdown) d.classList.remove('open');
        });
        dropdown.classList.toggle('open');
    });

    menu.querySelectorAll('.dropdown-item').forEach(item => {
        item.addEventListener('click', (e) => {
            e.stopPropagation();
            menu.querySelectorAll('.dropdown-item').forEach(i => i.classList.remove('active'));
            item.classList.add('active');
            dropdown.classList.remove('open');
            onSelect(item);
        });
    });
}

// 交易时段下拉
initDropdown('sessionDropdown', (item) => {
    const session = item.dataset.session;
    const label = item.textContent;
    document.getElementById('sessionLabel').textContent = label;
    AppState.klineSession = SESSION_MAP[session] || 101;
    clearPeriodActive();
    document.getElementById('sessionBtn').classList.add('active');
    AppState.currentPeriod = 'timeshare';
    if (AppState.currentStock) {
        loadKlineData(AppState.currentStock.code, 'timeshare');
    }
});

// 分钟K下拉
initDropdown('minuteDropdown', (item) => {
    const period = item.dataset.period;
    const label = item.textContent;
    document.getElementById('minuteLabel').textContent = label;
    clearPeriodActive();
    document.getElementById('minuteBtn').classList.add('active');
    AppState.currentPeriod = period;
    if (AppState.currentStock) {
        loadKlineData(AppState.currentStock.code, period);
        loadAnalysisData(AppState.currentStock.code);
        loadPatternsData(AppState.currentStock.code);
    }
});

// 点击外部关闭所有下拉
document.addEventListener('click', () => {
    document.querySelectorAll('.period-dropdown.open').forEach(d => d.classList.remove('open'));
});

// 资讯刷新按钮
document.getElementById('btnRefreshNews')?.addEventListener('click', () => {
    if (AppState.currentStock) {
        loadNewsData(AppState.currentStock.code);
    }
});

// 压力/支撑刷新
document.getElementById('btnRefreshSR')?.addEventListener('click', () => {
    if (AppState.currentStock) {
        const btn = document.getElementById('btnRefreshSR');
        btn.textContent = '⏳';
        loadAnalysisData(AppState.currentStock.code).then(() => btn.textContent = '🔄');
    }
});

// 估值刷新
document.getElementById('btnRefreshValuation')?.addEventListener('click', () => {
    if (AppState.currentStock) {
        const btn = document.getElementById('btnRefreshValuation');
        btn.textContent = '⏳';
        loadValuationData(AppState.currentStock.code).then(() => btn.textContent = '🔄');
    }
});

// 财报刷新
document.getElementById('btnRefreshFinancial')?.addEventListener('click', () => {
    if (AppState.currentStock) {
        const btn = document.getElementById('btnRefreshFinancial');
        btn.textContent = '⏳';
        loadFinancialData(AppState.currentStock.code).then(() => btn.textContent = '🔄');
    }
});

// 形态预警刷新
document.getElementById('btnRefreshPatterns')?.addEventListener('click', () => {
    if (AppState.currentStock) {
        const btn = document.getElementById('btnRefreshPatterns');
        btn.textContent = '⏳';
        loadPatternsData(AppState.currentStock.code).then(() => btn.textContent = '🔄');
    }
});

// 日程刷新
document.getElementById('btnRefreshActions')?.addEventListener('click', () => {
    if (AppState.currentStock) {
        const btn = document.getElementById('btnRefreshActions');
        btn.textContent = '⏳';
        loadActionsData(AppState.currentStock.code).then(() => btn.textContent = '🔄');
    }
});

// ============================================================
// 设置弹窗
// ============================================================
// ============================================================
// 键盘快捷键
// ============================================================
function initKeyboardShortcuts() {
    document.addEventListener('keydown', (e) => {
        // "/" 聚焦搜索
        if (e.key === '/' && !e.target.closest('input, textarea')) {
            e.preventDefault();
            document.getElementById('stockSearch').focus();
        }
        // Escape 关闭弹窗/搜索
        if (e.key === 'Escape') {
            document.getElementById('searchResults').classList.remove('active');
            document.getElementById('settingsModal').style.display = 'none';
        }
    });
}

// ============================================================
// 自选股管理（localStorage 持久化）
// ============================================================
function loadWatchlist() {
    try {
        const saved = localStorage.getItem('stock_watchlist');
        AppState.watchlist = saved ? JSON.parse(saved) : [];
    } catch (e) {
        AppState.watchlist = [];
    }
    renderWatchlist();
}

function saveWatchlist() {
    localStorage.setItem('stock_watchlist', JSON.stringify(AppState.watchlist));
}

function isInWatchlist(code, market) {
    return AppState.watchlist.some(s => s.code === code && s.market === market);
}

function addToWatchlist(stock) {
    if (isInWatchlist(stock.code, stock.market)) return;
    AppState.watchlist.push(stock);
    saveWatchlist();
    renderWatchlist();
}

function removeFromWatchlist(code, market) {
    AppState.watchlist = AppState.watchlist.filter(s => !(s.code === code && s.market === market));
    saveWatchlist();
    renderWatchlist();
}

/** 搜索结果里点 + 加自选 */
function addToWatchlistFromSearch(btnEl, stock) {
    if (isInWatchlist(stock.code, stock.market)) return;
    addToWatchlist(stock);
    btnEl.classList.add('added');
    btnEl.textContent = '✓';
    btnEl.title = '已在自选';
}

function renderWatchlist() {
    const scroll = document.getElementById('watchlistScroll');
    const empty = document.getElementById('watchlistEmpty');

    if (AppState.watchlist.length === 0) {
        scroll.innerHTML = '';
        scroll.appendChild(empty.cloneNode(true) || createEmptyHint());
        return;
    }

    const current = AppState.currentStock;

    scroll.innerHTML = AppState.watchlist.map(s => {
        const isActive = current && current.code === s.code && current.market === s.market;
        const sJson = JSON.stringify(s).replace(/'/g, "&#39;").replace(/"/g, '&quot;');
        return `
            <div class="watchlist-item ${isActive ? 'active' : ''}" onclick='selectStock(${sJson})'>
                <span class="wl-code">${s.code}</span>
                <span class="wl-name">${s.name || ''}</span>
                <span class="wl-market">${s.market}</span>
                <button class="wl-remove" onclick="event.stopPropagation(); removeFromWatchlist('${s.code}','${s.market}')" title="移除">×</button>
            </div>
        `;
    }).join('');
}

function createEmptyHint() {
    const d = document.createElement('div');
    d.className = 'watchlist-empty';
    d.innerHTML = '<span>⭐</span> 搜索股票后点击 <strong>+</strong> 添加到自选';
    return d;
}

// ============================================================
// 主题切换（白天/黑夜）
// ============================================================
function initTheme() {
    const saved = localStorage.getItem('stocklens-theme') || 'dark';
    applyTheme(saved);

    const btn = document.getElementById('btnThemeToggle');
    if (btn) {
        btn.addEventListener('click', () => {
            const current = document.documentElement.getAttribute('data-theme') || 'dark';
            const next = current === 'dark' ? 'light' : 'dark';
            applyTheme(next);
            localStorage.setItem('stocklens-theme', next);
        });
    }
}

function applyTheme(theme) {
    if (theme === 'light') {
        document.documentElement.setAttribute('data-theme', 'light');
    } else {
        document.documentElement.removeAttribute('data-theme');
    }

    // 切换图标
    document.querySelectorAll('.theme-icon-dark').forEach(el => {
        el.style.display = theme === 'dark' ? '' : 'none';
    });
    document.querySelectorAll('.theme-icon-light').forEach(el => {
        el.style.display = theme === 'light' ? '' : 'none';
    });

    // 重新渲染图表（ECharts 需要适配主题）
    if (AppState.currentStock && typeof renderKlineChart === 'function' && currentKlineData && currentKlineData.length > 0) {
        renderKlineChart(currentKlineData, AppState.currentPeriod);
    }
}

// ============================================================
// AI 聊天窗口拖拽
// ============================================================
function initChatDrag() {
    const chatWindow = document.getElementById('chatWindow');
    const chatHeader = chatWindow?.querySelector('.chat-header');
    if (!chatWindow || !chatHeader) return;

    let isDragging = false;
    let startX, startY, initialLeft, initialTop;

    chatHeader.addEventListener('mousedown', (e) => {
        // 不拖拽按钮区域
        if (e.target.closest('.chat-header-actions')) return;

        isDragging = true;
        chatWindow.classList.add('dragging');

        const rect = chatWindow.getBoundingClientRect();
        startX = e.clientX;
        startY = e.clientY;
        initialLeft = rect.left;
        initialTop = rect.top;

        // 切换为 left/top 定位（首次拖拽时）
        chatWindow.style.right = 'auto';
        chatWindow.style.bottom = 'auto';
        chatWindow.style.left = initialLeft + 'px';
        chatWindow.style.top = initialTop + 'px';

        e.preventDefault();
    });

    document.addEventListener('mousemove', (e) => {
        if (!isDragging) return;

        const dx = e.clientX - startX;
        const dy = e.clientY - startY;

        let newLeft = initialLeft + dx;
        let newTop = initialTop + dy;

        // 边界检测
        const maxLeft = window.innerWidth - chatWindow.offsetWidth;
        const maxTop = window.innerHeight - chatWindow.offsetHeight;
        newLeft = Math.max(0, Math.min(newLeft, maxLeft));
        newTop = Math.max(0, Math.min(newTop, maxTop));

        chatWindow.style.left = newLeft + 'px';
        chatWindow.style.top = newTop + 'px';
    });

    document.addEventListener('mouseup', () => {
        if (!isDragging) return;
        isDragging = false;
        chatWindow.classList.remove('dragging');
    });
}

// 在 DOMContentLoaded 后初始化（延迟等待 chat 元素）
setTimeout(initChatDrag, 100);

// ============================================================
// 大盘指数滚动条
// ============================================================
function initMarketTicker() {
    loadMarketIndices();
    // 每 60 秒刷新
    setInterval(loadMarketIndices, 60000);
}

async function loadMarketIndices() {
    try {
        const resp = await fetch('/api/market/indices');
        const json = await resp.json();
        const indices = json.data || [];

        if (!indices.length) return;

        const track = document.getElementById('tickerTrack');
        if (!track) return;

        // 构建 ticker 项（可点击进入分析）
        const buildItems = (data) => data.map(idx => {
            const sign = idx.change_pct >= 0 ? '+' : '';
            const cls = idx.change_pct >= 0 ? 'up' : 'down';
            // 解析 counter_id: IX/US/.DJI → product=IX, market=US, code=.DJI
            const parts = (idx.counter_id || '').split('/');
            const product = parts[0] || 'IX';
            const market = parts[1] || 'US';
            const code = parts[2] || '';
            return `<span class="ticker-item ticker-clickable"
                data-code="${code}" data-market="${market}" data-product="${product}" data-name="${idx.name}"
                title="点击分析 ${idx.name}">
                <span class="ticker-name">${idx.name}</span>
                <span class="ticker-price">${idx.last_done.toLocaleString()}</span>
                <span class="ticker-change ${cls}">${sign}${idx.change_pct.toFixed(2)}%</span>
            </span>`;
        }).join('');

        // 重复两份实现无缝循环滚动
        const items = buildItems(indices);
        track.innerHTML = items + items;

        // 点击事件委托
        track.onclick = (e) => {
            const item = e.target.closest('.ticker-clickable');
            if (!item) return;
            selectStock({
                code: item.dataset.code,
                name: item.dataset.name,
                market: item.dataset.market,
                product: item.dataset.product,
            });
        };
    } catch (err) {
        console.error('加载大盘指数失败:', err);
    }
}

// ============================================================
// 涨跌配色切换（美股:涨绿跌红 / A股:涨红跌绿）
// ============================================================
function initColorScheme() {
    const saved = localStorage.getItem('colorScheme') || 'us';
    applyColorScheme(saved);

    // 设置弹窗中 radio 按钮切换
    document.querySelectorAll('input[name="colorScheme"]').forEach(radio => {
        if (radio.value === saved) radio.checked = true;
        radio.addEventListener('change', (e) => {
            applyColorScheme(e.target.value);
            localStorage.setItem('colorScheme', e.target.value);
        });
    });

    // 主题 radio 按钮
    const currentTheme = document.documentElement.getAttribute('data-theme') || 'dark';
    document.querySelectorAll('input[name="themeMode"]').forEach(radio => {
        if (radio.value === currentTheme) radio.checked = true;
        radio.addEventListener('change', (e) => {
            document.documentElement.setAttribute('data-theme', e.target.value);
            localStorage.setItem('theme', e.target.value);
            // 同步顶部主题按钮图标
            const darkIcon = document.querySelector('.theme-icon-dark');
            const lightIcon = document.querySelector('.theme-icon-light');
            if (darkIcon && lightIcon) {
                darkIcon.style.display = e.target.value === 'dark' ? '' : 'none';
                lightIcon.style.display = e.target.value === 'light' ? '' : 'none';
            }
        });
    });

    // Tab 页签切换
    document.querySelectorAll('.settings-tab').forEach(tab => {
        tab.addEventListener('click', () => {
            document.querySelectorAll('.settings-tab').forEach(t => t.classList.remove('active'));
            document.querySelectorAll('.settings-tab-content').forEach(c => c.classList.remove('active'));
            tab.classList.add('active');
            const target = tab.getAttribute('data-tab');
            const panel = document.getElementById(target === 'display' ? 'tabDisplay' : 'tabAI');
            if (panel) panel.classList.add('active');
        });
    });
}

function applyColorScheme(scheme) {
    if (scheme === 'cn') {
        document.documentElement.setAttribute('data-color-scheme', 'cn');
    } else {
        document.documentElement.removeAttribute('data-color-scheme');
    }
}
