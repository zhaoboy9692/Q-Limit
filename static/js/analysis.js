/**
 * 股票分析平台 - 分析面板渲染
 * 压力位/支撑位、估值分析、消息面、财报
 */

// ============================================================
// 压力位/支撑位面板
// ============================================================
function renderAnalysisPanel(data) {
    currentAnalysisData = data;

    const sr = data.support_resistance || {};

    // 当前价格
    document.getElementById('srCurrentPrice').textContent =
        sr.current_price ? sr.current_price.toFixed(2) : '--';

    // 压力位
    const resistEl = document.getElementById('resistanceLevels');
    const cp = sr.current_price || 0;
    resistEl.innerHTML = (sr.resistance || []).map(r => {
        const dist = cp > 0 ? ((r.price / cp - 1) * 100).toFixed(1) : '?';
        const tip = `${r.type}｜${r.date || ''}｜强度: ${r.strength}｜距当前价 +${dist}%`;
        return `
        <div class="sr-level-item resistance" title="${tip}">
            <span class="sr-level-price">${r.price.toFixed(2)}</span>
            <div class="sr-level-info">
                <span class="sr-level-type">${r.type}</span>
                ${r.date ? `<span class="sr-level-date">${r.date}</span>` : ''}
            </div>
            <span class="sr-level-strength">${r.strength}</span>
        </div>`;
    }).join('') || '<div style="color:var(--text-muted);font-size:13px;padding:8px;">暂无数据</div>';

    // 支撑位
    const suppEl = document.getElementById('supportLevels');
    suppEl.innerHTML = (sr.support || []).map(s => {
        const dist = cp > 0 ? ((1 - s.price / cp) * 100).toFixed(1) : '?';
        const tip = `${s.type}｜${s.date || ''}｜强度: ${s.strength}｜距当前价 -${dist}%`;
        return `
        <div class="sr-level-item support" title="${tip}">
            <span class="sr-level-price">${s.price.toFixed(2)}</span>
            <div class="sr-level-info">
                <span class="sr-level-type">${s.type}</span>
                ${s.date ? `<span class="sr-level-date">${s.date}</span>` : ''}
            </div>
            <span class="sr-level-strength">${s.strength}</span>
        </div>`;
    }).join('') || '<div style="color:var(--text-muted);font-size:13px;padding:8px;">暂无数据</div>';

    // 技术概要
    renderTechSummary(sr);

    // 更新 K 线图标线
    updateKlineMarkLines();

    // 渲染 MACD 指标图
    renderIndicatorChart('macd', data);
}

function renderTechSummary(sr) {
    const el = document.getElementById('techSummary');
    if (!el) return;

    // 从分析数据提取技术概要
    const items = [];

    if (sr.current_price) {
        items.push({ label: '当前价格', value: sr.current_price.toFixed(2) });
    }

    if (sr.resistance && sr.resistance.length > 0) {
        items.push({
            label: '最近压力位',
            value: sr.resistance[0].price.toFixed(2),
            extra: `距离 ${((sr.resistance[0].price / sr.current_price - 1) * 100).toFixed(1)}%`,
        });
    }

    if (sr.support && sr.support.length > 0) {
        items.push({
            label: '最近支撑位',
            value: sr.support[0].price.toFixed(2),
            extra: `距离 ${((1 - sr.support[0].price / sr.current_price) * 100).toFixed(1)}%`,
        });
    }

    el.innerHTML = items.map(item => `
        <div class="tech-item">
            <span class="tech-label">${item.label}</span>
            <span class="tech-value">${item.value} ${item.extra ? `<span style="font-size:11px;color:var(--text-tertiary)">(${item.extra})</span>` : ''}</span>
        </div>
    `).join('');
}

// ============================================================
// 估值分析面板
// ============================================================
function renderValuationPanel(data) {
    const pe = data.pe || {};
    const pb = data.pb || {};

    // 如果 PE 和 PB 都无数据，显示 ETF 分析或提示
    const noPE = !pe.current_pe || pe.current_pe <= 0;
    const noPB = !pb.current_pb || pb.current_pb <= 0;

    const valPanel = document.querySelector('#tab-valuation .valuation-grid');

    if (noPE && noPB) {
        // 有 ETF 分析数据则渲染 ETF 面板
        if (data.etf_analysis) {
            _renderEtfPanel(valPanel, data.etf_analysis);
        } else {
            valPanel.innerHTML = `
                <div class="empty-state">
                    <span class="empty-icon">📊</span>
                    <p>该证券暂无 PE/PB 估值数据</p>
                    <p class="empty-hint">ETF、基金等通常不适用市盈率/市净率分析</p>
                </div>`;
        }
        return;
    }

    // 恢复 PE/PB 原始 HTML（可能被 _clearAllPanels 清空）
    if (valPanel && !document.getElementById('peValue')) {
        valPanel.innerHTML = _getValuationTemplate();
    }

    // PE
    const peValueEl = document.getElementById('peValue');
    const pePercentileEl = document.getElementById('pePercentile');
    const peStatusEl = document.getElementById('peStatus');
    const peMarkerEl = document.getElementById('peMarker');

    if (peValueEl) peValueEl.textContent = pe.current_pe ? pe.current_pe.toFixed(2) : '--';
    if (pePercentileEl) pePercentileEl.textContent = `历史百分位 ${pe.pe_percentile ? pe.pe_percentile.toFixed(0) + '%' : '--'}`;
    if (peStatusEl) {
        peStatusEl.textContent = pe.pe_status || '--';
        peStatusEl.style.color = getStatusColor(pe.pe_status);
    }
    if (pe.pe_percentile && peMarkerEl) {
        peMarkerEl.style.left = `${pe.pe_percentile}%`;
    }

    // PB
    const pbValueEl = document.getElementById('pbValue');
    const pbPercentileEl = document.getElementById('pbPercentile');
    const pbStatusEl = document.getElementById('pbStatus');
    const pbMarkerEl = document.getElementById('pbMarker');

    if (pbValueEl) pbValueEl.textContent = pb.current_pb ? pb.current_pb.toFixed(2) : '--';
    if (pbPercentileEl) pbPercentileEl.textContent = `历史百分位 ${pb.pb_percentile ? pb.pb_percentile.toFixed(0) + '%' : '--'}`;
    if (pbStatusEl) {
        pbStatusEl.textContent = pb.pb_status || '--';
        pbStatusEl.style.color = getStatusColor(pb.pb_status);
    }
    if (pb.pb_percentile && pbMarkerEl) {
        pbMarkerEl.style.left = `${pb.pb_percentile}%`;
    }

    // 投资建议卡片
    const adviceContainer = document.getElementById('stockAdviceCard');
    if (data.stock_advice) {
        const adv = data.stock_advice;
        const levelColors = {
            strong_buy: { bg: 'rgba(52,199,89,0.12)', border: '#34c759', text: '#34c759' },
            buy: { bg: 'rgba(52,199,89,0.08)', border: '#30d158', text: '#30d158' },
            hold: { bg: 'rgba(255,204,0,0.08)', border: '#ffcc00', text: '#ffcc00' },
            caution: { bg: 'rgba(255,149,0,0.08)', border: '#ff9500', text: '#ff9500' },
            sell: { bg: 'rgba(255,59,48,0.08)', border: '#ff3b30', text: '#ff3b30' },
        };
        const lc = levelColors[adv.advice_level] || levelColors.hold;
        const reasonsHtml = (adv.reasons || []).map(r => `<div class="etf-reason">${r}</div>`).join('');

        if (adviceContainer) {
            adviceContainer.innerHTML = `
                <div class="etf-advice-card" style="background:${lc.bg};border:1px solid ${lc.border}">
                    <div class="etf-advice-title" style="color:${lc.text}">${adv.advice}</div>
                    <div class="etf-advice-desc">${adv.advice_desc}</div>
                </div>
                <div class="etf-section">
                    <div class="etf-section-title">📋 分析依据</div>
                    ${reasonsHtml}
                </div>`;
        }
    } else if (adviceContainer) {
        adviceContainer.innerHTML = '';
    }

}

function _getValuationTemplate() {
    return `
        <div class="val-card" id="peCard">
            <div class="val-header">PE 市盈率 <span class="val-desc">（股价÷每股收益）</span></div>
            <div class="val-value" id="peValue">--</div>
            <div class="val-percentile">
                <div class="percentile-bar">
                    <div class="percentile-fill" id="peFill"></div>
                    <div class="percentile-marker" id="peMarker"></div>
                </div>
                <div class="percentile-labels">
                    <span>极低</span><span>低</span><span>中</span><span>高</span><span>极高</span>
                </div>
                <span class="percentile-text" id="pePercentile">历史百分位 --</span>
            </div>
            <div class="val-status" id="peStatus">--</div>
        </div>
        <div class="val-card" id="pbCard">
            <div class="val-header">PB 市净率 <span class="val-desc">（股价÷每股净资产）</span></div>
            <div class="val-value" id="pbValue">--</div>
            <div class="val-percentile">
                <div class="percentile-bar">
                    <div class="percentile-fill" id="pbFill"></div>
                    <div class="percentile-marker" id="pbMarker"></div>
                </div>
                <div class="percentile-labels">
                    <span>极低</span><span>低</span><span>中</span><span>高</span><span>极高</span>
                </div>
                <span class="percentile-text" id="pbPercentile">历史百分位 --</span>
            </div>
            <div class="val-status" id="pbStatus">--</div>
        </div>
        <div id="stockAdviceCard"></div>`;
}

function _renderEtfPanel(container, etf) {
    if (!container || !etf) return;

    // 加仓建议颜色
    const levelColors = {
        strong_buy: { bg: 'rgba(52,199,89,0.12)', border: '#34c759', text: '#34c759' },
        buy: { bg: 'rgba(52,199,89,0.08)', border: '#30d158', text: '#30d158' },
        hold: { bg: 'rgba(255,204,0,0.08)', border: '#ffcc00', text: '#ffcc00' },
        wait: { bg: 'rgba(255,59,48,0.08)', border: '#ff3b30', text: '#ff3b30' },
    };
    const lc = levelColors[etf.advice_level] || levelColors.hold;

    // RSI 仪表颜色
    const rsiColors = { green: '#34c759', red: '#ff3b30', yellow: '#ffcc00', gray: 'var(--text-muted)' };
    const rsiCol = rsiColors[etf.rsi_color] || rsiColors.gray;

    // MA 偏离率 HTML
    const maTooltips = {
        MA20: '20日均线（短期趋势）\n价格在上方=短期偏强，下方=短期偏弱',
        MA60: '60日均线（中期趋势）\n价格在上方=中线看多，下方=中线看空',
        MA200: '200日均线（长期牛熊分界线）\n价格在上方=牛市，下方=熊市',
    };
    let maHtml = '';
    for (const [key, val] of Object.entries(etf.ma_deviations || {})) {
        const label = key.toUpperCase();
        const devColor = val.deviation >= 0 ? 'var(--bear-color)' : 'var(--bull-color)';
        const tip = maTooltips[label] || '';
        maHtml += `
            <div class="etf-ma-row" title="${tip}">
                <span class="etf-ma-label">${label}</span>
                <span class="etf-ma-value">${val.ma_value}</span>
                <span class="etf-ma-dev" style="color:${devColor}">
                    ${val.deviation >= 0 ? '+' : ''}${val.deviation}%
                </span>
            </div>`;
    }

    // 原因列表
    const reasonsHtml = (etf.reasons || []).map(r =>
        `<div class="etf-reason">${r}</div>`
    ).join('');

    container.innerHTML = `
        <!-- 加仓建议卡片 -->
        <div class="etf-advice-card" style="background:${lc.bg};border:1px solid ${lc.border}">
            <div class="etf-advice-title" style="color:${lc.text}">${etf.advice}</div>
            <div class="etf-advice-desc">${etf.advice_desc}</div>
        </div>

        <!-- 指标网格 -->
        <div class="etf-metrics">
            <!-- ATH 回撤 -->
            <div class="etf-metric-card">
                <div class="etf-metric-label">📉 距历史高点回撤</div>
                <div class="etf-metric-value" style="color:${etf.drawdown >= 20 ? '#34c759' : etf.drawdown >= 10 ? '#ffcc00' : 'var(--text-primary)'}">
                    -${etf.drawdown}%
                </div>
                <div class="etf-metric-sub">
                    ATH: ${etf.ath} (${etf.ath_date})
                </div>
                <div class="etf-drawdown-bar">
                    <div class="etf-drawdown-fill" style="width:${Math.min(etf.drawdown, 50) * 2}%"></div>
                </div>
            </div>

            <!-- RSI -->
            <div class="etf-metric-card">
                <div class="etf-metric-label">🔋 RSI(14)</div>
                <div class="etf-metric-value" style="color:${rsiCol}">
                    ${etf.rsi}
                </div>
                <div class="etf-metric-sub">${etf.rsi_signal}</div>
                <div class="etf-rsi-bar">
                    <div class="etf-rsi-zone zone-oversold"></div>
                    <div class="etf-rsi-zone zone-neutral"></div>
                    <div class="etf-rsi-zone zone-overbought"></div>
                    <div class="etf-rsi-marker" style="left:${etf.rsi}%"></div>
                </div>
                <div class="etf-rsi-labels">
                    <span>超卖</span><span>中性</span><span>超买</span>
                </div>
            </div>
        </div>

        <!-- 均线偏离率 -->
        <div class="etf-section">
            <div class="etf-section-title">📏 均线偏离率</div>
            ${maHtml || '<div style="color:var(--text-muted);font-size:12px">数据不足</div>'}
        </div>

        <!-- 分析原因 -->
        <div class="etf-section">
            <div class="etf-section-title">📋 分析依据</div>
            ${reasonsHtml}
        </div>
    `;
}

function getStatusColor(status) {
    if (!status) return 'var(--text-secondary)';
    if (status.includes('极低') || status.includes('低估') || status.includes('破净')) return 'var(--bull-color)';
    if (status.includes('极高') || status.includes('高')) return 'var(--bear-color)';
    return 'var(--judge-color)';
}

// ============================================================
// 消息面面板
// ============================================================
function renderNewsPanel(data) {
    const el = document.getElementById('newsList');

    if (!data || data.length === 0) {
        el.innerHTML = `
            <div class="empty-state">
                <span class="empty-icon">📰</span>
                <p>暂无资讯数据</p>
                <p class="empty-hint">该股票暂未找到相关新闻</p>
            </div>
        `;
        return;
    }

    el.innerHTML = data.map(item => {
        const isFlash = item.kind === 2;
        const importantTag = item.important ? '<span class="news-tag important">重要</span>' : '';
        const kindTag = isFlash ? '<span class="news-tag flash">快讯</span>' : '';

        // 关联股票标签
        const stocksHtml = (item.related_stocks || []).slice(0, 3).map(s => {
            const ch = parseFloat(s.change || 0);
            const cls = ch >= 0 ? 'up' : 'down';
            const txt = ch ? `${ch >= 0 ? '+' : ''}${(ch * 100).toFixed(2)}%` : '';
            return `<span class="news-stock-tag ${cls}">${s.name || s.code}${txt ? ' ' + txt : ''}</span>`;
        }).join('');

        // AI 摘要
        const summaryHtml = item.ai_summary
            ? `<div class="news-ai-summary"><span class="ai-tag">🤖 AI</span>${item.ai_summary}</div>`
            : '';

        // 内容摘要（快讯直接显示全文，文章显示前120字）
        const showContent = item.content && item.title !== item.content;
        const descHtml = showContent
            ? `<div class="news-desc">${item.content.substring(0, 120)}${item.content.length > 120 ? '...' : ''}</div>`
            : '';

        return `
            <div class="news-item ${item.important ? 'important' : ''}" ${item.url ? `onclick="window.open('${item.url}', '_blank')"` : ''}>
                <div class="news-header">
                    ${importantTag}${kindTag}
                    <span class="news-time">${item.publish_time || ''}</span>
                </div>
                <div class="news-title">${item.title || '无标题'}</div>
                ${descHtml}
                ${stocksHtml ? `<div class="news-stocks">${stocksHtml}</div>` : ''}
                ${summaryHtml}
                <div class="news-meta">
                    <span class="news-source">${item.source || '长桥'}</span>
                </div>
            </div>
        `;
    }).join('');
}

// ============================================================
// 财报面板
// ============================================================
function renderFinancialPanel(data) {
    const el = document.getElementById('financialOverview');

    const km = data.key_metrics || {};
    const sheets = data.sheets || {};

    if (!km.eps && !km.revenue && Object.keys(sheets).length === 0) {
        el.innerHTML = `
            <div class="empty-state">
                <span class="empty-icon">📑</span>
                <p>暂无财报数据</p>
            </div>
        `;
        return;
    }

    let html = '';

    // 摘要
    if (data.summary) {
        html += `<div class="fin-summary">💡 ${data.summary}</div>`;
    }

    // 关键指标卡片
    const fmtVal = (v, unit) => {
        if (v == null) return '--';
        if (unit === 'B') return (v / 1e9).toFixed(2) + 'B';
        if (unit === '%') return v.toFixed(2) + '%';
        return v.toFixed(4);
    };

    const metricsRows = [
        { label: 'EPS', value: fmtVal(km.eps, ''), icon: '💰' },
        { label: 'ROE', value: fmtVal(km.roe, '%'), icon: '📊' },
        { label: '营业收入', value: fmtVal(km.revenue, 'B'), icon: '💵' },
        { label: '净利润', value: fmtVal(km.net_profit, 'B'), icon: '📈' },
        { label: '毛利率', value: fmtVal(km.gross_margin, '%'), icon: '📐' },
        { label: '净利率', value: fmtVal(km.net_margin, '%'), icon: '📏' },
        { label: '总资产', value: fmtVal(km.total_assets, 'B'), icon: '🏦' },
        { label: '每股净资产', value: fmtVal(km.bps, ''), icon: '📋' },
        { label: '经营现金流', value: fmtVal(km.operating_cf, 'B'), icon: '💧' },
        { label: '自由现金流', value: fmtVal(km.free_cf, 'B'), icon: '🆓' },
    ];

    html += '<div class="fin-metrics-grid">';
    html += metricsRows.map(m => `
        <div class="fin-metric-card">
            <span class="fin-metric-icon">${m.icon}</span>
            <div class="fin-metric-content">
                <span class="fin-metric-label">${m.label}</span>
                <span class="fin-metric-value">${m.value}</span>
            </div>
        </div>
    `).join('');
    html += '</div>';

    // 三大报表详情（折叠面板）
    const sheetNames = { BS: '📊 资产负债表', IS: '📈 利润表', CF: '💧 现金流量表' };
    for (const [key, label] of Object.entries(sheetNames)) {
        const indicators = sheets[key] || [];
        if (indicators.length === 0) continue;

        html += `<div class="fin-sheet-section">
            <div class="fin-sheet-header" onclick="this.parentElement.classList.toggle('expanded')">
                <span>${label}</span>
                <span class="fin-sheet-toggle">▶</span>
            </div>
            <div class="fin-sheet-body">`;

        for (const ind of indicators) {
            for (const acc of ind.accounts || []) {
                const latest = (acc.values && acc.values[0]) || {};
                const val = latest.value;
                let displayVal = '--';
                if (val) {
                    const num = parseFloat(val);
                    if (!isNaN(num)) {
                        if (acc.percent) {
                            displayVal = num.toFixed(2) + '%';
                        } else if (Math.abs(num) >= 1e9) {
                            displayVal = (num / 1e9).toFixed(2) + 'B';
                        } else if (Math.abs(num) >= 1e6) {
                            displayVal = (num / 1e6).toFixed(1) + 'M';
                        } else {
                            displayVal = num.toFixed(2);
                        }
                    }
                }
                const period = latest.period || '';
                const ranking = acc.ranking ? `<span class="fin-ranking">${acc.ranking}</span>` : '';

                html += `
                    <div class="fin-sheet-row">
                        <span class="fin-sheet-name">${acc.name} ${ranking}</span>
                        <div class="fin-sheet-val-wrap">
                            <span class="fin-sheet-val">${displayVal}</span>
                            <span class="fin-sheet-period">${period}</span>
                        </div>
                    </div>`;
            }
        }
        html += '</div></div>';
    }

    el.innerHTML = html;
}

function formatMoney(val) {
    if (!val) return '--';
    if (Math.abs(val) >= 1e8) return (val / 1e8).toFixed(1) + '亿';
    if (Math.abs(val) >= 1e4) return (val / 1e4).toFixed(0) + '万';
    return val.toFixed(0);
}

function formatPct(val) {
    if (!val && val !== 0) return '--';
    return (val * 100).toFixed(1) + '%';
}

// ============================================================
// K线形态预警面板
// ============================================================
function renderPatternsPanel(data) {
    const signalColor = (signal) => {
        if (signal === '看涨') return 'var(--bull-color)';
        if (signal === '看跌') return 'var(--bear-color)';
        return 'var(--text-secondary)';
    };

    const strengthBadge = (strength) => {
        const cls = strength === '强' ? 'strong' : strength === '中' ? 'medium' : 'weak';
        return `<span class="pattern-strength ${cls}">${strength}</span>`;
    };

    // K线形态
    const cpEl = document.getElementById('candlestickPatterns');
    const patterns = data.candlestick_patterns || [];
    cpEl.innerHTML = patterns.length ? patterns.map(p => `
        <div class="pattern-item">
            <div class="pattern-header">
                <span class="pattern-name">${p.pattern}</span>
                <div>
                    <span class="pattern-signal" style="color:${signalColor(p.signal)}">${p.signal}</span>
                    ${strengthBadge(p.strength)}
                </div>
            </div>
            <div class="pattern-desc">${p.desc}</div>
            <div class="pattern-date">${p.date || ''}</div>
        </div>
    `).join('') : '<div class="empty-state-sm">未检测到K线形态信号</div>';

    // 趋势结构
    const tsEl = document.getElementById('trendStructures');
    const trends = data.trend_structures || [];
    tsEl.innerHTML = trends.length ? trends.map(t => `
        <div class="pattern-item">
            <div class="pattern-header">
                <span class="pattern-name">${t.pattern}</span>
                <div>
                    <span class="pattern-signal" style="color:${signalColor(t.signal)}">${t.signal}</span>
                    ${strengthBadge(t.strength)}
                </div>
            </div>
            <div class="pattern-desc">${t.desc}</div>
            <div class="pattern-date">${t.date || ''}</div>
        </div>
    `).join('') : '<div class="empty-state-sm">未检测到趋势结构信号</div>';

    // 假突破预警
    const fbEl = document.getElementById('falseBreakouts');
    const breakouts = data.false_breakouts || [];
    fbEl.innerHTML = breakouts.length ? breakouts.map(b => `
        <div class="pattern-item warning">
            <div class="pattern-header">
                <span class="pattern-name">${b.type}</span>
                <span class="pattern-strength ${b.strength === '强' ? 'strong' : 'medium'}">${b.strength}</span>
            </div>
            <div class="pattern-desc">${b.warning}</div>
            <div class="pattern-meta">
                <span>价格: ${b.price}</span>
                <span>量比: ${b.volume_ratio}%</span>
                <span>${b.date || ''}</span>
            </div>
        </div>
    `).join('') : '<div class="empty-state-sm">未检测到假突破信号 ✅</div>';

    // 综合摘要
    const sumEl = document.getElementById('patternsSummary');
    if (data.summary) {
        sumEl.innerHTML = `<div class="patterns-summary-box">📋 ${data.summary}</div>`;
    }
}


// ============================================================
// 日程/公告面板
// ============================================================
function renderActionsPanel(items) {
    const el = document.getElementById('actionsTimeline');
    if (!el) return;

    if (!items || items.length === 0) {
        el.innerHTML = `
            <div class="empty-state">
                <span class="empty-icon">📅</span>
                <p>暂无日程数据</p>
                <p class="empty-hint">该证券暂无公开的日程/公告信息</p>
            </div>`;
        return;
    }

    // 只展示最近 20 条
    const recent = items.slice(0, 20);

    let html = '<div class="timeline">';
    let lastMonth = '';

    recent.forEach(item => {
        const dateStr = item.date || '';
        const year = dateStr.substring(0, 4);
        const month = dateStr.substring(4, 6);
        const day = dateStr.substring(6, 8);
        const monthKey = `${year}-${month}`;

        // 月份分组头
        if (monthKey !== lastMonth && month) {
            html += `<div class="timeline-month">${parseInt(month)} 月 ${year}</div>`;
            lastMonth = monthKey;
        }

        // 类型标签颜色
        const typeClass = item.date_type === '除权日' ? 'tag-warn'
            : item.date_type === '派息日' ? 'tag-green'
                : item.date_type === '登记日' ? 'tag-blue'
                    : item.date_type === '公告日' ? 'tag-gray'
                        : '';

        html += `
        <div class="timeline-item">
            <div class="timeline-date">
                <span class="timeline-day">${parseInt(day) || ''}</span>
            </div>
            <div class="timeline-dot"></div>
            <div class="timeline-content">
                <div class="timeline-act">
                    <span class="timeline-act-type">${item.act_type || ''}</span>
                    <span class="timeline-date-zone">${item.date_zone || ''}</span>
                </div>
                <div class="timeline-desc">${item.act_desc || ''}</div>
                <span class="timeline-tag ${typeClass}">${item.date_type || ''}</span>
            </div>
        </div>`;
    });

    html += '</div>';
    el.innerHTML = html;
}
