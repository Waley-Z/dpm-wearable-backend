import os

from flask import Flask

app = Flask(__name__)


@app.route("/", methods=['GET'])
def hello_world():
    name = os.environ.get("NAME", "World")
    return f"<p>Hello, {name}!</p>"


if __name__ == '__main__':
    app.run(debug=True, host="0.0.0.0", port=int(os.environ.get("PORT", 8080)))
