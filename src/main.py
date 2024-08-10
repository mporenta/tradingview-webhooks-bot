from flask import Flask, request, jsonify, render_template, Response
from flask_cors import CORS
from dotenv import load_dotenv
import os
import logging
import tbot
from commons import VERSION_NUMBER, LOG_LOCATION
from components.actions.base.action import am
from components.events.base.event import em
from components.logs.log_event import LogEvent
from components.schemas.trading import Order, Position
from utils.log import get_logger
from utils.register import register_action, register_event, register_link
from distutils.util import strtobool

# Load environment variables from .env file
load_dotenv()

# Initialize Flask app
app = Flask(__name__)

# Enable CORS for all routes
CORS(app)

# Configure logging
def get_logger(name, level=logging.DEBUG):
    fmt = logging.Formatter("%(asctime)s [%(threadName)-12.12s] [%(levelname)-5.5s]  %(message)s")
    logger = logging.getLogger(name)

    # Avoid duplicate handlers
    if not logger.hasHandlers():
        # Console handler
        ch = logging.StreamHandler()
        ch.setFormatter(fmt)
        logger.addHandler(ch)

        # File handler
        logfile = os.getenv('TBOT_LOGFILE', 'app.log')  # Default to app.log if TBOT_LOGFILE is not set
        fh = logging.FileHandler(logfile)
        fh.setFormatter(fmt)
        logger.addHandler(fh)

    logger.setLevel(level)
    return logger

logger = get_logger(__name__)
app.logger.handlers = logger.handlers  # Use the same handlers for the Flask logger
app.logger.setLevel(logger.level)

# Log all incoming requests
@app.before_request
def log_request_info():
    app.logger.debug(f"Received {request.method} request for {request.url}")
    app.logger.debug(f"Headers: {request.headers}")
    app.logger.debug(f"Body: {request.get_data()}")

@app.errorhandler(Exception)
def handle_exception(e):
    app.logger.error(f"Exception occurred: {e}", exc_info=True)
    return jsonify(error=str(e)), 500

# Register routes and handlers
app.add_url_rule("/", view_func=tbot.get_main)
app.add_url_rule("/orders", view_func=tbot.get_orders)
app.add_url_rule("/alerts", view_func=tbot.get_alerts)
app.add_url_rule("/ngrok", view_func=tbot.get_ngrok)
app.add_url_rule("/errors", view_func=tbot.get_errors)
app.add_url_rule("/tbot", view_func=tbot.get_tbot)
app.add_url_rule("/orders/data", view_func=tbot.get_orders_data)
app.add_url_rule("/alerts/data", view_func=tbot.get_alerts_data)
app.add_url_rule("/errors/data", view_func=tbot.get_errors_data)
app.add_url_rule("/tbot/data", view_func=tbot.get_tbot_data)
app.teardown_appcontext(tbot.close_connection)

schema_list = {"order": Order().as_json(), "position": Position().as_json()}

@app.route("/dashboard", methods=["GET"])
def dashboard():
    try:
        # Check if GUI key file exists
        try:
            with open('.gui_key', 'r') as key_file:
                gui_key = key_file.read().strip()
                # Check that the GUI key from file matches the GUI key from request
                if gui_key != request.args.get('guiKey', None):
                    logger.error('Access denied due to GUI key mismatch.')
                    return 'Access Denied', 401

        except FileNotFoundError:
            logger.warning('GUI key file not found. Open GUI mode detected.')

        # Fetch data for dashboard rendering
        try:
            action_list = am.get_all()
            event_list = em.get_all()
            logger.debug(f"Actions: {action_list}, Events: {event_list}")

            return render_template(
                'dashboard.html',
                schema_list=schema_list,
                action_list=action_list,
                event_list=event_list,
                version=VERSION_NUMBER
            )
        except Exception as e:
            logger.error(f"Error fetching data for dashboard: {e}", exc_info=True)
            return 'An error occurred while loading the dashboard.', 500
    except Exception as e:
        logger.error(f"Unexpected error in dashboard route: {e}", exc_info=True)
        return 'A server error occurred.', 500


@app.route("/webhook", methods=["POST"])
def webhook():
    if request.method == "POST":
        jsondic_data = request.get_json(force=True, silent=True)
        if not jsondic_data:
            logger.warning(f"Invalid JSON response {jsondic_data}")
            return Response(status=415)
        elif not jsondic_data.get("key"):
            logger.warning(f"Missing Key in the response {jsondic_data}")
            return Response(status=415)
        logger.debug(f"Request Data: {jsondic_data}")
        triggered_events = []
        for event in em.get_all():
            if event.webhook and event.key == jsondic_data["key"]:
                event.trigger(data=jsondic_data)
                triggered_events.append(event.name)

        if not triggered_events:
            logger.warning(f"No events triggered for webhook request {jsondic_data}")
        else:
            logger.info(f"Triggered events: {triggered_events}")
            if logger.level <= logging.INFO:
                logger.info(f"client IP: {request.remote_addr}")
                if request.environ.get("HTTP_X_FORWARDED_FOR") is None:
                    logger.info(request.environ["REMOTE_ADDR"])
                else:
                    logger.info(request.environ["HTTP_X_FORWARDED_FOR"])

    return Response(status=200)

@app.route("/logs", methods=["GET"])
def get_logs():
    if request.method == 'GET':
        with open(LOG_LOCATION, 'r') as log_file:
            logs = [LogEvent().from_line(log) for log in log_file.readlines()]
            return jsonify([log.as_json() for log in logs])

@app.route("/event/active", methods=["POST"])
def activate_event():
    if request.method == 'POST':
        event_name = request.args.get('event', None)

        if event_name is None:
            return Response(f'Event name cannot be empty ({event_name})', status=404)
        try:
            event = em.get(event_name)
        except ValueError:
            return Response(f'Cannot find event with name: {event_name}', status=404)

        event.active = request.args.get('active', True) == 'true'
        logger.info(f'Event {event.name} active set to: {event.active}, via POST request')
        return {'active': event.active}

if __name__ == "__main__":
    try:
        port = int(os.getenv("TVWB_HTTPS_PORT", "5000"))
        is_production = strtobool(os.getenv("TBOT_PRODUCTION", "False"))

        if is_production:
            logger.info("Starting in production mode.")
            from waitress import serve  # Ensure waitress is installed for production
            serve(app, host="0.0.0.0", port=port)
        else:
            logger.info("Starting in development mode with debug.")
            app.run(debug=True, host="0.0.0.0", port=port)
    except Exception as e:
        logger.exception("An error occurred while starting the Flask app.")
