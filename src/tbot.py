#!/usr/bin/env python3
"""
Reading database for Tbot on Tradingboat
"""
import sqlite3
import logging
import os
from flask import request, render_template
from flask import g
from dotenv import load_dotenv

from utils.log import get_logger

# Create logs directory if it doesn't exist
log_dir = os.path.dirname(os.path.abspath(__file__))
log_file = os.path.join(log_dir, 'flask_app.log')

# Configure logging
logging.basicConfig(
    level=logging.DEBUG,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler(log_file),
        logging.StreamHandler()  # Also print to console
    ]
)

logger = logging.getLogger(__name__)

# Set the default path to the .env file in the user's home directory
DEFAULT_ENV_FILE_PATH = os.path.expanduser("~/.env")

# Check if the .env file exists at the default path; if not, use the fallback
if os.path.isfile(DEFAULT_ENV_FILE_PATH):
    ENV_FILE_PATH = DEFAULT_ENV_FILE_PATH
else:
    ENV_FILE_PATH = "/home/tbot/.env"

# Load the environment variables from the chosen .env file
load_dotenv(dotenv_path=ENV_FILE_PATH, override=True)


def get_db():
    """Get the database"""
    database = getattr(g, "_database", None)
    if database is None:
        try:
            database = g._database = sqlite3.connect(
                os.environ.get("TBOT_DB_OFFICE", "/run/tbot/tbot_sqlite3"),
                timeout=10  # Add timeout to handle database locks
            )
            database.row_factory = sqlite3.Row
            logger.info("Database connection established.")
        except sqlite3.Error as e:
            logger.error(f"Database connection error: {e}")
            raise
    return database

def query_db(query, args=()):
    """Query database"""
    try:
        cur = get_db().execute(query, args)
        rows = cur.fetchall()
        unpacked = [{k: item[k] for k in item.keys()} for item in rows]
        cur.close()
        logger.info("Database query executed successfully.")
    except Exception as err:
        logger.error(f"Failed to execute query: {query} with error: {err}")
        return []
    return unpacked


def get_orders():
    """Get IBKR Orders"""
    return render_template(template_name_or_list="orders.html", title="IBKR Orders")


def get_orders_data():
    """Get IBKR Orders for AJAX"""
    logger.debug("Executing get_orders_data()")
    try:
        rows = query_db("""
            SELECT t.*, 
                   (SELECT net_liquidation 
                    FROM ACCOUNT_SUMMARY 
                    ORDER BY timestamp DESC 
                    LIMIT 1) as net_liquidation
            FROM TBOTORDERS t
        """)
        logger.info(f"Query returned {len(rows)} rows")
        logger.debug(f"Data: {rows}")
        return {"data": rows}
    except Exception as e:
        logger.error(f"Error in get_orders_data: {str(e)}", exc_info=True)
        return {"data": []}


def get_alerts():
    """Get TradingView alerts"""
    return render_template(
        template_name_or_list="alerts.html", title="TradingView Alerts to TBOT"
    )


def get_alerts_data():
    """Get TradingView alerts for AJAX"""
    rows = query_db("select * from TBOTALERTS")
    return {"data": rows}


def get_errors():
    """Get TradingView alerts"""
    return render_template(
        template_name_or_list="error.html", title="TradingView Errors to TBOT"
    )


def get_errors_data():
    """Get TradingView errors for AJAX"""
    rows = query_db("select * from TBOTERRORS")
    return {"data": rows}


def get_tbot():
    """Get the holstici view of Tbot"""
    return render_template(
        template_name_or_list="alerts_orders.html",
        title=" TradingView Alerts and IBKR Orders on TBOT",
    )


def get_ngrok():
    """Get NGROK Address"""
    addr = os.environ.get("TBOT_NGROK", "#")
    return {"data": {"address": addr}}


def get_tbot_data():
    """Get inner join between TBOTORDERS and TBOTALERTS to
    track orders from WebHook alerts to Orders.
    """
    query = (
        "SELECT "
        "TBOTORDERS.timestamp, "
        "TBOTORDERS.uniquekey, "
        "TBOTALERTS.tv_timestamp, "
        "TBOTALERTS.ticker, "
        "TBOTALERTS.tv_price, "
        "TBOTORDERS.avgprice, "
        "TBOTALERTS.direction, "
        "TBOTORDERS.action, "
        "TBOTORDERS.ordertype, "
        "TBOTORDERS.qty, "
        "TBOTORDERS.position, "
        "TBOTALERTS.orderref, "
        "TBOTORDERS.orderstatus "
        "FROM TBOTORDERS INNER JOIN TBOTALERTS "
        "ON TBOTALERTS.orderref = TBOTORDERS.orderref "
        "AND TBOTALERTS.uniquekey = TBOTORDERS.uniquekey "
        "ORDER BY TBOTORDERS.uniquekey DESC "
    )
    rows = query_db(query)
    return {"data": rows}


def get_main():
    """Get entry point for TradingBoat"""
    if request.method == "GET":
        # Make the open-gui mode in favor of the system-level firewall.
        try:
            os.remove(".gui_key")
        except FileNotFoundError:
            pass

        return render_template(template_name_or_list="tbot_dashboard.html")


def close_connection(exception):
    """Close connection"""
    database = getattr(g, "_database", None)
    if database is not None:
        database.close()
