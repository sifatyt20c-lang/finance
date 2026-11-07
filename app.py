import os

from cs50 import SQL
from flask import Flask, flash, redirect, render_template, request, session
from flask_session import Session
from werkzeug.security import check_password_hash, generate_password_hash

from helpers import login_required, lookup, usd

app = Flask(__name__)
app.jinja_env.filters["usd"] = usd

app.config["SESSION_PERMANENT"] = False
app.config["SESSION_TYPE"] = "filesystem"
Session(app)

db = SQL("sqlite:///finance.db")

@app.after_request
def after_request(response):
    response.headers["Cache-Control"] = "no-cache, no-store, must-revalidate"
    response.headers["Expires"] = 0
    response.headers["Pragma"] = "no-cache"
    return response

def apology(message, code=400):
    def escape(s):
        for old, new in [("-", "--"), ("_", "__"), (" ", "-"), ("?", "~q"),
                         ("%", "~p"), ("#", "~h"), ("/", "~s"), ("\"", "''")]:
            s = s.replace(old, new)
        return s
    return render_template("apology.html", top=code, message=escape(message)), code

@app.route("/")
@login_required
def index():
    user_id = session["user_id"]
    stocks = db.execute(
        "SELECT symbol, SUM(shares) as total_shares FROM transactions WHERE user_id = ? GROUP BY symbol HAVING total_shares > 0",
        user_id
    )
    cash_row = db.execute("SELECT cash FROM users WHERE id = ?", user_id)
    cash = cash_row[0]["cash"]
    
    total_value = cash
    portfolio = []
    
    for stock in stocks:
        quote = lookup(stock["symbol"])
        if quote:
            current_price = quote["price"]
            total_shares = stock["total_shares"]
            holding_total = current_price * total_shares
            total_value += holding_total
            portfolio.append({
                "symbol": stock["symbol"],
                "shares": total_shares,
                "price": current_price,
                "total": holding_total
            })
            
    return render_template("index.html", portfolio=portfolio, cash=cash, total_value=total_value)

@app.route("/quote", methods=["GET", "POST"])
@login_required
def quote():
    if request.method == "POST":
        symbol = request.form.get("symbol")
        if not symbol:
            return apology("must provide symbol", 400)
        stock = lookup(symbol.strip())
        if not stock:
            return apology("invalid symbol", 400)
        return render_template("quoted.html", stock=stock)
    else:
        return render_template("quote.html")

@app.route("/buy", methods=["GET", "POST"])
@login_required
def buy():
    if request.method == "POST":
        symbol = request.form.get("symbol")
        shares = request.form.get("shares")

        if not symbol:
            return apology("must provide symbol", 400)
        stock = lookup(symbol.strip())
        if not stock:
            return apology("invalid symbol", 400)

        try:
            shares = int(shares)
            if shares <= 0:
                raise ValueError
        except (ValueError, TypeError):
            return apology("shares must be a positive integer", 400)

        user_id = session["user_id"]
        user_cash = db.execute("SELECT cash FROM users WHERE id = ?", user_id)[0]["cash"]
        cost = stock["price"] * shares

        if user_cash < cost:
            return apology("can't afford", 400)

        db.execute("UPDATE users SET cash = cash - ? WHERE id = ?", cost, user_id)
        db.execute(
            "INSERT INTO transactions (user_id, symbol, shares, price) VALUES (?, ?, ?, ?)",
            user_id, stock["symbol"], shares, stock["price"]
        )
        return redirect("/")
    else:
        return render_template("buy.html")

@app.route("/sell", methods=["GET", "POST"])
@login_required
def sell():
    user_id = session["user_id"]
    if request.method == "POST":
        symbol = request.form.get("symbol")
        shares = request.form.get("shares")

        if not symbol:
            return apology("must provide symbol", 400)
        try:
            shares = int(shares)
            if shares <= 0:
                raise ValueError
        except (ValueError, TypeError):
            return apology("shares must be a positive integer", 400)

        user_shares = db.execute(
            "SELECT SUM(shares) as total_shares FROM transactions WHERE user_id = ? AND symbol = ? GROUP BY symbol",
            user_id, symbol
        )

        if not user_shares or user_shares[0]["total_shares"] < shares:
            return apology("too many shares", 400)

        stock = lookup(symbol)
        if not stock:
            return apology("invalid symbol", 400)

        revenue = stock["price"] * shares
        db.execute("UPDATE users SET cash = cash + ? WHERE id = ?", revenue, user_id)
        db.execute(
            "INSERT INTO transactions (user_id, symbol, shares, price) VALUES (?, ?, ?, ?)",
            user_id, symbol, -shares, stock["price"]
        )
        return redirect("/")
    else:
        stocks = db.execute(
            "SELECT symbol FROM transactions WHERE user_id = ? GROUP BY symbol HAVING SUM(shares) > 0",
            user_id
        )
        return render_template("sell.html", stocks=stocks)

@app.route("/history")
@login_required
def history():
    user_id = session["user_id"]
    transactions = db.execute(
        "SELECT symbol, shares, price, timestamp FROM transactions WHERE user_id = ? ORDER BY timestamp DESC",
        user_id
    )
    return render_template("history.html", transactions=transactions)

@app.route("/login", methods=["GET", "POST"])
def login():
    session.clear()
    if request.method == "POST":
        if not request.form.get("username"):
            return apology("must provide username", 403)
        elif not request.form.get("password"):
            return apology("must provide password", 403)
            
        rows = db.execute("SELECT * FROM users WHERE username = ?", request.form.get("username"))
        if len(rows) != 1 or not check_password_hash(rows[0]["hash"], request.form.get("password")):
            return apology("invalid username and/or password", 403)
            
        session["user_id"] = rows[0]["id"]
        return redirect("/")
    else:
        return render_template("login.html")

@app.route("/logout")
def logout():
    session.clear()
    return redirect("/")

@app.route("/register", methods=["GET", "POST"])
def register():
    if request.method == "POST":
        username = request.form.get("username")
        password = request.form.get("password")
        confirmation = request.form.get("confirmation")

        if not username:
            return apology("must provide username", 400)
        elif not password:
            return apology("must provide password", 400)
        elif not confirmation:
            return apology("must provide confirmation password", 400)
        elif password != confirmation:
            return apology("passwords must match", 400)

        rows = db.execute("SELECT * FROM users WHERE username = ?", username)
        if len(rows) > 0:
            return apology("username already exists", 400)

        hash_password = generate_password_hash(password)
        db.execute("INSERT INTO users (username, hash) VALUES (?, ?)", username, hash_password)
        return redirect("/login")
    else:
        return render_template("register.html")
