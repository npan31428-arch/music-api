import os
import io
import json
import sqlite3
import hashlib
import secrets
from datetime import datetime, timedelta

import requests
from fastapi import FastAPI, Query, HTTPException, Response, Header
from fastapi.responses import HTMLResponse
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from mutagen.mp4 import MP4, MP4Cover

app = FastAPI(title="Apple Music Mobile API")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

UPSTREAM = "https://music-downoader-api.froxtdevil.workers.dev/search"
DB_PATH = "apple_music.db"
SESSION_DAYS = 30


# ==========================================================
# DATABASE
# ==========================================================
def get_db():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys=ON")
    conn.execute("PRAGMA journal_mode=WAL")
    return conn


def init_db():
    conn = get_db()
    conn.executescript("""
        CREATE TABLE IF NOT EXISTS users (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            username TEXT UNIQUE NOT NULL COLLATE NOCASE,
            password_hash TEXT NOT NULL,
            created_at TEXT NOT NULL
        );
        CREATE TABLE IF NOT EXISTS sessions (
            token TEXT PRIMARY KEY,
            user_id INTEGER NOT NULL,
            created_at TEXT NOT NULL,
            expires_at TEXT NOT NULL,
            FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE
        );
        CREATE TABLE IF NOT EXISTS playlists (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER NOT NULL,
            name TEXT NOT NULL,
            created_at TEXT NOT NULL,
            FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE
        );
        CREATE TABLE IF NOT EXISTS playlist_songs (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            playlist_id INTEGER NOT NULL,
            song_id TEXT NOT NULL,
            song_data TEXT NOT NULL,
            position INTEGER NOT NULL,
            FOREIGN KEY (playlist_id) REFERENCES playlists(id) ON DELETE CASCADE
        );
        CREATE TABLE IF NOT EXISTS favorites (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER NOT NULL,
            song_id TEXT NOT NULL,
            song_data TEXT NOT NULL,
            created_at TEXT NOT NULL,
            UNIQUE(user_id, song_id),
            FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE
        );
    """)
    conn.commit()
    conn.close()


init_db()


# ==========================================================
# AUTH HELPERS
# ==========================================================
def hash_password(pw: str) -> str:
    salt = secrets.token_hex(16)
    h = hashlib.pbkdf2_hmac("sha256", pw.encode(), salt.encode(), 120000)
    return f"{salt}${h.hex()}"


def verify_password(pw: str, stored: str) -> bool:
    try:
        salt, h = stored.split("$")
        calc = hashlib.pbkdf2_hmac("sha256", pw.encode(), salt.encode(), 120000)
        return secrets.compare_digest(calc.hex(), h)
    except Exception:
        return False


def create_session(user_id: int) -> str:
    token = secrets.token_urlsafe(32)
    now = datetime.utcnow()
    exp = now + timedelta(days=SESSION_DAYS)
    conn = get_db()
    conn.execute(
        "INSERT INTO sessions (token, user_id, created_at, expires_at) VALUES (?, ?, ?, ?)",
        (token, user_id, now.isoformat(), exp.isoformat()),
    )
    conn.commit()
    conn.close()
    return token


def get_user_from_token(token: str):
    if not token:
        return None
    conn = get_db()
    row = conn.execute(
        "SELECT s.user_id, s.expires_at, u.username FROM sessions s "
        "JOIN users u ON u.id = s.user_id WHERE s.token = ?",
        (token,),
    ).fetchone()
    conn.close()
    if not row:
        return None
    try:
        if datetime.fromisoformat(row["expires_at"]) < datetime.utcnow():
            return None
    except Exception:
        return None
    return {"id": row["user_id"], "username": row["username"]}


def current_user(authorization: str = Header(None)):
    if not authorization or not authorization.startswith("Bearer "):
        return None
    return get_user_from_token(authorization[7:].strip())


def require_user(authorization: str = Header(None)):
    u = current_user(authorization)
    if not u:
        raise HTTPException(status_code=401, detail="Not authenticated")
    return u


# ==========================================================
# PYDANTIC MODELS
# ==========================================================
class AuthBody(BaseModel):
    username: str
    password: str


class PlaylistCreate(BaseModel):
    name: str


class SongBody(BaseModel):
    song: dict


class SyncBody(BaseModel):
    favorites: list


# ==========================================================
# SEARCH / DOWNLOAD  (unchanged)
# ==========================================================
@app.get("/api/search")
def search(song: str = Query(...)):
    try:
        r = requests.get(UPSTREAM, params={"song": song}, timeout=30)
        r.raise_for_status()
        return r.json()
    except Exception as e:
        raise HTTPException(status_code=502, detail=f"Upstream error: {e}")


@app.get("/api/dl")
def download_file(url: str, title: str, artist: str, image: str = ""):
    try:
        r = requests.get(url, timeout=30)
        r.raise_for_status()
        audio_io = io.BytesIO(r.content)
        try:
            audio = MP4(audio_io)
            audio["\xa9nam"] = title
            audio["\xa9ART"] = artist
            if image:
                try:
                    img_res = requests.get(image, timeout=10)
                    if img_res.status_code == 200:
                        audio["covr"] = [MP4Cover(img_res.content, imageformat=MP4Cover.FORMAT_JPEG)]
                except Exception:
                    pass
            audio.save(audio_io)
            audio_io.seek(0)
        except Exception as e:
            print(f"Tagging failed: {e}")
            audio_io.seek(0)
        safe_title = "".join(c for c in title if c.isalpha() or c.isdigit() or c in " -_").rstrip()
        safe_artist = "".join(c for c in artist if c.isalpha() or c.isdigit() or c in " -_").rstrip()
        filename = f"{safe_title} - {safe_artist}.m4a"
        return Response(
            content=audio_io.read(),
            media_type="audio/mp4",
            headers={"Content-Disposition": f'attachment; filename="{filename}"'},
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


# ==========================================================
# AUTH ENDPOINTS
# ==========================================================
@app.post("/api/auth/signup")
def signup(body: AuthBody):
    username = body.username.strip()
    if not (3 <= len(username) <= 30):
        raise HTTPException(status_code=400, detail="Username must be 3-30 characters")
    if len(body.password) < 6:
        raise HTTPException(status_code=400, detail="Password must be at least 6 characters")
    conn = get_db()
    try:
        cur = conn.execute(
            "INSERT INTO users (username, password_hash, created_at) VALUES (?, ?, ?)",
            (username, hash_password(body.password), datetime.utcnow().isoformat()),
        )
        user_id = cur.lastrowid
        conn.commit()
    except sqlite3.IntegrityError:
        conn.close()
        raise HTTPException(status_code=400, detail="Username already taken")
    conn.close()
    token = create_session(user_id)
    return {"token": token, "user": {"id": user_id, "username": username}}


@app.post("/api/auth/login")
def login(body: AuthBody):
    conn = get_db()
    row = conn.execute(
        "SELECT id, username, password_hash FROM users WHERE username = ?",
        (body.username.strip(),),
    ).fetchone()
    conn.close()
    if not row or not verify_password(body.password, row["password_hash"]):
        raise HTTPException(status_code=401, detail="Invalid username or password")
    token = create_session(row["id"])
    return {"token": token, "user": {"id": row["id"], "username": row["username"]}}


@app.post("/api/auth/logout")
def logout(authorization: str = Header(None)):
    if authorization and authorization.startswith("Bearer "):
        token = authorization[7:].strip()
        conn = get_db()
        conn.execute("DELETE FROM sessions WHERE token = ?", (token,))
        conn.commit()
        conn.close()
    return {"ok": True}


@app.get("/api/auth/me")
def me(authorization: str = Header(None)):
    u = current_user(authorization)
    if not u:
        raise HTTPException(status_code=401, detail="Not authenticated")
    return u


# ==========================================================
# PLAYLIST ENDPOINTS
# ==========================================================
@app.get("/api/playlists")
def list_playlists(authorization: str = Header(None)):
    u = require_user(authorization)
    conn = get_db()
    pls = conn.execute(
        "SELECT id, name, created_at FROM playlists WHERE user_id = ? ORDER BY id DESC",
        (u["id"],),
    ).fetchall()
    result = []
    for p in pls:
        songs = conn.execute(
            "SELECT song_data FROM playlist_songs WHERE playlist_id = ? ORDER BY position",
            (p["id"],),
        ).fetchall()
        result.append({
            "id": p["id"],
            "name": p["name"],
            "created_at": p["created_at"],
            "songs": [json.loads(s["song_data"]) for s in songs],
        })
    conn.close()
    return {"playlists": result}


@app.post("/api/playlists")
def create_playlist(body: PlaylistCreate, authorization: str = Header(None)):
    u = require_user(authorization)
    name = body.name.strip()
    if not name or len(name) > 60:
        raise HTTPException(status_code=400, detail="Invalid playlist name")
    conn = get_db()
    cur = conn.execute(
        "INSERT INTO playlists (user_id, name, created_at) VALUES (?, ?, ?)",
        (u["id"], name, datetime.utcnow().isoformat()),
    )
    pid = cur.lastrowid
    conn.commit()
    conn.close()
    return {"id": pid, "name": name, "songs": []}


@app.delete("/api/playlists/{pid}")
def delete_playlist(pid: int, authorization: str = Header(None)):
    u = require_user(authorization)
    conn = get_db()
    row = conn.execute(
        "SELECT id FROM playlists WHERE id = ? AND user_id = ?", (pid, u["id"])
    ).fetchone()
    if not row:
        conn.close()
        raise HTTPException(status_code=404, detail="Playlist not found")
    conn.execute("DELETE FROM playlists WHERE id = ?", (pid,))
    conn.commit()
    conn.close()
    return {"ok": True}


@app.post("/api/playlists/{pid}/songs")
def add_song_to_playlist(pid: int, body: SongBody, authorization: str = Header(None)):
    u = require_user(authorization)
    conn = get_db()
    row = conn.execute(
        "SELECT id FROM playlists WHERE id = ? AND user_id = ?", (pid, u["id"])
    ).fetchone()
    if not row:
        conn.close()
        raise HTTPException(status_code=404, detail="Playlist not found")
    song = body.song
    sid = str(song.get("id", ""))
    if not sid:
        conn.close()
        raise HTTPException(status_code=400, detail="Song must have an id")
    exists = conn.execute(
        "SELECT id FROM playlist_songs WHERE playlist_id = ? AND song_id = ?", (pid, sid)
    ).fetchone()
    if exists:
        conn.close()
        return {"ok": True, "already_exists": True}
    max_pos = conn.execute(
        "SELECT COALESCE(MAX(position), -1) FROM playlist_songs WHERE playlist_id = ?", (pid,)
    ).fetchone()[0]
    conn.execute(
        "INSERT INTO playlist_songs (playlist_id, song_id, song_data, position) VALUES (?, ?, ?, ?)",
        (pid, sid, json.dumps(song), max_pos + 1),
    )
    conn.commit()
    conn.close()
    return {"ok": True}


@app.delete("/api/playlists/{pid}/songs/{song_id}")
def remove_song_from_playlist(pid: int, song_id: str, authorization: str = Header(None)):
    u = require_user(authorization)
    conn = get_db()
    row = conn.execute(
        "SELECT id FROM playlists WHERE id = ? AND user_id = ?", (pid, u["id"])
    ).fetchone()
    if not row:
        conn.close()
        raise HTTPException(status_code=404, detail="Playlist not found")
    conn.execute(
        "DELETE FROM playlist_songs WHERE playlist_id = ? AND song_id = ?", (pid, song_id)
    )
    conn.commit()
    conn.close()
    return {"ok": True}


# ==========================================================
# FAVORITES ENDPOINTS
# ==========================================================
@app.get("/api/favorites")
def list_favorites(authorization: str = Header(None)):
    u = require_user(authorization)
    conn = get_db()
    rows = conn.execute(
        "SELECT song_data FROM favorites WHERE user_id = ? ORDER BY id DESC", (u["id"],)
    ).fetchall()
    conn.close()
    return {"favorites": [json.loads(r["song_data"]) for r in rows]}


@app.post("/api/favorites")
def add_favorite(body: SongBody, authorization: str = Header(None)):
    u = require_user(authorization)
    song = body.song
    sid = str(song.get("id", ""))
    if not sid:
        raise HTTPException(status_code=400, detail="Song must have an id")
    conn = get_db()
    conn.execute(
        "INSERT OR IGNORE INTO favorites (user_id, song_id, song_data, created_at) VALUES (?, ?, ?, ?)",
        (u["id"], sid, json.dumps(song), datetime.utcnow().isoformat()),
    )
    conn.commit()
    conn.close()
    return {"ok": True}


@app.delete("/api/favorites/{song_id}")
def remove_favorite(song_id: str, authorization: str = Header(None)):
    u = require_user(authorization)
    conn = get_db()
    conn.execute(
        "DELETE FROM favorites WHERE user_id = ? AND song_id = ?", (u["id"], song_id)
    )
    conn.commit()
    conn.close()
    return {"ok": True}


@app.post("/api/favorites/sync")
def sync_favorites(body: SyncBody, authorization: str = Header(None)):
    """Guest favorites ko server par merge karta hai jab user pehli baar login kare."""
    u = require_user(authorization)
    conn = get_db()
    added = 0
    for song in body.favorites:
        sid = str(song.get("id", ""))
        if not sid:
            continue
        cur = conn.execute(
            "INSERT OR IGNORE INTO favorites (user_id, song_id, song_data, created_at) VALUES (?, ?, ?, ?)",
            (u["id"], sid, json.dumps(song), datetime.utcnow().isoformat()),
        )
        added += cur.rowcount
    conn.commit()
    conn.close()
    return {"ok": True, "added": added}


# ==========================================================
# APPLE MUSIC — MOBILE UI
# ==========================================================
HTML_PAGE = """
<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0, viewport-fit=cover, user-scalable=no, maximum-scale=1">
<meta name="apple-mobile-web-app-capable" content="yes">
<meta name="apple-mobile-web-app-status-bar-style" content="black-translucent">
<meta name="theme-color" content="#000000">
<title>Apple Music</title>
<style>
  :root {
    --bg:#000; --surface:#1C1C1E; --surface-2:#2C2C2E; --surface-3:#3A3A3C;
    --text:#FFF; --text-sec:#8E8E93; --accent:#FA2D48;
    --tab-h:52px; --mini-h:60px;
    --safe-bottom:env(safe-area-inset-bottom,0px);
    --safe-top:env(safe-area-inset-top,0px);
  }
  *{box-sizing:border-box;margin:0;padding:0;-webkit-tap-highlight-color:transparent;}
  html,body{height:100%;overflow:hidden;background:var(--bg);color:var(--text);
    font-family:-apple-system,BlinkMacSystemFont,"SF Pro Display","Helvetica Neue",Arial,sans-serif;
    font-size:15px;-webkit-font-smoothing:antialiased;user-select:none;}
  body{display:flex;flex-direction:column;padding-top:var(--safe-top);}

  .app-main{flex:1;overflow-y:auto;overflow-x:hidden;
    padding-bottom:calc(var(--mini-h)+var(--tab-h)+var(--safe-bottom)+24px);
    -webkit-overflow-scrolling:touch;scrollbar-width:none;}
  .app-main::-webkit-scrollbar{display:none;}

  .page-header{padding:14px 16px 10px;display:flex;align-items:center;justify-content:space-between;
    position:sticky;top:0;background:rgba(0,0,0,0.85);backdrop-filter:blur(20px);
    -webkit-backdrop-filter:blur(20px);z-index:10;}
  .page-title{font-size:32px;font-weight:700;letter-spacing:-0.9px;}
  .page-action{width:34px;height:34px;border-radius:50%;background:var(--surface-2);
    display:flex;align-items:center;justify-content:center;font-size:15px;color:var(--text);
    border:none;cursor:pointer;flex-shrink:0;}

  .section{margin-bottom:26px;}
  .section-head{padding:0 16px 10px;display:flex;align-items:baseline;justify-content:space-between;}
  .section-title{font-size:21px;font-weight:700;letter-spacing:-0.4px;}
  .section-more{font-size:14px;color:var(--accent);font-weight:500;}
  .section-add{background:var(--surface-2);border:none;color:var(--accent);
    width:28px;height:28px;border-radius:50%;font-size:18px;
    display:flex;align-items:center;justify-content:center;cursor:pointer;}

  .hero{margin:0 16px 24px;border-radius:14px;overflow:hidden;position:relative;
    aspect-ratio:16/10;background:linear-gradient(135deg,#2b2b2b,#111);cursor:pointer;}
  .hero img{width:100%;height:100%;object-fit:cover;display:block;}
  .hero-overlay{position:absolute;inset:0;
    background:linear-gradient(to top,rgba(0,0,0,0.88) 0%,transparent 60%);
    display:flex;flex-direction:column;justify-content:flex-end;padding:14px 16px;}
  .hero-eyebrow{font-size:10px;font-weight:700;letter-spacing:1.2px;
    text-transform:uppercase;color:var(--accent);margin-bottom:3px;}
  .hero-title{font-size:20px;font-weight:700;letter-spacing:-0.3px;line-height:1.2;
    display:-webkit-box;-webkit-line-clamp:2;-webkit-box-orient:vertical;overflow:hidden;}
  .hero-sub{font-size:12px;color:rgba(255,255,255,0.75);margin-top:4px;
    white-space:nowrap;overflow:hidden;text-overflow:ellipsis;}

  .carousel{display:flex;gap:12px;padding:0 16px 4px;overflow-x:auto;
    scroll-snap-type:x mandatory;scrollbar-width:none;}
  .carousel::-webkit-scrollbar{display:none;}
  .carousel-card{flex-shrink:0;width:145px;scroll-snap-align:start;cursor:pointer;}
  .carousel-card .art{width:145px;height:145px;border-radius:10px;object-fit:cover;
    background:var(--surface-2);display:block;margin-bottom:8px;
    box-shadow:0 6px 16px rgba(0,0,0,0.4);}
  .carousel-card .name{font-size:13.5px;font-weight:600;line-height:1.25;
    white-space:nowrap;overflow:hidden;text-overflow:ellipsis;}
  .carousel-card .artist{font-size:12px;color:var(--text-sec);margin-top:2px;
    white-space:nowrap;overflow:hidden;text-overflow:ellipsis;}

  .track-list{padding:0 8px;}
  .track{display:flex;align-items:center;gap:12px;padding:8px;border-radius:8px;
    cursor:pointer;transition:background 0.1s;}
  .track:active{background:var(--surface-2);}
  .track .art{width:52px;height:52px;border-radius:6px;object-fit:cover;
    background:var(--surface-2);flex-shrink:0;}
  .track .meta{flex:1;min-width:0;}
  .track .name{font-size:15px;font-weight:500;white-space:nowrap;
    overflow:hidden;text-overflow:ellipsis;}
  .track.playing .name{color:var(--accent);}
  .track .artist{font-size:13px;color:var(--text-sec);margin-top:1px;
    white-space:nowrap;overflow:hidden;text-overflow:ellipsis;}
  .track .more-btn{color:var(--text-sec);font-size:18px;padding:4px 6px;
    background:none;border:none;cursor:pointer;flex-shrink:0;}
  .track .remove-btn{color:var(--text-sec);font-size:16px;padding:4px 8px;
    background:none;border:none;cursor:pointer;flex-shrink:0;}

  .search-bar{margin:0 16px 16px;display:flex;align-items:center;gap:8px;
    background:var(--surface-2);border-radius:10px;padding:9px 12px;}
  .search-bar .icon{color:var(--text-sec);font-size:15px;}
  .search-bar input{flex:1;background:none;border:none;color:var(--text);
    font-size:16px;outline:none;font-family:inherit;}
  .search-bar input::placeholder{color:var(--text-sec);}
  .search-chips{display:flex;flex-wrap:wrap;gap:8px;padding:0 16px 20px;}
  .chip{padding:8px 14px;background:var(--surface-2);border-radius:20px;
    font-size:13px;color:var(--text);border:none;cursor:pointer;font-family:inherit;}

  .empty{text-align:center;padding:70px 24px 40px;color:var(--text-sec);}
  .empty .big{font-size:48px;opacity:0.3;margin-bottom:14px;}
  .empty .title{font-size:17px;font-weight:600;color:var(--text);margin-bottom:6px;}
  .empty .sub{font-size:14px;}

  .skel{background:linear-gradient(90deg,#161616 0%,#242424 50%,#161616 100%);
    background-size:200% 100%;animation:shimmer 1.3s infinite;border-radius:6px;}
  @keyframes shimmer{0%{background-position:200% 0;}100%{background-position:-200% 0;}}

  .mini-player{position:fixed;left:8px;right:8px;
    bottom:calc(var(--tab-h) + var(--safe-bottom) + 6px);
    height:var(--mini-h);background:rgba(44,44,46,0.96);
    backdrop-filter:blur(20px);-webkit-backdrop-filter:blur(20px);
    border-radius:12px;display:flex;align-items:center;gap:10px;
    padding:8px 10px 8px 8px;z-index:60;
    box-shadow:0 6px 20px rgba(0,0,0,0.6);
    transform:translateY(140%);
    transition:transform 0.3s cubic-bezier(0.32,0.72,0,1);cursor:pointer;}
  .mini-player.show{transform:translateY(0);}
  .mini-player .art{width:44px;height:44px;border-radius:6px;object-fit:cover;
    background:var(--surface-3);flex-shrink:0;}
  .mini-player .meta{flex:1;min-width:0;}
  .mini-player .name{font-size:13.5px;font-weight:600;
    white-space:nowrap;overflow:hidden;text-overflow:ellipsis;}
  .mini-player .artist{font-size:12px;color:var(--text-sec);
    white-space:nowrap;overflow:hidden;text-overflow:ellipsis;margin-top:1px;}
  .mini-player .ctrl{background:none;border:none;color:var(--text);
    font-size:22px;padding:6px 8px;cursor:pointer;flex-shrink:0;line-height:1;}
  .mini-player .ctrl:active{opacity:0.6;}

  .tab-bar{position:fixed;left:0;right:0;bottom:0;
    height:calc(var(--tab-h) + var(--safe-bottom));
    padding-bottom:var(--safe-bottom);
    background:rgba(20,20,22,0.94);backdrop-filter:blur(24px);
    -webkit-backdrop-filter:blur(24px);
    border-top:0.5px solid rgba(255,255,255,0.1);display:flex;z-index:55;}
  .tab{flex:1;display:flex;flex-direction:column;align-items:center;justify-content:center;
    gap:2px;background:none;border:none;color:var(--text-sec);
    font-family:inherit;font-size:10px;font-weight:500;cursor:pointer;
    padding:6px 0;transition:color 0.15s;}
  .tab .ic{font-size:22px;line-height:1;}
  .tab.active{color:var(--accent);}

  .full-player{position:fixed;inset:0;background:#000;z-index:100;
    display:flex;flex-direction:column;padding-top:var(--safe-top);
    padding-bottom:calc(var(--safe-bottom) + 8px);
    transform:translateY(100%);
    transition:transform 0.35s cubic-bezier(0.32,0.72,0,1);}
  .full-player.show{transform:translateY(0);}
  .full-player .backdrop{position:absolute;inset:0;
    background:radial-gradient(circle at 50% 30%,rgba(250,45,72,0.32),transparent 65%);
    z-index:-1;pointer-events:none;transition:background 0.6s;}
  .player-top{display:flex;align-items:center;justify-content:space-between;
    padding:6px 16px;height:46px;}
  .player-top button{background:none;border:none;color:var(--text);
    font-size:22px;cursor:pointer;width:38px;height:38px;
    display:flex;align-items:center;justify-content:center;border-radius:50%;}
  .player-top button:active{background:rgba(255,255,255,0.1);}
  .player-top .src{font-size:10.5px;color:var(--text-sec);
    text-transform:uppercase;letter-spacing:1.2px;font-weight:600;}
  .player-art{flex:1;display:flex;align-items:center;justify-content:center;
    padding:16px 30px;min-height:0;}
  .player-art img{max-width:100%;max-height:100%;border-radius:12px;
    object-fit:cover;box-shadow:0 20px 60px rgba(0,0,0,0.7);background:var(--surface-2);}
  .player-info{padding:0 30px;display:flex;align-items:center;
    justify-content:space-between;margin-bottom:18px;gap:12px;}
  .player-info .meta{flex:1;min-width:0;}
  .player-info .name{font-size:20px;font-weight:700;letter-spacing:-0.3px;
    white-space:nowrap;overflow:hidden;text-overflow:ellipsis;}
  .player-info .artist{font-size:16.5px;color:var(--accent);margin-top:2px;
    white-space:nowrap;overflow:hidden;text-overflow:ellipsis;}
  .player-info .fav-btn{background:none;border:none;color:var(--text);
    font-size:22px;cursor:pointer;padding:6px;flex-shrink:0;}
  .player-info .fav-btn.active{color:var(--accent);}
  .player-progress{padding:0 30px;margin-bottom:16px;}
  .progress-track{height:5px;background:rgba(255,255,255,0.18);border-radius:3px;
    cursor:pointer;position:relative;margin-bottom:6px;}
  .progress-fill{height:100%;background:white;border-radius:3px;width:0%;}
  .progress-times{display:flex;justify-content:space-between;font-size:11px;
    color:var(--text-sec);font-variant-numeric:tabular-nums;}
  .player-controls{display:flex;align-items:center;justify-content:center;
    gap:34px;padding:0 30px 22px;}
  .ctrl-big{background:none;border:none;color:var(--text);cursor:pointer;
    display:flex;align-items:center;justify-content:center;line-height:1;
    transition:transform 0.1s;}
  .ctrl-big:active{transform:scale(0.9);}
  .ctrl-big.small{font-size:26px;color:var(--text);}
  .ctrl-big.play{font-size:42px;width:60px;height:60px;}
  .player-bottom{display:flex;align-items:center;gap:12px;
    padding:0 40px 6px;color:var(--text-sec);font-size:13px;}
  .player-bottom input[type="range"]{flex:1;accent-color:white;height:4px;cursor:pointer;}

  .toast{position:fixed;left:50%;
    bottom:calc(var(--tab-h) + var(--mini-h) + var(--safe-bottom) + 28px);
    transform:translate(-50%,16px);background:rgba(50,50,52,0.98);
    padding:10px 18px;border-radius:20px;font-size:13px;font-weight:500;color:white;
    z-index:200;opacity:0;pointer-events:none;transition:all 0.25s;
    box-shadow:0 6px 20px rgba(0,0,0,0.6);max-width:85vw;text-align:center;}
  .toast.show{opacity:1;transform:translate(-50%,0);}

  .sheet-backdrop{position:fixed;inset:0;background:rgba(0,0,0,0.6);
    z-index:150;opacity:0;pointer-events:none;transition:opacity 0.25s;
    backdrop-filter:blur(2px);}
  .sheet-backdrop.show{opacity:1;pointer-events:auto;}
  .action-sheet{position:fixed;left:8px;right:8px;
    bottom:calc(var(--safe-bottom) + 8px);
    background:rgba(40,40,42,0.98);backdrop-filter:blur(30px);
    -webkit-backdrop-filter:blur(30px);border-radius:14px;z-index:151;
    padding:8px 0;transform:translateY(120%);
    transition:transform 0.3s cubic-bezier(0.32,0.72,0,1);overflow:hidden;
    max-height:70vh;overflow-y:auto;}
  .action-sheet.show{transform:translateY(0);}
  .sheet-header{padding:12px 18px 10px;
    border-bottom:0.5px solid rgba(255,255,255,0.1);margin-bottom:4px;}
  .sheet-header .t{font-size:13px;font-weight:600;color:var(--text);
    white-space:nowrap;overflow:hidden;text-overflow:ellipsis;}
  .sheet-header .s{font-size:12px;color:var(--text-sec);margin-top:2px;
    white-space:nowrap;overflow:hidden;text-overflow:ellipsis;}
  .sheet-btn{display:flex;align-items:center;gap:12px;padding:14px 18px;
    background:none;border:none;color:var(--text);font-size:15px;font-weight:500;
    width:100%;text-align:left;cursor:pointer;font-family:inherit;}
  .sheet-btn:active{background:rgba(255,255,255,0.08);}
  .sheet-btn.danger{color:var(--accent);}
  .sheet-btn .ico{font-size:18px;width:22px;text-align:center;}
  .sheet-sub-header{padding:10px 18px 6px;font-size:11px;font-weight:700;
    color:var(--text-sec);text-transform:uppercase;letter-spacing:1px;
    border-top:0.5px solid rgba(255,255,255,0.1);margin-top:4px;}

  /* Modals */
  .modal-backdrop{position:fixed;inset:0;background:rgba(0,0,0,0.7);
    z-index:300;opacity:0;pointer-events:none;transition:opacity 0.2s;
    backdrop-filter:blur(4px);}
  .modal-backdrop.show{opacity:1;pointer-events:auto;}
  .modal{position:fixed;left:50%;top:50%;
    transform:translate(-50%,-50%) scale(0.94);
    background:var(--surface-2);border-radius:14px;z-index:301;
    width:calc(100% - 40px);max-width:360px;opacity:0;pointer-events:none;
    transition:all 0.2s;overflow:hidden;}
  .modal.show{opacity:1;pointer-events:auto;transform:translate(-50%,-50%) scale(1);}
  .modal-title{font-size:18px;font-weight:700;padding:18px 20px 10px;}
  .modal-body{padding:0 20px 12px;}
  .modal-body input{width:100%;background:var(--surface-3);border:none;
    color:var(--text);padding:12px 14px;border-radius:8px;font-size:16px;
    margin-bottom:8px;outline:none;font-family:inherit;}
  .modal-error{color:var(--accent);font-size:12px;min-height:16px;margin-top:2px;}
  .modal-actions{display:flex;gap:8px;padding:10px 20px 16px;}
  .modal-actions button{flex:1;padding:10px;border-radius:8px;border:none;
    font-size:15px;font-weight:600;font-family:inherit;cursor:pointer;}
  .modal-actions button:first-child{background:var(--surface-3);color:var(--text);}
  .modal-actions button:last-child{background:var(--accent);color:white;}
  .modal-switch{text-align:center;padding:0 20px 18px;font-size:13px;color:var(--text-sec);}
  .modal-switch a{color:var(--accent);text-decoration:none;font-weight:600;}

  .signin-banner{margin:0 16px 16px;padding:14px 16px;border-radius:12px;
    background:linear-gradient(135deg,rgba(250,45,72,0.18),rgba(250,45,72,0.08));
    border:1px solid rgba(250,45,72,0.3);}
  .signin-banner .t{font-size:14px;font-weight:700;margin-bottom:4px;}
  .signin-banner .s{font-size:12.5px;color:var(--text-sec);margin-bottom:10px;line-height:1.4;}
  .signin-banner button{background:var(--accent);color:white;border:none;
    padding:8px 16px;border-radius:18px;font-size:13px;font-weight:600;
    font-family:inherit;cursor:pointer;}

  .playlist-row{display:flex;align-items:center;gap:12px;padding:8px;
    border-radius:8px;cursor:pointer;}
  .playlist-row:active{background:var(--surface-2);}
  .playlist-icon{width:52px;height:52px;border-radius:6px;background:var(--surface-3);
    display:flex;align-items:center;justify-content:center;font-size:22px;
    color:var(--accent);flex-shrink:0;}
  .playlist-row .meta{flex:1;min-width:0;}
  .playlist-row .name{font-size:15px;font-weight:500;
    white-space:nowrap;overflow:hidden;text-overflow:ellipsis;}
  .playlist-row .count{font-size:13px;color:var(--text-sec);margin-top:1px;}

  .profile-row{display:flex;align-items:center;gap:12px;
    margin:0 16px 16px;padding:12px 14px;border-radius:12px;
    background:var(--surface-2);}
  .profile-avatar{width:40px;height:40px;border-radius:50%;
    background:var(--accent);color:white;
    display:flex;align-items:center;justify-content:center;
    font-size:17px;font-weight:700;flex-shrink:0;text-transform:uppercase;}
  .profile-row .meta{flex:1;min-width:0;}
  .profile-row .name{font-size:14px;font-weight:600;
    white-space:nowrap;overflow:hidden;text-overflow:ellipsis;}
  .profile-row .sub{font-size:12px;color:var(--text-sec);}
  .profile-row .logout{background:none;border:none;color:var(--accent);
    font-size:13px;font-weight:600;padding:6px 8px;font-family:inherit;cursor:pointer;}
</style>
</head>
<body>

<div class="app-main" id="appMain"></div>

<div class="mini-player" id="miniPlayer" onclick="openFullPlayer()">
  <img class="art" id="miniArt" src="" alt="">
  <div class="meta">
    <div class="name" id="miniName">Not Playing</div>
    <div class="artist" id="miniArtist">-</div>
  </div>
  <button class="ctrl" id="miniPlayBtn" onclick="event.stopPropagation(); togglePlay()">▶</button>
</div>

<div class="tab-bar">
  <button class="tab active" data-tab="home" onclick="switchTab('home')">
    <span class="ic">⌂</span><span>Home</span>
  </button>
  <button class="tab" data-tab="search" onclick="switchTab('search')">
    <span class="ic">⌕</span><span>Search</span>
  </button>
  <button class="tab" data-tab="library" onclick="switchTab('library')">
    <span class="ic">♡</span><span>Library</span>
  </button>
  <button class="tab" data-tab="queue" onclick="switchTab('queue')">
    <span class="ic">≡</span><span>Queue</span>
  </button>
</div>

<div class="full-player" id="fullPlayer">
  <div class="backdrop" id="playerBg"></div>
  <div class="player-top">
    <button onclick="closeFullPlayer()">⌄</button>
    <span class="src" id="playerSrc">Playing</span>
    <button onclick="openActionSheetCurrent()">⋯</button>
  </div>
  <div class="player-art"><img id="fullArt" src="" alt=""></div>
  <div class="player-info">
    <div class="meta">
      <div class="name" id="fullName">-</div>
      <div class="artist" id="fullArtist">-</div>
    </div>
    <button class="fav-btn" id="fullFavBtn" onclick="toggleFavCurrent()">♡</button>
  </div>
  <div class="player-progress">
    <div class="progress-track" onclick="seekAudio(event)">
      <div class="progress-fill" id="fullProgress"></div>
    </div>
    <div class="progress-times">
      <span id="fullCurr">0:00</span>
      <span id="fullDur">0:00</span>
    </div>
  </div>
  <div class="player-controls">
    <button class="ctrl-big small" onclick="playPrev()">⏮</button>
    <button class="ctrl-big play" id="fullPlayBtn" onclick="togglePlay()">▶</button>
    <button class="ctrl-big small" onclick="playNext()">⏭</button>
  </div>
  <div class="player-bottom">
    <span>🔈</span>
    <input type="range" min="0" max="1" step="0.01" value="1" oninput="audio.volume=this.value">
    <span>🔊</span>
  </div>
</div>

<div class="sheet-backdrop" id="sheetBackdrop" onclick="closeActionSheet()"></div>
<div class="action-sheet" id="actionSheet">
  <div class="sheet-header">
    <div class="t" id="sheetTitle">-</div>
    <div class="s" id="sheetSub">-</div>
  </div>
  <div id="sheetActions"></div>
</div>

<div class="modal-backdrop" id="authBackdrop" onclick="closeAuth()"></div>
<div class="modal" id="authModal">
  <div class="modal-title" id="authTitle">Sign In</div>
  <div class="modal-body">
    <input id="authUser" placeholder="Username" autocomplete="username" autocapitalize="off">
    <input id="authPass" type="password" placeholder="Password" autocomplete="current-password">
    <div class="modal-error" id="authError"></div>
  </div>
  <div class="modal-actions">
    <button onclick="closeAuth()">Cancel</button>
    <button id="authSubmit" onclick="submitAuth()">Sign In</button>
  </div>
  <div class="modal-switch">
    <span id="authSwitchMsg">Don't have an account?</span>
    <a href="#" onclick="event.preventDefault();toggleAuthMode()" id="authSwitchLink">Sign Up</a>
  </div>
</div>

<div class="modal-backdrop" id="plBackdrop" onclick="closeCreatePlaylist()"></div>
<div class="modal" id="plModal">
  <div class="modal-title">New Playlist</div>
  <div class="modal-body">
    <input id="plName" placeholder="Playlist name" maxlength="60">
    <div class="modal-error" id="plError"></div>
  </div>
  <div class="modal-actions">
    <button onclick="closeCreatePlaylist()">Cancel</button>
    <button onclick="submitCreatePlaylist()">Create</button>
  </div>
</div>

<audio id="audioPlayer"></audio>
<div class="toast" id="toast"></div>

<script>
/* ==========================================================
   STATE
   ========================================================== */
const state = {
  tab: 'home',
  searchResults: [],
  discover: [],
  trending: [],
  favorites: [],
  queue: [],
  playlists: [],
  librarySubView: null,           // null | { type:'playlist', id, name, songs }
  currentSong: null,
  isPlaying: false,
  loadingHome: false,
  loadingSearch: false,
  searchQuery: '',
  focusSearch: false,
  auth: {
    token: localStorage.getItem('musicAuthToken') || null,
    user: null
  },
  authMode: 'signin',             // 'signin' | 'signup'
  pendingSheetSong: null,
  pendingNewPlaylistSong: null
};

const audio = document.getElementById('audioPlayer');
const main  = document.getElementById('appMain');
const PLACEHOLDER = "data:image/svg+xml;utf8,<svg xmlns='http://www.w3.org/2000/svg' width='120' height='120'><rect width='120' height='120' fill='%23222'/><text x='50%25' y='55%25' dominant-baseline='middle' text-anchor='middle' font-size='40' fill='%23666'>♪</text></svg>";

/* ==========================================================
   HELPERS
   ========================================================== */
function esc(s) {
  return String(s == null ? '' : s)
    .replace(/&/g,'&amp;').replace(/</g,'&lt;').replace(/>/g,'&gt;')
    .replace(/"/g,'&quot;').replace(/'/g,'&#39;');
}
function fmtTime(s){ if(!isFinite(s)||s<0)s=0; const m=Math.floor(s/60),ss=Math.floor(s%60); return m+':'+(ss<10?'0':'')+ss; }
function artistOf(song){
  if(!song) return '';
  if(song.subtitle) return song.subtitle;
  if(song.artists && song.artists.length) return song.artists.join(', ');
  return 'Unknown Artist';
}
function playableUrl(song){
  if(!song) return null;
  const u = song.download_urls || {};
  return u['320'] || u['160'] || song.download_url || null;
}
function findSong(id){
  return state.searchResults.find(s=>s.id===id)
      || state.discover.find(s=>s.id===id)
      || state.trending.find(s=>s.id===id)
      || state.favorites.find(s=>s.id===id)
      || state.queue.find(s=>s.id===id)
      || (state.librarySubView && state.librarySubView.songs || []).find(s=>s.id===id);
}
function authHeaders(){
  return state.auth.token ? {'Authorization':'Bearer '+state.auth.token} : {};
}
let toastTimer;
function toast(msg){
  const t=document.getElementById('toast');
  t.textContent=msg; t.classList.add('show');
  clearTimeout(toastTimer);
  toastTimer=setTimeout(()=>t.classList.remove('show'),2000);
}

/* ==========================================================
   AUTH
   ========================================================== */
function openAuth(mode){
  state.authMode = mode || 'signin';
  updateAuthModal();
  document.getElementById('authError').textContent='';
  document.getElementById('authUser').value='';
  document.getElementById('authPass').value='';
  document.getElementById('authBackdrop').classList.add('show');
  document.getElementById('authModal').classList.add('show');
  setTimeout(()=>document.getElementById('authUser').focus(),250);
}
function closeAuth(){
  document.getElementById('authBackdrop').classList.remove('show');
  document.getElementById('authModal').classList.remove('show');
}
function toggleAuthMode(){
  state.authMode = state.authMode==='signin' ? 'signup' : 'signin';
  updateAuthModal();
}
function updateAuthModal(){
  const isSignup = state.authMode==='signup';
  document.getElementById('authTitle').textContent = isSignup ? 'Create Account' : 'Sign In';
  document.getElementById('authSubmit').textContent = isSignup ? 'Sign Up' : 'Sign In';
  document.getElementById('authSwitchMsg').textContent = isSignup ? 'Already have an account?' : "Don't have an account?";
  document.getElementById('authSwitchLink').textContent = isSignup ? 'Sign In' : 'Sign Up';
}
async function submitAuth(){
  const username = document.getElementById('authUser').value.trim();
  const password = document.getElementById('authPass').value;
  const err = document.getElementById('authError');
  const btn = document.getElementById('authSubmit');
  err.textContent='';
  if(username.length<3){ err.textContent='Username must be 3+ characters'; return; }
  if(password.length<6){ err.textContent='Password must be 6+ characters'; return; }
  btn.disabled=true; btn.textContent='...';
  try{
    const endpoint = state.authMode==='signup' ? '/api/auth/signup' : '/api/auth/login';
    const res = await fetch(endpoint,{
      method:'POST',
      headers:{'Content-Type':'application/json'},
      body: JSON.stringify({username, password})
    });
    const data = await res.json();
    if(!res.ok){ err.textContent = data.detail || 'Failed'; btn.disabled=false; updateAuthModal(); return; }
    await onLoginSuccess(data.token, data.user);
    closeAuth();
  }catch(e){
    err.textContent='Network error';
    btn.disabled=false; updateAuthModal();
  }
}
async function onLoginSuccess(token, user){
  state.auth.token = token;
  state.auth.user = user;
  localStorage.setItem('musicAuthToken', token);

  // Guest favourites ko server par migrate karo
  const localFavs = JSON.parse(localStorage.getItem('musicFavs')||'[]');
  if(localFavs.length){
    try{
      await fetch('/api/favorites/sync',{
        method:'POST',
        headers:{'Content-Type':'application/json',...authHeaders()},
        body: JSON.stringify({favorites: localFavs})
      });
    }catch(e){}
  }
  localStorage.removeItem('musicFavs');

  await loadFavoritesFromServer();
  await loadPlaylistsFromServer();
  toast('Welcome, '+user.username);
  renderTab();
}
async function logout(){
  try{
    await fetch('/api/auth/logout',{method:'POST',headers:authHeaders()});
  }catch(e){}
  state.auth.token = null;
  state.auth.user = null;
  localStorage.removeItem('musicAuthToken');
  state.playlists = [];
  state.librarySubView = null;
  // Local favourites wapas laao (guest mode)
  state.favorites = JSON.parse(localStorage.getItem('musicFavs')||'[]');
  renderTab();
  toast('Signed out');
}

/* ==========================================================
   FAVORITES (server or local)
   ========================================================== */
async function loadFavoritesFromServer(){
  if(!state.auth.user) return;
  try{
    const res = await fetch('/api/favorites',{headers:authHeaders()});
    if(res.ok){
      const data = await res.json();
      state.favorites = data.favorites || [];
    }
  }catch(e){}
}
function persistLocalFavs(){
  localStorage.setItem('musicFavs', JSON.stringify(state.favorites));
}
async function toggleFavById(id){
  const song = findSong(id);
  if(!song) return;
  const idx = state.favorites.findIndex(f=>f.id===id);
  const wasFav = idx > -1;
  if(wasFav) state.favorites.splice(idx,1);
  else state.favorites.push(song);

  if(state.auth.user){
    try{
      if(wasFav){
        await fetch('/api/favorites/'+encodeURIComponent(id),{method:'DELETE',headers:authHeaders()});
      }else{
        await fetch('/api/favorites',{
          method:'POST',
          headers:{'Content-Type':'application/json',...authHeaders()},
          body: JSON.stringify({song})
        });
      }
    }catch(e){ toast('Sync failed'); }
  }else{
    persistLocalFavs();
  }
  updateFavIcon();
  renderTab();
  toast(wasFav ? 'Removed from favorites' : 'Added to favorites');
}
function toggleFavCurrent(){
  if(state.currentSong) toggleFavById(state.currentSong.id);
}
function isFav(id){ return state.favorites.some(f=>f.id===id); }
function updateFavIcon(){
  const btn = document.getElementById('fullFavBtn');
  if(!btn) return;
  if(!state.currentSong){ btn.textContent='♡'; btn.classList.remove('active'); return; }
  const fav = isFav(state.currentSong.id);
  btn.textContent = fav ? '♥' : '♡';
  btn.classList.toggle('active', fav);
}

/* ==========================================================
   PLAYLISTS (server-side, requires login)
   ========================================================== */
async function loadPlaylistsFromServer(){
  if(!state.auth.user){ state.playlists=[]; return; }
  try{
    const res = await fetch('/api/playlists',{headers:authHeaders()});
    if(res.ok){
      const data = await res.json();
      state.playlists = data.playlists || [];
    }
  }catch(e){}
}
function openCreatePlaylist(song){
  if(!state.auth.user){ openAuth(); toast('Sign in to create playlists'); return; }
  state.pendingNewPlaylistSong = song || null;
  document.getElementById('plName').value='';
  document.getElementById('plError').textContent='';
  document.getElementById('plBackdrop').classList.add('show');
  document.getElementById('plModal').classList.add('show');
  setTimeout(()=>document.getElementById('plName').focus(),250);
}
function closeCreatePlaylist(){
  document.getElementById('plBackdrop').classList.remove('show');
  document.getElementById('plModal').classList.remove('show');
  state.pendingNewPlaylistSong = null;
}
async function submitCreatePlaylist(){
  const name = document.getElementById('plName').value.trim();
  const err = document.getElementById('plError');
  err.textContent='';
  if(!name || name.length>60){ err.textContent='Enter a name (max 60 chars)'; return; }
  try{
    const res = await fetch('/api/playlists',{
      method:'POST',
      headers:{'Content-Type':'application/json',...authHeaders()},
      body: JSON.stringify({name})
    });
    if(!res.ok){
      const d = await res.json();
      err.textContent = d.detail || 'Failed';
      return;
    }
    const p = await res.json();
    // Agar action sheet se create kiya tha aur song pending hai to add karo
    if(state.pendingNewPlaylistSong){
      await fetch('/api/playlists/'+p.id+'/songs',{
        method:'POST',
        headers:{'Content-Type':'application/json',...authHeaders()},
        body: JSON.stringify({song: state.pendingNewPlaylistSong})
      });
      toast('Added to "'+name+'"');
    }else{
      toast('Playlist created');
    }
    closeCreatePlaylist();
    await loadPlaylistsFromServer();
    renderTab();
  }catch(e){
    err.textContent='Network error';
  }
}
async function addSongToPlaylist(pid, song){
  if(!state.auth.user){ openAuth(); toast('Sign in required'); return; }
  try{
    const res = await fetch('/api/playlists/'+pid+'/songs',{
      method:'POST',
      headers:{'Content-Type':'application/json',...authHeaders()},
      body: JSON.stringify({song})
    });
    const data = await res.json();
    if(data.already_exists) toast('Already in playlist');
    else toast('Added to playlist');
    await loadPlaylistsFromServer();
    if(state.librarySubView && state.librarySubView.type==='playlist'){
      const p = state.playlists.find(x=>x.id===state.librarySubView.id);
      if(p) state.librarySubView = {type:'playlist',...p};
    }
    renderTab();
  }catch(e){ toast('Failed to add'); }
}
async function removeSongFromPlaylist(pid, songId){
  try{
    await fetch('/api/playlists/'+pid+'/songs/'+encodeURIComponent(songId),{
      method:'DELETE',headers:authHeaders()
    });
    toast('Removed from playlist');
    await loadPlaylistsFromServer();
    const p = state.playlists.find(x=>x.id===state.librarySubView.id);
    if(p) state.librarySubView = {type:'playlist',...p};
    renderTab();
  }catch(e){ toast('Failed'); }
}
async function deletePlaylist(pid){
  if(!confirm('Delete this playlist?')) return;
  try{
    await fetch('/api/playlists/'+pid,{method:'DELETE',headers:authHeaders()});
    toast('Playlist deleted');
    closePlaylistView();
    await loadPlaylistsFromServer();
    renderTab();
  }catch(e){ toast('Failed'); }
}
function openPlaylistView(id){
  const p = state.playlists.find(x=>x.id===id);
  if(!p) return;
  state.librarySubView = {type:'playlist', id:p.id, name:p.name, songs:p.songs||[]};
  main.scrollTop = 0;
  renderTab();
}
function closePlaylistView(){
  state.librarySubView = null;
  renderTab();
}

/* ==========================================================
   TAB SWITCHING
   ========================================================== */
function switchTab(tab){
  state.tab = tab;
  if(tab!=='library') state.librarySubView = null;
  document.querySelectorAll('.tab').forEach(t=>
    t.classList.toggle('active', t.dataset.tab===tab));
  main.scrollTop = 0;
  renderTab();
}
function renderTab(){
  if(state.tab==='home') renderHome();
  else if(state.tab==='search') renderSearchTab();
  else if(state.tab==='library') renderLibraryTab();
  else if(state.tab==='queue') renderQueueTab();
}

/* ==========================================================
   HOME
   ========================================================== */
async function loadHomeData(){
  state.loadingHome = true;
  renderHome();
  const queries = ["Top Bollywood Hits","Arijit Singh Best Songs","Trending Reels Songs",
                   "Shreya Ghoshal Hits","Punjabi Top 50","English Pop Hits"];
  try{
    const responses = await Promise.all(queries.map(q=>
      fetch('/api/search?song='+encodeURIComponent(q))
        .then(r=>r.json()).catch(()=>({}))
    ));
    let all = [];
    responses.forEach(d=>{ if(d.results) all = all.concat(d.results); });
    const seen = new Set();
    all = all.filter(s=>{
      if(!s||!s.id||seen.has(s.id)) return false;
      seen.add(s.id); return true;
    });
    all.sort(()=>Math.random()-0.5);
    state.discover = all.slice(0,10);
    state.trending = all.slice(10,25);
    state.searchResults = all;
    state.loadingHome = false;
    renderHome();
  }catch(e){
    state.loadingHome = false;
    renderHome();
  }
}
function renderHome(){
  let html = `
    <div class="page-header">
      <div class="page-title">Listen Now</div>
      <button class="page-action" onclick="switchTab('search')">⌕</button>
    </div>`;
  if(state.loadingHome){
    html += `<div style="margin:0 16px 24px;border-radius:14px;aspect-ratio:16/10;" class="skel"></div>
      <div class="section-head"><div class="section-title">Made For You</div></div>
      <div class="carousel">${skelCarousel(3)}</div>
      <div class="section-head" style="margin-top:20px;"><div class="section-title">Recently Played</div></div>
      <div class="track-list">${skelTracks(5)}</div>`;
    main.innerHTML = html; return;
  }
  const featured = state.discover[0];
  if(featured){
    html += `<div class="hero" onclick="playSongById('${esc(featured.id)}')">
      <img src="${esc(featured.image||PLACEHOLDER)}" onerror="this.src='${PLACEHOLDER}'">
      <div class="hero-overlay">
        <div class="hero-eyebrow">Featured</div>
        <div class="hero-title">${esc(featured.title)}</div>
        <div class="hero-sub">${esc(artistOf(featured))}</div>
      </div></div>`;
  }
  if(state.discover.length>1){
    html += `<div class="section"><div class="section-head"><div class="section-title">Made For You</div></div>
      <div class="carousel">${state.discover.slice(1,9).map(cardCarousel).join('')}</div></div>`;
  }
  if(state.trending.length){
    html += `<div class="section"><div class="section-head"><div class="section-title">Top Picks</div></div>
      <div class="carousel">${state.trending.slice(0,8).map(cardCarousel).join('')}</div></div>`;
  }
  if(state.trending.length>8){
    html += `<div class="section"><div class="section-head"><div class="section-title">Recently Played</div></div>
      <div class="track-list">${state.trending.slice(8,18).map(cardTrack).join('')}</div></div>`;
  }
  main.innerHTML = html;
}
function skelCarousel(n){
  return Array(n).fill(0).map(()=>
    `<div class="carousel-card"><div class="art skel"></div>
      <div class="skel" style="height:14px;width:70%;margin-bottom:6px;"></div>
      <div class="skel" style="height:12px;width:50%;"></div></div>`).join('');
}
function skelTracks(n){
  return Array(n).fill(0).map(()=>
    `<div class="track"><div class="art skel"></div>
      <div class="meta"><div class="skel" style="height:14px;width:70%;margin-bottom:6px;"></div>
      <div class="skel" style="height:12px;width:45%;"></div></div></div>`).join('');
}
function cardCarousel(song){
  return `<div class="carousel-card" onclick="playSongById('${esc(song.id)}')">
    <img class="art" src="${esc(song.image||PLACEHOLDER)}" onerror="this.src='${PLACEHOLDER}'">
    <div class="name">${esc(song.title)}</div>
    <div class="artist">${esc(artistOf(song))}</div></div>`;
}
function cardTrack(song){
  const playing = state.currentSong && state.currentSong.id===song.id;
  return `<div class="track ${playing?'playing':''}" onclick="playSongById('${esc(song.id)}')">
    <img class="art" src="${esc(song.image||PLACEHOLDER)}" onerror="this.src='${PLACEHOLDER}'">
    <div class="meta">
      <div class="name">${esc(song.title)}</div>
      <div class="artist">${esc(artistOf(song))}</div>
    </div>
    <button class="more-btn" onclick="event.stopPropagation();openActionSheetFor('${esc(song.id)}')">⋯</button>
  </div>`;
}
function cardPlaylistTrack(song, pid){
  const playing = state.currentSong && state.currentSong.id===song.id;
  return `<div class="track ${playing?'playing':''}" onclick="playSongById('${esc(song.id)}')">
    <img class="art" src="${esc(song.image||PLACEHOLDER)}" onerror="this.src='${PLACEHOLDER}'">
    <div class="meta">
      <div class="name">${esc(song.title)}</div>
      <div class="artist">${esc(artistOf(song))}</div>
    </div>
    <button class="remove-btn" onclick="event.stopPropagation();removeSongFromPlaylist(${pid},'${esc(song.id)}')">✕</button>
  </div>`;
}

/* ==========================================================
   SEARCH
   ========================================================== */
function renderSearchTab(){
  let html = `<div class="page-header"><div class="page-title">Search</div></div>
    <div class="search-bar">
      <span class="icon">⌕</span>
      <input id="searchInput" placeholder="Artists, songs, or albums"
        autocomplete="off" autocorrect="off" autocapitalize="off"
        onkeydown="if(event.key==='Enter'){event.preventDefault();doSearch();}"
        value="${esc(state.searchQuery||'')}">
    </div>`;
  if(!state.searchResults.length && !state.searchQuery){
    html += `<div class="section-head"><div class="section-title">Browse Categories</div></div>
      <div class="search-chips">
        ${["Top Bollywood","Arijit Singh","Punjabi Hits","Shreya Ghoshal","English Pop","Reels Trending","Lofi Mix","Romantic"]
          .map(c=>`<button class="chip" onclick="searchQuick('${esc(c)}')">${esc(c)}</button>`).join('')}
      </div>`;
  }
  if(state.searchQuery && !state.searchResults.length && !state.loadingSearch){
    html += `<div class="empty"><div class="big">🔍</div><div class="title">No results</div>
      <div class="sub">Try a different search.</div></div>`;
  }
  if(state.loadingSearch){
    html += `<div class="track-list">${skelTracks(6)}</div>`;
  }else if(state.searchResults.length){
    html += `<div class="section"><div class="section-head"><div class="section-title">Songs</div></div>
      <div class="track-list">${state.searchResults.map(cardTrack).join('')}</div></div>`;
  }
  main.innerHTML = html;
  if(state.focusSearch){
    state.focusSearch = false;
    const inp = document.getElementById('searchInput');
    if(inp) setTimeout(()=>inp.focus(),100);
  }
}
function searchQuick(q){
  const inp = document.getElementById('searchInput');
  if(inp) inp.value = q;
  doSearch();
}
async function doSearch(){
  const inp = document.getElementById('searchInput');
  const q = (inp ? inp.value : '').trim();
  if(!q) return;
  state.searchQuery = q;
  state.loadingSearch = true;
  state.searchResults = [];
  renderSearchTab();
  try{
    const res = await fetch('/api/search?song='+encodeURIComponent(q));
    const data = await res.json();
    state.searchResults = data.results || [];
  }catch(e){
    state.searchResults = [];
    toast('Search failed');
  }
  state.loadingSearch = false;
  renderSearchTab();
}

/* ==========================================================
   LIBRARY
   ========================================================== */
function renderLibraryTab(){
  if(state.librarySubView && state.librarySubView.type==='playlist'){
    renderPlaylistDetail(); return;
  }
  const loggedIn = !!state.auth.user;
  let html = `<div class="page-header"><div class="page-title">Library</div></div>`;

  if(loggedIn){
    const initial = (state.auth.user.username||'?').charAt(0).toUpperCase();
    html += `<div class="profile-row">
      <div class="profile-avatar">${esc(initial)}</div>
      <div class="meta">
        <div class="name">${esc(state.auth.user.username)}</div>
        <div class="sub">Signed in</div>
      </div>
      <button class="logout" onclick="logout()">Sign Out</button>
    </div>`;
  }else{
    html += `<div class="signin-banner">
      <div class="t">Save your music</div>
      <div class="s">Sign in to save playlists & sync favorites across devices.</div>
      <button onclick="openAuth('signin')">Sign In / Sign Up</button>
    </div>`;
  }

  // Playlists
  if(loggedIn){
    html += `<div class="section">
      <div class="section-head">
        <div class="section-title">Playlists</div>
        <button class="section-add" onclick="openCreatePlaylist()">+</button>
      </div>`;
    if(!state.playlists.length){
      html += `<div class="empty" style="padding:30px 24px;">
        <div class="title">No playlists yet</div>
        <div class="sub">Tap + to create one.</div></div>`;
    }else{
      html += `<div class="track-list">${state.playlists.map(p=>`
        <div class="playlist-row" onclick="openPlaylistView(${p.id})">
          <div class="playlist-icon">♪</div>
          <div class="meta">
            <div class="name">${esc(p.name)}</div>
            <div class="count">${(p.songs||[]).length} ${(p.songs||[]).length===1?'song':'songs'}</div>
          </div>
        </div>`).join('')}</div>`;
    }
    html += `</div>`;
  }

  // Favorites
  html += `<div class="section">
    <div class="section-head"><div class="section-title">Favorites</div></div>`;
  if(!state.favorites.length){
    html += `<div class="empty" style="padding:30px 24px;">
      <div class="title">No favorites yet</div>
      <div class="sub">Tap the heart on any song.</div></div>`;
  }else{
    html += `<div class="track-list">${state.favorites.map(cardTrack).join('')}</div>`;
  }
  html += `</div>`;

  main.innerHTML = html;
}

function renderPlaylistDetail(){
  const p = state.librarySubView;
  let html = `<div class="page-header" style="justify-content:flex-start;gap:12px;">
    <button class="page-action" onclick="closePlaylistView()" style="font-size:22px;">‹</button>
    <div class="page-title" style="font-size:22px;flex:1;min-width:0;
      white-space:nowrap;overflow:hidden;text-overflow:ellipsis;">${esc(p.name)}</div>
    <button class="page-action" onclick="deletePlaylist(${p.id})"
      style="background:transparent;color:var(--accent);">🗑</button>
  </div>`;
  if(!p.songs || !p.songs.length){
    html += `<div class="empty"><div class="big">♪</div>
      <div class="title">Empty playlist</div>
      <div class="sub">Add songs from the ⋯ menu on any track.</div></div>`;
  }else{
    html += `<div class="track-list">${p.songs.map(s=>cardPlaylistTrack(s, p.id)).join('')}</div>`;
  }
  main.innerHTML = html;
}

/* ==========================================================
   QUEUE
   ========================================================== */
function renderQueueTab(){
  let html = `<div class="page-header"><div class="page-title">Up Next</div></div>`;
  if(!state.queue.length){
    html += `<div class="empty"><div class="big">☰</div>
      <div class="title">Queue is empty</div>
      <div class="sub">Songs you play will appear here.</div></div>`;
  }else{
    html += `<div class="track-list">${state.queue.map((s,i)=>cardQueue(s,i)).join('')}</div>`;
  }
  main.innerHTML = html;
}
function cardQueue(song, i){
  const playing = state.currentSong && state.currentSong.id===song.id;
  return `<div class="track ${playing?'playing':''}" onclick="playQueueIndex(${i})">
    <img class="art" src="${esc(song.image||PLACEHOLDER)}" onerror="this.src='${PLACEHOLDER}'">
    <div class="meta">
      <div class="name">${esc(song.title)}</div>
      <div class="artist">${esc(artistOf(song))}</div>
    </div>
    <button class="more-btn" onclick="event.stopPropagation();openActionSheetFor('${esc(song.id)}')">⋯</button>
  </div>`;
}

/* ==========================================================
   QUEUE OPS
   ========================================================== */
function addToQueueById(id){
  const song = findSong(id);
  if(!song) return;
  if(state.queue.some(q=>q.id===id)){ toast('Already in queue'); return; }
  state.queue.push(song);
  toast('Added to queue');
  if(state.tab==='queue') renderQueueTab();
  if(!state.currentSong) playSongById(id);
}

/* ==========================================================
   PLAYBACK
   ========================================================== */
function playSongById(id){
  const song = findSong(id);
  if(!song) return;
  state.currentSong = song;
  if(!state.queue.some(q=>q.id===song.id)) state.queue.push(song);
  const url = playableUrl(song);
  if(!url){ toast('No playable URL'); return; }
  audio.src = url;
  audio.play().then(()=>{ state.isPlaying=true; updatePlayButtons(); })
    .catch(()=>{ state.isPlaying=false; updatePlayButtons(); toast('Playback failed'); });
  updateNowPlayingUI();
  renderTab();
}
function playQueueIndex(i){
  const song = state.queue[i];
  if(!song) return;
  state.currentSong = song;
  const url = playableUrl(song);
  if(!url){ toast('No playable URL'); return; }
  audio.src = url;
  audio.play().then(()=>{ state.isPlaying=true; updatePlayButtons(); })
    .catch(()=>{ state.isPlaying=false; updatePlayButtons(); });
  updateNowPlayingUI();
  renderTab();
}
function togglePlay(){
  if(!audio.src){
    if(state.queue.length){ playQueueIndex(0); return; }
    toast('Nothing to play'); return;
  }
  if(state.isPlaying){ audio.pause(); state.isPlaying=false; }
  else{ audio.play().then(()=>{ state.isPlaying=true; updatePlayButtons(); }).catch(()=>{}); }
  updatePlayButtons();
}
function playNext(){
  if(!state.currentSong) return;
  const idx = state.queue.findIndex(q=>q.id===state.currentSong.id);
  if(idx>-1 && idx<state.queue.length-1) playQueueIndex(idx+1);
}
function playPrev(){
  if(!state.currentSong) return;
  const idx = state.queue.findIndex(q=>q.id===state.currentSong.id);
  if(idx>0) playQueueIndex(idx-1);
}
function updatePlayButtons(){
  const icon = state.isPlaying ? '⏸' : '▶';
  document.getElementById('miniPlayBtn').textContent = icon;
  document.getElementById('fullPlayBtn').textContent = icon;
}
function updateNowPlayingUI(){
  const song = state.currentSong;
  const mini = document.getElementById('miniPlayer');
  if(!song){ mini.classList.remove('show'); return; }
  document.getElementById('miniArt').src = song.image || PLACEHOLDER;
  document.getElementById('miniName').textContent = song.title || '-';
  document.getElementById('miniArtist').textContent = artistOf(song) || '-';
  document.getElementById('fullArt').src = song.image || PLACEHOLDER;
  document.getElementById('fullName').textContent = song.title || '-';
  document.getElementById('fullArtist').textContent = artistOf(song) || '-';
  mini.classList.add('show');
  updateFavIcon();
  updatePlayButtons();
}

/* ==========================================================
   FULL PLAYER
   ========================================================== */
function openFullPlayer(){
  if(!state.currentSong) return;
  document.getElementById('fullPlayer').classList.add('show');
  updateNowPlayingUI();
}
function closeFullPlayer(){
  document.getElementById('fullPlayer').classList.remove('show');
}
function seekAudio(e){
  const track = e.currentTarget;
  const rect = track.getBoundingClientRect();
  const x = (e.touches ? e.touches[0].clientX : e.clientX) - rect.left;
  const pct = Math.max(0, Math.min(1, x/rect.width));
  if(audio.duration) audio.currentTime = pct * audio.duration;
}

/* ==========================================================
   ACTION SHEET
   ========================================================== */
let sheetSong = null;

function openActionSheetFor(id){
  const song = findSong(id);
  if(!song) return;
  sheetSong = song;
  document.getElementById('sheetTitle').textContent = song.title || '-';
  document.getElementById('sheetSub').textContent = artistOf(song);
  buildActionSheet(song);
  document.getElementById('sheetBackdrop').classList.add('show');
  document.getElementById('actionSheet').classList.add('show');
}
function openActionSheetCurrent(){
  if(state.currentSong) openActionSheetFor(state.currentSong.id);
}
function buildActionSheet(song){
  const urls = song.download_urls || {};
  const fav = isFav(song.id);
  const parts = [];

  parts.push(`<button class="sheet-btn" onclick="sheetAction('play')"><span class="ico">▶</span>Play</button>`);
  parts.push(`<button class="sheet-btn" onclick="sheetAction('queue')"><span class="ico">＋</span>Add to Queue</button>`);

  if(state.auth.user){
    parts.push(`<button class="sheet-btn" onclick="sheetAction('playlist')"><span class="ico">♪</span>Add to Playlist</button>`);
  }else{
    parts.push(`<button class="sheet-btn" onclick="openAuth()"><span class="ico">♪</span>Sign in to add to Playlist</button>`);
  }

  parts.push(`<button class="sheet-btn" onclick="sheetAction('fav')"><span class="ico">${fav?'♥':'♡'}</span>${fav?'Remove from Favorites':'Add to Favorites'}</button>`);

  if(urls['320']) parts.push(`<button class="sheet-btn" onclick="sheetAction('dl320')"><span class="ico">⬇</span>Download 320kbps</button>`);
  if(urls['160']) parts.push(`<button class="sheet-btn" onclick="sheetAction('dl160')"><span class="ico">⬇</span>Download 160kbps</button>`);

  // Playlist detail view me remove option
  if(state.librarySubView && state.librarySubView.type==='playlist'){
    parts.push(`<button class="sheet-btn danger" onclick="sheetAction('removeFromPlaylist')"><span class="ico">✕</span>Remove from Playlist</button>`);
  }

  document.getElementById('sheetActions').innerHTML = parts.join('');
}

function buildPlaylistPicker(song){
  if(!state.auth.user){ openAuth(); closeActionSheet(); return; }
  const parts = [];
  if(state.playlists.length){
    parts.push(`<div class="sheet-sub-header">Add to Playlist</div>`);
    state.playlists.forEach(p=>{
      const already = (p.songs||[]).some(s=>s.id===song.id);
      parts.push(`<button class="sheet-btn" onclick="pickPlaylist(${p.id})" ${already?'style="opacity:0.5"':''}>
        <span class="ico">♪</span>${esc(p.name)}${already?' (added)':''}</button>`);
    });
  }
  parts.push(`<button class="sheet-btn" onclick="pickNewPlaylist()"><span class="ico">＋</span>New Playlist</button>`);
  document.getElementById('sheetActions').innerHTML = parts.join('');
}
function pickPlaylist(pid){
  if(!sheetSong) return;
  const p = state.playlists.find(x=>x.id===pid);
  if(p && (p.songs||[]).some(s=>s.id===sheetSong.id)){
    toast('Already in "'+p.name+'"'); closeActionSheet(); return;
  }
  const s = sheetSong;
  addSongToPlaylist(pid, s);
  closeActionSheet();
}
function pickNewPlaylist(){
  const s = sheetSong;
  closeActionSheet();
  setTimeout(()=>openCreatePlaylist(s), 250);
}

function sheetAction(kind){
  const song = sheetSong;
  if(!song){ closeActionSheet(); return; }
  const id = song.id;

  if(kind==='play') playSongById(id);
  else if(kind==='queue') addToQueueById(id);
  else if(kind==='fav') toggleFavById(id);
  else if(kind==='playlist'){ buildPlaylistPicker(song); return; }
  else if(kind==='removeFromPlaylist'){
    if(state.librarySubView && state.librarySubView.type==='playlist'){
      removeSongFromPlaylist(state.librarySubView.id, id);
    }
  }
  else if(kind==='dl320' || kind==='dl160'){
    const u = song.download_urls || {};
    const url = kind==='dl320' ? u['320'] : u['160'];
    if(url) triggerDownload(url, song);
  }
  closeActionSheet();
}
function closeActionSheet(){
  document.getElementById('sheetBackdrop').classList.remove('show');
  document.getElementById('actionSheet').classList.remove('show');
  sheetSong = null;
}
function triggerDownload(url, song){
  const dlUrl = '/api/dl?url='+encodeURIComponent(url)
    +'&title='+encodeURIComponent(song.title||'')
    +'&artist='+encodeURIComponent(artistOf(song))
    +'&image='+encodeURIComponent(song.image||'');
  toast('Download started');
  window.location.href = dlUrl;
}

/* ==========================================================
   AUDIO EVENTS
   ========================================================== */
audio.addEventListener('timeupdate', ()=>{
  const curr = audio.currentTime;
  const dur = audio.duration || 0;
  document.getElementById('fullCurr').textContent = fmtTime(curr);
  document.getElementById('fullDur').textContent = fmtTime(dur);
  if(dur>0) document.getElementById('fullProgress').style.width = (curr/dur*100)+'%';
});
audio.addEventListener('play', ()=>{ state.isPlaying=true; updatePlayButtons(); });
audio.addEventListener('pause', ()=>{ state.isPlaying=false; updatePlayButtons(); });
audio.addEventListener('ended', playNext);

/* ==========================================================
   BOOTSTRAP
   ========================================================== */
async function bootstrap(){
  // Guest favourites pehle load karo
  state.favorites = JSON.parse(localStorage.getItem('musicFavs')||'[]');

  // Token check
  if(state.auth.token){
    try{
      const res = await fetch('/api/auth/me',{headers:authHeaders()});
      if(res.ok){
        state.auth.user = await res.json();
        await loadFavoritesFromServer();
        await loadPlaylistsFromServer();
      }else{
        state.auth.token = null; state.auth.user = null;
        localStorage.removeItem('musicAuthToken');
      }
    }catch(e){}
  }

  renderTab();
  loadHomeData();
  if(state.currentSong) updateNowPlayingUI();
}

window.addEventListener('load', bootstrap);
</script>
</body>
</html>
"""


@app.get("/", response_class=HTMLResponse)
def home():
    return HTML_PAGE


@app.get("/health")
def health():
    return {"status": "ok"}
