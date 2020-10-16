import os

from cs50 import SQL
from flask import Flask, flash, jsonify, redirect, render_template, request, session
from flask_session import Session
from tempfile import mkdtemp
from werkzeug.exceptions import default_exceptions, HTTPException, InternalServerError
from werkzeug.security import check_password_hash, generate_password_hash

from helpers import apology, login_required, lookup, usd

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
db = SQL("postgres://lwbltamvgcigwb:dd1b48d778a25a3547b7838c3fe47311c62cdcefa00d2491b8f54a2818c44c74@ec2-54-75-229-28.eu-west-1.compute.amazonaws.com:5432/ddcu4f2tbi57eq")

# Make sure API key is set [INACTIVE]
#if not os.environ.get("API_KEY"):
    #raise RuntimeError("API_KEY not set")

# Make sure API key is set
if not os.environ.get("API_KEY"):
    try:
        os.environ["API_KEY"]="pk_0841a6a938d94bf1b59e720032396ee3"
    except:
        raise RuntimeError("API_KEY not set")

@app.route("/")
@login_required
def index():
    """Show portfolio of stocks"""

    # Define empty lists. Lists are used because some variable such as the stock price and total needs to go through a pre-defined function (ie. usd)
    # So it's not sufficient to just export the return dictionary from execute below. Maybe there is a better way but I haven't found it yet.
    stock_symbol = []
    stock_name = []
    shares_owned = []
    stock_price = []
    total = []
    gross = 0

    # SQL query return rows (dictionary) containing shares that the user owns
    rows = db.execute("SELECT * FROM shares WHERE id = ? ORDER BY stock_symbol", session["user_id"])
    for row in range(len(rows)):
        stock_symbol.append(rows[row]["stock_symbol"])
        stock_name.append(rows[row]["stock_name"])
        shares_owned.append(rows[row]["shares_owned"])
        stock_price.append(usd(rows[row]["stock_price"]))
        total.append(usd(rows[row]["total"]))
        gross = gross + rows[row]["total"]

    # SQL query returns one row where the user's cash can be extracted
    rowss = db.execute("SELECT * FROM users WHERE id = ?", session["user_id"])
    cash = usd(rowss[0]["cash"])
    gross = usd(gross + rowss[0]["cash"])

    return render_template("index.html", rows=rows, cash=cash, stock_symbol=stock_symbol, stock_name=stock_name, shares_owned=shares_owned, stock_price=stock_price, total=total, gross=gross)


@app.route("/buy", methods=["GET", "POST"])
@login_required
def buy():
    """Buy shares of stock"""

    # If the user presses buy on the buy page
    if request.method == "POST":

        # Define variables
        symbol = request.form.get("symbol")
        shares = request.form.get("shares")
        quote = lookup(symbol)

        # Error checks
        if not symbol:
            return apology("must provide stock symbol", 403)
        if quote == None:
            return apology("stock does not exist", 403)
        if not shares:
            return apology("must specify number of shares", 403)
        if int(shares) <= 0:
            return apology("must specify positive integer of shares", 403)

        # Extract user's cash
        rows = db.execute("SELECT * FROM users WHERE id = ?", session["user_id"])
        cash = rows[0]["cash"]

        total = quote["price"] * int(shares)

        # Error check
        if total > cash:
            return apology("insufficient cash to complete transaction", 403)

        # Log the transaction
        db.execute("INSERT INTO transactions (stock_symbol, stock_price, shares_transacted, id, timestamp) VALUES (?, ?, ?, ?, CURRENT_TIMESTAMP)", quote ["symbol"], quote["price"], shares, session["user_id"])

        # Extract information on user's currently owned shares
        check = db.execute("SELECT * FROM shares WHERE id = ?", session["user_id"])

        # Check whether the user already owns this stock. If so, update the number of shares owned
        found = False
        if len(check) != 0:
            for row in range(len(check)):
                if check[row]["stock_symbol"] == symbol:
                    db.execute("UPDATE shares SET shares_owned = shares_owned + ?, total = total + ? WHERE id = ? AND stock_symbol = ?", int(shares), total, session["user_id"], quote["symbol"])
                    found = True
                    break

        # If the user does not own a share of this stock of any stock, create a new row into shares database
        if len(check) == 0 or found == False:
            db.execute("INSERT INTO shares (stock_symbol, stock_name, shares_owned, stock_price, total, id) VALUES (?, ?, ?, ?, ?, ?)", quote["symbol"], quote["name"], int(shares), quote["price"], total, session["user_id"])

        # Update user's cash
        db.execute("UPDATE users SET cash = cash - ? WHERE id = ?", total, session["user_id"])

        # Notify user and redirect to index
        flash("Bought!")
        return redirect("/")

    # If the user goes to the buy page
    else:
        return render_template("buy.html")



@app.route("/history")
@login_required
def history():
    """Show history of transactions"""

    # Same case with index. Lists are used here
    stock_symbol = []
    shares_transacted = []
    stock_price = []
    timestamp = []

    # Iterate over rows of transactions and append it to the empty lists
    rows = db.execute("SELECT * FROM transactions WHERE id = ?", session["user_id"])
    for row in range(len(rows)):
        stock_symbol.append(rows[row]["stock_symbol"])
        shares_transacted.append(rows[row]["shares_transacted"])
        stock_price.append(usd(rows[row]["stock_price"]))
        timestamp.append(rows[row]["timestamp"])

    return render_template("history.html", stock_symbol=stock_symbol, shares_transacted=shares_transacted, stock_price=stock_price, timestamp=timestamp)


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
    """Get stock quote."""

    # If user presses quote on quote page
    if request.method == "POST":

        # Use lookup function to quote
        if lookup(request.form.get("symbol")) == None:
            return apology("stock does not exist", 403)
        quote = lookup(request.form.get("symbol"))
        return render_template("quotes.html", name=quote["name"], price=quote["price"], symbol=quote["symbol"])

    # If user goes to quote page
    else:
        return render_template("quote.html")


@app.route("/register", methods=["GET", "POST"])
def register():
    """Register user"""

    # If user presses register on register page
    if request.method == "POST":

        # Error checks
        if not request.form.get("username"):
            return apology("must provide username", 403)
        elif not request.form.get("password"):
            return apology("must provide password", 403)
        elif not request.form.get("confirmation"):
            return apology("please confirm your password", 403)
        elif request.form.get("password") != request.form.get("confirmation"):
            return apology("the passwords do not match", 403)

        # Extract row from users, check if username is taken
        rows = db.execute("SELECT * FROM users WHERE username = :username", username=request.form.get("username"))
        if len(rows) == 1:
            return apology("sorry that username is taken", 403)

        # Hash the password
        password = generate_password_hash(request.form.get("password"))

        # db.execute returns user_id
        key = db.execute("INSERT INTO users (username, hash) VALUES (?, ?)", request.form.get("username"), password)
        session["user_id"] = key

        # Notify user and redirect to index
        flash("Registered!")
        return redirect("/")

    # If user goes to register page
    else:
        return render_template("register.html")


@app.route("/sell", methods=["GET", "POST"])
@login_required
def sell():
    """Sell shares of stock"""

    # If user presses sell on sell page
    if request.method == "POST":

        # Define variables
        symbol = request.form.get("symbol")
        shares = request.form.get("shares")
        quote = lookup(symbol)

        # Error checks
        if not symbol:
            return apology("must provide stock symbol", 403)
        if not shares:
            return apology("must specify number of shares", 403)
        if int(shares) <= 0:
            return apology("must specify positive integer of shares", 403)
        if quote == None:
            return apology("stock does not exist", 403)

        # Extract from shares and check if user has a share of specified stock and has enough
        rows = db.execute("SELECT * FROM shares WHERE id = ? AND stock_symbol = ?", session["user_id"], quote["symbol"])
        if rows[0]["shares_owned"] == 0:
            return apology("you do not own a share of the specified stock", 403)
        if rows[0]["shares_owned"] < int(shares):
            return apology("you have insufficient number of shares", 403)

        sold = quote["price"] * int(shares)

        shares = -(int(shares))

        # Log transaction, update share_owned and update cash
        db.execute("INSERT INTO transactions (stock_symbol, stock_price, shares_transacted, id, timestamp) VALUES (?, ?, ?, ?, CURRENT_TIMESTAMP)", quote ["symbol"], quote["price"], shares, session["user_id"])
        db.execute("UPDATE shares SET shares_owned = shares_owned + ?, total = total - ? WHERE id = ? AND stock_symbol = ?", shares, sold, session["user_id"], quote["symbol"])
        db.execute("UPDATE users SET cash = cash + ? WHERE id = ?", sold, session["user_id"])

        # If user no longer owns a share of a stock, delete it from the shares database
        check = db.execute("SELECT * FROM shares WHERE id = ? AND stock_symbol = ?", session["user_id"], quote["symbol"])
        if check[0]["shares_owned"] == 0:
            db.execute("DELETE FROM shares WHERE id = ? AND stock_symbol = ?", session["user_id"], quote["symbol"])

        # Notify and redirect user to index
        flash("Sold!")
        return redirect("/")

    # If user goes to sell page
    else:
        stock_list = db.execute("SELECT * FROM shares WHERE id = ?", session["user_id"])
        return render_template("sell.html", stock_list=stock_list)

@app.route("/account")
@login_required
def account():
    """Account Configuration Menu"""
    return render_template("account.html")

@app.route("/add", methods=["GET", "POST"])
@login_required
def add():
    """Add Cash to Account"""

    # If user presses add cash on add cash page
    if request.method == "POST":

        # Define variable
        amount = request.form.get("amount")

        # Update users database
        db.execute("UPDATE users SET cash = cash + ? WHERE id = ?", float(amount), session["user_id"])

        # Notify and redirect user to index
        flash("Cash Added!")
        return redirect("/")

    # If user goes to add cash page
    else:
        return render_template("add.html")

@app.route("/change", methods=["GET", "POST"])
@login_required
def change():
    """Change Account Password"""

    # If user presses change password on change password page
    if request.method == "POST":

        # Define variables
        current = request.form.get("current")
        new = request.form.get("new")
        confirmation = request.form.get("confirmation")
        current_hash = generate_password_hash(current)

        # Error check
        if not current or not new or not confirmation:
            return apology("please fill in all of the fields", 403)
        rows = db.execute("SELECT * FROM users WHERE id = ?", session["user_id"])
        if not check_password_hash(rows[0]["hash"], current):
            return apology("incorrect current password", 403)
        if new != confirmation:
            return apology("the new password and confirmation do not match", 403)

        # Hash the new password
        new_hash = generate_password_hash(new)

        # Update users database
        db.execute("UPDATE users SET hash = ? WHERE id = ?", new_hash, session["user_id"])

        # Notify and redirect user to index
        flash("Password Changed")
        return redirect("/")

    # If user goes to change password page
    else:
        return render_template("change.html")

@app.route("/delete", methods=["GET", "POST"])
@login_required
def delete():
    """Delete Account"""

    # If user presses delete account on delete page
    if request.method == "POST":

        # Delete user from all three database
        if request.form.get("confirm") == "yes":
            db.execute("DELETE FROM shares WHERE id = ?", session["user_id"])
            db.execute("DELETE FROM transactions WHERE id = ?", session["user_id"])
            db.execute("DELETE FROM users WHERE id = ?", session["user_id"])

            # Log user out
            session.clear()
            flash("Account Deleted")
            return redirect("/")

        else:
            return redirect("/account")

    # If user goes to delete page
    else:
        return render_template("delete.html")


def errorhandler(e):
    """Handle error"""
    if not isinstance(e, HTTPException):
        e = InternalServerError()
    return apology(e.name, e.code)


# Listen for errors
for code in default_exceptions:
    app.errorhandler(code)(errorhandler)
