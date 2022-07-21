import datetime
import logging
import os
import time

import flask
from flask import Flask, request, Response

import sqlalchemy

from connect_connector import connect_with_connector
from connect_tcp import connect_tcp_socket
from connect_unix import connect_unix_socket

app = Flask(__name__)

logger = logging.getLogger()

############
# Database #
############


def init_connection_pool() -> sqlalchemy.engine.base.Engine:
    # use a TCP socket when INSTANCE_HOST (e.g. 127.0.0.1) is defined
    if os.environ.get("INSTANCE_HOST"):
        return connect_tcp_socket()

    # use a Unix socket when INSTANCE_UNIX_SOCKET (e.g. /cloudsql/project:region:instance) is defined
    if os.environ.get("INSTANCE_UNIX_SOCKET"):
        return connect_unix_socket()

    # use the connector when INSTANCE_CONNECTION_NAME (e.g. project:region:instance) is defined
    if os.environ.get("INSTANCE_CONNECTION_NAME"):
        return connect_with_connector()

    raise ValueError(
        "Missing database connection type. Please define one of INSTANCE_HOST, INSTANCE_UNIX_SOCKET, or INSTANCE_CONNECTION_NAME"
    )


# create tables in database if not already exist
def migrate_db(db: sqlalchemy.engine.base.Engine) -> None:
    with db.connect() as conn:

        # user table
        conn.execute("CREATE TABLE IF NOT EXISTS users "
                     "(user_id INTEGER AUTO_INCREMENT PRIMARY KEY, "
                     "fullname VARCHAR(40) NOT NULL, "
                     "group_id VARCHAR(20) NOT NULL, "
                     "age INTEGER NOT NULL, "
                     "max_heart_rate INTEGER NOT NULL, "
                     "rest_heart_rate INTEGER NOT NULL, "
                     "hrr_cp INTEGER NOT NULL, "
                     "awc_tot INTEGER NOT NULL, "
                     "k_value INTEGER NOT NULL, "
                     "fatigue_level INTEGER NOT NULL, "
                     "last_update DATETIME, "
                     "created DATETIME DEFAULT CURRENT_TIMESTAMP); ")

        # heart_rates table
        conn.execute(
            "CREATE TABLE IF NOT EXISTS heart_rates "
            "(user_id INTEGER NOT NULL, "
            "heart_rate INTEGER NOT NULL, "
            "timestamp DATETIME NOT NULL, "
            "FOREIGN KEY (user_id) REFERENCES users(user_id) ON DELETE CASCADE); "
        )

        # fatigue_levels table
        conn.execute(
            "CREATE TABLE IF NOT EXISTS fatigue_levels "
            "(user_id INTEGER NOT NULL, "
            "fatigue_level INTEGER NOT NULL, "
            "timestamp DATETIME NOT NULL, "
            "FOREIGN KEY(user_id) REFERENCES users(user_id) ON DELETE CASCADE); "
        )


# initiate a connection pool to a Cloud SQL database
db = init_connection_pool()
# creates required 'votes' table in database (if it does not exist)
migrate_db(db)

############
# REST API #
############


# index GET
@app.route("/", methods=["GET"])
def hello_world():
    name = os.environ.get("NAME", "World")
    return f"<p>Hello, {name}!</p>"


# user
@app.route("/api/v1/user/login/", methods=['POST'])
def post_user_login():
    """Receive user name and check the database.
    If exists, return with user info;
    if not exists, return new user."""
    stmt = sqlalchemy.text("SELECT * FROM users WHERE fullname=:fullname")
    try:
        with db.connect() as conn:
            fullname = request.json['fullname']
            query = conn.execute(stmt, fullname=fullname).fetchone()
            if not query:
                context = {"fullname": fullname, "created": False}
            else:
                context = {
                    "fullname": fullname,
                    "created": True,
                    "user_id": query['user_id'],
                    "group_id": query['group_id'],
                    "age": query['age'],
                    "max_heart_rate": query['max_heart_rate'],
                    "rest_heart_rate": query['rest_heart_rate'],
                    "hrr_cp": query['hrr_cp'],
                    "awc_tot": query['awc_tot'],
                    "k_value": query['k_value'],
                }
            return flask.jsonify(**context)
    except Exception as e:
        logger.exception(e)
        return Response(
            status=500,
            response="Unable to successfully login user! Please check the "
            "application logs for more details.",
        )


@app.route("/api/v1/user/new/", methods=['POST'])
def post_user_new():
    """Receive user info, group_id, and create new user in database.
    Return user_id."""

    stmt_insert = sqlalchemy.text("""INSERT INTO users
        (fullname, group_id, age, max_heart_rate, rest_heart_rate, hrr_cp, awc_tot, k_value, fatigue_level)
        VALUES (:fullname, :group_id, :age, :max_heart_rate, :rest_heart_rate, :hrr_cp, :awc_tot, :k_value, -1)""")

    stmt_update = sqlalchemy.text("""UPDATE users 
        SET fullname = :fullname, group_id = :group_id, 
        age = :age, max_heart_rate = :max_heart_rate, rest_heart_rate = :rest_heart_rate, 
        hrr_cp = :hrr_cp, awc_tot = :awc_tot, k_value = :k_value
        WHERE user_id = :user_id""")

    try:
        with db.connect() as conn:
            fullname = request.json['fullname']
            query = conn.execute(sqlalchemy.text(
                "SELECT * FROM users WHERE fullname=:fullname"), fullname=fullname).fetchone()
            max_heart_rate = 200 - round(0.7 * float(request.json['age']))
            if not query:
                # new user
                result = conn.execute(
                    stmt_insert,
                    fullname=request.json['fullname'],
                    group_id=request.json['group_id'],
                    age=request.json['age'],
                    max_heart_rate=max_heart_rate,
                    rest_heart_rate=request.json['rest_heart_rate'],
                    hrr_cp=request.json['hrr_cp'],
                    awc_tot=request.json['awc_tot'],
                    k_value=request.json['k_value'])
                user_id = result.lastrowid
                context = {
                    "timestamp": time.time(),
                    "user_id": user_id,
                    "max_heart_rate": max_heart_rate
                }
            else:
                result = conn.execute(
                    stmt_update,
                    fullname=request.json['fullname'],
                    group_id=request.json['group_id'],
                    age=request.json['age'],
                    max_heart_rate=max_heart_rate,
                    rest_heart_rate=request.json['rest_heart_rate'],
                    hrr_cp=request.json['hrr_cp'],
                    awc_tot=request.json['awc_tot'],
                    k_value=request.json['k_value'],
                    user_id=request.json['user_id'])
                context = {
                    "timestamp": time.time(),
                    "user_id": request.json['user_id'],
                    "max_heart_rate": max_heart_rate
                }
            return flask.jsonify(**context)

    except Exception as e:
        logger.exception(e)
        return Response(
            status=500,
            response="Unable to successfully create user! Please check the "
            "application logs for more details.",
        )


# upload
@app.route("/api/v1/upload/heart_rate/", methods=['POST'])
def post_heart_rate():
    """Receive heart rate and user info and save to database.
    Return acknowledgement."""
    print(request.json)

    stmt = sqlalchemy.text(
        """INSERT INTO heart_rates (user_id, heart_rate, timestamp)
        VALUES (:user_id, :heart_rate, :timestamp)""")
    try:
        user_id = request.json['user_id']
        heart_rate = request.json['heart_rate']
        timestamp = int(request.json['timestamp'])

        print(f"{timestamp} {user_id} heart rate: {heart_rate}")

        with db.connect() as conn:
            conn.execute(stmt,
                         user_id=user_id,
                         heart_rate=heart_rate,
                         timestamp=datetime.datetime.utcfromtimestamp(
                             timestamp).strftime('%Y-%m-%d %H:%M:%S'))
            return Response(
                response="Success",
                status=200,
            )

    except Exception as e:
        logger.exception(e)
        return Response(
            status=500,
            response="Unable to successfully upload data! Please check the "
            "application logs for more details.",
        )


@app.route("/api/v1/upload/fatigue/", methods=['POST'])
def post_fatigue():
    """Receive fatigue and user info and save to database.
    Return acknowledgement."""
    print(request.json)

    stmt_fatigue = sqlalchemy.text(
        """INSERT INTO fatigue_levels (user_id, fatigue_level, timestamp)
        VALUES (:user_id, :fatigue_level, :timestamp)""")
    stmt_user = sqlalchemy.text(
        "UPDATE users SET fatigue_level=:fatigue_level, last_update=:last_update WHERE user_id=:user_id"
    )
    try:
        user_id = request.json['user_id']
        fatigue_level = request.json['fatigue_level']
        timestamp = int(request.json['timestamp'])
        dtime = datetime.datetime.utcfromtimestamp(timestamp).strftime(
            '%Y-%m-%d %H:%M:%S')

        print(f"{timestamp} {user_id} fatigue level: {fatigue_level}")

        with db.connect() as conn:
            conn.execute(stmt_fatigue,
                         user_id=user_id,
                         fatigue_level=fatigue_level,
                         timestamp=dtime)
            conn.execute(stmt_user,
                         user_id=user_id,
                         fatigue_level=fatigue_level,
                         last_update=dtime)

            return Response(
                response="Success",
                status=200,
            )

    except Exception as e:
        logger.exception(e)
        return Response(
            status=500,
            response="Unable to successfully upload data! Please check the "
            "application logs for more details.",
        )


# peer
@app.route("/api/v1/peer/group/<group_id>/", methods=['GET'])
def get_peer_group(group_id):
    """Receive group_id and query database.
    Return list of user_id, fatigue."""

    peers = []

    stmt = sqlalchemy.text(
        "SELECT user_id, fullname, fatigue_level, last_update FROM users WHERE group_id=:group_id"
    )

    try:
        with db.connect() as conn:
            query = conn.execute(stmt, group_id=group_id).fetchall()

        for row in query:
            timestamp = 0
            if row[3] is not None:
                timestamp = int(
                    round(row[3].replace(
                        tzinfo=datetime.timezone.utc).timestamp()))
            peers.append({
                "user_id": row[0],
                "fullname": row[1],
                "fatigue_level": row[2],
                "last_update": timestamp
            })

        context = {"timestamp": time.time(), "peers": peers}
        return flask.jsonify(**context)

    except Exception as e:
        logger.exception(e)
        return Response(
            status=500,
            response="Unable to successfully upload data! Please check the "
            "application logs for more details.",
        )


@app.route("/api/v1/peer/<user_id>/", methods=['GET'])
def get_peer(user_id):
    """Receive user_id and query database.
    Return list of timestamp, fatigue_level within a timeframe."""

    stmt = sqlalchemy.text(
        "SELECT fatigue_level, timestamp FROM fatigue_levels WHERE user_id=:user_id AND timestamp >= now() - INTERVAL 12 HOUR;"
    )

    try:
        with db.connect() as conn:
            query = conn.execute(stmt, user_id=user_id).fetchall()

        data = [dict(row) for row in query]

        context = {"timestamp": time.time(), "fatigue_levels": data}
        return flask.jsonify(**context)

    except Exception as e:
        logger.exception(e)
        return Response(
            status=500,
            response="Unable to successfully upload data! Please check the "
            "application logs for more details.",
        )


if __name__ == "__main__":
    app.run(debug=True, host="0.0.0.0", port=int(os.environ.get("PORT", 8080)))
