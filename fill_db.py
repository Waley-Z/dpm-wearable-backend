import os
from datetime import datetime, timezone, timedelta
from dateutil import tz
import numpy as np


def utc_to_local(utc_dt):
    return utc_dt.replace(tzinfo=timezone.utc).astimezone(tz=tz.gettz('America/Detroit'))

def main():
    now = utc_to_local(datetime.utcnow())
    midnight = now - timedelta(hours=now.hour)

    with open("fill_db", "w+") as f:
        f.write("#!/bin/bash\n")

        for user_id in range(3):

            y = 0
            result = []
            for _ in range(48):
                result.append(y)
                d = np.random.normal(scale=10)
                if y + d < 0 or y + d > 150:
                    y -= d
                else:
                    y += d

            for dt in range(now.hour):
                t = midnight + timedelta(hours=dt)
                ts = int(datetime.timestamp(t))
                f.write(f"""
http \
POST \
"http://localhost:8080/api/v1/upload/fatigue/" \
user_id={user_id+1} \
fatigue_level={int(result[dt*2])} \
timestamp={ts}
                """)
                f.write(f"""
http \
POST \
"http://localhost:8080/api/v1/upload/fatigue/" \
user_id={user_id+1} \
fatigue_level={int(result[dt*2+1])} \
timestamp={ts}
                """)

if __name__ == "__main__":
    main()
