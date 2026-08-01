/**
 * SAAS RAMOS - Módulo de Estoque de Contas na Nuvem
 * 
 * Este módulo deve ser ADICIONADO ao panel.js da extensão Chrome.
 * Ele permite que a extensão puxe contas do servidor e as retorne
 * após o uso, automatizando o fluxo de importação manual.
 * 
 * INSTRUÇÕES DE INTEGRAÇÃO:
 * 1. Copie este código e cole no final do seu panel.js
 * 2. Adicione o campo de configuração na UI (URL do servidor + Token)
 * 3. O bot vai automaticamente puxar do estoque quando não tiver contas locais
 */

// ═══════════════════════════════════════════════════════════════════
// CONFIGURAÇÃO DO ESTOQUE
// ═══════════════════════════════════════════════════════════════════

let stockConfig = {
    serverUrl: '',       // URL do seu servidor (ex: https://meu-servidor.onrender.com)
    apiToken: '',        // Token API (encontrado no dashboard do servidor)
    autoPull: false,     // Ativar puxada automática do estoque
    autoReturn: true,    // Retornar conta ao estoque após uso
    heartbeatInterval: 30000 // Heartbeat a cada 30s
};

let currentStockAccount = null;  // Conta atualmente puxada
let heartbeatTimer = null;

function loadStockConfig() {
    chrome.storage.local.get(['stockConfig'], (result) => {
        if (result.stockConfig) {
            stockConfig = { ...stockConfig, ...result.stockConfig };
        }
    });
}

function saveStockConfig() {
    chrome.storage.local.set({ stockConfig });
}

// ═══════════════════════════════════════════════════════════════════
// API DO ESTOQUE
// ═══════════════════════════════════════════════════════════════════

async function stockApi(endpoint, method = 'GET', body = null) {
    if (!stockConfig.serverUrl || !stockConfig.apiToken) {
        throw new Error('Servidor ou token não configurado');
    }
    
    const options = {
        method,
        headers: {
            'Authorization': `Bearer ${stockConfig.apiToken}`,
            'Content-Type': 'application/json'
        }
    };
    
    if (body) {
        options.body = JSON.stringify(body);
    }
    
    const response = await fetch(`${stockConfig.serverUrl}${endpoint}`, options);
    const data = await response.json();
    
    if (!response.ok || !data.success) {
        throw new Error(data.message || `Erro ${response.status}`);
    }
    
    return data;
}

// ═══════════════════════════════════════════════════════════════════
// PUXAR CONTA DO ESTOQUE
// ═══════════════════════════════════════════════════════════════════

async function pullFromStock() {
    try {
        addLog('► [Estoque] Puxando conta do servidor...', 'info');
        const data = await stockApi('/api/stock/pull');
        
        if (!data.accounts || data.accounts.length === 0) {
            addLog('► [Estoque] Estoque vazio no servidor.', 'warn');
            return null;
        }
        
        const acc = data.accounts[0];
        addLog(`► [Estoque] Conta puxada: @${acc.username} (${data.count} no total)`, 'ok');
        
        // Converter para formato compatível com o bot
        currentStockAccount = {
            id: acc.id,
            username: acc.username,
            nameReal: acc.name_real,
            json: acc.json_data,
            balance: acc.balance,
            stockId: acc.id,
            source: 'stock'
        };
        
        // Iniciar heartbeat
        startHeartbeat(acc.id);
        
        return currentStockAccount;
        
    } catch (err) {
        addLog(`► [Estoque] Erro ao puxar: ${err.message}`, 'err');
        return null;
    }
}

// ═══════════════════════════════════════════════════════════════════
// RETORNAR CONTA AO ESTOQUE
// ═══════════════════════════════════════════════════════════════════

async function returnToStock(account, status = 'available') {
    if (!account || !account.stockId) {
        addLog('► [Estoque] Conta sem stockId, pulando retorno.', 'warn');
        return;
    }
    
    stopHeartbeat();
    
    try {
        const data = await stockApi('/api/stock/return', 'POST', {
            account_id: account.stockId,
            status: status,
            action_count: account.actionCount || 0,
            balance: parseFloat(account.balance || 0),
            json_expired: account.jsonExpired === true,
            daily_actions: account.dailyActions || {},
            name_real: account.nameReal || null,
            name_verified: account.nameVerified === true
        });
        
        addLog(`► [Estoque] Conta @${account.username} retornada como ${status}.`, 'ok');
        currentStockAccount = null;
        
    } catch (err) {
        addLog(`► [Estoque] Erro ao retornar: ${err.message}`, 'err');
    }
}

// ═══════════════════════════════════════════════════════════════════
// HEARTBEAT
// ═══════════════════════════════════════════════════════════════════

function startHeartbeat(stockAccountId) {
    stopHeartbeat();
    
    heartbeatTimer = setInterval(async () => {
        try {
            await stockApi('/api/stock/heartbeat', 'POST', {
                account_id: stockAccountId,
                action_count: currentStockAccount?.actionCount || 0,
                balance: parseFloat(currentStockAccount?.balance || 0)
            });
        } catch (err) {
            // Silencioso - heartbeat não deve spammar logs
        }
    }, stockConfig.heartbeatInterval);
}

function stopHeartbeat() {
    if (heartbeatTimer) {
        clearInterval(heartbeatTimer);
        heartbeatTimer = null;
    }
}

// ═══════════════════════════════════════════════════════════════════
// INTEGRAÇÃO COM O BOT - MODIFICAÇÕES NECESSÁRIAS
// ═══════════════════════════════════════════════════════════════════

/*
 * SUBSTITUIR no panel.js:
 * 
 * 1. Na função runBotLoop(), antes de trocar de conta:
 *    - Se accounts.length === 0 E stockConfig.autoPull:
 *      const stockAcc = await pullFromStock();
 *      if (stockAcc) {
 *          accounts.push(stockAcc);
 *          renderAccountList();
 *      }
 * 
 * 2. Após conclusão de tarefa (sucesso):
 *    - Se account.source === 'stock':
 *      account.actionCount = (account.actionCount || 0) + 1;
 *      registerConfirmedAction(account, reward);
 * 
 * 3. Ao trocar de conta (switchAccount):
 *    - Se a conta atual é do estoque E stockConfig.autoReturn:
 *      await returnToStock(currentAccount, 'available');
 *      accounts = accounts.filter(a => a !== currentAccount);
 * 
 * 4. Ao punir conta (applyAccountPenalty):
 *    - Se account.source === 'stock':
 *      account.jsonExpired = true; // se motivo é JSON
 *      await returnToStock(account, 'punished');
 *      accounts = accounts.filter(a => a !== account);
 */

// ═══════════════════════════════════════════════════════════════════
// UI - ADICIONAR NO PANEL.HTML
// ═══════════════════════════════════════════════════════════════════

/*
 * ADICIONAR no panel.html antes do </body>:
 * 
 * <div class="stock-section" style="margin-top:16px;border-top:1px solid #2a2a5a;padding-top:12px;">
 *   <h3 style="font-size:12px;color:#00d2ff;margin-bottom:8px;">ESTOQUE NA NUVEM</h3>
 *   <div style="display:flex;flex-direction:column;gap:6px;">
 *     <input type="text" id="stockServerUrl" placeholder="URL do servidor (https://...)" 
 *            style="width:100%;padding:6px 10px;background:#0f0f25;border:1px solid #2a2a5a;border-radius:4px;color:#e0e0ff;font-size:11px;">
 *     <input type="text" id="stockApiToken" placeholder="Token API" 
 *            style="width:100%;padding:6px 10px;background:#0f0f25;border:1px solid #2a2a5a;border-radius:4px;color:#e0e0ff;font-size:11px;">
 *     <label style="font-size:11px;color:#8888aa;display:flex;align-items:center;gap:6px;">
 *       <input type="checkbox" id="stockAutoPull"> Puxar automaticamente do estoque
 *     </label>
 *     <button id="stockTestBtn" style="padding:6px 12px;background:rgba(0,210,255,0.2);color:#00d2ff;border:1px solid rgba(0,210,255,0.4);border-radius:4px;font-size:11px;cursor:pointer;">
 *       Testar Conexão
 *     </button>
 *     <button id="stockSaveBtn" style="padding:6px 12px;background:rgba(76,175,80,0.2);color:#4caf50;border:1px solid rgba(76,175,80,0.4);border-radius:4px;font-size:11px;cursor:pointer;">
 *       Salvar Configuração
 *     </button>
 *   </div>
 * </div>
 * 
 * E no panel.js, adicionar no DOMContentLoaded:
 * 
 * loadStockConfig();
 * 
 * const stockServerUrlInput = document.getElementById('stockServerUrl');
 * const stockApiTokenInput = document.getElementById('stockApiToken');
 * const stockAutoPullCheckbox = document.getElementById('stockAutoPull');
 * const stockTestBtn = document.getElementById('stockTestBtn');
 * const stockSaveBtn = document.getElementById('stockSaveBtn');
 * 
 * if (stockServerUrlInput) stockServerUrlInput.value = stockConfig.serverUrl;
 * if (stockApiTokenInput) stockApiTokenInput.value = stockConfig.apiToken;
 * if (stockAutoPullCheckbox) stockAutoPullCheckbox.checked = stockConfig.autoPull;
 * 
 * if (stockSaveBtn) {
 *   stockSaveBtn.onclick = () => {
 *     stockConfig.serverUrl = stockServerUrlInput.value.replace(/\/$/, '');
 *     stockConfig.apiToken = stockApiTokenInput.value.trim();
 *     stockConfig.autoPull = stockAutoPullCheckbox.checked;
 *     saveStockConfig();
 *     addLog('► [Estoque] Configuração salva.', 'ok');
 *   };
 * }
 * 
 * if (stockTestBtn) {
 *   stockTestBtn.onclick = async () => {
 *     stockConfig.serverUrl = stockServerUrlInput.value.replace(/\/$/, '');
 *     stockConfig.apiToken = stockApiTokenInput.value.trim();
 *     try {
 *       const data = await stockApi('/api/stock/stats');
 *       addLog(`► [Estoque] Conexão OK! ${data.stats.total_accounts} contas no estoque.`, 'ok');
 *     } catch (err) {
 *       addLog(`► [Estoque] Falha: ${err.message}`, 'err');
 *     }
 *   };
 * }
 */

// Exportar funções para uso global
window.stockApi = stockApi;
window.pullFromStock = pullFromStock;
window.returnToStock = returnToStock;
window.loadStockConfig = loadStockConfig;
window.saveStockConfig = saveStockConfig;
