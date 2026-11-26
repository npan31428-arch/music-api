import os
import requests
from fastapi import FastAPI, Query, HTTPException
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.middleware.cors import CORSMiddleware

app = FastAPI(title="Pro Music API")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

UPSTREAM = "https://music-downoader-api.froxtdevil.workers.dev/search"

@app.get("/api/search")
def search(song: str = Query(..., description="Song name")):
    try:
        r = requests.get(UPSTREAM, params={"song": song}, timeout=30)
        r.raise_for_status()
        return r.json()
    except Exception as e:
        raise HTTPException(status_code=502, detail=f"Upstream error: {e}")

# PRO PLAYER HTML/CSS/JS
HTML_PAGE = """
<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>🎵 Pro Music Player</title>
<style>
  :root {
    --bg: #0f172a; --surface: #1e293b; --primary: #6366f1; --primary-hover: #4f46e5;
    --text: #f8fafc; --text-muted: #94a3b8; --danger: #ef4444;
  }
  *{box-sizing:border-box; margin:0; padding:0; font-family:'Segoe UI', Tahoma, Geneva, Verdana, sans-serif;}
  body{background:var(--bg); color:var(--text); height:100vh; display:flex; flex-direction:column; overflow:hidden;}
  
  /* Layout */
  .header{padding:15px 30px; background:var(--surface); display:flex; gap:20px; align-items:center; box-shadow:0 4px 6px rgba(0,0,0,0.3); z-index:10;}
  .header h1{font-size:1.5rem; color:var(--primary); white-space:nowrap;}
  .search-box{flex:1; display:flex; gap:10px; max-width:600px;}
  .search-box input{flex:1; padding:12px; border-radius:8px; border:1px solid #334155; background:var(--bg); color:white; outline:none;}
  .search-box input:focus{border-color:var(--primary);}
  .search-box button{padding:12px 24px; border-radius:8px; border:none; background:var(--primary); color:white; font-weight:bold; cursor:pointer; transition:0.2s;}
  .search-box button:hover{background:var(--primary-hover);}
  
  .main-content{flex:1; display:flex; overflow:hidden; padding-bottom:90px;}
  .results-section{flex:2; padding:20px; overflow-y:auto;}
  .queue-section{flex:1; padding:20px; background:var(--surface); border-left:1px solid #334155; display:flex; flex-direction:column;}
  
  /* Lists */
  .section-title{font-size:1.2rem; margin-bottom:15px; color:var(--text-muted); border-bottom:1px solid #334155; padding-bottom:10px;}
  .song-card{display:flex; align-items:center; gap:15px; padding:10px; border-radius:8px; margin-bottom:10px; background:rgba(255,255,255,0.03); transition:0.2s;}
  .song-card:hover{background:rgba(255,255,255,0.08);}
  .song-card img{width:60px; height:60px; border-radius:6px; object-fit:cover;}
  .song-info{flex:1; min-width:0;}
  .song-title{font-weight:bold; font-size:1rem; white-space:nowrap; overflow:hidden; text-overflow:ellipsis;}
  .song-meta{font-size:0.85rem; color:var(--text-muted); white-space:nowrap; overflow:hidden; text-overflow:ellipsis;}
  .btn-icon{background:var(--primary); border:none; color:white; padding:8px 12px; border-radius:6px; cursor:pointer; font-size:1.2rem; transition:0.2s;}
  .btn-icon:hover{background:var(--primary-hover); transform:scale(1.05);}
  .btn-queue{background:transparent; border:1px solid var(--text-muted); color:var(--text-muted);}
  .btn-queue:hover{background:var(--text-muted); color:var(--bg);}
  
  /* Player Bar */
  .player-bar{position:fixed; bottom:0; left:0; right:0; height:90px; background:var(--surface); display:flex; align-items:center; justify-content:space-between; padding:0 30px; box-shadow:0 -4px 10px rgba(0,0,0,0.5); border-top:1px solid #334155;}
  .now-playing{display:flex; align-items:center; gap:15px; width:30%;}
  .now-playing img{width:60px; height:60px; border-radius:8px; object-fit:cover; box-shadow:0 4px 8px rgba(0,0,0,0.3);}
  .player-controls{display:flex; flex-direction:column; align-items:center; flex:1;}
  .controls-btns{display:flex; gap:20px; align-items:center; margin-bottom:10px;}
  .controls-btns button{background:none; border:none; color:white; font-size:1.5rem; cursor:pointer;}
  .controls-btns .play-btn{font-size:2.2rem; color:var(--primary);}
  .progress-container{width:50%; display:flex; align-items:center; gap:10px; font-size:0.8rem; color:var(--text-muted);}
  .progress-bar{flex:1; height:5px; background:#334155; border-radius:3px; cursor:pointer; position:relative;}
  .progress-fill{height:100%; background:var(--primary); width:0%; border-radius:3px; transition:0.1s;}
  .volume-control{width:20%; display:flex; justify-content:flex-end; align-items:center; gap:10px;}
  .volume-control input{width:100px; accent-color:var(--primary);}
  
  /* Equalizer Modal */
  .eq-modal{display:none; position:fixed; top:50%; left:50%; transform:translate(-50%,-50%); background:var(--surface); padding:30px; border-radius:12px; box-shadow:0 10px 30px rgba(0,0,0,0.8); z-index:100; border:1px solid #334155;}
  .eq-modal.active{display:flex; gap:20px; flex-direction:column; align-items:center;}
  .eq-bands{display:flex; gap:20px; height:150px; align-items:flex-end;}
  .eq-band{display:flex; flex-direction:column; align-items:center; gap:10px;}
  .eq-band input[type=range]{writing-mode:bt-lr; -webkit-appearance:slider-vertical; width:10px; height:120px; background:#334155; outline:none; border-radius:5px;}
  .eq-close{position:absolute; top:10px; right:15px; background:none; border:none; color:white; font-size:1.5rem; cursor:pointer;}
  
  /* Scrollbar */
  ::-webkit-scrollbar{width:8px;}
  ::-webkit-scrollbar-track{background:var(--bg);}
  ::-webkit-scrollbar-thumb{background:#475569; border-radius:4px;}
  ::-webkit-scrollbar-thumb:hover{background:var(--primary);}
  
  @media (max-width: 768px) {
    .main-content{flex-direction:column;}
    .queue-section{display:none;}
    .volume-control{display:none;}
    .now-playing{width:40%;}
    .player-bar{padding:0 15px;}
  }
</style>
</head>
<body>

<div class="header">
  <h1>🎵 Pro Music</h1>
  <form class="search-box" onsubmit="doSearch(event)">
    <input id="q" placeholder="Search songs..." autofocus>
    <button type="submit" id="searchBtn">Search</button>
  </form>
  <button class="btn-icon" onclick="toggleEQ()" title="Equalizer">🎛️ EQ</button>
</div>

<div class="main-content">
  <div class="results-section">
    <div class="section-title" id="resultsTitle">Search Results</div>
    <div id="results"></div>
  </div>
  <div class="queue-section">
    <div class="section-title" style="display:flex; justify-content:space-between;">
      <span>Up Next (Queue)</span>
      <button style="background:none;border:none;color:var(--danger);cursor:pointer;font-size:0.8rem;" onclick="clearQueue()">Clear</button>
    </div>
    <div id="queueList" style="flex:1; overflow-y:auto;"></div>
  </div>
</div>

<!-- Player Bar -->
<div class="player-bar">
  <div class="now-playing">
    <img id="playerImg" src="https://via.placeholder.com/60?text=Music" alt="Cover">
    <div class="song-info">
      <div class="song-title" id="playerTitle">Select a song</div>
      <div class="song-meta" id="playerArtist">-</div>
    </div>
  </div>
  
  <div class="player-controls">
    <div class="controls-btns">
      <button onclick="playPrev()">⏮️</button>
      <button class="play-btn" id="playPauseBtn" onclick="togglePlay()">▶️</button>
      <button onclick="playNext()">⏭️</button>
    </div>
    <div class="progress-container">
      <span id="currTime">0:00</span>
      <div class="progress-bar" onclick="seekAudio(event)">
        <div class="progress-fill" id="progressFill"></div>
      </div>
      <span id="totalTime">0:00</span>
    </div>
  </div>

  <div class="volume-control">
    <span>🔊</span>
    <input type="range" id="volumeSlider" min="0" max="1" step="0.01" value="1" onchange="changeVolume(this.value)">
  </div>
</div>

<!-- Equalizer Modal -->
<div class="eq-modal" id="eqModal">
  <button class="eq-close" onclick="toggleEQ()">×</button>
  <h3>5-Band Equalizer</h3>
  <p style="font-size:0.8rem;color:#94a3b8;text-align:center;">*If audio stops, disable EQ due to CORS limits.</p>
  <div class="eq-bands">
    <div class="eq-band"><input type="range" id="eq60" min="-15" max="15" value="0" oninput="updateEQ(0, this.value)"><span>60Hz</span></div>
    <div class="eq-band"><input type="range" id="eq230" min="-15" max="15" value="0" oninput="updateEQ(1, this.value)"><span>230Hz</span></div>
    <div class="eq-band"><input type="range" id="eq910" min="-15" max="15" value="0" oninput="updateEQ(2, this.value)"><span>910Hz</span></div>
    <div class="eq-band"><input type="range" id="eq3k" min="-15" max="15" value="0" oninput="updateEQ(3, this.value)"><span>3kHz</span></div>
    <div class="eq-band"><input type="range" id="eq14k" min="-15" max="15" value="0" oninput="updateEQ(4, this.value)"><span>14kHz</span></div>
  </div>
  <button style="background:var(--primary);color:white;border:none;padding:8px 16px;border-radius:6px;cursor:pointer;" onclick="resetEQ()">Reset EQ</button>
</div>

<!-- Hidden Audio Element -->
<audio id="audioPlayer"></audio>

<script>
  // --- State Management ---
  let searchResults = [];
  let queue = [];
  let currentIndex = -1;
  let isPlaying = false;
  const audio = document.getElementById('audioPlayer');

  // --- Web Audio API (Equalizer) ---
  let audioCtx, source, filters = [];
  const eqFrequencies = [60, 230, 910, 3000, 14000];
  let isEQEnabled = false;

  function initEQ() {
    if (audioCtx) return;
    try {
      const AudioContext = window.AudioContext || window.webkitAudioContext;
      audioCtx = new AudioContext();
      source = audioCtx.createMediaElementSource(audio);
      
      let prevNode = source;
      eqFrequencies.forEach(freq => {
        const filter = audioCtx.createBiquadFilter();
        filter.type = 'peaking';
        filter.frequency.value = freq;
        filter.Q.value = 1;
        filter.gain.value = 0;
        prevNode.connect(filter);
        prevNode = filter;
        filters.push(filter);
      });
      prevNode.connect(audioCtx.destination);
    } catch(e) {
      console.log("EQ Error: CORS might block Web Audio API");
    }
  }

  function toggleEQ() {
    document.getElementById('eqModal').classList.toggle('active');
    if (!isEQEnabled) {
      initEQ();
      isEQEnabled = true;
      if (audioCtx) audioCtx.resume();
    }
  }

  function updateEQ(index, value) {
    if (filters[index]) filters[index].gain.value = parseFloat(value);
  }

  function resetEQ() {
    const ids = ['eq60', 'eq230', 'eq910', 'eq3k', 'eq14k'];
    ids.forEach((id, i) => {
      document.getElementById(id).value = 0;
      updateEQ(i, 0);
    });
  }

  // --- Search Functionality ---
  async function doSearch(e) {
    e.preventDefault();
    const query = document.getElementById('q').value.trim();
    if (!query) return;
    
    document.getElementById('resultsTitle').innerText = 'Searching...';
    document.getElementById('results').innerHTML = '';
    document.getElementById('searchBtn').disabled = true;

    try {
      const res = await fetch('/api/search?song=' + encodeURIComponent(query));
      const data = await res.json();
      
      if (!res.ok) throw new Error(data.detail || 'Error');
      
      searchResults = data.results || [];
      document.getElementById('resultsTitle').innerText = `Results (${data.total || searchResults.length})`;
      renderResults(searchResults);
    } catch (err) {
      document.getElementById('resultsTitle').innerText = 'Error!';
      document.getElementById('results').innerHTML = `<p style="color:var(--danger)">${err.message}</p>`;
    } finally {
      document.getElementById('searchBtn').disabled = false;
    }
  }

  function renderResults(songs) {
    const container = document.getElementById('results');
    container.innerHTML = songs.map((s, i) => `
      <div class="song-card">
        <img src="${s.image || ''}" onerror="this.style.display='none'">
        <div class="song-info">
          <div class="song-title">${s.title}</div>
          <div class="song-meta">${s.subtitle || ''}</div>
        </div>
        <button class="btn-icon" onclick="playFromSearch(${i})">▶</button>
        <button class="btn-icon btn-queue" onclick="addToQueue(${i})">+ Queue</button>
      </div>
    `).join('');
  }

  // --- Queue Management ---
  function renderQueue() {
    const container = document.getElementById('queueList');
    if (queue.length === 0) {
      container.innerHTML = '<p style="color:var(--text-muted);font-size:0.9rem;text-align:center;margin-top:20px;">Queue is empty</p>';
      return;
    }
    container.innerHTML = queue.map((s, i) => `
      <div class="song-card" style="${i === currentIndex ? 'border:1px solid var(--primary)' : ''}">
        <img src="${s.image || ''}" style="width:40px;height:40px;">
        <div class="song-info">
          <div class="song-title" style="font-size:0.9rem;">${s.title}</div>
        </div>
        <button class="btn-icon" style="font-size:0.8rem;padding:4px 8px;background:var(--danger)" onclick="removeFromQueue(${i})">×</button>
      </div>
    `).join('');
  }

  function addToQueue(index) {
    queue.push(searchResults[index]);
    renderQueue();
    if (currentIndex === -1) {
      // Auto-start if nothing is playing
      currentIndex = 0;
      playSong(queue[0]);
    }
  }

  function removeFromQueue(index) {
    queue.splice(index, 1);
    if (index === currentIndex) {
      currentIndex = Math.min(currentIndex, queue.length - 1);
      if (queue.length > 0) playSong(queue[currentIndex]);
      else stopPlayer();
    } else if (index < currentIndex) {
      currentIndex--;
    }
    renderQueue();
  }

  function clearQueue() {
    queue = [];
    currentIndex = -1;
    renderQueue();
    stopPlayer();
  }

  // --- Player Controls ---
  function playFromSearch(index) {
    const song = searchResults[index];
    // Add all search results below this to queue if queue is empty
    if (queue.length === 0) {
      queue = searchResults.slice(index);
      currentIndex = 0;
    } else {
      queue.push(song);
      currentIndex = queue.length - 1;
    }
    renderQueue();
    playSong(song);
  }

  function playSong(song) {
    if (!song) return;
    document.getElementById('playerImg').src = song.image || '';
    document.getElementById('playerTitle').innerText = song.title;
    document.getElementById('playerArtist').innerText = song.subtitle || '';
    
    // Use 320kbps by default
    const url = song.download_urls['320'] || song.download_url;
    audio.src = url;
    audio.play().then(() => {
      isPlaying = true;
      document.getElementById('playPauseBtn').innerText = '⏸️';
    }).catch(e => console.log("Playback failed:", e));
  }

  function stopPlayer() {
    audio.pause();
    audio.src = '';
    isPlaying = false;
    document.getElementById('playPauseBtn').innerText = '▶️';
    document.getElementById('playerTitle').innerText = 'Select a song';
    document.getElementById('playerArtist').innerText = '-';
    document.getElementById('playerImg').src = 'https://via.placeholder.com/60?text=Music';
    document.getElementById('progressFill').style.width = '0%';
    document.getElementById('currTime').innerText = '0:00';
    document.getElementById('totalTime').innerText = '0:00';
  }

  function togglePlay() {
    if (!audio.src) return;
    if (isPlaying) {
      audio.pause();
      document.getElementById('playPauseBtn').innerText = '▶️';
    } else {
      audio.play();
      document.getElementById('playPauseBtn').innerText = '⏸️';
    }
    isPlaying = !isPlaying;
  }

  function playNext() {
    if (currentIndex < queue.length - 1) {
      currentIndex++;
      playSong(queue[currentIndex]);
      renderQueue();
    }
  }

  function playPrev() {
    if (currentIndex > 0) {
      currentIndex--;
      playSong(queue[currentIndex]);
      renderQueue();
    }
  }

  // --- Audio Events ---
  audio.addEventListener('timeupdate', () => {
    const curr = audio.currentTime;
    const dur = audio.duration || 0;
    if (dur > 0) {
      document.getElementById('progressFill').style.width = (curr / dur) * 100 + '%';
      document.getElementById('currTime').innerText = formatTime(curr);
      document.getElementById('totalTime').innerText = formatTime(dur);
    }
  });

  audio.addEventListener('ended', () => {
    playNext();
  });

  function seekAudio(e) {
    const bar = e.currentTarget;
    const percent = e.offsetX / bar.offsetWidth;
    if (audio.duration) audio.currentTime = percent * audio.duration;
  }

  function changeVolume(val) {
    audio.volume = val;
  }

  function formatTime(seconds) {
    const m = Math.floor(seconds / 60);
    const s = Math.floor(seconds % 60);
    return `${m}:${s < 10 ? '0' : ''}${s}`;
  }

  // Initialize empty queue on load
  renderQueue();
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
