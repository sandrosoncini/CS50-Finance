import os

import sys
from datetime import datetime
from cs50 import SQL
from flask import Flask, flash, jsonify, redirect, render_template, request, session
from flask_session import Session
from tempfile import mkdtemp
from werkzeug.exceptions import default_exceptions, HTTPException, InternalServerError
from werkzeug.security import check_password_hash, generate_password_hash

from helpers import apology, login_required, lookup, usd, can_afford, check_own_shares

# Configure application
app = Flask(__name__)

# Ensure templates are auto-reloaded
app.config["TEMPLATES_AUTO_RELOAD"] = True

# Ensure responses aren't cached
@app.after_request
def after_request(response):
    response.headers["Cache-Control"] = "no-cache, no-store, must-revalidate"
    response.headers["Expires"] = 0
    response.headers["Pragma"] = "no-cache"
    return response

# Custom filter
app.jinja_env.filters["usd"] = usd

# Configure session to use filesystem (instead of signed cookies)
app.config["SESSION_FILE_DIR"] = mkdtemp()
app.config["SESSION_PERMANENT"] = False
app.config["SESSION_TYPE"] = "filesystem"
Session(app)

# Configure CS50 Library to use SQLite database
db = SQL("sqlite:///finance.db")

# Make sure API key is set
if not os.environ.get("API_KEY"):
    raise RuntimeError("API_KEY not set")


@app.route("/")
@login_required
def index():
    """Show portfolio of stocks"""
    
    
    shares = db.execute("SELECT symbol, name, shares FROM shares WHERE user_id = :user_id", user_id= session["user_id"])
    cash = db.execute ("SELECT cash FROM users WHERE id=:id", id=session["user_id"])
    total = 0
    own = [] 
    
    
    for share in shares:
        symbol = lookup(share["symbol"])
        own.append({
            "symbol": share["symbol"],
            "name": share["name"],
            "shares": share["shares"],
            "price": usd(symbol["price"]),
            "total_price": usd(share["shares"] * symbol["price"])
            })
          
        total += share["shares"] * symbol["price"]
        
    return render_template("index.html", own = own, cash=usd(cash[0]["cash"]) , total=usd(total + cash[0]["cash"]))

@app.route("/buy", methods=["GET", "POST"])
@login_required
def buy():
    """Buy shares of stock"""
    
    if request.method == "POST":
        symbol = lookup(request.form.get("symbol"))
        shares = int(request.form.get("shares"))
        user = session["user_id"]
        date = datetime.now()
        cash = can_afford(symbol["price"], shares, user)
        own_shares = int(check_own_shares(user, symbol["symbol"]))
       
        
        if  shares <= 0:
            return apology("Share quantity must be greater than 0", 403)
        elif symbol == None:
            return apology("Symbol does not exist", 403)
        elif cash - (symbol["price"] * shares) < 0:
            return apology("you can not afford", 403)
            
        if own_shares > 0:
            
            db.execute("UPDATE shares SET shares=:shares WHERE user_id=:user_id AND symbol=:symbol", shares=shares + own_shares, user_id=user, symbol=symbol["symbol"])
            db.execute("INSERT INTO transactions (user_id, shares, symbol, price ) VALUES (:user_id, :shares, :symbol, :price)",user_id = user, shares = shares,symbol= symbol["symbol"], price=symbol["price"]) 
        else:
            db.execute("INSERT INTO shares (user_id, shares, symbol,name, price,created_at ) VALUES (:user_id, :shares, :symbol, :name, :price, :created_at)", 
                        user_id = user, shares = shares,symbol= symbol["symbol"], name= symbol["name"], price=symbol["price"], created_at = date)  
            db.execute("INSERT INTO transactions (user_id, shares, symbol, price ) VALUES (:user_id, :shares, :symbol, :price)",user_id = user, shares = shares,symbol= symbol["symbol"], price=symbol["price"]) 
        db.execute("UPDATE users SET cash=:cash Where id=:id", cash=cash - (symbol["price"] * shares), id=user)
        
        return redirect("/")
    else:
        return render_template("buy.html")


@app.route("/history")
@login_required
def history():
    """Show history of transactions"""
    
    transactions = db.execute("SELECT * FROM transactions WHERE user_id = :user_id", user_id= session["user_id"])
    
    transacted = [] 
    for t in transactions:
        transacted.append({
            "symbol": t["symbol"],
            "shares": t["shares"],
            "price": usd(t["price"]),
            "create_at": t["create_at"]
            })
          
        
    
    
    return render_template("history.html", transacted= transacted)


@app.route("/login", methods=["GET", "POST"])
def login():
    """Log user in"""

    # Forget any user_id
    session.clear()

    # User reached route via POST (as by submitting a form via POST)
    if request.method == "POST":

        # Ensure username was submitted
        if not request.form.get("username"):
            return apology("must provide username", 403)

        # Ensure password was submitted
        elif not request.form.get("password"):
            return apology("must provide password", 403)

        # Query database for username
        rows = db.execute("SELECT * FROM users WHERE username = :username",
                          username=request.form.get("username"))

        # Ensure username exists and password is correct
        if len(rows) != 1 or not check_password_hash(rows[0]["hash"], request.form.get("password")):
            return apology("invalid username and/or password", 403)

        # Remember which user has logged in
        session["user_id"] = rows[0]["id"]

        # Redirect user to home page
        return redirect("/")

    # User reached route via GET (as by clicking a link or via redirect)
    else:
        return render_template("login.html")


@app.route("/logout")
def logout():
    """Log user out"""

    # Forget any user_id
    session.clear()

    # Redirect user to login form
    return redirect("/")


@app.route("/quote", methods=["GET", "POST"])
@login_required
def quote():

    if request.method == "POST":
        symbol = request.form.get("symbol")
        quoted = lookup(request.form.get("symbol"))
        if quoted == None or symbol == '':
            return apology("Symbol does not exit", 403)

        return render_template("quoted.html", name=quoted["name"], price=quoted["price"], symbol=quoted["symbol"])
    else:
        return render_template("quote.html")


@app.route("/register", methods=["GET", "POST"])
def register():
    username = request.form.get("username")
    password = request.form.get("password")
    password_confirmation = request.form.get("confirm_password")
    cash = request.form.get("cash")

    if request.method == "POST":

        if not username:
            return apology("must provide username", 403)

        elif not password:
            return apology("must provide password", 403)

        elif password != password_confirmation:
            return apology("password and confirm password must be the same", 403)
        else:
            rows = db.execute("SELECT * FROM users")

            for row in rows:
                if row["username"].lower() == username.lower():
                    return apology("username alredy exist", 403)

            db.execute("INSERT INTO users (username, hash, cash) VALUES (:username, :password, :cash)", username = username, password=generate_password_hash(password), cash=cash)
            return redirect ("/")
    else:
        
        return render_template("register.html")


@app.route("/sell", methods=["GET", "POST"])
@login_required
def sell():
    """Sell shares of stock"""
    
    
    if request.method == "POST":
        symbol = lookup(request.form.get("symbol"))
        shares =  -1 * int(request.form.get("shares"))
        user = session["user_id"]
        cash = can_afford(symbol["price"], shares, user) 
        rows = db.execute("SELECT shares FROM shares WHERE user_id=:user_id AND symbol=:symbol", user_id= user, symbol=symbol["symbol"])
        
        # if  rows = 0:
        #     return apology("Share quantity must be greater than 0", 403)
        # elif symbol == None:
        #     return apology("Symbol does not exist", 403)
        # elif cash < 0:
        #     return apology("you can not afford", 403)
          
          
            
        # if check_own_shares(user, symbol["symbol"]):
        #     db.execute("UPDATE shares SET shares=:shares WHERE user_id=:user_id AND symbol=:symbol", shares=shares, user_id=user, symbol=symbol["symbol"])
        # else:
        db.execute("INSERT INTO transactions (user_id, shares, symbol, price ) VALUES (:user_id, :shares, :symbol, :price )", 
                        user_id = user, shares = shares,symbol= symbol["symbol"], price=symbol["price"])  
       
        db.execute("UPDATE shares SET shares=:shares Where user_id=:user_id", shares=(rows[0]['shares'] + shares), user_id=user)
        db.execute("UPDATE users SET cash=:cash Where id=:id", cash=cash, id=user)
        
        return redirect("/")
    else:
        return render_template("sell.html")
    


def errorhandler(e):
    """Handle error"""
    if not isinstance(e, HTTPException):
        e = InternalServerError()
    return apology(e.name, e.code)


# Listen for errors
for code in default_exceptions:
    app.errorhandler(code)(errorhandler)
