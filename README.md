# SAAS RAMOS - Estoque de Contas TikTok na Nuvem

Sistema completo para gerenciar um estoque de contas TikTok em um servidor na nuvem, permitindo que a extensão Chrome puxe e retorne contas automaticamente.

---

## Arquitetura

```
┌─────────────────────┐     ┌──────────────────────────┐     ┌─────────────────────┐
│   Interface Web     │     │   API REST (Flask)       │     │   Extensão Chrome   │
│   (Painel Admin)    │────▶│   /api/stock/*           │◀────│   (SAAS RAMOS)      │
│   Upload JSON       │     │   SQLite                 │     │   Puxe/Retorne      │
│   Ver status        │     │                          │     │   contas            │
└─────────────────────┘     └──────────────────────────┘     └─────────────────────┘
```

## Deploy Gratuito (Render.com)

### Passo 1: Preparar o código

1. Faça upload do projeto para um repositório GitHub
2. Vá em [Render.com](https://render.com) e crie uma conta gratuita
3. Clique em "New +" > "Web Service"
4. Conecte seu repositório GitHub
5. Configure:

| Campo | Valor |
|-------|-------|
| **Name** | `saas-ramos-estoque` |
| **Region** | `Oregon` (mais perto do Brasil) |
| **Branch** | `main` |
| **Runtime** | `Docker` |
| **Instance Type** | `Free` |
| **Health Check Path** | `/dashboard` (ignore) |

6. Clique em "Create Web Service"
7. Aguarde o deploy (~2 minutos)
8. Copie a URL gerada (ex: `https://saas-ramos-estoque.onrender.com`)

### Passo 2: Criar sua conta

1. Acesse a URL do Render
2. Clique em "Criar conta"
3. Defina usuário e senha

### Passo 3: Copiar o Token API

1. Faça login no painel
2. Copie o "Token API" exibido no dashboard

---

## Como Usar

### No Painel Web:
1. **Importar Contas:** Clique em "Importar" > selecione arquivos JSON ou cole o conteúdo
2. **Ver Status:** Dashboard mostra total, disponíveis, em uso, punidas, JSON expirado
3. **Baixar JSON:** Clique no ícone 💾 para baixar o cookie de uma conta
4. **Ver Logs:** Clique em 📋 para ver o histórico de ações da conta

### Na Extensão Chrome:
1. No painel da extensão, configure:
   - **URL do Servidor:** `https://saas-ramos-estoque.onrender.com`
   - **Token API:** (copiado do dashboard)
   - Marque "Puxar automaticamente do estoque"
2. O bot vai puxar contas do servidor quando o estoque local estiver vazio
3. Após uso, a conta é retornada automaticamente

---

## Endpoints da API

| Método | Endpoint | Descrição |
|--------|----------|-----------|
| GET | `/api/stock/pull` | Puxa uma conta disponível |
| POST | `/api/stock/return` | Retorna conta ao estoque |
| POST | `/api/stock/heartbeat` | Mantém conta como "em uso" |
| GET | `/api/stock/list` | Lista todas as contas |
| GET | `/api/stock/stats` | Estatísticas do estoque |

---

## Integração com a Extensão

O arquivo `extension-stock.js` contém o módulo completo para integrar com a extensão Chrome. Siga estas etapas:

### 1. Adicionar o módulo ao panel.js

Copie o conteúdo de `extension-stock.js` e cole no **final** do `panel.js` da extensão.

### 2. Adicionar a UI no panel.html

Antes do `</body>` no `panel.html`, adicione a seção de configuração do estoque (código comentado no final do `extension-stock.js`).

### 3. Modificar o runBotLoop()

No `panel.js`, dentro de `runBotLoop()`, adicione a lógica de puxar do estoque quando não houver contas locais:

```javascript
// Dentro do loop de troca de conta
if (accounts.length === 0 && stockConfig.autoPull) {
    const stockAcc = await pullFromStock();
    if (stockAcc) {
        accounts.push(stockAcc);
        renderAccountList();
        addLog('Conta puxada do estoque na nuvem!', 'ok');
    } else {
        addLog('Estoque vazio e sem contas locais. Aguardando 60s...', 'warn');
        await new Promise(r => setTimeout(r, 60000));
        continue;
    }
}
```

### 4. Retornar conta após tarefa

Após uma tarefa bem-sucedida, se a conta é do estoque:

```javascript
// Após registerConfirmedAction
if (acc.source === 'stock' && stockConfig.autoReturn) {
    await returnToStock(acc, 'available');
    accounts = accounts.filter(a => a.id !== acc.id);
    renderAccountList();
}
```

---

## Variáveis de Ambiente (opcionais)

| Variável | Padrão | Descrição |
|----------|--------|-----------|
| `DATABASE_URL` | `estoque.db` (local) | URL do banco de dados |
| `SECRET_KEY` | Aleatória | Chave para sessão Flask |
| `PORT` | `5000` | Porta do servidor |

---

## Estrutura de Arquivos

```
estoque_contas/
├── app.py              # Backend Flask completo
├── requirements.txt    # Dependências Python
├── Dockerfile          # Configuração Docker
├── extension-stock.js  # Módulo para a extensão Chrome
├── README.md           # Este arquivo
├── templates/
│   ├── login.html      # Tela de login
│   ├── register.html   # Tela de registro
│   ├── dashboard.html  # Painel principal
│   ├── add_accounts.html # Importar contas
│   └── account_logs.html # Logs de uma conta
└── static/
    └── css/
        └── style.css   # Estilos dark mode
```
