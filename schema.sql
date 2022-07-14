CREATE TABLE IF NOT EXISTS users(
  user_id INTEGER PRIMARY KEY AUTOINCREMENT,
  fullname VARCHAR(40) NOT NULL,
  group_id VARCHAR(20) NOT NULL,

  age INTEGER NOT NULL,
  max_heart_rate INTEGER NOT NULL,
  rest_heart_rate INTEGER NOT NULL,
  hrr_cp INTEGER NOT NULL,
  awc_tot INTEGER NOT NULL,
  k_value INTEGER NOT NULL,

  fatigue_level INTEGER NOT NULL,
  last_update DATETIME,

  created DATETIME DEFAULT CURRENT_TIMESTAMP,
);

CREATE TABLE IF NOT EXISTS heart_rates(
  user_id INTEGER NOT NULL,
  heart_rate INTEGER NOT NULL,
  timestamp DATETIME NOT NULL,

  FOREIGN KEY(user_id)
    REFERENCES users(user_id)
    ON DELETE CASCADE,
);

CREATE TABLE IF NOT EXISTS fatigue_levels(
  user_id INTEGER NOT NULL,
  fatigue_level INTEGER NOT NULL,
  timestamp DATETIME NOT NULL,

  FOREIGN KEY(user_id)
    REFERENCES users(user_id)
    ON DELETE CASCADE,
);
