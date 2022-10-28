from datetime import datetime, timezone
from dateutil import tz

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
                     "first_name VARCHAR(40) NOT NULL, "
                     "last_name VARCHAR(40) NOT NULL, "
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

        # activities table
        conn.execute(
            "CREATE TABLE IF NOT EXISTS activities "
            "(user_id INTEGER NOT NULL, "
            "peer_id INTEGER NOT NULL, "
            "timestamp DATETIME NOT NULL, "
            "if_open BOOLEAN NOT NULL, "
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
    stmt = sqlalchemy.text("SELECT * FROM users WHERE first_name=:first_name AND last_name=:last_name")
    try:
        with db.connect() as conn:
            first_name = request.json['first_name']
            last_name = request.json['last_name']
            query = conn.execute(stmt, first_name=first_name, last_name=last_name).fetchone()
            if not query:
                context = {"first_name": first_name, "last_name": last_name, "created": False}
            else:
                context = {
                    "first_name": first_name,
                    "last_name": last_name,
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
        (first_name, last_name, group_id, age, max_heart_rate, rest_heart_rate, hrr_cp, awc_tot, k_value, fatigue_level)
        VALUES (:first_name, :last_name, :group_id, :age, :max_heart_rate, :rest_heart_rate, :hrr_cp, :awc_tot, :k_value, -1)""")

    stmt_update = sqlalchemy.text("""UPDATE users 
        SET first_name = :first_name, last_name = :last_name, group_id = :group_id, 
        age = :age, max_heart_rate = :max_heart_rate, rest_heart_rate = :rest_heart_rate, 
        hrr_cp = :hrr_cp, awc_tot = :awc_tot, k_value = :k_value
        WHERE user_id = :user_id""")

    try:
        with db.connect() as conn:
            first_name = request.json['first_name']
            last_name = request.json['last_name']
            query = conn.execute(sqlalchemy.text(
                "SELECT * FROM users WHERE first_name=:first_name AND last_name=:last_name"), first_name=first_name, last_name=last_name).fetchone()
            max_heart_rate = 200 - round(0.7 * float(request.json['age']))
            if not query:
                # new user
                result = conn.execute(
                    stmt_insert,
                    first_name=first_name,
                    last_name=last_name,
                    group_id=request.json['group_id'],
                    age=request.json['age'],
                    max_heart_rate=max_heart_rate,
                    rest_heart_rate=request.json['rest_heart_rate'],
                    hrr_cp=request.json['hrr_cp'],
                    awc_tot=request.json['awc_tot'],
                    k_value=request.json['k_value'])
                user_id = result.lastrowid
                context = {
                    "user_id": user_id,
                    "max_heart_rate": max_heart_rate
                }
            else:
                result = conn.execute(
                    stmt_update,
                    first_name=first_name,
                    last_name=last_name,
                    group_id=request.json['group_id'],
                    age=request.json['age'],
                    max_heart_rate=max_heart_rate,
                    rest_heart_rate=request.json['rest_heart_rate'],
                    hrr_cp=request.json['hrr_cp'],
                    awc_tot=request.json['awc_tot'],
                    k_value=request.json['k_value'],
                    user_id=request.json['user_id'])
                context = {
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
                         timestamp=datetime.utcfromtimestamp(
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


@app.route("/api/v1/upload/fatigue_level/", methods=['POST'])
def post_fatigue_level():
    """Receive fatigue level and user info and save to database.
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
        dtime = datetime.utcfromtimestamp(timestamp).strftime(
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


@app.route("/api/v1/upload/activity/", methods=['POST'])
def post_activity():
    """Receive activity logging and save to database.
    Return acknowledgement."""
    print(request.json)

    stmt = sqlalchemy.text(
        """INSERT INTO activities (user_id, peer_id, timestamp, if_open)
        VALUES (:user_id, :peer_id, :timestamp, :if_open)""")
    try:
        user_id = request.json['user_id']
        peer_id = request.json['peer_id']
        timestamp = int(request.json['timestamp'])
        if_open = bool(request.json['if_open'])

        print(f"{timestamp} {user_id} on {peer_id}. if_open = {if_open}")

        with db.connect() as conn:
            conn.execute(stmt,
                         user_id=user_id,
                         peer_id=peer_id,
                         timestamp=datetime.utcfromtimestamp(
                             timestamp).strftime('%Y-%m-%d %H:%M:%S'),
                         if_open=if_open)
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
        "SELECT user_id, first_name, fatigue_level, last_update FROM users WHERE group_id=:group_id"
    )

    try:
        with db.connect() as conn:
            query = conn.execute(stmt, group_id=group_id).fetchall()

        for row in query:
            timestamp = 0
            if row[3] is not None:
                timestamp = int(
                    round(row[3].replace(
                        tzinfo=timezone.utc).timestamp()))
            peers.append({
                "user_id": row[0],
                "first_name": row[1],
                "fatigue_level": row[2],
                "last_update": timestamp
            })

        context = {"peers": peers}
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
    Return ranges and average of fatigue_level today by hour."""

    print("------------")

    # abstract = [[-1, -1]] * 24
    fatigue_levels = [[] for _ in range(24)]

    stmt = sqlalchemy.text(
        "SELECT fatigue_level, timestamp FROM fatigue_levels WHERE user_id=:user_id AND timestamp >= now() - INTERVAL 24 HOUR;"
    )

    try:
        with db.connect() as conn:
            query = conn.execute(stmt, user_id=user_id).fetchall()

        print(query)

        def utc_to_local(utc_dt):
            return utc_dt.replace(tzinfo=timezone.utc).astimezone(tz=tz.gettz('America/Detroit'))

        def updateAbstract(hour, fatigue_level):
            fatigue_levels[hour].append(fatigue_level)
            print(hour, fatigue_level)
            print(fatigue_levels)

        now = utc_to_local(datetime.utcnow())
        print("now: ", now)

        for x in query:
            fatigue_level = x[0]
            timestamp = utc_to_local(x[1])
            print(timestamp)
            if timestamp.date() == now.date():
                updateAbstract(timestamp.hour, fatigue_level)

        fatigue_levels = [ lst if lst else [-1] for lst in fatigue_levels ]
        data = [{"hour_from_midnight": ind, "fatigue_level_range": [min(ele), max(ele)], "avg_fatigue_level": sum(ele)/len(ele) } for ind, ele in enumerate(fatigue_levels)]

        context = {"observations": data}
        print(context)

        print("------------")

        return flask.jsonify(**context)

    except Exception as e:
        logger.exception(e)
        return Response(
            status=500,
            response="Unable to successfully upload data! Please check the "
            "application logs for more details.",
        )


if __name__ == "__main__":
    app.run(debug=False, host="0.0.0.0", port=int(os.environ.get("PORT", 8080)))
