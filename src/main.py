from flask import Flask, request, jsonify, render_template, Response
from flask_cors import CORS
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

# Initialize Flask app
app = Flask(__name__)

# Function to dynamically check and set CORS origins
def get_cors_origin(origin):
    allowed_domains = [
        "localhost:5000",
        "ngrok.com",
        "ngrok-free.app"
    ]

    if origin:
        for domain in allowed_domains:
            if origin == f"http://{domain}" or origin == f"https://{domain}" or origin.endswith(f".{domain}"):
                return True
    return False

# Enable CORS
CORS(app, origins=get_cors_origin)

# Configure logging
logger = get_logger(__name__)
app.logger.setLevel(logging.DEBUG)  # Set Flask's logger to DEBUG level

# Add a handler to log to the console
console_handler = logging.StreamHandler()
console_handler.setLevel(logging.DEBUG)  # Set handler to DEBUG level
formatter = logging.Formatter('%(asctime)s [%(levelname)s] in %(module)s: %(message)s')
console_handler.setFormatter(formatter)
app.logger.addHandler(console_handler)

# Log all incoming requests
@app.before_request
def log_request_info():
    app.logger.debug(f"Received {request.method} request for {request.url}")
    app.logger.debug(f"Headers: {request.headers}")
    app.logger.debug(f"Body: {request.get_data()}")

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
        if request.method == 'GET':
            with open('.gui_key', 'r') as key_file:
                gui_key = key_file.read().strip()
                if gui_key != request.args.get('guiKey', None):
                    return 'Access Denied', 401
    except FileNotFoundError:
        logger.warning('GUI key file not found. Open GUI mode detected.')

    action_list = am.get_all()
    return render_template(
        template_name_or_list='dashboard.html',
        schema_list=schema_list,
        action_list=action_list,
        event_list=registered_events,
        version=VERSION_NUMBER
    )

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
            serve(app, host="0.0.0.0", port=port)
        else:
            logger.info("Starting in development mode with debug.")
            app.run(debug=True, host="0.0.0.0", port=port)
    except Exception as e:
        logger.exception("An error occurred while starting the Flask app.")
