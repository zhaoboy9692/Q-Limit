/**
 * 股票分析平台 - AI 多角色聊天窗口
 * 支持多头/空头/裁判对话 + 一键辩论 + SSE 流式
 */

// ============================================================
// 状态
// ============================================================
const ChatState = {
    isOpen: false,
    activeRole: 'bull',
    isLoading: false,
    sessionId: Date.now().toString(36),
};

const ROLE_CONFIG = {
    bull: { icon: '🐂', name: '多头分析师', color: 'var(--bull-color)', msgClass: 'bull-msg', roleClass: 'bull' },
    bear: { icon: '🐻', name: '空头分析师', color: 'var(--bear-color)', msgClass: 'bear-msg', roleClass: 'bear' },
    judge: { icon: '⚖️', name: '裁判分析师', color: 'var(--judge-color)', msgClass: 'judge-msg', roleClass: 'judge' },
    user: { icon: '👤', name: '你', color: 'var(--accent-blue)', msgClass: 'user-msg', roleClass: 'user' },
};

// ============================================================
// 初始化
// ============================================================
document.addEventListener('DOMContentLoaded', () => {
    initChat();
});

function initChat() {
    // 展开/收起
    document.getElementById('chatToggle').addEventListener('click', toggleChat);
    document.getElementById('btnChatMinimize').addEventListener('click', toggleChat);

    // 角色切换
    document.querySelectorAll('.role-btn').forEach(btn => {
        btn.addEventListener('click', () => {
            const role = btn.dataset.role;
            if (role === 'debate') {
                startDebate();
                return;
            }
            setActiveRole(role);
        });
    });

    // 发送消息
    document.getElementById('btnChatSend').addEventListener('click', sendMessage);
    document.getElementById('chatInput').addEventListener('keydown', (e) => {
        if (e.key === 'Enter' && !e.shiftKey) {
            e.preventDefault();
            sendMessage();
        }
    });

    // 自适应输入框
    document.getElementById('chatInput').addEventListener('input', function () {
        this.style.height = 'auto';
        this.style.height = Math.min(this.scrollHeight, 100) + 'px';
    });

    // 模型设置弹窗
    const btnSettings = document.getElementById('btnSettings');
    if (btnSettings) {
        btnSettings.addEventListener('click', openSettingsModal);
    }
    const btnChatSettings = document.getElementById('btnChatSettings');
    if (btnChatSettings) {
        btnChatSettings.addEventListener('click', openSettingsModal);
    }

    document.getElementById('btnCloseSettings').addEventListener('click', closeSettingsModal);
    document.getElementById('btnCancelSettings').addEventListener('click', closeSettingsModal);
    document.getElementById('btnSaveSettings').addEventListener('click', saveSettings);

    document.getElementById('settingsModal').addEventListener('click', (e) => {
        if (e.target.id === 'settingsModal') closeSettingsModal();
    });

    // 弹窗 Tab 切换
    document.querySelectorAll('.settings-tab').forEach(tab => {
        tab.addEventListener('click', () => {
            document.querySelectorAll('.settings-tab').forEach(t => t.classList.remove('active'));
            document.querySelectorAll('.settings-tab-content').forEach(c => c.classList.remove('active'));
            tab.classList.add('active');
            const targetId = tab.dataset.tab === 'ai' ? 'tabAI' : 'tabDisplay';
            document.getElementById(targetId).classList.add('active');
        });
    });
}

// ============================================================
// 展开/收起
// ============================================================
function toggleChat() {
    ChatState.isOpen = !ChatState.isOpen;
    const windowEl = document.getElementById('chatWindow');
    const toggleEl = document.getElementById('chatToggle');

    if (ChatState.isOpen) {
        windowEl.style.display = 'flex';
        toggleEl.style.display = 'none';
    } else {
        windowEl.style.display = 'none';
        toggleEl.style.display = 'flex';
    }
}

// ============================================================
// 角色切换
// ============================================================
function setActiveRole(role) {
    ChatState.activeRole = role;
    document.querySelectorAll('.role-btn').forEach(btn => {
        btn.classList.toggle('active', btn.dataset.role === role);
    });
}

// ============================================================
// 发送消息（单角色）
// ============================================================
async function sendMessage() {
    const input = document.getElementById('chatInput');
    const message = input.value.trim();
    if (!message || ChatState.isLoading) return;

    const stock = AppState.currentStock;
    if (!stock) {
        appendSystemMessage('请先搜索并选择一只股票');
        return;
    }

    input.value = '';
    input.style.height = 'auto';

    ChatState.isLoading = true;

    // 显示用户消息
    appendMessage('user', message);

    // 显示 thinking 状态
    const thinkingId = appendThinking(ChatState.activeRole);

    // 获取当前角色的 AI 配置
    const apiConfig = getApiConfig(ChatState.activeRole);

    // SSE 请求
    try {
        const response = await fetch('/api/chat', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({
                role: ChatState.activeRole,
                message: message,
                stock_code: stock.code,
                session_id: ChatState.sessionId,
                api_config: apiConfig
            }),
        });

        const reader = response.body.getReader();
        const decoder = new TextDecoder();
        let fullContent = '';

        while (true) {
            const { done, value } = await reader.read();
            if (done) break;

            const text = decoder.decode(value, { stream: true });
            const lines = text.split('\n');

            for (const line of lines) {
                if (!line.startsWith('data: ')) continue;
                const data = line.slice(6);
                if (data === '[DONE]') break;

                try {
                    const chunk = JSON.parse(data);

                    if (chunk.tool_call) {
                        appendToolCall(chunk.role, chunk.tool_call);
                    } else if (chunk.content) {
                        fullContent = chunk.content;
                    } else if (chunk.error) {
                        fullContent = `⚠️ ${chunk.error}`;
                    }
                } catch (e) { /* ignore parse errors */ }
            }
        }

        // 移除 thinking，显示最终内容
        removeThinking(thinkingId);
        if (fullContent) {
            appendMessage(ChatState.activeRole, fullContent);
        }

    } catch (err) {
        removeThinking(thinkingId);
        appendSystemMessage(`请求失败: ${err.message}`);
    } finally {
        ChatState.isLoading = false;
    }
}

// ============================================================
// 一键辩论
// ============================================================
async function startDebate() {
    const stock = AppState.currentStock;
    if (!stock) {
        appendSystemMessage('请先搜索并选择一只股票');
        return;
    }
    if (ChatState.isLoading) return;

    // 清除所有角色按钮高亮，只亮辩论按钮
    document.querySelectorAll('.role-btn').forEach(btn => {
        btn.classList.toggle('active', btn.dataset.role === 'debate');
    });

    ChatState.isLoading = true;

    // 清空提示
    const messagesEl = document.getElementById('chatMessages');
    const welcomeMsg = messagesEl.querySelector('.chat-welcome-msg');
    if (welcomeMsg) welcomeMsg.remove();

    appendSystemMessage(`⚔️ 开始对 ${stock.name || stock.code} 进行多空辩论分析...`);

    // 对于一键辩论，把三个角色的配置都取出来传给后端（或者后端自己处理，但现在后端 debate 接口需要完整的配置，为了简单，前端在此合并为一个包含三个角色配置的对象，不过当前的 app.api_chat_debate 接收的是单个 api_config，由于 debate 是内部按序调用，我们可以给 debate 接口传所有配置）
    // 为了后端兼容，修改传给 /api/chat/debate 的 api_config，不再是单一的一个，而是包含了牛熊裁三种的 map
    const combinedConfig = {
        bull: getApiConfig('bull'),
        bear: getApiConfig('bear'),
        judge: getApiConfig('judge')
    };

    try {
        const response = await fetch('/api/chat/debate', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({
                stock_code: stock.code,
                prompt: `请对股票 ${stock.code} (${stock.name || ''}) 进行全面分析`,
                session_id: ChatState.sessionId,
                api_config: combinedConfig  // 这里传合集的 config
            }),
        });

        const reader = response.body.getReader();
        const decoder = new TextDecoder();
        let currentThinkingId = null;

        while (true) {
            const { done, value } = await reader.read();
            if (done) break;

            const text = decoder.decode(value, { stream: true });
            const lines = text.split('\n');

            for (const line of lines) {
                if (!line.startsWith('data: ')) continue;
                const data = line.slice(6);
                if (data === '[DONE]') break;

                try {
                    const chunk = JSON.parse(data);

                    if (chunk.status === 'thinking') {
                        if (currentThinkingId) removeThinking(currentThinkingId);
                        currentThinkingId = appendThinking(chunk.role);
                    } else if (chunk.status === 'calling_tool') {
                        appendToolCall(chunk.role, chunk.tool);
                    } else if (chunk.status === 'done') {
                        if (currentThinkingId) {
                            removeThinking(currentThinkingId);
                            currentThinkingId = null;
                        }
                        appendMessage(chunk.role, chunk.content);
                    } else if (chunk.status === 'error') {
                        if (currentThinkingId) {
                            removeThinking(currentThinkingId);
                            currentThinkingId = null;
                        }
                        appendMessage(chunk.role, `⚠️ ${chunk.content}`);
                    } else if (chunk.status === 'skipped') {
                        appendMessage(chunk.role, chunk.content);
                    }
                } catch (e) { /* ignore */ }
            }
        }

        if (currentThinkingId) removeThinking(currentThinkingId);

    } catch (err) {
        appendSystemMessage(`辩论请求失败: ${err.message}`);
    } finally {
        ChatState.isLoading = false;
    }
}

// ============================================================
// UI 消息渲染
// ============================================================
function appendMessage(role, content) {
    const messagesEl = document.getElementById('chatMessages');
    const config = ROLE_CONFIG[role] || ROLE_CONFIG.user;

    // 移除欢迎消息
    const welcomeMsg = messagesEl.querySelector('.chat-welcome-msg');
    if (welcomeMsg) welcomeMsg.remove();

    const msgDiv = document.createElement('div');
    msgDiv.className = 'chat-msg';
    msgDiv.innerHTML = `
        <div class="chat-msg-header">
            <span class="chat-msg-icon">${config.icon}</span>
            <span class="chat-msg-role ${config.roleClass}">${config.name}</span>
        </div>
        <div class="chat-msg-body ${config.msgClass}">
            ${renderMarkdown(content)}
        </div>
    `;

    messagesEl.appendChild(msgDiv);
    scrollToBottom();
}

function appendSystemMessage(text) {
    const messagesEl = document.getElementById('chatMessages');
    const div = document.createElement('div');
    div.style.cssText = 'text-align:center;font-size:12px;color:var(--text-tertiary);padding:8px;';
    div.textContent = text;
    messagesEl.appendChild(div);
    scrollToBottom();
}

function appendToolCall(role, toolName) {
    const messagesEl = document.getElementById('chatMessages');
    const config = ROLE_CONFIG[role] || ROLE_CONFIG.user;

    const toolNames = {
        'get_pe_analysis': 'PE/PB 估值分析',
        'get_support_resistance': '压力位/支撑位',
        'get_technical_indicators': '技术指标',
        'get_stock_news': '资讯数据',
        'get_financial_report': '财报数据',
        'get_kline_summary': 'K线走势',
    };

    const div = document.createElement('div');
    div.className = 'chat-tool-call';
    div.innerHTML = `
        <span class="chat-tool-spinner"></span>
        <span>${config.icon} 正在调用工具: ${toolNames[toolName] || toolName}</span>
    `;
    messagesEl.appendChild(div);
    scrollToBottom();
}

let thinkingCounter = 0;
function appendThinking(role) {
    const messagesEl = document.getElementById('chatMessages');
    const config = ROLE_CONFIG[role] || ROLE_CONFIG.user;
    const id = `thinking-${++thinkingCounter}`;

    const div = document.createElement('div');
    div.id = id;
    div.className = 'chat-thinking';
    div.innerHTML = `
        <span>${config.icon}</span>
        <span style="color:${config.color}">${config.name}</span>
        <span>正在分析</span>
        <div class="thinking-dots">
            <span class="thinking-dot"></span>
            <span class="thinking-dot"></span>
            <span class="thinking-dot"></span>
        </div>
    `;
    messagesEl.appendChild(div);
    scrollToBottom();
    return id;
}

function removeThinking(id) {
    const el = document.getElementById(id);
    if (el) el.remove();
}

function scrollToBottom() {
    const el = document.getElementById('chatMessages');
    el.scrollTop = el.scrollHeight;
}

// ============================================================
// Markdown 渲染
// ============================================================
function renderMarkdown(text) {
    if (!text) return '';
    if (typeof marked !== 'undefined') {
        try {
            return marked.parse(text);
        } catch (e) {
            return escapeHtml(text).replace(/\n/g, '<br>');
        }
    }
    return escapeHtml(text).replace(/\n/g, '<br>');
}

function escapeHtml(str) {
    const div = document.createElement('div');
    div.textContent = str;
    return div.innerHTML;
}

// ============================================================
// 设置弹窗逻辑
// ============================================================
function getApiConfig(role) {
    const saved = localStorage.getItem(`ai_config_${role}`);

    if (saved) {
        try {
            return JSON.parse(saved);
        } catch (e) {
            return { api_key: '', base_url: '', model: '' };
        }
    }
    return { api_key: '', base_url: '', model: '' };
}

function openSettingsModal() {
    const modal = document.getElementById('settingsModal');
    const settingsBody = document.getElementById('settingsBody');

    // 切换到 AI 配置 Tab
    document.querySelectorAll('.settings-tab').forEach(t => t.classList.remove('active'));
    document.querySelectorAll('.settings-tab-content').forEach(c => c.classList.remove('active'));
    document.querySelector('.settings-tab[data-tab="ai"]').classList.add('active');
    document.getElementById('tabAI').classList.add('active');

    // 渲染三个角色的表单
    const roles = [
        { id: 'bull', name: '🐂 多头分析师' },
        { id: 'bear', name: '🐻 空头分析师' },
        { id: 'judge', name: '⚖️ 裁判分析师' }
    ];

    let html = '';
    roles.forEach(role => {
        const cfg = getApiConfig(role.id);
        html += `
            <div class="role-config-card" style="margin-bottom: 20px; padding: 15px; background: var(--bg-secondary); border-radius: 8px;">
                <h4 style="margin-top: 0; color: var(--text-primary);">${role.name}</h4>
                <div style="margin-bottom: 10px;">
                    <label style="display:block; margin-bottom: 5px; color: var(--text-secondary); font-size: 13px;">API 密钥 <span style="font-size: 11px; color:#f44336">*必填</span></label>
                    <div style="position: relative; display: flex; align-items: center;">
                        <input type="password" id="key_${role.id}" value="${cfg.api_key || ''}" placeholder="sk-..." class="form-input" style="width: 100%; padding: 8px; padding-right: 32px; border: 1px solid var(--border-color); border-radius: 4px; background: var(--bg-primary); color: var(--text-primary);">
                        <span class="toggle-pwd-btn" data-target="key_${role.id}" style="position: absolute; right: 10px; cursor: pointer; color: var(--text-tertiary); user-select: none;" title="显示/隐藏密钥">👁️</span>
                    </div>
                </div>
                <div style="margin-bottom: 10px;">
                    <label style="display:block; margin-bottom: 5px; color: var(--text-secondary); font-size: 13px;">API 地址 (Base URL)</label>
                    <input type="text" id="url_${role.id}" value="${cfg.base_url}" placeholder="https://api.openai.com/v1" class="form-input" style="width: 100%; padding: 8px; border: 1px solid var(--border-color); border-radius: 4px; background: var(--bg-primary); color: var(--text-primary);">
                </div>
                <div>
                    <label style="display:block; margin-bottom: 5px; color: var(--text-secondary); font-size: 13px;">模型 (Model)</label>
                    <input type="text" id="model_${role.id}" value="${cfg.model}" placeholder="gpt-4o" class="form-input" style="width: 100%; padding: 8px; border: 1px solid var(--border-color); border-radius: 4px; background: var(--bg-primary); color: var(--text-primary);">
                </div>
            </div>
        `;
    });

    settingsBody.innerHTML = html;
    modal.style.display = 'flex';

    // 绑定显示/隐藏密码事件
    document.querySelectorAll('.toggle-pwd-btn').forEach(btn => {
        btn.addEventListener('click', function () {
            const targetId = this.dataset.target;
            const input = document.getElementById(targetId);
            if (input.type === 'password') {
                input.type = 'text';
                this.textContent = '👁️'; // 睁开眼睛，当前密码可见
            } else {
                input.type = 'password';
                this.textContent = '🕶️'; // 闭上/墨镜，当前密码不可见
            }
        });
    });
}

function closeSettingsModal() {
    document.getElementById('settingsModal').style.display = 'none';
}

function saveSettings() {
    const roles = ['bull', 'bear', 'judge'];
    roles.forEach(role => {
        const cfg = {
            api_key: document.getElementById(`key_${role}`).value.trim(),
            base_url: document.getElementById(`url_${role}`).value.trim(),
            model: document.getElementById(`model_${role}`).value.trim(),
        };
        localStorage.setItem(`ai_config_${role}`, JSON.stringify(cfg));
    });

    closeSettingsModal();
    // 弹窗提示
    const msg = document.createElement('div');
    msg.textContent = '✅ AI 配置已保存到浏览器';
    msg.style.cssText = 'position:fixed; top:20px; left:50%; transform:translateX(-50%); background:var(--bull-color); color:white; padding:10px 20px; border-radius:4px; z-index:10000; box-shadow: 0 4px 12px rgba(0,0,0,0.15);';
    document.body.appendChild(msg);
    setTimeout(() => msg.remove(), 2500);
}
