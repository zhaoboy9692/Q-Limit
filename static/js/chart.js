/**
 * 股票分析平台 - K线图表（ECharts）
 * 支持K线、均线、压力位/支撑位标线、成交量
 */

let klineChartInstance = null;
let indicatorChartInstance = null;
let currentKlineData = [];
let currentAnalysisData = {};

// ============================================================
// K线图渲染
// ============================================================
function renderKlineChart(data, period) {
    currentKlineData = data;
    if (!data || data.length === 0) return;

    const container = document.getElementById('klineChart');
    if (!container) return;

    if (klineChartInstance) {
        klineChartInstance.dispose();
    }
    klineChartInstance = echarts.init(container, null, { renderer: 'canvas' });

    const isTimeshare = period === 'timeshare' || period === '5day';
    const isMinute = ['1min', '5min', '15min', '30min', '60min'].includes(period);

    if (isTimeshare) {
        _renderTimeshareChart(data, period);
    } else {
        _renderCandlestickChart(data, isMinute);
    }

    // 响应式
    window.addEventListener('resize', () => {
        if (klineChartInstance) klineChartInstance.resize();
    });
}

// ---- 分时图（折线） ----
function _renderTimeshareChart(data, period) {
    const dates = data.map(d => {
        const s = String(d.date);
        // 提取 HH:MM
        if (s.includes(' ')) return s.split(' ')[1];
        return s;
    });
    const prices = data.map(d => d.close);
    const avgPrices = data.map(d => d.avg_price || null);
    const volumes = data.map(d => d.volume);

    // 计算均价（如果没有 avg_price 字段则用累计均价）
    const hasAvg = avgPrices.some(v => v && v > 0);

    const option = {
        animation: false,
        backgroundColor: 'transparent',
        tooltip: {
            trigger: 'axis',
            axisPointer: { type: 'cross' },
            backgroundColor: 'rgba(17, 24, 39, 0.95)',
            borderColor: 'rgba(255,255,255,0.1)',
            textStyle: { color: '#e8eaed', fontSize: 12, fontFamily: 'Inter' },
            formatter: function (params) {
                if (!params || params.length === 0) return '';
                const p = params[0];
                const idx = p.dataIndex;
                const item = data[idx];
                if (!item) return '';
                return `
                    <div style="font-weight:600;margin-bottom:4px">${dates[idx]}</div>
                    <div>价格: <span style="color:#3b82f6;font-family:JetBrains Mono">${item.close.toFixed(3)}</span></div>
                    ${item.avg_price ? `<div>均价: <span style="color:#ffd600;font-family:JetBrains Mono">${item.avg_price.toFixed(3)}</span></div>` : ''}
                    <div>成交量: <span style="font-family:JetBrains Mono">${formatVolume(item.volume)}</span></div>
                `;
            },
        },
        grid: [
            { left: 60, right: 20, top: 30, bottom: 130 },
            { left: 60, right: 20, top: 'auto', bottom: 30, height: 80 },
        ],
        xAxis: [
            {
                type: 'category',
                data: dates,
                gridIndex: 0,
                axisLine: { lineStyle: { color: 'rgba(255,255,255,0.06)' } },
                axisLabel: { color: '#6b7280', fontSize: 11, fontFamily: 'JetBrains Mono', interval: Math.floor(dates.length / 6) },
                axisTick: { show: false },
                boundaryGap: false,
            },
            {
                type: 'category',
                data: dates,
                gridIndex: 1,
                axisLine: { lineStyle: { color: 'rgba(255,255,255,0.06)' } },
                axisLabel: { show: false },
                axisTick: { show: false },
            },
        ],
        yAxis: [
            {
                type: 'value',
                gridIndex: 0,
                splitLine: { lineStyle: { color: 'rgba(255,255,255,0.04)' } },
                axisLine: { show: false },
                axisLabel: { color: '#6b7280', fontSize: 11, fontFamily: 'JetBrains Mono' },
                scale: true,
            },
            {
                type: 'value',
                gridIndex: 1,
                splitLine: { show: false },
                axisLine: { show: false },
                axisLabel: { show: false },
                scale: true,
            },
        ],
        series: [
            {
                name: '价格',
                type: 'line',
                data: prices,
                smooth: false,
                showSymbol: false,
                lineStyle: { width: 1.5, color: '#3b82f6' },
                areaStyle: {
                    color: {
                        type: 'linear',
                        x: 0, y: 0, x2: 0, y2: 1,
                        colorStops: [
                            { offset: 0, color: 'rgba(59, 130, 246, 0.25)' },
                            { offset: 1, color: 'rgba(59, 130, 246, 0.02)' },
                        ],
                    },
                },
                xAxisIndex: 0,
                yAxisIndex: 0,
            },
            // 均价线
            ...(hasAvg ? [{
                name: '均价',
                type: 'line',
                data: avgPrices,
                smooth: false,
                showSymbol: false,
                lineStyle: { width: 1, color: '#ffd600', type: 'dashed' },
                xAxisIndex: 0,
                yAxisIndex: 0,
            }] : []),
            // 成交量
            {
                name: '成交量',
                type: 'bar',
                data: volumes.map((v, i) => ({
                    value: v,
                    itemStyle: {
                        color: i > 0 && prices[i] >= prices[i - 1]
                            ? 'rgba(0, 200, 83, 0.5)'
                            : 'rgba(255, 23, 68, 0.5)',
                    },
                })),
                xAxisIndex: 1,
                yAxisIndex: 1,
            },
        ],
    };

    klineChartInstance.setOption(option);
}

// ---- K线蜡烛图 ----
function _renderCandlestickChart(data, isMinute) {
    const dates = data.map(d => {
        if (isMinute) {
            const s = String(d.date);
            if (s.includes(' ')) return s.split(' ')[1];
            return s;
        }
        return formatDate(d.date);
    });
    const ohlc = data.map(d => [d.open, d.close, d.low, d.high]);
    const volumes = data.map(d => d.volume);
    const closes = data.map(d => d.close);

    // 计算均线
    const ma5 = calcMA(closes, 5);
    const ma10 = calcMA(closes, 10);
    const ma20 = calcMA(closes, 20);
    const ma60 = calcMA(closes, 60);

    // 压力位/支撑位标线
    const markLines = buildMarkLines();

    const option = {
        animation: false,
        backgroundColor: 'transparent',
        tooltip: {
            trigger: 'axis',
            axisPointer: { type: 'cross' },
            backgroundColor: 'rgba(17, 24, 39, 0.95)',
            borderColor: 'rgba(255,255,255,0.1)',
            textStyle: { color: '#e8eaed', fontSize: 12, fontFamily: 'Inter' },
            formatter: function (params) {
                if (!params || params.length === 0) return '';
                const k = params[0];
                if (!k || !k.data) return '';
                const idx = k.dataIndex;
                const item = data[idx];
                if (!item) return '';

                const color = item.close >= item.open ? '#00c853' : '#ff1744';
                return `
                    <div style="font-weight:600;margin-bottom:6px">${dates[idx]}</div>
                    <div>开盘: <span style="color:${color};font-family:JetBrains Mono">${item.open.toFixed(2)}</span></div>
                    <div>收盘: <span style="color:${color};font-family:JetBrains Mono">${item.close.toFixed(2)}</span></div>
                    <div>最高: <span style="font-family:JetBrains Mono">${item.high.toFixed(2)}</span></div>
                    <div>最低: <span style="font-family:JetBrains Mono">${item.low.toFixed(2)}</span></div>
                    <div>成交量: <span style="font-family:JetBrains Mono">${formatVolume(item.volume)}</span></div>
                    ${item.change_pct !== undefined ? `<div>涨跌幅: <span style="color:${color};font-family:JetBrains Mono">${item.change_pct >= 0 ? '+' : ''}${item.change_pct.toFixed(2)}%</span></div>` : ''}
                `;
            },
        },
        axisPointer: {
            link: [{ xAxisIndex: 'all' }],
        },
        grid: [
            { left: 60, right: 20, top: 30, bottom: 130 },
            { left: 60, right: 20, top: 'auto', bottom: 30, height: 80 },
        ],
        xAxis: [
            {
                type: 'category',
                data: dates,
                gridIndex: 0,
                axisLine: { lineStyle: { color: 'rgba(255,255,255,0.06)' } },
                axisLabel: { color: '#6b7280', fontSize: 11, fontFamily: 'JetBrains Mono' },
                axisTick: { show: false },
            },
            {
                type: 'category',
                data: dates,
                gridIndex: 1,
                axisLine: { lineStyle: { color: 'rgba(255,255,255,0.06)' } },
                axisLabel: { show: false },
                axisTick: { show: false },
            },
        ],
        yAxis: [
            {
                type: 'value',
                gridIndex: 0,
                splitLine: { lineStyle: { color: 'rgba(255,255,255,0.04)' } },
                axisLine: { show: false },
                axisLabel: { color: '#6b7280', fontSize: 11, fontFamily: 'JetBrains Mono' },
                scale: true,
            },
            {
                type: 'value',
                gridIndex: 1,
                splitLine: { show: false },
                axisLine: { show: false },
                axisLabel: { show: false },
                scale: true,
            },
        ],
        dataZoom: [
            {
                type: 'inside',
                xAxisIndex: [0, 1],
                start: Math.max(0, 100 - Math.min(100, 120 / data.length * 100)),
                end: 100,
            },
            {
                type: 'slider',
                xAxisIndex: [0, 1],
                bottom: 5,
                height: 20,
                borderColor: 'transparent',
                backgroundColor: 'rgba(255,255,255,0.02)',
                fillerColor: 'rgba(59,130,246,0.15)',
                handleStyle: { color: '#3b82f6', borderColor: '#3b82f6' },
                textStyle: { color: '#6b7280', fontSize: 10 },
                start: Math.max(0, 100 - Math.min(100, 120 / data.length * 100)),
                end: 100,
            },
        ],
        series: [
            // K线
            {
                name: 'K线',
                type: 'candlestick',
                data: ohlc,
                xAxisIndex: 0,
                yAxisIndex: 0,
                itemStyle: {
                    color: '#00c853',
                    color0: '#ff1744',
                    borderColor: '#00c853',
                    borderColor0: '#ff1744',
                },
                markLine: markLines,
            },
            // MA5
            {
                name: 'MA5',
                type: 'line',
                data: ma5,
                smooth: true,
                showSymbol: false,
                lineStyle: { width: 1, color: '#ffd600' },
                xAxisIndex: 0,
                yAxisIndex: 0,
            },
            // MA10
            {
                name: 'MA10',
                type: 'line',
                data: ma10,
                smooth: true,
                showSymbol: false,
                lineStyle: { width: 1, color: '#2196f3' },
                xAxisIndex: 0,
                yAxisIndex: 0,
            },
            // MA20
            {
                name: 'MA20',
                type: 'line',
                data: ma20,
                smooth: true,
                showSymbol: false,
                lineStyle: { width: 1, color: '#e040fb' },
                xAxisIndex: 0,
                yAxisIndex: 0,
            },
            // MA60
            {
                name: 'MA60',
                type: 'line',
                data: ma60,
                smooth: true,
                showSymbol: false,
                lineStyle: { width: 1, color: '#00bcd4' },
                xAxisIndex: 0,
                yAxisIndex: 0,
            },
            // 成交量
            {
                name: '成交量',
                type: 'bar',
                data: volumes.map((v, i) => ({
                    value: v,
                    itemStyle: {
                        color: data[i].close >= data[i].open
                            ? 'rgba(0, 200, 83, 0.5)'
                            : 'rgba(255, 23, 68, 0.5)',
                    },
                })),
                xAxisIndex: 1,
                yAxisIndex: 1,
            },
        ],
    };

    klineChartInstance.setOption(option);
}

// ============================================================
// 指标图渲染
// ============================================================
function renderIndicatorChart(type, data) {
    const container = document.getElementById('indicatorChart');
    if (!container) return;

    if (indicatorChartInstance) {
        indicatorChartInstance.dispose();
    }
    indicatorChartInstance = echarts.init(container, null, { renderer: 'canvas' });

    let option = {};

    if (type === 'macd' && data.macd) {
        const dates = data.macd.map(d => formatDate(d.date));
        option = {
            backgroundColor: 'transparent',
            animation: false,
            grid: { left: 60, right: 20, top: 15, bottom: 25 },
            tooltip: {
                trigger: 'axis',
                backgroundColor: 'rgba(17,24,39,0.95)',
                borderColor: 'rgba(255,255,255,0.1)',
                textStyle: { color: '#e8eaed', fontSize: 11 },
            },
            xAxis: {
                type: 'category',
                data: dates,
                axisLine: { lineStyle: { color: 'rgba(255,255,255,0.06)' } },
                axisLabel: { show: false },
                axisTick: { show: false },
            },
            yAxis: {
                type: 'value',
                splitLine: { lineStyle: { color: 'rgba(255,255,255,0.04)' } },
                axisLine: { show: false },
                axisLabel: { color: '#6b7280', fontSize: 10 },
                scale: true,
            },
            series: [
                {
                    name: 'DIF',
                    type: 'line',
                    data: data.macd.map(d => d.dif),
                    lineStyle: { width: 1, color: '#3b82f6' },
                    showSymbol: false,
                },
                {
                    name: 'DEA',
                    type: 'line',
                    data: data.macd.map(d => d.dea),
                    lineStyle: { width: 1, color: '#ffd600' },
                    showSymbol: false,
                },
                {
                    name: 'MACD',
                    type: 'bar',
                    data: data.macd.map(d => ({
                        value: d.macd,
                        itemStyle: { color: d.macd >= 0 ? 'rgba(0,200,83,0.7)' : 'rgba(255,23,68,0.7)' },
                    })),
                },
            ],
        };
    } else if (type === 'kdj' && data.kdj) {
        const dates = data.kdj.map(d => formatDate(d.date));
        option = {
            backgroundColor: 'transparent',
            animation: false,
            grid: { left: 60, right: 20, top: 15, bottom: 25 },
            tooltip: {
                trigger: 'axis',
                backgroundColor: 'rgba(17,24,39,0.95)',
                borderColor: 'rgba(255,255,255,0.1)',
                textStyle: { color: '#e8eaed', fontSize: 11 },
            },
            xAxis: {
                type: 'category',
                data: dates,
                axisLine: { lineStyle: { color: 'rgba(255,255,255,0.06)' } },
                axisLabel: { show: false },
                axisTick: { show: false },
            },
            yAxis: {
                type: 'value',
                min: 0,
                max: 100,
                splitLine: { lineStyle: { color: 'rgba(255,255,255,0.04)' } },
                axisLine: { show: false },
                axisLabel: { color: '#6b7280', fontSize: 10 },
            },
            series: [
                { name: 'K', type: 'line', data: data.kdj.map(d => d.k), lineStyle: { width: 1, color: '#3b82f6' }, showSymbol: false },
                { name: 'D', type: 'line', data: data.kdj.map(d => d.d), lineStyle: { width: 1, color: '#ffd600' }, showSymbol: false },
                { name: 'J', type: 'line', data: data.kdj.map(d => d.j), lineStyle: { width: 1, color: '#e040fb' }, showSymbol: false },
            ],
        };
    } else if (type === 'vol' && currentKlineData.length > 0) {
        const dates = currentKlineData.map(d => formatDate(d.date));
        option = {
            backgroundColor: 'transparent',
            animation: false,
            grid: { left: 60, right: 20, top: 15, bottom: 25 },
            tooltip: {
                trigger: 'axis',
                backgroundColor: 'rgba(17,24,39,0.95)',
                borderColor: 'rgba(255,255,255,0.1)',
                textStyle: { color: '#e8eaed', fontSize: 11 },
            },
            xAxis: {
                type: 'category',
                data: dates,
                axisLine: { lineStyle: { color: 'rgba(255,255,255,0.06)' } },
                axisLabel: { show: false },
                axisTick: { show: false },
            },
            yAxis: {
                type: 'value',
                splitLine: { lineStyle: { color: 'rgba(255,255,255,0.04)' } },
                axisLine: { show: false },
                axisLabel: { color: '#6b7280', fontSize: 10, formatter: v => formatVolume(v) },
            },
            dataZoom: [{ type: 'inside', start: Math.max(0, 100 - 50), end: 100 }],
            series: [{
                type: 'bar',
                data: currentKlineData.map(d => ({
                    value: d.volume,
                    itemStyle: { color: d.close >= d.open ? 'rgba(0,200,83,0.6)' : 'rgba(255,23,68,0.6)' },
                })),
            }],
        };
    }

    if (Object.keys(option).length > 0) {
        indicatorChartInstance.setOption(option);
    }

    window.addEventListener('resize', () => {
        if (indicatorChartInstance) indicatorChartInstance.resize();
    });
}

function switchIndicator(type) {
    renderIndicatorChart(type, currentAnalysisData);
}

// ============================================================
// 压力位/支撑位标线
// ============================================================
function buildMarkLines() {
    const sr = currentAnalysisData.support_resistance;
    if (!sr) return {};

    const lines = [];

    (sr.resistance || []).forEach(r => {
        lines.push({
            yAxis: r.price,
            name: `${r.type} ${r.price}`,
            lineStyle: { color: '#ff1744', width: 1, type: 'dashed' },
            label: {
                formatter: `压 ${r.price}`,
                color: '#ff1744',
                fontSize: 10,
                fontFamily: 'JetBrains Mono',
            },
        });
    });

    (sr.support || []).forEach(s => {
        lines.push({
            yAxis: s.price,
            name: `${s.type} ${s.price}`,
            lineStyle: { color: '#00c853', width: 1, type: 'dashed' },
            label: {
                formatter: `撑 ${s.price}`,
                color: '#00c853',
                fontSize: 10,
                fontFamily: 'JetBrains Mono',
            },
        });
    });

    return {
        silent: true,
        symbol: 'none',
        data: lines,
    };
}

function updateKlineMarkLines() {
    if (!klineChartInstance || !currentKlineData.length) return;
    const markLines = buildMarkLines();
    klineChartInstance.setOption({
        series: [{ name: 'K线', markLine: markLines }],
    });
}

// ============================================================
// 工具函数
// ============================================================
function calcMA(data, period) {
    const result = [];
    for (let i = 0; i < data.length; i++) {
        if (i < period - 1) {
            result.push(null);
        } else {
            let sum = 0;
            for (let j = 0; j < period; j++) {
                sum += data[i - j];
            }
            result.push(+(sum / period).toFixed(2));
        }
    }
    return result;
}

function formatDate(dateStr) {
    if (!dateStr) return '';
    const s = String(dateStr).replace(/-/g, '');
    if (s.length === 8) {
        return `${s.slice(4, 6)}-${s.slice(6, 8)}`;
    }
    return dateStr;
}

function formatVolume(vol) {
    if (vol >= 1e8) return (vol / 1e8).toFixed(1) + '亿';
    if (vol >= 1e4) return (vol / 1e4).toFixed(0) + '万';
    return String(vol);
}
