"""SQLite 数据库模型层 — 纯 sqlite3，无 ORM 依赖。"""

import hashlib
import json
import os
import sqlite3
from typing import Any

import config


def _hash_password(password: str) -> str:
    return hashlib.sha256(f"opinion_salt_{password}".encode()).hexdigest()


def get_db() -> sqlite3.Connection:
    os.makedirs(config.INSTANCE_DIR, exist_ok=True)
    conn = sqlite3.connect(config.DATABASE)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("PRAGMA foreign_keys=ON")
    return conn


def init_db() -> None:
    conn = get_db()
    conn.executescript("""
        CREATE TABLE IF NOT EXISTS users (
            id          INTEGER PRIMARY KEY AUTOINCREMENT,
            username    TEXT    UNIQUE NOT NULL,
            password_hash TEXT   NOT NULL,
            role        TEXT    DEFAULT '分析员'
        );

        CREATE TABLE IF NOT EXISTS events (
            id              TEXT PRIMARY KEY,
            title           TEXT    NOT NULL,
            summary         TEXT    DEFAULT '',
            source          TEXT    DEFAULT '',
            heat            REAL    DEFAULT 0,
            risk_level      TEXT    DEFAULT '低',
            sentiment       TEXT    DEFAULT '中性',
            occur_time      TEXT    DEFAULT '',
            update_time     TEXT    DEFAULT '',
            keywords        TEXT    DEFAULT '[]',
            trend_data      TEXT    DEFAULT '[]',
            sentiment_data  TEXT    DEFAULT '[]',
            platform_data   TEXT    DEFAULT '[]',
            wordcloud_data  TEXT    DEFAULT '[]',
            propagation_data TEXT   DEFAULT '{}'
        );

        CREATE TABLE IF NOT EXISTS daily_stats (
            date            TEXT PRIMARY KEY,
            comment_count   INTEGER DEFAULT 0,
            positive        INTEGER DEFAULT 0,
            negative        INTEGER DEFAULT 0,
            neutral         INTEGER DEFAULT 0,
            heat_index      REAL    DEFAULT 0
        );

        CREATE TABLE IF NOT EXISTS follow_platforms (
            id          INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id     INTEGER NOT NULL,
            name        TEXT    NOT NULL,
            url         TEXT    NOT NULL,
            created_at  TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (user_id) REFERENCES users(id)
        );

        CREATE TABLE IF NOT EXISTS follow_keywords (
            id          INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id     INTEGER NOT NULL,
            word        TEXT    NOT NULL,
            level       TEXT    DEFAULT '中',
            created_at  TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (user_id) REFERENCES users(id)
        );
    """)
    conn.commit()

    # 兼容旧数据库：为已有 events 表补充新字段
    _migrate_add_column(conn, "events", "propagation_data", "TEXT DEFAULT '{}'")

    # 确保默认管理员存在
    _ensure_default_user(conn)
    conn.close()


def _migrate_add_column(conn: sqlite3.Connection, table: str, column: str, col_def: str) -> None:
    """安全添加列，已存在则跳过。"""
    try:
        conn.execute(f"ALTER TABLE {table} ADD COLUMN {column} {col_def}")
        conn.commit()
        print(f"[models] 已添加字段 {table}.{column}")
    except sqlite3.OperationalError:
        pass  # 列已存在


def _ensure_default_user(conn: sqlite3.Connection) -> None:
    row = conn.execute("SELECT id FROM users WHERE username = ?", ("admin",)).fetchone()
    if row is None:
        conn.execute(
            "INSERT INTO users (username, password_hash, role) VALUES (?, ?, ?)",
            ("admin", _hash_password("123456"), "系统管理员"),
        )
        conn.commit()


# ── 用户认证 ──────────────────────────────────────────────

def verify_login(username: str, password: str) -> dict | None:
    conn = get_db()
    row = conn.execute(
        "SELECT id, username, role FROM users WHERE username = ? AND password_hash = ?",
        (username, _hash_password(password)),
    ).fetchone()
    conn.close()
    if row:
        return {"id": row["id"], "name": row["username"], "role": row["role"]}
    return None


def get_user_by_id(user_id: int) -> dict | None:
    conn = get_db()
    row = conn.execute("SELECT id, username, role FROM users WHERE id = ?", (user_id,)).fetchone()
    conn.close()
    if row:
        return {"id": row["id"], "name": row["username"], "role": row["role"]}
    return None


def change_password(user_id: int, old_password: str, new_password: str) -> bool:
    conn = get_db()
    row = conn.execute(
        "SELECT id FROM users WHERE id = ? AND password_hash = ?",
        (user_id, _hash_password(old_password)),
    ).fetchone()
    if row is None:
        conn.close()
        return False
    conn.execute(
        "UPDATE users SET password_hash = ? WHERE id = ?",
        (_hash_password(new_password), user_id),
    )
    conn.commit()
    conn.close()
    return True


# ── 事件查询 ──────────────────────────────────────────────

def _row_to_event(row: sqlite3.Row) -> dict:
    return {
        "id": row["id"],
        "title": row["title"],
        "summary": row["summary"],
        "source": row["source"],
        "heat": row["heat"],
        "riskLevel": row["risk_level"],
        "sentiment": row["sentiment"],
        "occurTime": row["occur_time"],
        "updateTime": row["update_time"],
        "keywords": json.loads(row["keywords"]),
    }


def query_events(keyword: str = "", risk_level: str = "", sort_by: str = "time") -> list[dict]:
    conn = get_db()
    sql = "SELECT * FROM events WHERE 1=1"
    params: list[Any] = []
    if keyword:
        sql += " AND (title LIKE ? OR summary LIKE ? OR keywords LIKE ?)"
        like = f"%{keyword}%"
        params.extend([like, like, like])
    if risk_level:
        sql += " AND risk_level = ?"
        params.append(risk_level)
    if sort_by == "heat":
        sql += " ORDER BY heat DESC"
    else:
        sql += " ORDER BY occur_time ASC"
    rows = conn.execute(sql, params).fetchall()
    conn.close()
    return [_row_to_event(r) for r in rows]


def get_event_by_id(event_id: str) -> dict | None:
    conn = get_db()
    row = conn.execute("SELECT * FROM events WHERE id = ?", (event_id,)).fetchone()
    conn.close()
    if row:
        return _row_to_event(row)
    return None


def get_event_trend(event_id: str) -> list[dict]:
    """返回指定事件的趋势数据。当前使用全局 daily_stats 作为近似。"""
    conn = get_db()
    if event_id == "overview":
        rows = conn.execute("SELECT * FROM daily_stats ORDER BY date").fetchall()
    else:
        event = conn.execute("SELECT trend_data FROM events WHERE id = ?", (event_id,)).fetchone()
        conn.close()
        if event:
            return json.loads(event["trend_data"])
        return []
    conn.close()
    result: list[dict] = []
    for r in rows:
        date_str = r["date"]
        # 格式化为 MM-DD
        parts = date_str.split("-")
        time_label = f"{parts[1]}-{parts[2]}" if len(parts) >= 3 else date_str
        result.append({
            "time": time_label,
            "heat": round(r["heat_index"], 1),
            "posts": r["comment_count"],
        })
    return result


def get_event_sentiment(event_id: str) -> list[dict]:
    conn = get_db()
    row = conn.execute("SELECT sentiment_data FROM events WHERE id = ?", (event_id,)).fetchone()
    conn.close()
    if row:
        return json.loads(row["sentiment_data"])
    return []


def get_event_platforms(event_id: str) -> list[dict]:
    conn = get_db()
    row = conn.execute("SELECT platform_data FROM events WHERE id = ?", (event_id,)).fetchone()
    conn.close()
    if row:
        return json.loads(row["platform_data"])
    return []


def get_event_wordcloud(event_id: str) -> list[dict]:
    conn = get_db()
    row = conn.execute("SELECT wordcloud_data FROM events WHERE id = ?", (event_id,)).fetchone()
    conn.close()
    if row:
        return json.loads(row["wordcloud_data"])
    return []


def get_event_propagation(event_id: str) -> dict:
    conn = get_db()
    row = conn.execute("SELECT propagation_data FROM events WHERE id = ?", (event_id,)).fetchone()
    conn.close()
    if row:
        try:
            data = json.loads(row["propagation_data"])
            if isinstance(data, dict) and data:
                return data
        except (json.JSONDecodeError, TypeError):
            pass
    return {}


# ── 概览统计 ──────────────────────────────────────────────

def get_overview_stats() -> dict:
    conn = get_db()
    total = conn.execute("SELECT COUNT(*) as c FROM events").fetchone()["c"]
    hot = conn.execute("SELECT COUNT(*) as c FROM events WHERE heat > 5000").fetchone()["c"]
    high_risk = conn.execute("SELECT COUNT(*) as c FROM events WHERE risk_level = '高'").fetchone()["c"]
    platforms_set = set()
    all_events = conn.execute("SELECT platform_data FROM events").fetchall()
    for row in all_events:
        for p in json.loads(row["platform_data"]):
            platforms_set.add(p.get("platform", ""))
    conn.close()

    # 情感指数: 正面占比 * 100
    total_comments = 0
    positive_total = 0
    conn2 = get_db()
    stats_rows = conn2.execute("SELECT positive, negative, neutral, comment_count FROM daily_stats").fetchall()
    conn2.close()
    for r in stats_rows:
        total_comments += r["comment_count"]
        positive_total += r["positive"]
    avg_emotion = round(positive_total / max(total_comments, 1) * 100, 1)

    return {
        "eventTotal": total,
        "hotEventTotal": hot,
        "highRiskTotal": high_risk,
        "platformTotal": len(platforms_set),
        "todayIncrement": total,  # 演示用
        "avgEmotionScore": avg_emotion,
    }


# ── 关注平台 CRUD ─────────────────────────────────────────

def get_platforms(user_id: int) -> list[dict]:
    conn = get_db()
    rows = conn.execute(
        "SELECT id, name, url FROM follow_platforms WHERE user_id = ? ORDER BY id DESC",
        (user_id,),
    ).fetchall()
    conn.close()
    return [{"id": r["id"], "name": r["name"], "url": r["url"]} for r in rows]


def add_platform(user_id: int, name: str, url: str) -> dict:
    conn = get_db()
    cur = conn.execute(
        "INSERT INTO follow_platforms (user_id, name, url) VALUES (?, ?, ?)",
        (user_id, name, url),
    )
    conn.commit()
    row_id = cur.lastrowid
    conn.close()
    return {"id": row_id, "name": name, "url": url}


def delete_platform(platform_id: int, user_id: int) -> bool:
    conn = get_db()
    cur = conn.execute(
        "DELETE FROM follow_platforms WHERE id = ? AND user_id = ?",
        (platform_id, user_id),
    )
    conn.commit()
    deleted = cur.rowcount > 0
    conn.close()
    return deleted


# ── 关注关键词 CRUD ───────────────────────────────────────

def get_keywords(user_id: int) -> list[dict]:
    conn = get_db()
    rows = conn.execute(
        "SELECT id, word, level FROM follow_keywords WHERE user_id = ? ORDER BY id DESC",
        (user_id,),
    ).fetchall()
    conn.close()
    return [{"id": r["id"], "word": r["word"], "level": r["level"]} for r in rows]


def add_keyword(user_id: int, word: str, level: str) -> dict:
    conn = get_db()
    cur = conn.execute(
        "INSERT INTO follow_keywords (user_id, word, level) VALUES (?, ?, ?)",
        (user_id, word, level),
    )
    conn.commit()
    row_id = cur.lastrowid
    conn.close()
    return {"id": row_id, "word": word, "level": level}


def delete_keyword(keyword_id: int, user_id: int) -> bool:
    conn = get_db()
    cur = conn.execute(
        "DELETE FROM follow_keywords WHERE id = ? AND user_id = ?",
        (keyword_id, user_id),
    )
    conn.commit()
    deleted = cur.rowcount > 0
    conn.close()
    return deleted
