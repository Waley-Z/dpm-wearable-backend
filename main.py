import os
import flask
from flask import Flask, request
import time

app = Flask(__name__)


@app.route("/")
def hello_world():
    name = os.environ.get("NAME", "World")
    return f"<p>Hello, {name}!</p>"


@app.route("/api/v1/")
def get_entry():
    """Return entries."""
    context = {
        "data": "/api/v1/data/",
    }
    return flask.jsonify(**context)


@app.route("/api/v1/data/heart_rate/", methods=['POST'])
def post_heart_rate():
    """Return fatigue level."""
    print(request.json)
    username = request.json['username']
    heart_rate = request.json['heart_rate']
    timestamp = request.json['timestamp']
    print(f"{timestamp} {username} heart rate: {heart_rate}")
    context = {
        "timestamp": time.time(),
        "fatigue_bool": True,
        "fatigue_level": 30
    }
    return flask.jsonify(**context)


if __name__ == '__main__':
    app.run(debug=True, host="0.0.0.0", port=int(os.environ.get("PORT", 8080)))
