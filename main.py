import os
import flask
from flask import Flask

app = Flask(__name__)


@app.route("/", methods=['GET'])
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


if __name__ == '__main__':
    app.run(debug=True, host="0.0.0.0", port=int(os.environ.get("PORT", 8080)))
