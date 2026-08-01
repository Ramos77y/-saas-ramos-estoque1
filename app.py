"""
SAAS RAMOS - Estoque de Contas TikTok na Nuvem
Backend Flask com API REST + Interface Web
Deploy gratuito: Render.com / Fly.io
"""

import os
import json
import sqlite3
import uuid
import hashlib
from datetime import datetime
from functools import wraps
from flask import (
    Flask, request, jsonify, render_template,
    redirect, url_for, session, flash, g, send_from_directory
)
from werkzeug.security import generate_password_hash, check_password_hash

# ═══════════════════════════════════════════════════════════════════
# CONFIGURAÇÃO
# ═══════════════════════════════════════════════════════════════════
app = Flask(__name__)
app.secret_key = os.environ.get('SECRET_KEY', 'saas_ramos_estoque_' + uuid.uuid4().hex[:16])
DATABASE = os.environ.get('DATABASE_URL', os.path.join(os.path.dirname(__file__), 'estoque.db'))

# ═══════════════════════════════════════════════════════════════════
# BANCO DE DADOS
# ═══════════════════════════════════════════════════════════════════

def get_db():
    """Obtém conexão com o banco (padrão Flask)"""
    if 'db' not in g:
        if DATABASE.startswith('postgres://') or DATABASE.startswith('postgresql://'):
            import psycopg2
            g.db = psycopg2.connect(DATABASE)
        else:
            g.db = sqlite3.connect(DATABASE)
            g.db.row_factory = sqlite3.Row
    return g.db

@app.teardown_appcontext
def close_db(exception):
    db = g.pop('db', None)
    if db is not None:
        db.close()

def init_db():
    """Inicializa as tabelas do banco"""
    db = get_db()
    db.execute('''
        CREATE TABLE IF NOT EXISTS users (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            username TEXT UNIQUE NOT NULL,
            password_hash TEXT NOT NULL,
            api_token TEXT UNIQUE NOT NULL,
            created_at TEXT DEFAULT (datetime('now'))
        )
    ''')
    db.execute('''
        CREATE TABLE IF NOT EXISTS accounts (
            id TEXT PRIMARY KEY,
            user_id INTEGER NOT NULL,
            username TEXT NOT NULL,
            name_real TEXT,
            json_data TEXT NOT NULL,
            status TEXT DEFAULT 'available',
            punishment_until INTEGER DEFAULT 0,
            action_count INTEGER DEFAULT 0,
            balance REAL DEFAULT 0.0,
            daily_actions TEXT DEFAULT '{}',
            json_expired INTEGER DEFAULT 0,
            name_verified INTEGER DEFAULT 0,
            last_used TEXT,
            created_at TEXT DEFAULT (datetime('now')),
            updated_at TEXT DEFAULT (datetime('now')),
            FOREIGN KEY (user_id) REFERENCES users(id)
        )
    ''')
    db.execute('''
        CREATE TABLE IF NOT EXISTS account_log (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            account_id TEXT NOT NULL,
            event TEXT NOT NULL,
            message TEXT,
            created_at TEXT DEFAULT (datetime('now')),
            FOREIGN KEY (account_id) REFERENCES accounts(id)
        )
    ''')
    db.execute('''
        CREATE INDEX IF NOT EXISTS idx_accounts_user ON accounts(user_id)
    ''')
    db.execute('''
        CREATE INDEX IF NOT EXISTS idx_accounts_status ON accounts(status)
    ''')
    db.commit()

def dict_from_row(row):
    """Converte Row object em dict"""
    if row is None:
        return None
    try:
        return dict(row)
    except Exception:
        if isinstance(row, dict):
            return row
        return dict(zip(row.keys(), row))

# ═══════════════════════════════════════════════════════════════════
# AUTENTICAÇÃO
# ═══════════════════════════════════════════════════════════════════

def login_required(f):
    @wraps(f)
    def decorated(*args, **kwargs):
        if 'user_id' not in session:
            flash('Faça login primeiro.', 'error')
            return redirect(url_for('login'))
        return f(*args, **kwargs)
    return decorated

def api_auth_required(f):
    """Autenticação por API Token para a extensão"""
    @wraps(f)
    def decorated(*args, **kwargs):
        auth_header = request.headers.get('Authorization', '')
        if not auth_header.startswith('Bearer '):
            return jsonify({'success': False, 'message': 'Token não fornecido'}), 401
        
        token = auth_header.replace('Bearer ', '')
        db = get_db()
        user = dict_from_row(db.execute(
            'SELECT * FROM users WHERE api_token = ?', (token,)
        ).fetchone())
        
        if not user:
            return jsonify({'success': False, 'message': 'Token inválido'}), 403
        
        g.api_user = user
        return f(*args, **kwargs)
    return decorated

# ═══════════════════════════════════════════════════════════════════
# ROTAS WEB (Interface)
# ═══════════════════════════════════════════════════════════════════

@app.route('/')
def index():
    if 'user_id' in session:
        return redirect(url_for('dashboard'))
    return redirect(url_for('login'))

@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        username = request.form.get('username', '').strip()
        password = request.form.get('password', '').strip()
        
        db = get_db()
        user = dict_from_row(db.execute(
            'SELECT * FROM users WHERE username = ?', (username,)
        ).fetchone())
        
        if user and check_password_hash(user['password_hash'], password):
            session['user_id'] = user['id']
            session['username'] = user['username']
            return redirect(url_for('dashboard'))
        
        flash('Usuário ou senha incorretos.', 'error')
    
    return render_template('login.html')

@app.route('/logout')
def logout():
    session.clear()
    return redirect(url_for('login'))

@app.route('/register', methods=['GET', 'POST'])
def register():
    if request.method == 'POST':
        username = request.form.get('username', '').strip()
        password = request.form.get('password', '').strip()
        confirm = request.form.get('confirm', '').strip()
        
        if not username or not password:
            flash('Preencha todos os campos.', 'error')
        elif len(password) < 6:
            flash('Senha deve ter pelo menos 6 caracteres.', 'error')
        elif password != confirm:
            flash('As senhas não coincidem.', 'error')
        else:
            db = get_db()
            try:
                api_token = hashlib.sha256(username.encode() + os.urandom(32)).hexdigest()
                db.execute(
                    'INSERT INTO users (username, password_hash, api_token) VALUES (?, ?, ?)',
                    (username, generate_password_hash(password), api_token)
                )
                db.commit()
                flash('Conta criada com sucesso! Faça login.', 'success')
                return redirect(url_for('login'))
            except Exception as e:
                if 'UNIQUE' in str(e) or 'duplicate' in str(e):
                    flash('Usuário já existe.', 'error')
                else:
                    flash(f'Erro: {str(e)}', 'error')
    
    return render_template('register.html')

@app.route('/dashboard')
@login_required
def dashboard():
    user_id = session['user_id']
    db = get_db()
    
    # Estatísticas
    total = db.execute(
        'SELECT COUNT(*) as cnt FROM accounts WHERE user_id = ?', (user_id,)
    ).fetchone()['cnt']
    
    available = db.execute(
        "SELECT COUNT(*) as cnt FROM accounts WHERE user_id = ? AND status = 'available'", (user_id,)
    ).fetchone()['cnt']
    
    in_use = db.execute(
        "SELECT COUNT(*) as cnt FROM accounts WHERE user_id = ? AND status = 'in_use'", (user_id,)
    ).fetchone()['cnt']
    
    punished = db.execute(
        "SELECT COUNT(*) as cnt FROM accounts WHERE user_id = ? AND status = 'punished'", (user_id,)
    ).fetchone()['cnt']
    
    expired = db.execute(
        "SELECT COUNT(*) as cnt FROM accounts WHERE user_id = ? AND json_expired = 1", (user_id,)
    ).fetchone()['cnt']
    
    # Últimas 20 contas
    accounts = []
    rows = db.execute(
        'SELECT * FROM accounts WHERE user_id = ? ORDER BY updated_at DESC LIMIT 20', (user_id,)
    ).fetchall()
    for row in rows:
        acc = dict_from_row(row)
        try:
            acc['json_data'] = json.loads(acc['json_data'])
        except:
            pass
        try:
            acc['daily_actions'] = json.loads(acc['daily_actions'])
        except:
            acc['daily_actions'] = {}
        accounts.append(acc)
    
    return render_template(
        'dashboard.html',
        total=total, available=available, in_use=in_use,
        punished=punished, expired=expired, accounts=accounts,
        api_token=session.get('api_token', '')
    )

@app.route('/dashboard/token')
@login_required
def show_token():
    user_id = session['user_id']
    db = get_db()
    user = dict_from_row(db.execute(
        'SELECT api_token FROM users WHERE id = ?', (user_id,)
    ).fetchone())
    token = user['api_token'] if user else ''
    return jsonify({'api_token': token})

@app.route('/accounts/add', methods=['GET', 'POST'])
@login_required
def add_accounts():
    if request.method == 'POST':
        user_id = session['user_id']
        files = request.files.getlist('json_files')
        json_text = request.form.get('json_text', '').strip()
        
        added = 0
        errors = []
        db = get_db()
        
        # Processar arquivos JSON
        jsons_to_process = []
        
        for f in files:
            if f.filename and f.filename.endswith('.json'):
                try:
                    data = json.load(f)
                    jsons_to_process.append(data)
                except Exception as e:
                    errors.append(f'Arquivo {f.filename}: JSON inválido')
        
        # Processar JSON colado no textarea
        if json_text:
            try:
                data = json.loads(json_text)
                # Suporta array de JSONs
                if isinstance(data, list):
                    jsons_to_process.extend(data)
                else:
                    jsons_to_process.append(data)
            except:
                # Tenta separar múltiplos JSONs por linha
                for line in json_text.strip().split('\n'):
                    line = line.strip()
                    if line.startswith('{'):
                        try:
                            jsons_to_process.append(json.loads(line))
                        except:
                            pass
        
        for data in jsons_to_process:
            # Extrair username
            username = ''
            try:
                # Tenta pegar do localStorage ou cookies
                ls = json.loads(data.get('localStorage', '{}')) if data.get('localStorage') else {}
                
                # Username pode estar em diferentes lugares
                for key in ['__tea_cache_users', 'tea_cache_users', 'userInfo']:
                    if key in ls:
                        try:
                            user_info = json.loads(ls[key]) if isinstance(ls[key], str) else ls[key]
                            if isinstance(user_info, dict):
                                for k in ['uniqueId', 'uid', 'username', 'nickName']:
                                    if k in user_info:
                                        username = user_info[k]
                                        break
                        except:
                            pass
                if not username:
                    username = f"conta_{uuid.uuid4().hex[:8]}"
            except:
                username = f"conta_{uuid.uuid4().hex[:8]}"
            
            account_id = str(uuid.uuid4())
            
            # Verificar se já existe
            existing = db.execute(
                'SELECT id FROM accounts WHERE user_id = ? AND json_data = ?',
                (user_id, json.dumps(data))
            ).fetchone()
            
            if existing:
                continue
            
            try:
                db.execute(
                    '''INSERT INTO accounts (id, user_id, username, json_data)
                       VALUES (?, ?, ?, ?)''',
                    (account_id, user_id, username, json.dumps(data))
                )
                db.execute(
                    '''INSERT INTO account_log (account_id, event, message)
                       VALUES (?, ?, ?)''',
                    (account_id, 'imported', f'Conta importada: @{username}')
                )
                added += 1
            except Exception as e:
                errors.append(f'@{username}: {str(e)[:50]}')
        
        db.commit()
        
        if added > 0:
            flash(f'{added} conta(s) importada(s) com sucesso!', 'success')
        if errors:
            for e in errors[:5]:
                flash(e, 'error')
        
        return redirect(url_for('dashboard'))
    
    return render_template('add_accounts.html')

@app.route('/accounts/<account_id>/status', methods=['POST'])
@login_required
def update_account_status():
    user_id = session['user_id']
    account_id = account_id
    new_status = request.form.get('status', 'available')
    
    db = get_db()
    acc = dict_from_row(db.execute(
        'SELECT * FROM accounts WHERE id = ? AND user_id = ?', (account_id, user_id)
    ).fetchone())
    
    if not acc:
        flash('Conta não encontrada.', 'error')
        return redirect(url_for('dashboard'))
    
    db.execute(
        "UPDATE accounts SET status = ?, updated_at = datetime('now') WHERE id = ?",
        (new_status, account_id)
    )
    db.commit()
    
    flash(f'@{acc["username"]} atualizada para: {new_status}', 'success')
    return redirect(url_for('dashboard'))

@app.route('/accounts/<account_id>/delete', methods=['POST'])
@login_required
def delete_account():
    user_id = session['user_id']
    account_id = account_id
    
    db = get_db()
    db.execute('DELETE FROM accounts WHERE id = ? AND user_id = ?', (account_id, user_id))
    db.execute('DELETE FROM account_log WHERE account_id = ?', (account_id,))
    db.commit()
    
    flash('Conta removida.', 'success')
    return redirect(url_for('dashboard'))

@app.route('/accounts/download/<account_id>')
@login_required
def download_account(account_id):
    user_id = session['user_id']
    db = get_db()
    acc = dict_from_row(db.execute(
        'SELECT * FROM accounts WHERE id = ? AND user_id = ?', (account_id, user_id)
    ).fetchone())
    
    if not acc:
        return jsonify({'error': 'Não encontrada'}), 404
    
    data = json.loads(acc['json_data'])
    return jsonify(data)

@app.route('/accounts/<account_id>/logs')
@login_required
def account_logs(account_id):
    user_id = session['user_id']
    db = get_db()
    acc = dict_from_row(db.execute(
        'SELECT * FROM accounts WHERE id = ? AND user_id = ?', (account_id, user_id)
    ).fetchone())
    
    if not acc:
        flash('Conta não encontrada.', 'error')
        return redirect(url_for('dashboard'))
    
    logs = []
    rows = db.execute(
        'SELECT * FROM account_log WHERE account_id = ? ORDER BY created_at DESC LIMIT 50',
        (account_id,)
    ).fetchall()
    for row in rows:
        logs.append(dict_from_row(row))
    
    return render_template('account_logs.html', account=acc, logs=logs)

# ═══════════════════════════════════════════════════════════════════
# API REST (para a extensão)
# ═══════════════════════════════════════════════════════════════════

@app.route('/api/stock/pull', methods=['GET'])
@api_auth_required
def api_pull():
    """
    Puxa uma conta disponível do estoque.
    GET /api/stock/pull?social=tiktok&limit=1
    """
    user_id = g.api_user['id']
    limit = min(int(request.args.get('limit', 1)), 10)
    
    db = get_db()
    accounts = db.execute(
        '''SELECT * FROM accounts WHERE user_id = ? 
           AND status = 'available' AND json_expired = 0
           ORDER BY action_count ASC LIMIT ?''',
        (user_id, limit)
    ).fetchall()
    
    if not accounts:
        return jsonify({'success': True, 'accounts': [], 'message': 'Estoque vazio'})
    
    result = []
    for acc in accounts:
        acc_dict = dict_from_row(acc)
        json_data = json.loads(acc_dict['json_data'])
        
        # Marca como em uso
        db.execute(
            "UPDATE accounts SET status = 'in_use', last_used = datetime('now'), updated_at = datetime('now') WHERE id = ?",
            (acc_dict['id'],)
        )
        
        db.execute(
            'INSERT INTO account_log (account_id, event, message) VALUES (?, ?, ?)',
            (acc_dict['id'], 'pulled', 'Conta puxada pela extensão')
        )
        
        result.append({
            'id': acc_dict['id'],
            'username': acc_dict['username'],
            'name_real': acc_dict.get('name_real'),
            'json_data': json_data,
            'action_count': acc_dict['action_count'],
            'balance': acc_dict['balance'],
        })
    
    db.commit()
    return jsonify({'success': True, 'accounts': result, 'count': len(result)})

@app.route('/api/stock/return', methods=['POST'])
@api_auth_required
def api_return():
    """
    Retorna uma conta ao estoque após uso.
    POST /api/stock/return
    Body: { account_id: string, status: string, json_data?: object, action_count?: int, balance?: float, punishment_until?: int, json_expired?: bool, daily_actions?: object }
    """
    user_id = g.api_user['id']
    data = request.get_json()
    
    if not data or 'account_id' not in data:
        return jsonify({'success': False, 'message': 'account_id obrigatório'}), 400
    
    account_id = data['account_id']
    status = data.get('status', 'available')
    
    db = get_db()
    acc = dict_from_row(db.execute(
        'SELECT * FROM accounts WHERE id = ? AND user_id = ?', (account_id, user_id)
    ).fetchone())
    
    if not acc:
        return jsonify({'success': False, 'message': 'Conta não encontrada'}), 404
    
    # Atualizar campos
    updates = ["status = ?", "updated_at = datetime('now')"]
    params = [status]
    
    if 'json_data' in data:
        updates.append("json_data = ?")
        params.append(json.dumps(data['json_data']))
    
    if 'action_count' in data:
        updates.append("action_count = ?")
        params.append(int(data['action_count']))
    
    if 'balance' in data:
        updates.append("balance = ?")
        params.append(float(data['balance']))
    
    if 'punishment_until' in data:
        updates.append("punishment_until = ?")
        params.append(int(data['punishment_until']))
    
    if 'json_expired' in data:
        updates.append("json_expired = ?")
        params.append(1 if data['json_expired'] else 0)
    
    if 'daily_actions' in data:
        updates.append("daily_actions = ?")
        params.append(json.dumps(data['daily_actions']))
    
    if 'name_real' in data:
        updates.append("name_real = ?")
        params.append(data['name_real'])
    
    if 'name_verified' in data:
        updates.append("name_verified = ?")
        params.append(1 if data['name_verified'] else 0)
    
    params.append(account_id)
    db.execute(
        f"UPDATE accounts SET {', '.join(updates)} WHERE id = ?",
        tuple(params)
    )
    
    db.execute(
        'INSERT INTO account_log (account_id, event, message) VALUES (?, ?, ?)',
        (account_id, 'returned', f'Retornada ao estoque com status: {status}')
    )
    
    db.commit()
    return jsonify({'success': True, 'message': f'@{acc["username"]} retornada como {status}'})

@app.route('/api/stock/heartbeat', methods=['POST'])
@api_auth_required
def api_heartbeat():
    """
    Heartbeat para manter conta como 'em uso' e reportar progresso.
    POST /api/stock/heartbeat
    Body: { account_id: string, action_count?: int, balance?: float }
    """
    user_id = g.api_user['id']
    data = request.get_json()
    
    if not data or 'account_id' not in data:
        return jsonify({'success': False}), 400
    
    db = get_db()
    db.execute(
        "UPDATE accounts SET updated_at = datetime('now') WHERE id = ? AND user_id = ?",
        (data['account_id'], user_id)
    )
    
    updates = []
    params = []
    
    if 'action_count' in data:
        updates.append("action_count = ?")
        params.append(int(data['action_count']))
    if 'balance' in data:
        updates.append("balance = ?")
        params.append(float(data['balance']))
    
    if updates:
        params.append(data['account_id'])
        params.append(user_id)
        db.execute(
            f"UPDATE accounts SET {', '.join(updates)} WHERE id = ? AND user_id = ?",
            tuple(params)
        )
    
    db.commit()
    return jsonify({'success': True})

@app.route('/api/stock/list', methods=['GET'])
@api_auth_required
def api_list():
    """Lista todas as contas do estoque."""
    user_id = g.api_user['id']
    db = get_db()
    
    status_filter = request.args.get('status')
    
    if status_filter:
        rows = db.execute(
            "SELECT * FROM accounts WHERE user_id = ? AND status = ? ORDER BY updated_at DESC",
            (user_id, status_filter)
        ).fetchall()
    else:
        rows = db.execute(
            "SELECT * FROM accounts WHERE user_id = ? ORDER BY updated_at DESC LIMIT 100",
            (user_id,)
        ).fetchall()
    
    accounts = []
    for row in rows:
        acc = dict_from_row(row)
        accounts.append({
            'id': acc['id'],
            'username': acc['username'],
            'name_real': acc.get('name_real'),
            'status': acc['status'],
            'action_count': acc['action_count'],
            'balance': acc['balance'],
            'json_expired': bool(acc['json_expired']),
            'last_used': acc['last_used'],
            'created_at': acc['created_at'],
        })
    
    return jsonify({'success': True, 'accounts': accounts, 'count': len(accounts)})

@app.route('/api/stock/stats', methods=['GET'])
@api_auth_required
def api_stats():
    """Estatísticas do estoque."""
    user_id = g.api_user['id']
    db = get_db()
    
    total = db.execute('SELECT COUNT(*) as cnt FROM accounts WHERE user_id = ?', (user_id,)).fetchone()['cnt']
    available = db.execute("SELECT COUNT(*) as cnt FROM accounts WHERE user_id = ? AND status = 'available'", (user_id,)).fetchone()['cnt']
    in_use = db.execute("SELECT COUNT(*) as cnt FROM accounts WHERE user_id = ? AND status = 'in_use'", (user_id,)).fetchone()['cnt']
    punished = db.execute("SELECT COUNT(*) as cnt FROM accounts WHERE user_id = ? AND status = 'punished'", (user_id,)).fetchone()['cnt']
    expired = db.execute("SELECT COUNT(*) as cnt FROM accounts WHERE user_id = ? AND json_expired = 1", (user_id,)).fetchone()['cnt']
    
    total_actions = db.execute(
        'SELECT COALESCE(SUM(action_count), 0) as total FROM accounts WHERE user_id = ?', (user_id,)
    ).fetchone()['total']
    
    total_balance = db.execute(
        'SELECT COALESCE(SUM(balance), 0) as total FROM accounts WHERE user_id = ?', (user_id,)
    ).fetchone()['total']
    
    return jsonify({
        'success': True,
        'stats': {
            'total_accounts': total,
            'available': available,
            'in_use': in_use,
            'punished': punished,
            'json_expired': expired,
            'total_actions': total_actions,
            'total_balance': float(total_balance),
        }
    })

# ═══════════════════════════════════════════════════════════════════
# INICIALIZAÇÃO
# ═══════════════════════════════════════════════════════════════════

with app.app_context():
    init_db()

if __name__ == '__main__':
    port = int(os.environ.get('PORT', 5000))
    app.run(host='0.0.0.0', port=port, debug=False)
