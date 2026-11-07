import csv
import datetime
import pytz
import requests
import subprocess
import urllib
import uuid

from flask import redirect, render_template, session
from functools import wraps


def apology(message, code=400):
    """Render message as an apology to user."""
    def escape(s):
        for old, new in [("-", "--"), ("_", "__"), (" ", "-"), ("?", "~q"),
                         ("%", "~p"), ("#", "~h"), ("/", "~s"), ("\"", "''")]:
            s = s.replace(old, new)
        return s
    return render_template("apology.html", top=code, message=escape(message)), code


def login_required(f):
    """
    Decorate routes to require login.

    https://flask.palletsprojects.com/en/latest/patterns/viewdecorators/
    """
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if session.get("user_id") is None:
            return redirect("/login")
        return f(*args, **kwargs)
    return decorated_function


def lookup(symbol):
    """Look up quote for symbol."""

    # Reject symbol if it starts with a caret
    if symbol.startswith("^"):
        return None

    # Reject symbol if it contains a slash
    if "/" in symbol:
        return None

    # Contact Yahoo Finance
    url = f"https://query1.finance.yahoo.com/v7/finance/download/{urllib.parse.quote_plus(symbol)}?period1=0&period2=9999999999&interval=1d&events=history&includeAdjustedClose=true"
    try:
        response = requests.get(url, headers={"User-Agent": "Mozilla/5.0"})
        response.raise_for_status()

        # Parse CSV data
        decoded = response.content.decode("utf-8")
        reader = csv.DictReader(decoded.splitlines())
        
        # Get the last row (most recent quote)
        rows = list(reader)
        if not rows:
            return None
        row = rows[-1]

        return {
            "price": float(row["Close"]),
            "symbol": symbol.upper()
        }
    except (requests.RequestException, ValueError, KeyError, IndexError):
        return None


def usd(value):
    """Format value as USD."""
    return f"${value:,.2f}"
