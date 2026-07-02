#!/usr/bin/env python3
"""
Financas Familiares - PythonAnywhere Production
Flask + SQLite + Chart.js
"""

import os
from flask import Flask, render_template, request, redirect, url_for, flash, session, jsonify
from flask_sqlalchemy import SQLAlchemy
from werkzeug.security import generate_password_hash, check_password_hash
from functools import wraps
from datetime import datetime

# ============================================================
# CONFIGURACAO
# ============================================================

basedir = os.path.abspath(os.path.dirname(__file__))

app = Flask(__name__)
app.config['SECRET_KEY'] = os.environ.get('SECRET_KEY', 'financas-familia-2024-seguro')
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///' + os.path.join(basedir, 'financas.db')
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
app.config['SQLALCHEMY_ENGINE_OPTIONS'] = {'pool_pre_ping': True}

db = SQLAlchemy(app)

# ============================================================
# MODELOS
# ============================================================

class User(db.Model):
    __tablename__ = 'users'
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), nullable=False)
    email = db.Column(db.String(120), unique=True, nullable=False)
    password_hash = db.Column(db.String(256), nullable=False)
    is_admin = db.Column(db.Boolean, default=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    expenses = db.relationship('VariableExpense', backref='user', lazy=True, cascade='all, delete-orphan')
    fixed_expenses = db.relationship('FixedExpense', backref='user', lazy=True, cascade='all, delete-orphan')

class ExpenseType(db.Model):
    __tablename__ = 'expense_types'
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), nullable=False)
    color = db.Column(db.String(7), default='#FF6B00')
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    variable_expenses = db.relationship('VariableExpense', backref='expense_type', lazy=True)
    fixed_expenses = db.relationship('FixedExpense', backref='expense_type', lazy=True)

class FixedExpense(db.Model):
    __tablename__ = 'fixed_expenses'
    id = db.Column(db.Integer, primary_key=True)
    description = db.Column(db.String(200), nullable=False)
    value = db.Column(db.Float, nullable=False)
    due_day = db.Column(db.Integer, nullable=False)
    paid = db.Column(db.Boolean, default=False)
    paid_at = db.Column(db.DateTime, nullable=True)
    month = db.Column(db.Integer, nullable=False)
    year = db.Column(db.Integer, nullable=False)
    is_recurring = db.Column(db.Boolean, default=True)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)
    expense_type_id = db.Column(db.Integer, db.ForeignKey('expense_types.id'), nullable=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

class VariableExpense(db.Model):
    __tablename__ = 'variable_expenses'
    id = db.Column(db.Integer, primary_key=True)
    description = db.Column(db.String(200), nullable=False)
    value = db.Column(db.Float, nullable=False)
    date = db.Column(db.DateTime, default=datetime.utcnow)
    month = db.Column(db.Integer, nullable=False)
    year = db.Column(db.Integer, nullable=False)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)
    expense_type_id = db.Column(db.Integer, db.ForeignKey('expense_types.id'), nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

# ============================================================
# HELPERS
# ============================================================

MONTHS_PT = [
    "Janeiro", "Fevereiro", "Marco", "Abril", "Maio", "Junho",
    "Julho", "Agosto", "Setembro", "Outubro", "Novembro", "Dezembro"
]

def login_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if 'user_id' not in session:
            flash('Faca login para continuar.', 'warning')
            return redirect(url_for('login'))
        return f(*args, **kwargs)
    return decorated_function

def get_month_context(month_idx, year):
    month_idx = max(0, min(11, month_idx))
    return {
        "name": MONTHS_PT[month_idx],
        "index": month_idx,
        "year": year,
        "prev_month": month_idx - 1 if month_idx > 0 else 11,
        "prev_year": year if month_idx > 0 else year - 1,
        "next_month": month_idx + 1 if month_idx < 11 else 0,
        "next_year": year if month_idx < 11 else year + 1,
    }

def format_currency(value):
    return f"R$ {value:,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")

def get_current_month_year():
    now = datetime.now()
    return now.month - 1, now.year

# ============================================================
# SEED DATA - Apenas usuarios e tipos basicos
# ============================================================

def seed_data():
    default_types = [
        ("Alimentacao", "#FF6B00"),
        ("Transporte", "#4ECDC4"),
        ("Saude", "#45B7D1"),
        ("Lazer", "#96CEB4"),
        ("Educacao", "#FFEAA7"),
        ("Moradia", "#DDA0DD"),
        ("Internet", "#74B9FF"),
        ("Energia", "#FDCB6E"),
        ("Agua", "#55A3FF"),
        ("Streaming", "#E17055"),
    ]

    for name, color in default_types:
        if not ExpenseType.query.filter_by(name=name).first():
            db.session.add(ExpenseType(name=name, color=color))

    if not User.query.filter_by(email="paulo@familia.com").first():
        db.session.add(User(
            name="Paulo",
            email="paulo@familia.com",
            password_hash=generate_password_hash("123456"),
            is_admin=True
        ))

    if not User.query.filter_by(email="cris@familia.com").first():
        db.session.add(User(
            name="Cris",
            email="cris@familia.com",
            password_hash=generate_password_hash("123456"),
            is_admin=False
        ))

    db.session.commit()

# ============================================================
# ROTAS - AUTH
# ============================================================

@app.route("/login", methods=["GET", "POST"])
def login():
    if 'user_id' in session:
        return redirect(url_for('dashboard'))

    if request.method == "POST":
        email = request.form.get("email", "").strip().lower()
        password = request.form.get("password", "")

        user = User.query.filter_by(email=email).first()
        if user and check_password_hash(user.password_hash, password):
            session['user_id'] = user.id
            session['user_name'] = user.name
            session['is_admin'] = user.is_admin
            flash(f'Bem-vindo, {user.name}!', 'success')
            return redirect(url_for('dashboard'))
        else:
            flash('Email ou senha incorretos.', 'danger')

    return render_template("login.html")

@app.route("/register", methods=["GET", "POST"])
def register():
    if request.method == "POST":
        name = request.form.get("name", "").strip()
        email = request.form.get("email", "").strip().lower()
        password = request.form.get("password", "")
        confirm = request.form.get("confirm", "")

        if not all([name, email, password]):
            flash('Preencha todos os campos.', 'warning')
            return redirect(url_for('register'))

        if password != confirm:
            flash('As senhas nao coincidem.', 'warning')
            return redirect(url_for('register'))

        if User.query.filter_by(email=email).first():
            flash('Email ja cadastrado.', 'warning')
            return redirect(url_for('register'))

        is_first = User.query.count() == 0
        user = User(
            name=name,
            email=email,
            password_hash=generate_password_hash(password),
            is_admin=is_first
        )
        db.session.add(user)
        db.session.commit()

        flash('Conta criada com sucesso! Faca login.', 'success')
        return redirect(url_for('login'))

    return render_template("register.html")

@app.route("/logout")
def logout():
    session.clear()
    flash('Voce saiu da conta.', 'info')
    return redirect(url_for('login'))

# ============================================================
# ROTAS - DASHBOARD
# ============================================================

@app.route("/")
@app.route("/dashboard")
@login_required
def dashboard():
    month = request.args.get("month", type=int)
    year = request.args.get("year", type=int)

    if month is None or year is None:
        month, year = get_current_month_year()

    month = max(0, min(11, month))
    ctx = get_month_context(month, year)

    users = {u.id: {"name": u.name, "email": u.email} for u in User.query.all()}

    fixed_all = FixedExpense.query.filter_by(month=month, year=year).all()
    total_fixed = len(fixed_all)
    paid_fixed = sum(1 for f in fixed_all if f.paid)
    pending_fixed = [f for f in fixed_all if not f.paid]

    variable_all = VariableExpense.query.filter_by(month=month, year=year).all()

    chart_labels = []
    chart_data = []
    chart_colors = []

    for et in ExpenseType.query.all():
        total = sum(v.value for v in variable_all if v.expense_type_id == et.id)
        if total > 0:
            chart_labels.append(et.name)
            chart_data.append(round(total, 2))
            chart_colors.append(et.color)

    user_expense_data = {}
    for uid, uinfo in users.items():
        total = sum(v.value for v in variable_all if v.user_id == uid)
        user_expense_data[uid] = {
            "name": uinfo["name"],
            "total": round(total, 2)
        }

    total_variable = sum(v.value for v in variable_all)
    total_fixed_paid = sum(f.value for f in fixed_all if f.paid)
    total_fixed_pending = sum(f.value for f in fixed_all if not f.paid)
    total_gastos = total_variable + total_fixed_paid + total_fixed_pending

    recent_variables = VariableExpense.query.filter_by(month=month, year=year).order_by(VariableExpense.created_at.desc()).limit(10).all()

    return render_template("dashboard.html",
        month_ctx=ctx,
        total_gastos=total_gastos,
        total_variable=total_variable,
        total_fixed_paid=total_fixed_paid,
        total_fixed_pending=total_fixed_pending,
        total_fixed=total_fixed,
        paid_fixed=paid_fixed,
        pending_fixed=pending_fixed,
        chart_labels=chart_labels,
        chart_data=chart_data,
        chart_colors=chart_colors,
        user_expense_data=user_expense_data,
        users=users,
        expense_types=ExpenseType.query.all(),
        recent_variables=recent_variables,
        all_users=User.query.all(),
    )

# ============================================================
# ROTAS - DESPESAS FIXAS
# ============================================================

@app.route("/fixed-expenses")
@login_required
def fixed_expenses():
    month = request.args.get("month", type=int)
    year = request.args.get("year", type=int)

    if month is None or year is None:
        month, year = get_current_month_year()

    month = max(0, min(11, month))
    ctx = get_month_context(month, year)

    expenses = FixedExpense.query.filter_by(month=month, year=year).order_by(FixedExpense.due_day).all()
    users = {u.id: u.name for u in User.query.all()}
    types = {t.id: t.name for t in ExpenseType.query.all()}

    return render_template("fixed_expenses.html",
        month_ctx=ctx,
        expenses=expenses,
        users=users,
        types=types,
        expense_types=ExpenseType.query.all(),
        all_users=User.query.all(),
    )

@app.route("/fixed-expenses/pay/<int:expense_id>", methods=["POST"])
@login_required
def pay_fixed_expense(expense_id):
    expense = FixedExpense.query.get_or_404(expense_id)

    if expense.paid:
        expense.paid = False
        expense.paid_at = None
        db.session.commit()
        flash(f'Despesa "{expense.description}" marcada como pendente.', 'warning')
        return redirect(request.referrer or url_for('fixed_expenses',
            month=expense.month, year=expense.year))

    real_value = request.form.get("real_value", "").strip()
    if real_value:
        try:
            expense.value = float(real_value.replace(",", "."))
        except ValueError:
            pass

    expense.paid = True
    expense.paid_at = datetime.utcnow()
    db.session.commit()

    flash(f'Despesa "{expense.description}" paga! Valor: R$ {expense.value:.2f}', 'success')
    return redirect(request.referrer or url_for('fixed_expenses',
        month=expense.month, year=expense.year))

@app.route("/fixed-expenses/add", methods=["POST"])
@login_required
def add_fixed_expense():
    description = request.form.get("description", "").strip()
    value = float(request.form.get("value", 0))
    due_day = int(request.form.get("due_day", 1))
    user_id = int(request.form.get("user_id", session.get('user_id', 1)))
    expense_type_id = request.form.get("expense_type_id", type=int)
    is_recurring = request.form.get("is_recurring") == "on"
    month = request.args.get("month", type=int, default=get_current_month_year()[0])
    year = request.args.get("year", type=int, default=get_current_month_year()[1])

    if not description or value <= 0:
        flash('Preencha todos os campos corretamente.', 'warning')
        return redirect(url_for('fixed_expenses', month=month, year=year))

    expense = FixedExpense(
        description=description,
        value=value,
        due_day=due_day,
        month=month,
        year=year,
        is_recurring=is_recurring,
        user_id=user_id,
        expense_type_id=expense_type_id
    )
    db.session.add(expense)
    db.session.commit()

    if is_recurring:
        created_count = 1
        for i in range(1, 12):
            target_month = month + i
            target_year = year

            while target_month > 11:
                target_month -= 12
                target_year += 1

            exists = FixedExpense.query.filter_by(
                description=description,
                month=target_month,
                year=target_year,
                user_id=user_id
            ).first()

            if not exists:
                rec_expense = FixedExpense(
                    description=description,
                    value=value,
                    due_day=due_day,
                    month=target_month,
                    year=target_year,
                    is_recurring=True,
                    user_id=user_id,
                    expense_type_id=expense_type_id
                )
                db.session.add(rec_expense)
                created_count += 1

        db.session.commit()
        flash(f'Despesa recorrente cadastrada! {created_count} meses criados.', 'success')
    else:
        flash('Despesa fixa cadastrada com sucesso!', 'success')

    return redirect(url_for('fixed_expenses', month=month, year=year))

@app.route("/fixed-expenses/delete/<int:expense_id>", methods=["POST"])
@login_required
def delete_fixed_expense(expense_id):
    expense = FixedExpense.query.get_or_404(expense_id)
    month, year = expense.month, expense.year
    db.session.delete(expense)
    db.session.commit()
    flash('Despesa fixa removida.', 'info')
    return redirect(url_for('fixed_expenses', month=month, year=year))

# ============================================================
# ROTAS - DESPESAS VARIAVEIS
# ============================================================

@app.route("/variable-expenses")
@login_required
def variable_expenses():
    month = request.args.get("month", type=int)
    year = request.args.get("year", type=int)

    if month is None or year is None:
        month, year = get_current_month_year()

    month = max(0, min(11, month))
    ctx = get_month_context(month, year)

    expenses = VariableExpense.query.filter_by(month=month, year=year).order_by(VariableExpense.date.desc()).all()
    users = {u.id: u.name for u in User.query.all()}
    types = {t.id: {"name": t.name, "color": t.color} for t in ExpenseType.query.all()}

    total = sum(e.value for e in expenses)

    return render_template("variable_expenses.html",
        month_ctx=ctx,
        expenses=expenses,
        users=users,
        types=types,
        total=total,
        expense_types=ExpenseType.query.all(),
        all_users=User.query.all(),
    )

@app.route("/variable-expenses/add", methods=["POST"])
@login_required
def add_variable_expense():
    description = request.form.get("description", "").strip()
    value = float(request.form.get("value", 0))
    expense_type_id = int(request.form.get("expense_type_id", 1))
    user_id = int(request.form.get("user_id", session.get('user_id', 1)))
    month = request.args.get("month", type=int, default=get_current_month_year()[0])
    year = request.args.get("year", type=int, default=get_current_month_year()[1])

    if not description or value <= 0:
        flash('Preencha todos os campos corretamente.', 'warning')
        return redirect(url_for('variable_expenses', month=month, year=year))

    expense = VariableExpense(
        description=description,
        value=value,
        month=month,
        year=year,
        user_id=user_id,
        expense_type_id=expense_type_id
    )
    db.session.add(expense)
    db.session.commit()

    flash('Despesa variavel adicionada!', 'success')
    return redirect(url_for('variable_expenses', month=month, year=year))

@app.route("/variable-expenses/delete/<int:expense_id>", methods=["POST"])
@login_required
def delete_variable_expense(expense_id):
    expense = VariableExpense.query.get_or_404(expense_id)
    month, year = expense.month, expense.year
    db.session.delete(expense)
    db.session.commit()
    flash('Despesa removida.', 'info')
    return redirect(url_for('variable_expenses', month=month, year=year))

# ============================================================
# ROTAS - TIPOS DE DESPESA
# ============================================================

@app.route("/expense-types")
@login_required
def expense_types():
    types = ExpenseType.query.order_by(ExpenseType.name).all()
    return render_template("expense_types.html", types=types)

@app.route("/expense-types/add", methods=["POST"])
@login_required
def add_expense_type():
    name = request.form.get("name", "").strip()
    color = request.form.get("color", "#FF6B00").strip()

    if not name:
        flash('Informe o nome do tipo.', 'warning')
        return redirect(url_for('expense_types'))

    if ExpenseType.query.filter_by(name=name).first():
        flash('Este tipo ja existe.', 'warning')
        return redirect(url_for('expense_types'))

    db.session.add(ExpenseType(name=name, color=color))
    db.session.commit()
    flash(f'Tipo "{name}" cadastrado!', 'success')
    return redirect(url_for('expense_types'))

@app.route("/expense-types/delete/<int:type_id>", methods=["POST"])
@login_required
def delete_expense_type(type_id):
    et = ExpenseType.query.get_or_404(type_id)
    db.session.delete(et)
    db.session.commit()
    flash('Tipo removido.', 'info')
    return redirect(url_for('expense_types'))

# ============================================================
# ROTAS - API
# ============================================================

@app.route("/api/chart-data")
@login_required
def api_chart_data():
    month = request.args.get("month", type=int, default=get_current_month_year()[0])
    year = request.args.get("year", type=int, default=get_current_month_year()[1])

    variable_all = VariableExpense.query.filter_by(month=month, year=year).all()

    labels = []
    data = []
    colors = []

    for et in ExpenseType.query.all():
        total = sum(v.value for v in variable_all if v.expense_type_id == et.id)
        if total > 0:
            labels.append(et.name)
            data.append(round(total, 2))
            colors.append(et.color)

    return jsonify({"labels": labels, "data": data, "colors": colors})

# ============================================================
# ROTA DE INICIALIZACAO (rode uma vez na producao)
# ============================================================

@app.route("/init")
def init():
    """Rota para inicializar o banco. Acesse /init uma vez apos o deploy."""
    try:
        db.create_all()
        seed_data()
        return "Banco inicializado com sucesso! <a href='/login'>Ir para login</a>"
    except Exception as e:
        return f"Erro: {str(e)}"

# ============================================================
# FILTROS JINJA
# ============================================================

@app.template_filter('currency')
def currency_filter(value):
    return format_currency(float(value))

@app.template_filter('month_name')
def month_name_filter(idx):
    return MONTHS_PT[idx] if 0 <= idx < 12 else ""

# ============================================================
# CONTEXT PROCESSORS
# ============================================================

@app.context_processor
def inject_globals():
    return {
        'now': datetime.now(),
        'months': MONTHS_PT,
    }

# ============================================================
# MAIN (apenas para desenvolvimento local)
# ============================================================

if __name__ == "__main__":
    with app.app_context():
        db.create_all()
        seed_data()
    app.run(debug=True, port=5000)
