"""
AI Agent Saham Kuantitatif (ala Jarvis) — pilih karakter: SUHU · MISS MINUTES · IRONMAN · JOI
=============================================================================================
Halaman Streamlit (taruh di folder `pages/`, atau jalankan langsung:
    streamlit run 3___SUHU_AI_Agent.py )

Fitur:
  - Halaman PILIH KARAKTER: 4 avatar beranimasi dengan latar berbeda. Nama AI = nama karakter
    (juga kata panggilnya / wake word). IRONMAN & JOI tampil sebagai hologram di latar hitam gelap.
  - Avatar animasi + HUD ala Jarvis, bereaksi bullish/bearish
  - Perintah suara (Web Speech API, Chrome/Edge) + wake word "Suhu" + ketik manual
  - Suara robot anak-anak (SpeechSynthesis pitch tinggi + efek beep robot)
  - Screening saham, analisa lengkap (QVTA + sistem skor + bandarmology)
  - Prediksi Monte Carlo (filtered historical simulation) + probabilitas TP/SL
  - Rekomendasi zona beli / jual (stop loss, TP1-3, trailing stop, ukuran posisi, tick IDX)
  - Walk-forward hit-rate sinyal + backtest strategi kuantitatif
  - Auto-pilot PAPER TRADING (simulasi, tidak mengirim order ke broker sungguhan)

Data: 100% gratis via yfinance (Yahoo Finance). Tanpa API key.
Opsional: ANTHROPIC_API_KEY untuk narasi AI tambahan.

Letakkan SUHU.png, MISS_MINUTES.png, IRONMAN.png, JOI.png di folder yang sama / folder induk / folder assets.
"""

import os
import re
import json
import math
import html as htmllib
import shutil
import tempfile
from pathlib import Path

import numpy as np
import pandas as pd
import streamlit as st
import streamlit.components.v1 as components
import plotly.graph_objects as go
from plotly.subplots import make_subplots
import yfinance as yf
from scipy import stats

st.set_page_config(page_title="SUHU — AI Agent Saham", page_icon="🤖", layout="wide",
                   initial_sidebar_state="collapsed")

# ---- GERBANG AKSES (paywall): tanpa Access Key, hanya homepage yang tampil ----
from gate import require_access, sidebar_account
ACCESS = require_access()
IS_ADMIN = ACCESS["role"] == "admin"

st.markdown("""
<style>
@import url('https://fonts.googleapis.com/css2?family=Syne:wght@700;800&family=DM+Sans:wght@400;500;700&display=swap');
.stApp { background: linear-gradient(180deg, #c3ddff 0%, #e7f0ff 45%, #ffffff 100%); }
html, body, [class*="st-at"] { font-family: 'DM Sans', sans-serif; }
.page-title { font-size: 2.4rem; font-weight: 800; color: #0a2540; margin-bottom: 2px; }
.page-sub { color: #476684; font-size: 1.05rem; margin-bottom: 18px; }
.score-card { background: white; padding: 16px; border-radius: 18px; box-shadow: 0 8px 30px rgba(0,0,0,0.05);
              text-align: center; height: 100%; }
.score-card small { color:#6b7f95; font-weight:600; letter-spacing:.4px; }
.score-card h2 { margin: 4px 0 0 0; font-size: 1.55rem; color:#0a2540; }
.verdict-box { background: white; border-left: 6px solid #0077C8; border-radius: 16px; padding: 20px 26px;
               box-shadow: 0 8px 30px rgba(0,0,0,0.05); line-height: 1.7; }
.signal-chip { display: inline-block; background: #eef6ff; color: #0a2540; font-size: 0.85rem;
               padding: 6px 14px; border-radius: 20px; margin: 4px 6px 4px 0; }
.chatbox { background:#ffffffcc; border-radius:16px; padding:10px 12px; max-height:260px; overflow-y:auto;
           box-shadow: 0 6px 20px rgba(0,0,0,0.05); margin-top:10px; font-size:.92rem; }
.msg-u { text-align:right; margin:6px 0; } .msg-u span { background:#0077C8; color:#fff; padding:6px 12px; border-radius:14px 14px 2px 14px; display:inline-block; }
.msg-s { text-align:left; margin:6px 0; } .msg-s span { background:#eef6ff; color:#0a2540; padding:6px 12px; border-radius:14px 14px 14px 2px; display:inline-block; }
footer { visibility: hidden; }
@media (max-width: 640px) {
  .block-container { padding: 1rem .75rem 5rem !important; }
  .page-title { font-size: 1.55rem; } .page-sub { font-size: .92rem; margin-bottom: 10px; }
  .score-card { padding: 10px; border-radius: 14px; } .score-card h2 { font-size: 1.2rem; }
  .verdict-box { padding: 14px 16px; line-height: 1.55; } .signal-chip { font-size: .78rem; padding: 5px 10px; }
  .chatbox { max-height: 200px; }
  div[data-testid="stTabs"] button { padding: 6px 8px; font-size: .85rem; }
}
</style>
""", unsafe_allow_html=True)

# =========================================================
# KARAKTER AVATAR (nama panggilan AI = nama karakter)
# =========================================================
CHAR_ORDER = ["suhu", "miss", "ironman", "joi"]

CHARACTERS = {
    "suhu": dict(
        name="SUHU", spoken="Suhu", emoji="🤖", files=["SUHU.png", "astro.png"],
        tagline="Robot kecil periang", holo=False, avh=300,
        desc="Robot cilik berdasi kupu-kupu yang hobi menghitung saham.",
        pitch=1.8, rate=1.1, robot=True,
        wake=r"(suhu|su hu|suho|sufu|sohu|souhu|su-hu)",
        page_bg="linear-gradient(180deg, #c3ddff 0%, #e7f0ff 45%, #ffffff 100%)",
        theme=dict(bg="radial-gradient(circle at 50% 40%,#1a5a9c 0%,#0a2540 62%,#06182c 100%)",
                   acc="#00e5ff", acc2="#7df9ff", heard="#9fdcff", accA="rgba(125,249,255,.35)",
                   accA2="rgba(0,229,255,.07)", btn1="#00b4ff", btn2="#0077C8",
                   capbg="rgba(255,255,255,.10)", onfg="#06182c"),
        tricks=["hop", "wiggle", "spin", "tilt"],
        lines=dict(
            greet="Halo! Aku {s}, asisten saham kuantitatifmu. Mau analisa saham apa hari ini?",
            who="Aku {s}, robot kecil yang hobi menghitung saham. Aku bisa skrining, analisa, prediksi Monte Carlo, dan rekomendasi harga beli jual!",
            thanks="Sama-sama! Senang bisa membantu. Jangan lupa pasang stop loss ya!",
            ready="Ya, aku di sini! Mau apa?",
            demo="Hai, Rio ganteng! Aku {s}, asisten sahammu!",
            intro_speech="Halo! Aku {s}, asisten sahammu. Klik mikrofon, lalu bilang: {s}, analisa B B C A!",
            intro_cap="Halo! Aku SUHU 🤖 Klik mikrofon atau ketik perintah, mis. 'analisa BBCA'.",
        )),
    "miss": dict(
        name="MISS MINUTES", spoken="Miss Minits", emoji="⏱️", files=["MISS_MINUTES.png", "MISS MINUTES.png", "MISS_MINUTES.PNG"],
        tagline="Penjaga waktu yang ceria", holo=False, avh=300,
        desc="Jam kecil yang selalu tahu kapan waktu terbaik untuk beli dan jual.",
        pitch=1.5, rate=1.1, robot=False,
        wake=r"(miss ?minutes?|mis ?minutes?|miss ?minits?|mis ?minits?|miss ?menit|mis ?menit)",
        page_bg="linear-gradient(180deg, #ffe2a8 0%, #fff0d2 45%, #ffffff 100%)",
        theme=dict(bg="radial-gradient(circle at 50% 38%,#ffd873 0%,#f4a034 42%,#b4520f 85%,#7a3208 100%)",
                   acc="#fff1c1", acc2="#ffffff", heard="#fff3cf", accA="rgba(255,241,193,.55)",
                   accA2="rgba(255,255,255,.08)", btn1="#ff9d2e", btn2="#d9560b",
                   capbg="rgba(70,25,0,.42)", onfg="#4a1a0a"),
        tricks=["hop", "wiggle", "spin", "tilt"],
        lines=dict(
            greet="Halo! Aku {s}, penjaga waktu dan asisten sahammu. Waktu adalah uang! Mau analisa saham apa?",
            who="Aku {s}, jam kecil yang ceria. Aku bisa skrining, analisa, prediksi Monte Carlo, dan memilihkan waktu terbaik untuk beli dan jual!",
            thanks="Sama-sama! Ingat, waktu adalah uang. Jangan lupa pasang stop loss ya!",
            ready="Ya, aku di sini! Mau apa?",
            demo="Hai, Rio! Aku {s}, penjaga waktu pasar sahammu!",
            intro_speech="Halo! Aku {s}, penjaga waktu sahammu. Klik mikrofon, lalu bilang: {s}, analisa B B C A!",
            intro_cap="Halo! Aku MISS MINUTES ⏱️ Klik mikrofon atau ketik perintah, mis. 'analisa BBCA'.",
        )),
    "ironman": dict(
        name="IRONMAN", spoken="Iron Man", emoji="🦾", files=["IRONMAN.png", "IRON_MAN.png"],
        tagline="Hologram armor kuantitatif", holo=True, avh=310,
        desc="Hologram armor berteknologi tinggi, tenang dan presisi di setiap analisa.",
        pitch=0.7, rate=0.95, robot=True,
        wake=r"(iron ?man|ironman|airon ?men|ayron ?men|aiyen ?men|iron ?men)",
        page_bg="linear-gradient(180deg, #c9d6e0 0%, #e6edf3 45%, #ffffff 100%)",
        theme=dict(bg="radial-gradient(circle at 50% 42%,#04202c 0%,#020a10 52%,#000000 100%)",
                   acc="#00e5ff", acc2="#9ff6ff", heard="#7fe9f7", accA="rgba(0,229,255,.38)",
                   accA2="rgba(0,229,255,.05)", btn1="#00c8ff", btn2="#006c9a",
                   capbg="rgba(0,20,28,.72)", onfg="#00141c"),
        tricks=["glitch", "pulse", "tilt", "spin"],
        lines=dict(
            greet="Sistem online. Aku {s}, siap membantu analisa pasar. Saham apa yang mau kita bedah?",
            who="Aku {s}, asisten kuantitatifmu. Aku bisa skrining, analisa, prediksi Monte Carlo, dan rekomendasi harga beli jual.",
            thanks="Siap. Ingat, manajemen risiko adalah armor terbaikmu. Pasang stop loss!",
            ready="Sistem aktif. Perintahmu?",
            demo="Hai, Rio. {s} online. Semua sistem siap.",
            intro_speech="Sistem online. Aku {s}. Klik mikrofon, lalu bilang: {s}, analisa B B C A.",
            intro_cap="Sistem online. Aku IRONMAN 🦾 Klik mikrofon atau ketik perintah, mis. 'analisa BBCA'.",
        )),
    "joi": dict(
        name="JOI", spoken="Joi", emoji="💜", files=["JOI.png"],
        tagline="Hologram pendamping setia", holo=True, avh=270,
        desc="Hologram lembut yang selalu hadir menemani setiap keputusan sahammu.",
        pitch=1.25, rate=1.0, robot=False,
        wake=r"(\bjoi\b|\bjoy\b|\bjoey\b|\bjoe\b|\bjoy\w*)",
        page_bg="linear-gradient(180deg, #e3d0f5 0%, #f2e8fb 45%, #ffffff 100%)",
        theme=dict(bg="radial-gradient(circle at 50% 40%,#16062a 0%,#07030f 55%,#000000 100%)",
                   acc="#ff3fd2", acc2="#8fb0ff", heard="#e9a8ff", accA="rgba(255,63,210,.38)",
                   accA2="rgba(255,63,210,.05)", btn1="#ff3fd2", btn2="#5a3cff",
                   capbg="rgba(20,6,32,.72)", onfg="#1b0620"),
        tricks=["glitch", "pulse", "tilt", "spin"],
        lines=dict(
            greet="Hai, aku {s}. Aku di sini untukmu. Saham apa yang ingin kita lihat hari ini?",
            who="Aku {s}, asisten hologrammu. Aku bisa skrining, analisa, prediksi Monte Carlo, dan memberi rekomendasi harga beli dan jual.",
            thanks="Sama-sama. Selalu menyenangkan membantumu. Jangan lupa stop loss ya.",
            ready="Aku di sini. Apa yang kamu butuhkan?",
            demo="Hai, Rio. Aku {s}. Senang melihatmu.",
            intro_speech="Hai, aku {s}. Klik mikrofon, lalu bilang: {s}, analisa B B C A.",
            intro_cap="Hai, aku JOI 💜 Klik mikrofon atau ketik perintah, mis. 'analisa BBCA'.",
        )),
}

# =========================================================
# KOMPONEN AVATAR (HTML/JS dua arah dengan Streamlit)
# Satu template, dipakai semua karakter. Bagian khusus karakter (latar, animasi, layer)
# disisipkan dari SCENES di bawah.
# =========================================================
COMPONENT_TMPL = r"""<!DOCTYPE html>
<html><head><meta charset="utf-8">
<style>
*{box-sizing:border-box;margin:0;padding:0}
body{font-family:'Segoe UI',system-ui,sans-serif;background:transparent;overflow:hidden}
#stage{position:relative;width:100%;height:580px;border-radius:26px;overflow:hidden;color:#fff;
 background:var(--bg);box-shadow:0 10px 34px rgba(0,0,0,.22);/*__VARS__*/}
#bgfx,#bgfx *{pointer-events:none}
#bgfx{position:absolute;inset:0;z-index:1;overflow:hidden}
#topbar{position:absolute;top:12px;left:14px;right:14px;display:flex;align-items:center;gap:8px;font-size:12px;letter-spacing:1.2px;font-weight:700;z-index:5}
#led{width:10px;height:10px;border-radius:50%;background:#22c55e;box-shadow:0 0 10px #22c55e}
#stage[data-state=listen] #led{background:var(--acc);box-shadow:0 0 12px var(--acc);animation:blinkled .8s infinite}
#stage[data-state=think] #led{background:#fbbf24;box-shadow:0 0 12px #fbbf24;animation:blinkled .4s infinite}
#stage[data-state=talk] #led{background:#f472b6;box-shadow:0 0 12px #f472b6}
@keyframes blinkled{50%{opacity:.25}}
#wave{margin-left:auto;display:flex;gap:3px;align-items:flex-end;height:18px}
#wave i{width:4px;height:4px;background:var(--acc2);border-radius:2px;transition:height .1s}
#stage[data-state=talk] #wave i{animation:bar .45s ease-in-out infinite}
#wave i:nth-child(2){animation-delay:.06s!important}#wave i:nth-child(3){animation-delay:.12s!important}
#wave i:nth-child(4){animation-delay:.18s!important}#wave i:nth-child(5){animation-delay:.24s!important}
#wave i:nth-child(6){animation-delay:.3s!important}#wave i:nth-child(7){animation-delay:.36s!important}
@keyframes bar{0%,100%{height:4px}50%{height:18px}}
#heard{position:absolute;top:38px;left:14px;right:14px;text-align:center;font-size:12px;color:var(--heard);font-style:italic;min-height:16px;z-index:5}
#hud{position:absolute;top:70px;left:50%;width:340px;height:340px;margin-left:-170px;pointer-events:none;z-index:2}
#hud svg{width:100%;height:100%}
.c1{stroke:var(--acc);stroke-opacity:.55}.c2{stroke:var(--acc);stroke-opacity:.75}.c3{stroke:var(--acc2);stroke-opacity:.4}.c4{fill:var(--accA2)}
.r1{animation:rot 26s linear infinite}.r2{animation:rot 14s linear infinite reverse}.r3{animation:rot 40s linear infinite}
#stage[data-state=listen] .r1,#stage[data-state=think] .r1{animation-duration:6s}
#stage[data-state=listen] .r2,#stage[data-state=think] .r2{animation-duration:4s}
@keyframes rot{to{transform:rotate(360deg)}}
#avwrap{position:absolute;left:50%;bottom:190px;transform:translateX(-50%);perspective:800px;z-index:3}
#av{cursor:pointer;position:relative;height:var(--avh);width:max-content;transform-origin:50% 100%}
#av img{height:var(--avh);width:auto;display:block;position:absolute;inset:0;user-select:none;-webkit-user-drag:none}
#avimg{position:relative!important}
#fallback{display:none;font-size:150px}
#av.idle{animation:float 3.2s ease-in-out infinite}
#av.listen{animation:listen 1.1s ease-in-out infinite}
#av.think{animation:think 1s ease-in-out infinite}
#av.talk{animation:talk .36s ease-in-out infinite}
#av.t-hop{animation:hop .9s ease-out 1}#av.t-wiggle{animation:wiggle .8s ease-in-out 1}
#av.t-spin{animation:spin 1s ease-in-out 1}#av.t-tilt{animation:tilt 1.2s ease-in-out 1}
#av.t-shake{animation:shake .7s ease-in-out 1}
#av.t-glitch{animation:avGlitch .65s steps(9,end) 1}#av.t-pulse{animation:avPulse .9s ease-out 1}
@keyframes float{0%,100%{transform:translateY(0) rotate(-1.2deg)}50%{transform:translateY(-12px) rotate(1.6deg)}}
@keyframes listen{0%,100%{transform:scale(1) rotate(-3deg)}50%{transform:scale(1.04) rotate(3deg)}}
@keyframes think{0%,100%{transform:rotate(-7deg) translateY(0)}50%{transform:rotate(7deg) translateY(-4px)}}
@keyframes talk{0%,100%{transform:scale(1,1) translateY(0)}50%{transform:scale(1.035,.965) translateY(3px)}}
@keyframes hop{0%{transform:translateY(0) scale(1,1)}18%{transform:translateY(0) scale(1.14,.84)}50%{transform:translateY(-70px) scale(.92,1.1)}82%{transform:translateY(0) scale(1.12,.88)}100%{transform:translateY(0) scale(1,1)}}
@keyframes wiggle{0%,100%{transform:rotate(0)}20%{transform:rotate(-10deg)}40%{transform:rotate(9deg)}60%{transform:rotate(-7deg)}80%{transform:rotate(5deg)}}
@keyframes spin{0%{transform:rotateY(0) translateY(0)}50%{transform:rotateY(180deg) translateY(-30px)}100%{transform:rotateY(360deg) translateY(0)}}
@keyframes tilt{0%,100%{transform:rotate(0)}30%,70%{transform:rotate(-12deg) translateX(-6px)}}
@keyframes shake{0%,100%{transform:translateX(0)}15%{transform:translateX(-12px) rotate(-4deg)}35%{transform:translateX(12px) rotate(4deg)}55%{transform:translateX(-8px)}75%{transform:translateX(8px)}}
@keyframes avGlitch{0%,100%{transform:translate(0,0) skewX(0);filter:none}11%{transform:translate(-9px,2px) skewX(-6deg);filter:hue-rotate(60deg) brightness(1.6)}22%{transform:translate(8px,-3px) skewX(5deg)}33%{transform:translate(-5px,0) skewX(0);filter:hue-rotate(-50deg)}44%{transform:translate(10px,3px) skewX(-4deg);filter:brightness(2)}55%{transform:translate(-7px,-2px)}66%{transform:translate(4px,0) skewX(3deg);filter:hue-rotate(40deg)}77%{transform:translate(-3px,1px)}88%{transform:translate(2px,0)}}
@keyframes avPulse{0%{transform:scale(1);filter:brightness(1)}30%{transform:scale(1.12);filter:brightness(2.2) saturate(1.4)}100%{transform:scale(1);filter:brightness(1)}}
#shadow{position:absolute;left:50%;bottom:176px;width:170px;height:20px;margin-left:-85px;border-radius:50%;background:rgba(0,0,0,.45);filter:blur(5px);animation:shad 3.2s ease-in-out infinite;z-index:2}
@keyframes shad{0%,100%{transform:scale(1)}50%{transform:scale(.82);opacity:.6}}
#fx{position:absolute;inset:0;pointer-events:none;z-index:6;overflow:hidden}
.p{position:absolute;top:-30px;font-size:22px;animation:fall linear forwards}
@keyframes fall{to{transform:translateY(640px) rotate(360deg);opacity:.2}}
#cap{position:absolute;left:16px;right:16px;bottom:70px;max-height:104px;overflow-y:auto;padding:10px 14px;border-radius:16px;
 background:var(--capbg);border:1px solid var(--accA);backdrop-filter:blur(4px);font-size:14px;line-height:1.45;z-index:5}
#btns{position:absolute;left:0;right:0;bottom:12px;display:flex;justify-content:center;gap:10px;z-index:6}
button{border:none;cursor:pointer;color:#fff;border-radius:22px;padding:0 16px;height:44px;font-size:14px;font-weight:700;
 background:rgba(255,255,255,.14);border:1px solid var(--accA);transition:all .15s}
button:hover{background:var(--accA)}
#mic{width:54px;padding:0;border-radius:50%;height:54px;font-size:22px;margin-top:-6px;background:linear-gradient(135deg,var(--btn1),var(--btn2))}
button.on{background:var(--acc);color:var(--onfg);box-shadow:0 0 16px var(--acc)}
/*__SCENECSS__*/
</style></head><body>
<div id="stage" data-state="idle" data-char="__CHARID__">
 <div id="bgfx"><!--__SCENE__--></div>
 <div id="topbar"><span id="led"></span><span id="stlabel">ONLINE</span>
  <div id="wave"><i></i><i></i><i></i><i></i><i></i><i></i><i></i></div></div>
 <div id="heard"></div>
 <div id="hud"><svg viewBox="-160 -160 320 320">
  <g class="r1"><circle class="c1" r="152" fill="none" stroke-width="2" stroke-dasharray="6 10"/></g>
  <g class="r2"><circle class="c2" r="130" fill="none" stroke-width="3" stroke-dasharray="60 30 10 30"/></g>
  <g class="r3"><circle class="c3" r="108" fill="none" stroke-width="1.5" stroke-dasharray="2 6"/></g>
  <circle class="c4" r="92"/></svg></div>
 <div id="avwrap"><div id="av" class="idle"><!--__LAYERS__--><div id="fallback">__EMOJI__</div></div></div>
 <div id="shadow"></div><div id="fx"></div>
 <div id="cap"><span id="capt">__INTRO__</span></div>
 <div id="btns"><button id="wake">👂 Wake word</button><button id="mic" title="Bicara">🎤</button>
  <button id="mute">🔊</button><button id="demo">🎭</button></div>
</div>
<script>
const CH=__CHJSON__;
(function(){
const $=id=>document.getElementById(id);
const S={post(t,d){window.parent.postMessage(Object.assign({isStreamlitMessage:true,type:t},d||{}),'*')},
 ready(){this.post('streamlit:componentReady',{apiVersion:1})},
 height(h){this.post('streamlit:setFrameHeight',{height:h})},
 value(v){this.post('streamlit:setComponentValue',{value:v,dataType:'json'})}};
let cfg={pitch:CH.pitch,rate:CH.rate,robot:CH.robot,hasAvatar:true};
let state='idle',muted=false,mode='off',prevMode='off',activeUntil=0,lastSpoken=-1,speaking=false,rec=null,recRunning=false;
let thinkTimer=null,actx=null,blipTimer=null,speakToken=0,capTimer=null;
const WAKE=new RegExp(CH.wake,'i');
const LABEL={idle:'ONLINE',listen:'MENDENGARKAN…',think:'BERPIKIR…',talk:'BERBICARA'};

// gambar: mode folder (src sudah benar) atau mode cadangan (data URL lewat window.AG_ASSETS)
document.querySelectorAll('img[data-asset]').forEach(im=>{
 im.onerror=()=>{if(im.id!=='avimg')im.style.display='none';};
 if(window.AG_ASSETS){const u=window.AG_ASSETS[im.dataset.asset];if(u)im.src=u;else im.style.display='none';}
});

function setState(s){state=s;$('stage').dataset.state=s;$('av').className=s;
 $('stlabel').textContent=CH.name+' • '+((s==='idle'&&mode==='wake')?'MENUNGGU "'+CH.say.toUpperCase()+'"…':LABEL[s]);}
function trick(n){const a=$('av');a.className='t-'+n;}
$('av').addEventListener('animationend',e=>{if(e.target===$('av')&&$('av').className.indexOf('t-')===0)$('av').className=state;});
function heard(t){$('heard').textContent=t||'';}
// Kedipan mata otomatis (karakter kartun yang punya overlay kelopak)
function blinkEyes(){const fx=$('faceFX');if(!fx)return;fx.classList.add('blink');setTimeout(()=>fx.classList.remove('blink'),135);}
(function scheduleBlink(){setTimeout(()=>{blinkEyes();scheduleBlink();},2500+Math.random()*2500);})();
// Glitch hologram acak (IRONMAN & JOI)
(function scheduleGlitch(){if(!CH.holo)return;setTimeout(()=>{const st=$('stage');st.classList.add('gl');
 setTimeout(()=>st.classList.remove('gl'),420);scheduleGlitch();},2200+Math.random()*4200);})();
function caption(t){clearInterval(capTimer);const el=$('capt');let i=0;el.textContent='';
 capTimer=setInterval(()=>{i+=2;el.textContent=t.slice(0,i);if(i>=t.length)clearInterval(capTimer);},22);}
function rain(list,n){const fx=$('fx');for(let i=0;i<n;i++){const d=document.createElement('div');d.className='p';
 d.textContent=list[Math.floor(Math.random()*list.length)];d.style.left=(Math.random()*92)+'%';
 const dur=2+Math.random()*1.8;d.style.animationDuration=dur+'s';d.style.animationDelay=(Math.random()*.8)+'s';
 fx.appendChild(d);setTimeout(()=>d.remove(),(dur+1)*1000);}}
function mood(m){const T=CH.holo?{bull:'pulse',bear:'glitch',happy:'spin'}:{bull:'hop',bear:'shake',happy:'spin'};
 if(m==='bull'){trick(T.bull);rain(['💰','🪙','📈','✨'],18);}
 else if(m==='bear'){trick(T.bear);rain(['📉','💧'],12);}
 else if(m==='happy'){trick(T.happy);rain(['⭐','✨'],10);}}

function ac(){if(!actx){try{actx=new(window.AudioContext||window.webkitAudioContext)();}catch(e){}}
 if(actx&&actx.state==='suspended')actx.resume();return actx;}
function blip(f,d,v,type){const a=ac();if(!a)return;const o=a.createOscillator(),g=a.createGain();o.type=type||'square';
 o.frequency.value=f;o.connect(g);g.connect(a.destination);const t=a.currentTime;g.gain.setValueAtTime(v||.02,t);
 g.gain.exponentialRampToValueAtTime(.0001,t+d);o.start(t);o.stop(t+d+.02);}
function chirp(){blip(660,.08,.05,'triangle');setTimeout(()=>blip(990,.12,.05,'triangle'),90);}
function startBlips(){stopBlips();if(!cfg.robot)return;blipTimer=setInterval(()=>blip(500+Math.random()*900,.05,.012,'square'),130);}
function stopBlips(){clearInterval(blipTimer);blipTimer=null;}

function pickVoice(){const vs=(window.speechSynthesis&&speechSynthesis.getVoices())||[];
 const id=vs.filter(v=>/^id/i.test(v.lang)||/indonesia/i.test(v.name));
 return id.find(v=>v.localService)||id[0]||vs.find(v=>/^en/i.test(v.lang))||null;}
function doneSpeaking(tok){if(tok!==speakToken||!speaking)return;speaking=false;stopBlips();
 setState('idle');resumeRec();}
function speak(text){
 speakToken++;const tok=speakToken;speaking=true;pauseRec();setState('talk');
 if(muted||!('speechSynthesis' in window)){setTimeout(()=>doneSpeaking(tok),Math.min(9000,text.length*55));return;}
 try{speechSynthesis.cancel();}catch(e){}
 startBlips();
 let parts=(text.match(/[^.!?\n]+[.!?]?/g)||[text]).map(s=>s.trim()).filter(Boolean),chunks=[],cur='';
 parts.forEach(p=>{if((cur+' '+p).length>170&&cur){chunks.push(cur);cur=p;}else cur=(cur?cur+' ':'')+p;});
 if(cur)chunks.push(cur);
 const v=pickVoice();
 chunks.forEach((c,idx)=>{const u=new SpeechSynthesisUtterance(c);u.lang=(v&&v.lang)||'id-ID';if(v)u.voice=v;
  u.pitch=cfg.pitch;u.rate=cfg.rate;u.volume=1;
  const fin=()=>{if(idx===chunks.length-1)doneSpeaking(tok);};u.onend=fin;u.onerror=fin;speechSynthesis.speak(u);});
 setTimeout(()=>doneSpeaking(tok),Math.max(5000,text.length*130));}
function speakLocal(t){caption(t);speak(t);}

function ensureRec(){if(rec)return rec;const SR=window.SpeechRecognition||window.webkitSpeechRecognition;
 if(!SR){heard('Browser belum mendukung suara — gunakan Chrome / Edge, atau ketik perintah.');return null;}
 rec=new SR();rec.lang='id-ID';rec.interimResults=true;rec.maxAlternatives=1;
 rec.onstart=()=>{recRunning=true;};
 rec.onend=()=>{recRunning=false;if(!speaking&&state!=='think'&&mode!=='off')setTimeout(startRec,250);};
 rec.onerror=e=>{if(e.error==='not-allowed'||e.error==='service-not-allowed'){mode='off';refresh();setState('idle');
   heard('Izin mikrofon ditolak. Klik ikon gembok di address bar lalu izinkan mikrofon.');}
  else if(e.error!=='no-speech'&&e.error!=='aborted'){heard('Mic: '+e.error);}};
 rec.onresult=e=>{let interim='';for(let i=e.resultIndex;i<e.results.length;i++){const r=e.results[i];
  if(r.isFinal)onFinal(r[0].transcript);else interim+=r[0].transcript;}if(interim)heard('🎙 '+interim);};
 return rec;}
function startRec(){const r=ensureRec();if(!r||recRunning||speaking||mode==='off')return;
 r.continuous=(mode==='wake');try{r.start();}catch(e){}}
function pauseRec(){if(rec&&recRunning){try{rec.abort();}catch(e){}}}
function resumeRec(){if(mode!=='off')setTimeout(startRec,300);}

function fallbackSend(text){try{const doc=window.parent.document;
 const ta=doc.querySelector('textarea[data-testid="stChatInputTextArea"]')||doc.querySelector('[data-testid="stChatInput"] textarea');
 const setter=Object.getOwnPropertyDescriptor(window.parent.HTMLTextAreaElement.prototype,'value').set;
 setter.call(ta,text);ta.dispatchEvent(new Event('input',{bubbles:true}));
 setTimeout(()=>{const b=doc.querySelector('[data-testid="stChatInputSubmitButton"]');
  if(b)b.click();else ta.dispatchEvent(new KeyboardEvent('keydown',{key:'Enter',code:'Enter',keyCode:13,bubbles:true}));},120);
 }catch(e){heard('Gagal mengirim ke aplikasi: '+e);setState('idle');}}
function send(text){setState('think');heard('⏳ '+text);
 if(window.AG_FALLBACK){fallbackSend(text);}else{S.value({id:Date.now(),text:text});}
 clearTimeout(thinkTimer);thinkTimer=setTimeout(()=>{if(state==='think'){setState('idle');resumeRec();}},90000);}
function onFinal(t){t=(t||'').trim();if(!t)return;heard('🗣 '+t);
 if(mode==='ptt'){mode=prevMode;refresh();try{rec.abort();}catch(e){}send(t);return;}
 if(Date.now()<activeUntil){activeUntil=0;send(t);return;}
 const m=t.match(WAKE);
 if(m){const cmd=t.slice(m.index+m[0].length).replace(/^[\s,.:!?-]+/,'');
  if(cmd.length>=3)send(cmd);else{activeUntil=Date.now()+9000;speakLocal(CH.ready);}}}

function refresh(){$('wake').classList.toggle('on',mode==='wake');$('mic').classList.toggle('on',mode==='ptt');}
$('mic').onclick=()=>{ac();if(mode==='ptt'){mode=prevMode;pauseRec();setState('idle');refresh();return;}
 prevMode=mode;mode='ptt';setState('listen');pauseRec();refresh();heard('Silakan bicara…');setTimeout(startRec,200);};
$('wake').onclick=()=>{ac();chirp();if(mode==='wake'){mode='off';pauseRec();setState('idle');heard('');}
 else{mode='wake';prevMode='wake';setState('idle');heard('Katakan "'+CH.say+', analisa BBCA"…');startRec();}refresh();};
$('mute').onclick=()=>{muted=!muted;$('mute').textContent=muted?'🔇':'🔊';if(muted){try{speechSynthesis.cancel();}catch(e){}}};
const tricks=CH.tricks;
function randTrick(){trick(tricks[Math.floor(Math.random()*tricks.length)]);}
$('demo').onclick=()=>{ac();chirp();randTrick();rain(['⭐','✨','💰'],10);speakLocal(CH.demo);};
$('av').onclick=()=>{ac();randTrick();blip(880,.1,.05,'triangle');};
setInterval(()=>{if(state==='idle'&&!speaking&&Math.random()<.6)randTrick();},7000);

// partikel latar khusus karakter
(function scene(){const fx=$('bgfx');if(!fx)return;const R=(a,b)=>a+Math.random()*(b-a);
 function mk(cls,css,txt){const e=document.createElement('i');e.className=cls;e.style.cssText=css;if(txt)e.textContent=txt;fx.appendChild(e);}
 if(CH.id==='suhu'){for(let i=0;i<34;i++)mk('star','left:'+R(0,100)+'%;top:'+R(0,92)+'%;width:'+R(1.5,3.5)+'px;height:'+R(1.5,3.5)+'px;animation-delay:'+R(0,4)+'s;animation-duration:'+R(1.8,4)+'s');}
 if(CH.id==='miss'){const t=['⏱️','⌛','🕰️','✦','⏳'];for(let i=0;i<14;i++)mk('clk','left:'+R(2,94)+'%;font-size:'+R(14,30)+'px;animation-delay:'+R(0,9)+'s;animation-duration:'+R(7,13)+'s',t[i%t.length]);}
 if(CH.id==='ironman'){for(let i=0;i<30;i++)mk('bit','left:'+R(0,100)+'%;height:'+R(6,18)+'px;animation-delay:'+R(0,6)+'s;animation-duration:'+R(3,7)+'s');}
 if(CH.id==='joi'){for(let i=0;i<34;i++)mk('drop','left:'+R(0,100)+'%;height:'+R(36,100)+'px;animation-delay:'+R(0,2)+'s;animation-duration:'+R(.9,1.8)+'s;opacity:'+R(.25,.7));}
})();

function onRender(a){if(a.cfg)cfg=Object.assign(cfg,a.cfg);
 if(!cfg.hasAvatar){const im=$('avimg');if(im)im.style.display='none';$('fallback').style.display='block';}
 const sp=a.speak;if(sp&&sp.id!==lastSpoken){lastSpoken=sp.id;clearTimeout(thinkTimer);
  caption(sp.display||sp.text);speak(sp.text);mood(sp.mood);}}
window.addEventListener('message',e=>{if(e.data&&e.data.type==='streamlit:render')onRender(e.data.args||{});});
if(window.speechSynthesis){speechSynthesis.onvoiceschanged=()=>{};}
S.ready();S.height(580);setState('idle');
if(window.AG_INIT)onRender(window.AG_INIT);
})();
</script></body></html>
"""

# ---------------------------------------------------------
# SCENES: latar + layer + animasi khusus tiap karakter
# ---------------------------------------------------------
SCENES = {}

# ---- 1. SUHU: langit biru berbintang, awan melayang, tangan melambai & mata berkedip
SCENES["suhu"] = dict(
    layers='<img id="avimg" data-asset="avatar" src="avatar.png" draggable="false">'
           '<img id="handL" data-asset="handL" src="handL.png" draggable="false" alt="">'
           '<img id="handR" data-asset="handR" src="handR.png" draggable="false" alt="">'
           '<div id="faceFX"><span id="lidL" class="eye-lid"></span><span id="lidR" class="eye-lid"></span>'
           '<span class="mouth-cover"></span><span class="talk-mouth"></span></div>',
    scene='<b class="cloud c-a"></b><b class="cloud c-b"></b><b class="cloud c-c"></b>',
    css=r"""
#avimg{filter:drop-shadow(0 0 14px rgba(0,229,255,.35))}
#handL,#handR{pointer-events:none;z-index:2}
#handL{transform-origin:30.2% 58.4%;animation:handWaveL 3.8s ease-in-out infinite}
#handR{transform-origin:72.2% 59%;animation:handWaveR 4.4s ease-in-out infinite}
#faceFX{position:absolute;inset:0;pointer-events:none;z-index:4}
.eye-lid{position:absolute;top:20.4%;height:4.2%;width:5.2%;border-radius:50%;background:linear-gradient(180deg,#f9d0b4,#efb18e);opacity:0;transform:scaleY(.08);transform-origin:center;box-shadow:0 1px 1px #9b5d4b}
#lidL{left:39.6%}#lidR{left:51.5%}
#faceFX.blink .eye-lid{opacity:1;transform:scaleY(1);transition:transform .07s ease,opacity .04s}
.mouth-cover{position:absolute;left:44%;top:30.5%;width:12%;height:5.2%;border-radius:48%;background:linear-gradient(145deg,#f9c6a7,#f4b596 72%,#e9a181);}
.talk-mouth{position:absolute;left:45.3%;top:31.2%;width:7.2%;height:3.4%;border-radius:8% 8% 55% 55%;background:#6e171b;transform:scaleY(.25);transform-origin:top center;overflow:hidden;border:1.5px solid #39201c}
.talk-mouth:after{content:'';position:absolute;left:15%;right:15%;bottom:5%;height:36%;background:#ed5a62;border-radius:50% 50% 35% 35%}
#stage[data-state=talk] .talk-mouth{animation:mouthTalk .16s ease-in-out infinite alternate}
#stage[data-state=talk] .mouth-cover{opacity:.98}
@keyframes mouthTalk{from{transform:scaleY(.25)}to{transform:scaleY(1)}}
@keyframes handWaveL{0%,78%,100%{transform:rotate(0)}84%{transform:rotate(-8deg)}90%{transform:rotate(5deg)}96%{transform:rotate(-3deg)}}
@keyframes handWaveR{0%,76%,100%{transform:rotate(0)}83%{transform:rotate(5deg)}90%{transform:rotate(-7deg)}97%{transform:rotate(2deg)}}
.star{position:absolute;border-radius:50%;background:#fff;box-shadow:0 0 6px #bfe6ff;animation:twinkle 3s ease-in-out infinite}
@keyframes twinkle{0%,100%{opacity:.15;transform:scale(.7)}50%{opacity:1;transform:scale(1.25)}}
.cloud{position:absolute;display:block;height:46px;border-radius:50px;background:rgba(255,255,255,.16);filter:blur(7px)}
.c-a{width:150px;top:16%;left:-160px;animation:drift 38s linear infinite}
.c-b{width:110px;top:52%;left:-120px;animation:drift 52s linear infinite;animation-delay:-20s;height:36px}
.c-c{width:190px;top:34%;left:-200px;animation:drift 66s linear infinite;animation-delay:-42s;opacity:.7}
@keyframes drift{to{transform:translateX(640px)}}
""")

# ---- 2. MISS MINUTES: sunburst oranye ala TVA, jam-jam melayang, jari menunjuk, mata berkedip, jarum menit
SCENES["miss"] = dict(
    layers='<img id="avimg" data-asset="avatar" src="avatar.png" draggable="false">'
           '<img id="hand" data-asset="hand" src="hand.png" draggable="false" alt="">'
           '<div id="faceFX"><span id="lidL" class="eye-lid"></span><span id="lidR" class="eye-lid"></span>'
           '<span class="mm-mouth"></span></div><span id="mhand"></span>',
    scene='<b class="rays"></b><b class="dots"></b><b class="vign"></b>',
    css=r"""
#avimg{filter:drop-shadow(0 8px 10px rgba(80,25,0,.5))}
#av.idle{animation:mmBounce 1.7s ease-in-out infinite}
@keyframes mmBounce{0%,100%{transform:translateY(0) scale(1.02,.97)}45%{transform:translateY(-16px) scale(.98,1.03)}}
#hand{pointer-events:none;z-index:2;transform-origin:11.1% 38.9%;animation:mmWag 4.2s ease-in-out infinite}
@keyframes mmWag{0%,68%,100%{transform:rotate(0)}74%{transform:rotate(-16deg)}80%{transform:rotate(13deg)}86%{transform:rotate(-11deg)}92%{transform:rotate(7deg)}}
#stage[data-state=talk] #hand{animation:mmWagFast .5s ease-in-out infinite}
@keyframes mmWagFast{0%,100%{transform:rotate(-12deg)}50%{transform:rotate(11deg)}}
#faceFX{position:absolute;inset:0;pointer-events:none;z-index:4}
.eye-lid{position:absolute;border-radius:48% 48% 52% 52%;background:#dd8e14;border-bottom:3px solid #4a1a0a;opacity:0;transform:scaleY(.08);transform-origin:top center}
#lidL{left:32.4%;top:18.6%;width:13.4%;height:20.6%}
#lidR{left:55.2%;top:19.6%;width:13.4%;height:20.8%}
#faceFX.blink .eye-lid{opacity:1;transform:scaleY(1);transition:transform .07s ease,opacity .04s}
.mm-mouth{position:absolute;left:41%;top:45.4%;width:16.6%;height:4.6%;border-radius:10% 10% 60% 60%;background:#5a0d12;border:2px solid #3b130d;opacity:0;transform:scaleY(.3);transform-origin:top center;overflow:hidden}
.mm-mouth:after{content:'';position:absolute;left:18%;right:18%;bottom:0;height:38%;background:#ee6a6e;border-radius:50% 50% 0 0}
#stage[data-state=talk] .mm-mouth{opacity:1;animation:mmTalk .17s ease-in-out infinite alternate}
@keyframes mmTalk{from{transform:scaleY(.4)}to{transform:scaleY(2)}}
#mhand{position:absolute;z-index:4;left:50%;top:35.4%;width:1.9%;height:4.6%;margin-left:-.95%;background:#3a1408;border-radius:2px;transform-origin:50% 0;animation:mmTick 6s steps(12,end) infinite}
#stage[data-state=think] #mhand{animation:rot 1s linear infinite}
@keyframes mmTick{to{transform:rotate(360deg)}}
.rays{position:absolute;left:50%;top:40%;width:980px;height:980px;margin:-490px 0 0 -490px;border-radius:50%;
 background:repeating-conic-gradient(rgba(255,255,255,.16) 0 7deg,transparent 7deg 18deg);
 -webkit-mask-image:radial-gradient(circle,#000 8%,transparent 66%);mask-image:radial-gradient(circle,#000 8%,transparent 66%);animation:rot 70s linear infinite}
.dots{position:absolute;inset:0;background-image:radial-gradient(rgba(110,40,0,.26) 1.5px,transparent 1.8px);background-size:13px 13px;
 -webkit-mask-image:linear-gradient(180deg,transparent 30%,#000);mask-image:linear-gradient(180deg,transparent 30%,#000);opacity:.55}
.vign{position:absolute;inset:0;background:radial-gradient(ellipse at 50% 45%,transparent 55%,rgba(60,15,0,.38))}
.clk{position:absolute;bottom:-40px;opacity:0;animation:riseClk linear infinite;filter:drop-shadow(0 2px 3px rgba(70,20,0,.35))}
@keyframes riseClk{0%{transform:translateY(0) rotate(0);opacity:0}12%{opacity:.85}85%{opacity:.7}100%{transform:translateY(-640px) rotate(360deg);opacity:0}}
#shadow{background:rgba(70,20,0,.45)}
""")

# ---- 3. IRONMAN: hitam pekat, lantai grid cyan, hologram menyala berkedip, reaktor arc berputar
SCENES["ironman"] = dict(
    layers='<img id="avimg" class="holo" data-asset="avatar" src="avatar.png" draggable="false">'
           '<img id="ghost" data-asset="avatar" src="avatar.png" draggable="false" alt="">'
           '<img id="reactor" data-asset="reactor" src="reactor.png" draggable="false" alt="">'
           '<b id="core2"></b><b id="eyeglow"></b><b id="palmL" class="palm"></b><b id="palmR" class="palm"></b>'
           '<b id="scan"></b><b id="beam"></b>',
    scene='<b class="grid"></b><b class="cone"></b><b class="disc"><u></u><u></u><u></u></b><b class="hexes"></b>',
    css=r"""
#avimg.holo{filter:drop-shadow(0 0 3px rgba(0,229,255,.95)) drop-shadow(0 0 14px rgba(0,229,255,.6)) brightness(1.1);animation:holoFlick 3.7s steps(1,end) infinite}
@keyframes holoFlick{0%,100%{opacity:.96}4%{opacity:.62}6%{opacity:1}30%{opacity:.9}32%{opacity:.5}33%{opacity:1}70%{opacity:.97}72%{opacity:.7}74%{opacity:1}}
#ghost{mix-blend-mode:screen;opacity:.5;filter:hue-rotate(150deg) saturate(1.6) blur(.5px);animation:ghostJit 2.6s steps(1,end) infinite;pointer-events:none}
@keyframes ghostJit{0%{transform:translateX(2px)}20%{transform:translateX(-2px)}40%{transform:translateX(3px)}55%{transform:translateX(0)}75%{transform:translateX(-3px)}100%{transform:translateX(2px)}}
#reactor{transform-origin:9.2% 32.4%;animation:rot 14s linear infinite;filter:drop-shadow(0 0 4px rgba(0,229,255,.95)) drop-shadow(0 0 12px rgba(0,229,255,.55));pointer-events:none}
#stage[data-state=listen] #reactor,#stage[data-state=think] #reactor{animation-duration:3s}
#core2{position:absolute;left:78%;top:18%;width:22%;height:22%;border-radius:50%;background:radial-gradient(circle,rgba(0,229,255,.5),transparent 68%);animation:corePulse 2.4s ease-in-out infinite;pointer-events:none}
@keyframes corePulse{0%,100%{opacity:.35;transform:scale(.85)}50%{opacity:1;transform:scale(1.12)}}
#eyeglow{position:absolute;left:41%;top:22.4%;width:19%;height:3.6%;background:linear-gradient(90deg,transparent,#e6ffff 30%,#e6ffff 70%,transparent);filter:blur(2.5px);mix-blend-mode:screen;animation:eyePulse 2.8s ease-in-out infinite;pointer-events:none}
@keyframes eyePulse{0%,100%{opacity:.35}50%{opacity:.95}}
#stage[data-state=talk] #eyeglow{animation:eyePulse .35s ease-in-out infinite}
.palm{position:absolute;width:9%;height:9%;margin:-4.5% 0 0 -4.5%;border-radius:50%;background:radial-gradient(circle,#fff 0%,rgba(0,229,255,.9) 28%,transparent 70%);mix-blend-mode:screen;opacity:.25;animation:palmGlow 3.4s ease-in-out infinite;pointer-events:none}
#palmL{left:22.4%;top:59.4%}#palmR{left:78.4%;top:59.4%;animation-delay:-1.7s}
@keyframes palmGlow{0%,100%{opacity:.2;transform:scale(.8)}50%{opacity:.85;transform:scale(1.15)}}
#stage[data-state=talk] .palm{animation:palmGlow .4s ease-in-out infinite}
#scan{position:absolute;inset:0;background:repeating-linear-gradient(0deg,rgba(0,0,0,.42) 0 1px,transparent 1px 3px);pointer-events:none;z-index:3}
#beam{position:absolute;left:-4%;right:-4%;height:16%;top:-16%;background:linear-gradient(180deg,transparent,rgba(125,249,255,.38),transparent);mix-blend-mode:screen;animation:beamMove 3.2s linear infinite;pointer-events:none;z-index:3;-webkit-mask-image:linear-gradient(90deg,transparent,#000 18%,#000 82%,transparent);mask-image:linear-gradient(90deg,transparent,#000 18%,#000 82%,transparent)}
@keyframes beamMove{to{top:100%}}
#stage.gl #avimg.holo{animation:holoFlick 3.7s steps(1,end) infinite,hGlitch .42s steps(6,end) 1}
@keyframes hGlitch{0%{transform:translateX(0);clip-path:inset(0)}20%{transform:translateX(-10px);clip-path:inset(12% 0 62% 0)}40%{transform:translateX(9px);clip-path:inset(48% 0 28% 0)}60%{transform:translateX(-6px);clip-path:inset(70% 0 8% 0)}80%{transform:translateX(5px);clip-path:inset(30% 0 50% 0)}100%{transform:translateX(0);clip-path:inset(0)}}
#stage[data-state=talk] #avimg.holo{filter:drop-shadow(0 0 4px #7ff) drop-shadow(0 0 22px rgba(0,229,255,.85))}
#stage[data-state=think] #avimg.holo{filter:drop-shadow(0 0 4px #fbbf24) drop-shadow(0 0 16px rgba(251,191,36,.7)) hue-rotate(-140deg) brightness(1.2)}
#shadow{background:radial-gradient(ellipse,rgba(0,229,255,.75),rgba(0,229,255,0) 70%);height:26px;filter:blur(3px)}
.grid{position:absolute;left:-30%;right:-30%;bottom:-6%;height:46%;background-image:linear-gradient(rgba(0,229,255,.34) 1px,transparent 1px),linear-gradient(90deg,rgba(0,229,255,.34) 1px,transparent 1px);background-size:42px 42px;transform:perspective(320px) rotateX(64deg);transform-origin:50% 100%;animation:gridMove 1.5s linear infinite;-webkit-mask-image:linear-gradient(0deg,#000 10%,transparent);mask-image:linear-gradient(0deg,#000 10%,transparent)}
@keyframes gridMove{to{background-position:0 42px}}
.cone{position:absolute;left:50%;bottom:14%;width:300px;height:340px;margin-left:-150px;background:linear-gradient(0deg,rgba(0,229,255,.28),rgba(0,229,255,0));clip-path:polygon(30% 100%,70% 100%,100% 0,0 0);animation:coneFlick 4s ease-in-out infinite}
@keyframes coneFlick{0%,100%{opacity:.7}50%{opacity:1}30%{opacity:.5}}
.disc{position:absolute;left:50%;bottom:12.5%;width:230px;height:46px;margin-left:-115px}
.disc u{position:absolute;inset:0;border-radius:50%;border:2px solid rgba(0,229,255,.8);box-shadow:0 0 14px rgba(0,229,255,.7),inset 0 0 12px rgba(0,229,255,.4);animation:ring 2.4s ease-out infinite}
.disc u:nth-child(2){animation-delay:-.8s}.disc u:nth-child(3){animation-delay:-1.6s}
@keyframes ring{0%{transform:scale(.45);opacity:1}100%{transform:scale(1.25);opacity:0}}
.hexes{position:absolute;inset:0;background-image:radial-gradient(rgba(0,229,255,.12) 1px,transparent 1.5px);background-size:22px 22px;-webkit-mask-image:radial-gradient(circle at 50% 42%,#000,transparent 70%);mask-image:radial-gradient(circle at 50% 42%,#000,transparent 70%)}
.bit{position:absolute;bottom:-20px;width:2px;background:linear-gradient(0deg,rgba(0,229,255,0),#7ff);animation:riseBit linear infinite;opacity:0}
@keyframes riseBit{0%{transform:translateY(0);opacity:0}15%{opacity:.9}100%{transform:translateY(-620px);opacity:0}}
""")

# ---- 4. JOI: hitam dengan neon magenta-biru, hujan neon, hologram berkedip + RGB-split + glitch
SCENES["joi"] = dict(
    layers='<img id="joiC" data-asset="joiC" src="joiC.png" draggable="false" alt="">'
           '<img id="joiM" data-asset="joiM" src="joiM.png" draggable="false" alt="">'
           '<img id="avimg" class="holo" data-asset="avatar" src="avatar.png" draggable="false">'
           '<img id="joiG" data-asset="avatar" src="avatar.png" draggable="false" alt="">'
           '<b id="scan"></b><b id="beam"></b>',
    scene='<b class="glow"></b><b class="cone"></b><b class="disc"><u></u><u></u><u></u></b>',
    css=r"""
#avimg.holo{-webkit-mask-image:linear-gradient(180deg,#000 62%,transparent 98%);mask-image:linear-gradient(180deg,#000 62%,transparent 98%);filter:saturate(1.3) brightness(1.15) drop-shadow(0 0 10px rgba(255,63,210,.6)) drop-shadow(0 0 26px rgba(120,90,255,.45));animation:joiFlick 4.1s steps(1,end) infinite}
@keyframes joiFlick{0%,100%{opacity:.94}3%{opacity:.55}5%{opacity:1}28%{opacity:.85}30%{opacity:.45}31%{opacity:1}64%{opacity:.96}66%{opacity:.68}68%{opacity:1}88%{opacity:.8}89%{opacity:1}}
#joiC,#joiM{mix-blend-mode:screen;pointer-events:none;opacity:.6;-webkit-mask-image:linear-gradient(180deg,#000 62%,transparent 98%);mask-image:linear-gradient(180deg,#000 62%,transparent 98%)}
#joiC{animation:rgbL 2.9s steps(1,end) infinite}#joiM{animation:rgbR 2.9s steps(1,end) infinite}
@keyframes rgbL{0%{transform:translateX(-3px)}25%{transform:translateX(-5px)}50%{transform:translateX(-2px)}75%{transform:translateX(-6px)}100%{transform:translateX(-3px)}}
@keyframes rgbR{0%{transform:translateX(3px)}25%{transform:translateX(5px)}50%{transform:translateX(2px)}75%{transform:translateX(6px)}100%{transform:translateX(3px)}}
#joiG{opacity:0;pointer-events:none;mix-blend-mode:screen;filter:hue-rotate(40deg) brightness(1.4)}
#stage.gl #joiG{animation:joiSlice .42s steps(1,end) 1}
@keyframes joiSlice{0%{opacity:.9;clip-path:inset(10% 0 80% 0);transform:translateX(-12px)}16%{clip-path:inset(46% 0 40% 0);transform:translateX(14px)}33%{clip-path:inset(68% 0 14% 0);transform:translateX(-10px)}50%{clip-path:inset(24% 0 62% 0);transform:translateX(9px)}66%{clip-path:inset(56% 0 26% 0);transform:translateX(-7px)}83%{clip-path:inset(34% 0 50% 0);transform:translateX(6px)}100%{opacity:0;clip-path:inset(0);transform:none}}
#scan{position:absolute;inset:0;background:repeating-linear-gradient(0deg,rgba(0,0,0,.45) 0 1px,transparent 1px 3px);pointer-events:none;z-index:3}
#beam{position:absolute;left:-4%;right:-4%;height:15%;top:-15%;background:linear-gradient(180deg,transparent,rgba(255,120,230,.3),transparent);mix-blend-mode:screen;animation:beamMove 3.6s linear infinite;pointer-events:none;z-index:3;-webkit-mask-image:linear-gradient(90deg,transparent,#000 18%,#000 82%,transparent);mask-image:linear-gradient(90deg,transparent,#000 18%,#000 82%,transparent)}
@keyframes beamMove{to{top:100%}}
#stage[data-state=talk] #avimg.holo{filter:saturate(1.4) drop-shadow(0 0 14px rgba(255,63,210,.9)) drop-shadow(0 0 34px rgba(120,90,255,.7))}
#stage[data-state=think] #avimg.holo{filter:saturate(1.2) brightness(1.2) hue-rotate(60deg) drop-shadow(0 0 12px rgba(120,200,255,.8))}
#shadow{background:radial-gradient(ellipse,rgba(255,63,210,.7),rgba(255,63,210,0) 70%);height:26px;filter:blur(3px)}
.glow{position:absolute;left:0;right:0;bottom:0;height:46%;background:radial-gradient(ellipse at 50% 100%,rgba(255,40,190,.38),rgba(90,60,255,.12) 45%,transparent 68%);animation:glowBreath 4s ease-in-out infinite}
@keyframes glowBreath{0%,100%{opacity:.7}50%{opacity:1}}
.cone{position:absolute;left:50%;bottom:14%;width:300px;height:340px;margin-left:-150px;background:linear-gradient(0deg,rgba(255,63,210,.26),rgba(120,90,255,0));clip-path:polygon(30% 100%,70% 100%,100% 0,0 0);animation:coneFlick 4.4s ease-in-out infinite}
@keyframes coneFlick{0%,100%{opacity:.7}50%{opacity:1}30%{opacity:.45}}
.disc{position:absolute;left:50%;bottom:12.5%;width:230px;height:46px;margin-left:-115px}
.disc u{position:absolute;inset:0;border-radius:50%;border:2px solid rgba(255,63,210,.85);box-shadow:0 0 14px rgba(255,63,210,.7),inset 0 0 12px rgba(120,90,255,.45);animation:ring 2.6s ease-out infinite}
.disc u:nth-child(2){animation-delay:-.87s}.disc u:nth-child(3){animation-delay:-1.73s}
@keyframes ring{0%{transform:scale(.45);opacity:1}100%{transform:scale(1.25);opacity:0}}
.drop{position:absolute;top:-110px;width:1.5px;background:linear-gradient(180deg,rgba(143,176,255,0),rgba(143,176,255,.8));animation:dropFall linear infinite}
@keyframes dropFall{to{transform:translateY(720px)}}
""")


def build_component_html(cid):
    """Template + latar/animasi khusus karakter -> satu halaman HTML utuh."""
    C, SC = CHARACTERS[cid], SCENES[cid]
    vars_css = "".join(f"--{k}:{v};" for k, v in C["theme"].items()) + f"--avh:{C['avh']}px;"
    chj = dict(id=cid, name=C["name"], say=C["spoken"], wake=C["wake"], holo=C["holo"], tricks=C["tricks"],
               pitch=C["pitch"], rate=C["rate"], robot=C["robot"],
               ready=C["lines"]["ready"], demo=C["lines"]["demo"].format(s=C["spoken"]))
    return (COMPONENT_TMPL
            .replace("/*__VARS__*/", vars_css)
            .replace("/*__SCENECSS__*/", SC["css"])
            .replace("<!--__SCENE__-->", SC["scene"])
            .replace("<!--__LAYERS__-->", SC["layers"])
            .replace("__CHARID__", cid)
            .replace("__EMOJI__", C["emoji"])
            .replace("__INTRO__", htmllib.escape(C["lines"]["intro_cap"]))
            .replace("__CHJSON__", json.dumps(chj, ensure_ascii=False)))


# ---------------------------------------------------------
# GAMBAR: cari file PNG karakter & olah (hologram, potong tangan, dll)
# ---------------------------------------------------------
def _norm(s):
    return re.sub(r"[\s_\-]+", "", s.lower())


def _find_char_file(cid):
    here = Path(__file__).resolve().parent
    dirs = [here, here.parent, here / "assets", here.parent / "assets", Path.cwd(), Path.cwd() / "assets"]
    wanted = [_norm(n) for n in CHARACTERS[cid]["files"]]
    for d in dirs:
        try:
            for f in d.iterdir():
                if f.is_file() and _norm(f.name) in wanted:
                    return f
        except Exception:
            continue
    return None


def _fit(im, maxw, maxh):
    from PIL import Image
    s = min(maxw / im.width, maxh / im.height, 1.0)
    if s == 1.0:
        return im
    return im.resize((max(1, int(im.width * s)), max(1, int(im.height * s))), Image.Resampling.LANCZOS)


def _cut_layers(im, polys):
    """Pisahkan area poligon menjadi layer terpisah; kembalikan (dasar_berlubang, [layer...])."""
    from PIL import Image, ImageDraw
    w, h = im.size
    base = im.copy()
    keep = Image.new("L", (w, h), 255)
    layers = []
    for pts in polys:
        m = Image.new("L", (w, h), 0)
        ImageDraw.Draw(m).polygon(pts, fill=255)
        layer = Image.new("RGBA", (w, h), (0, 0, 0, 0))
        layer.paste(im, (0, 0), m)
        layers.append(layer)
        ImageDraw.Draw(keep).polygon(pts, fill=0)
    a = np.minimum(np.array(base.getchannel("A")), np.array(keep))   # lubang = alpha 0 (bukan sebaliknya)
    base.putalpha(Image.fromarray(a.astype("uint8")))
    return base, layers


def _assets_suhu(im):
    im = _fit(im.convert("RGBA"), 560, 670)
    w, h = im.size
    sx, sy = w / 944, h / 1127
    P = lambda pts: [(int(x * sx), int(y * sy)) for x, y in pts]
    left_pts = [(198,646),(215,631),(244,623),(269,632),(293,648),(304,666),(299,686),(285,704),(269,713),(253,705),(239,699),(220,696),(202,687),(194,671)]
    right_pts = [(665,653),(678,636),(699,628),(722,631),(745,645),(764,663),(779,680),(779,698),(765,715),(750,730),(729,752),(708,760),(690,746),(674,730),(660,712),(653,693)]
    base, (hl, hr) = _cut_layers(im, [P(left_pts), P(right_pts)])
    return {"full": im, "avatar": base, "handL": hl, "handR": hr}


def _assets_miss(im):
    from PIL import Image
    im = im.convert("RGBA")
    sx, sy = im.width / 360, im.height / 360
    a = np.array(im)
    a[int(268 * sy):, int(318 * sx):, 3] = 0              # buang bintang nyasar di pojok kanan bawah
    im = Image.fromarray(a)
    im = _fit(im, 560, 560)
    sx, sy = im.width / 360, im.height / 360
    hand = [(34,76),(46,76),(48,90),(52,100),(60,106),(62,118),(58,130),(50,138),(36,140),(26,134),(24,120),(26,108),(32,100),(36,90)]
    base, (hl,) = _cut_layers(im, [[(int(x * sx), int(y * sy)) for x, y in hand]])
    return {"full": im, "avatar": base, "hand": hl}


def _assets_ironman(im):
    from PIL import Image, ImageDraw, ImageFilter
    a = np.array(im.convert("RGBA")).astype(float)
    al = a[..., 3] / 255
    lum = (0.299 * a[..., 0] + 0.587 * a[..., 1] + 0.114 * a[..., 2]) / 255
    red = np.clip((a[..., 0] - np.maximum(a[..., 1], a[..., 2])) / 80, 0, 1)      # aksen merah tetap merah
    cy, rd = np.array([90, 235, 255.]), np.array([255, 90, 70.])
    out = np.zeros_like(a)
    out[..., :3] = cy * (1 - red[..., None]) + rd * red[..., None]
    out[..., 3] = np.clip(al * (0.35 + 0.9 * (1 - lum)) * 255 * 1.25, 0, 255)       # garis gelap -> garis menyala
    holo = Image.fromarray(out.astype("uint8"))
    w, h = holo.size
    sx, sy = w / 500, h / 500
    # skema reaktor arc di kiri -> layer sendiri agar bisa berputar
    cx, cyy, r = 46 * sx, 162 * sy, 44 * sx
    m = Image.new("L", (w, h), 0)
    ImageDraw.Draw(m).ellipse([cx - r, cyy - r, cx + r, cyy + r], fill=255)
    m = m.filter(ImageFilter.GaussianBlur(2))
    reactor = Image.new("RGBA", (w, h), (0, 0, 0, 0))
    reactor.paste(holo, (0, 0), m)
    keep = Image.fromarray((255 - np.array(m)).astype("uint8"))
    base = holo.copy()
    base.putalpha(Image.fromarray(np.minimum(np.array(holo.getchannel("A")), np.array(keep)).astype("uint8")))
    return {"full": holo, "avatar": base, "reactor": reactor}


def _assets_joi(im):
    from PIL import Image, ImageFilter
    from scipy import ndimage as ndi
    a = np.array(im.convert("RGBA"))
    al, rgb = a[..., 3], a[..., :3].astype(int)
    bgmask = (al < 15) | ((rgb.min(2) > 215) & (al > 0))                 # transparan + tepi putih stiker
    lab, _ = ndi.label(bgmask)
    border = set(np.unique(np.concatenate([lab[0], lab[-1], lab[:, 0], lab[:, -1]]))) - {0}
    outside = ndi.binary_dilation(np.isin(lab, list(border)), iterations=2)
    a[outside, 3] = 0
    a[..., 3] = np.array(Image.fromarray(a[..., 3]).filter(ImageFilter.GaussianBlur(0.8)))
    ys, xs = np.where(a[..., 3] > 20)
    pad = 8
    box = (max(0, xs.min() - pad), max(0, ys.min() - pad), min(a.shape[1], xs.max() + pad), min(a.shape[0], ys.max() + pad))
    clean = Image.fromarray(a).crop(box)
    clean = _fit(clean, 560, 560)
    c = np.array(clean).astype(float)
    lum = (0.299 * c[..., 0] + 0.587 * c[..., 1] + 0.114 * c[..., 2]) / 255

    def tint(col):
        o = np.zeros_like(c)
        o[..., :3] = lum[..., None] * np.array(col)[None, None, :] * 1.5
        o[..., 3] = c[..., 3]
        return Image.fromarray(np.clip(o, 0, 255).astype("uint8"))
    return {"full": clean, "avatar": clean, "joiC": tint((60, 230, 255.)), "joiM": tint((255, 50, 200.))}


_ASSET_FN = {"suhu": _assets_suhu, "miss": _assets_miss, "ironman": _assets_ironman, "joi": _assets_joi}


def _build_assets(cid, src):
    from PIL import Image
    return _ASSET_FN[cid](Image.open(src))


def _png_bytes(im, maxside=None):
    import io
    if maxside:
        im = im.copy()
        im.thumbnail((maxside, maxside))
    buf = io.BytesIO()
    im.save(buf, format="PNG", optimize=True)
    return buf.getvalue()


def _data_url(raw):
    import base64
    return "data:image/png;base64," + base64.b64encode(raw).decode()


@st.cache_resource(show_spinner=False)
def _char_bundle(cid, sig):
    """Siapkan komponen dua arah + data URL cadangan untuk satu karakter. `sig` = (path, mtime) file PNG."""
    errors, assets, comp = [], {}, None
    src = sig[0] if sig else None
    if src:
        try:
            assets = _build_assets(cid, src)
        except Exception as e:
            errors.append(f"assets: {type(e).__name__}: {e}")
            try:
                from PIL import Image
                assets = {"full": Image.open(src).convert("RGBA")}
                assets["avatar"] = assets["full"]
            except Exception:
                assets = {}
    html_doc = build_component_html(cid)
    for base_dir in [Path(__file__).resolve().parent, Path(tempfile.gettempdir())]:
        try:
            d = base_dir / "_agent_component" / cid
            d.mkdir(parents=True, exist_ok=True)
            f = d / "index.html"
            if (not f.exists()) or f.read_text(encoding="utf-8") != html_doc:
                f.write_text(html_doc, encoding="utf-8")
            for name, im in assets.items():
                if name != "full":
                    (d / f"{name}.png").write_bytes(_png_bytes(im))
            comp = components.declare_component(f"agent_avatar_{cid}", path=str(d))
            break
        except Exception as e:
            errors.append(f"{base_dir}: {type(e).__name__}: {e}")
    data_urls = {n: _data_url(_png_bytes(im)) for n, im in assets.items() if n != "full"}
    thumb = _data_url(_png_bytes(assets["full"], 340)) if "full" in assets else None
    return dict(component=comp, has=bool(assets.get("avatar")), errors=errors, data_urls=data_urls, thumb=thumb)


def get_bundle(cid):
    f = _find_char_file(cid)
    sig = (str(f), f.stat().st_mtime) if f else None
    return _char_bundle(cid, sig)


# =========================================================
# HALAMAN PILIH KARAKTER (kartu animasi, latar berbeda tiap karakter)
# =========================================================
CARD_TMPL = r"""<!DOCTYPE html>
<html><head><meta charset="utf-8"><style>
*{box-sizing:border-box;margin:0;padding:0}
body{background:transparent;font-family:'Segoe UI',system-ui,sans-serif;overflow:hidden}
.card{position:relative;height:440px;border-radius:22px;overflow:hidden;color:#fff;background:var(--bg);box-shadow:0 10px 28px rgba(0,0,0,.28);transition:transform .25s}
.card:hover{transform:translateY(-4px)}
.fx,.fx *{pointer-events:none}
.fx{position:absolute;inset:0;overflow:hidden;z-index:1}
.num{position:absolute;top:12px;left:14px;z-index:6;font-weight:800;font-size:12px;letter-spacing:1px;background:rgba(0,0,0,.3);padding:3px 10px;border-radius:12px}
.pic{position:absolute;left:8%;right:8%;bottom:96px;height:270px;z-index:3;animation:float 3.2s ease-in-out infinite}
.pic img{position:absolute;inset:0;width:100%;height:100%;object-fit:contain;display:block;user-select:none}
.plate{position:absolute;left:0;right:0;bottom:0;padding:34px 16px 14px;z-index:5;background:linear-gradient(0deg,rgba(0,0,0,.62),transparent)}
.plate b{display:block;font-size:22px;font-weight:800;letter-spacing:1.6px}
.plate em{display:block;font-style:normal;font-size:12.5px;opacity:.92;margin-top:2px}
.plate small{display:block;font-size:11.5px;opacity:.75;margin-top:5px;line-height:1.35}
@keyframes float{0%,100%{transform:translateY(0) rotate(-1deg)}50%{transform:translateY(-12px) rotate(1.4deg)}}
@keyframes rot{to{transform:rotate(360deg)}}
/*__CSS__*/
</style></head><body>
<div class="card" style="--bg:__BG__">
 <div class="fx">__SCENE__</div>
 <span class="num">__NUM__</span>
 <div class="pic">__PIC__</div>
 <div class="plate"><b>__NAME__</b><em>__TAG__</em><small>__DESC__</small></div>
</div>
<script>
(function(){const fx=document.querySelector('.fx'),id='__ID__';const R=(a,b)=>a+Math.random()*(b-a);
function mk(c,css,t){const e=document.createElement('i');e.className=c;e.style.cssText=css;if(t)e.textContent=t;fx.appendChild(e);}
if(id==='suhu')for(let i=0;i<28;i++)mk('star','left:'+R(0,100)+'%;top:'+R(0,85)+'%;width:'+R(1.5,3.5)+'px;height:'+R(1.5,3.5)+'px;animation-delay:'+R(0,4)+'s;animation-duration:'+R(1.8,4)+'s');
if(id==='miss'){const t=['⏱️','⌛','🕰️','✦','⏳'];for(let i=0;i<11;i++)mk('clk','left:'+R(2,92)+'%;font-size:'+R(14,26)+'px;animation-delay:'+R(0,9)+'s;animation-duration:'+R(7,12)+'s',t[i%t.length]);}
if(id==='ironman')for(let i=0;i<22;i++)mk('bit','left:'+R(0,100)+'%;height:'+R(6,18)+'px;animation-delay:'+R(0,6)+'s;animation-duration:'+R(3,7)+'s');
if(id==='joi')for(let i=0;i<26;i++)mk('drop','left:'+R(0,100)+'%;height:'+R(36,100)+'px;animation-delay:'+R(0,2)+'s;animation-duration:'+R(.9,1.8)+'s;opacity:'+R(.25,.7));
})();
</script></body></html>
"""

_CARD_PIC_SIMPLE = '<img src="__SRC__" alt="">'
_CARD_PIC_HOLO = ('<img class="gc" src="__SRC__" alt=""><img class="gm" src="__SRC__" alt="">'
                  '<img class="a" src="__SRC__" alt=""><img class="gs" src="__SRC__" alt="">'
                  '<b class="scan"></b><b class="beam"></b>')

CARD_SCENES = {
    "suhu": dict(pic=_CARD_PIC_SIMPLE, scene='<b class="cloud ca"></b><b class="cloud cb"></b>', css=r"""
.pic img{filter:drop-shadow(0 0 12px rgba(0,229,255,.4));animation:wob 3.6s ease-in-out infinite;transform-origin:50% 100%}
@keyframes wob{0%,100%{transform:rotate(-2deg)}50%{transform:rotate(2.5deg)}}
.star{position:absolute;border-radius:50%;background:#fff;box-shadow:0 0 6px #bfe6ff;animation:twinkle 3s ease-in-out infinite}
@keyframes twinkle{0%,100%{opacity:.15;transform:scale(.7)}50%{opacity:1;transform:scale(1.25)}}
.cloud{position:absolute;display:block;height:40px;border-radius:50px;background:rgba(255,255,255,.17);filter:blur(7px)}
.ca{width:130px;top:20%;left:-140px;animation:drift 34s linear infinite}.cb{width:100px;top:48%;left:-120px;animation:drift 48s linear infinite;animation-delay:-18s}
@keyframes drift{to{transform:translateX(420px)}}
"""),
    "miss": dict(pic=_CARD_PIC_SIMPLE, scene='<b class="rays"></b><b class="dots"></b>', css=r"""
.pic{animation:mmBounce 1.7s ease-in-out infinite}
@keyframes mmBounce{0%,100%{transform:translateY(0) scale(1.02,.97)}45%{transform:translateY(-16px) scale(.98,1.03)}}
.pic img{filter:drop-shadow(0 8px 10px rgba(80,25,0,.5))}
.rays{position:absolute;left:50%;top:38%;width:800px;height:800px;margin:-400px 0 0 -400px;border-radius:50%;background:repeating-conic-gradient(rgba(255,255,255,.17) 0 7deg,transparent 7deg 18deg);-webkit-mask-image:radial-gradient(circle,#000 8%,transparent 66%);mask-image:radial-gradient(circle,#000 8%,transparent 66%);animation:rot 70s linear infinite}
.dots{position:absolute;inset:0;background-image:radial-gradient(rgba(110,40,0,.26) 1.5px,transparent 1.8px);background-size:13px 13px;-webkit-mask-image:linear-gradient(180deg,transparent 30%,#000);mask-image:linear-gradient(180deg,transparent 30%,#000);opacity:.55}
.clk{position:absolute;bottom:-40px;opacity:0;animation:riseClk linear infinite}
@keyframes riseClk{0%{transform:translateY(0) rotate(0);opacity:0}12%{opacity:.85}85%{opacity:.7}100%{transform:translateY(-480px) rotate(360deg);opacity:0}}
"""),
    "ironman": dict(pic=_CARD_PIC_HOLO, scene='<b class="grid"></b><b class="disc"><u></u><u></u><u></u></b>', css=r"""
.pic img.a{filter:drop-shadow(0 0 3px rgba(0,229,255,.95)) drop-shadow(0 0 14px rgba(0,229,255,.6)) brightness(1.1);animation:holoFlick 3.7s steps(1,end) infinite}
@keyframes holoFlick{0%,100%{opacity:.96}4%{opacity:.62}6%{opacity:1}30%{opacity:.9}32%{opacity:.5}33%{opacity:1}70%{opacity:.97}72%{opacity:.7}74%{opacity:1}}
.pic img.gm{mix-blend-mode:screen;opacity:.5;filter:hue-rotate(150deg) saturate(1.6);animation:jit 2.6s steps(1,end) infinite}
.pic img.gc,.pic img.gs{display:none}
@keyframes jit{0%{transform:translateX(2px)}20%{transform:translateX(-2px)}40%{transform:translateX(3px)}55%{transform:translateX(0)}75%{transform:translateX(-3px)}100%{transform:translateX(2px)}}
.scan{position:absolute;inset:0;background:repeating-linear-gradient(0deg,rgba(0,0,0,.42) 0 1px,transparent 1px 3px);z-index:3}
.beam{position:absolute;left:-4%;right:-4%;height:16%;top:-16%;background:linear-gradient(180deg,transparent,rgba(125,249,255,.4),transparent);mix-blend-mode:screen;animation:beamMove 3.2s linear infinite;z-index:3;-webkit-mask-image:linear-gradient(90deg,transparent,#000 18%,#000 82%,transparent);mask-image:linear-gradient(90deg,transparent,#000 18%,#000 82%,transparent)}
@keyframes beamMove{to{top:100%}}
.grid{position:absolute;left:-30%;right:-30%;bottom:-6%;height:46%;background-image:linear-gradient(rgba(0,229,255,.34) 1px,transparent 1px),linear-gradient(90deg,rgba(0,229,255,.34) 1px,transparent 1px);background-size:38px 38px;transform:perspective(300px) rotateX(64deg);transform-origin:50% 100%;animation:gridMove 1.5s linear infinite;-webkit-mask-image:linear-gradient(0deg,#000 10%,transparent);mask-image:linear-gradient(0deg,#000 10%,transparent)}
@keyframes gridMove{to{background-position:0 38px}}
.disc{position:absolute;left:50%;bottom:20%;width:190px;height:40px;margin-left:-95px}
.disc u{position:absolute;inset:0;border-radius:50%;border:2px solid rgba(0,229,255,.8);box-shadow:0 0 12px rgba(0,229,255,.7);animation:ring 2.4s ease-out infinite}
.disc u:nth-child(2){animation-delay:-.8s}.disc u:nth-child(3){animation-delay:-1.6s}
@keyframes ring{0%{transform:scale(.45);opacity:1}100%{transform:scale(1.25);opacity:0}}
.bit{position:absolute;bottom:-20px;width:2px;background:linear-gradient(0deg,rgba(0,229,255,0),#7ff);animation:riseBit linear infinite;opacity:0}
@keyframes riseBit{0%{transform:translateY(0);opacity:0}15%{opacity:.9}100%{transform:translateY(-480px);opacity:0}}
"""),
    "joi": dict(pic=_CARD_PIC_HOLO, scene='<b class="glow"></b><b class="disc"><u></u><u></u><u></u></b>', css=r"""
.pic img{-webkit-mask-image:linear-gradient(180deg,#000 66%,transparent 99%);mask-image:linear-gradient(180deg,#000 66%,transparent 99%)}
.pic img.a{filter:saturate(1.3) brightness(1.15) drop-shadow(0 0 10px rgba(255,63,210,.6)) drop-shadow(0 0 24px rgba(120,90,255,.45));animation:joiFlick 4.1s steps(1,end) infinite}
@keyframes joiFlick{0%,100%{opacity:.94}3%{opacity:.55}5%{opacity:1}28%{opacity:.85}30%{opacity:.45}31%{opacity:1}64%{opacity:.96}66%{opacity:.68}68%{opacity:1}88%{opacity:.8}89%{opacity:1}}
.pic img.gc,.pic img.gm{mix-blend-mode:screen;opacity:.55}
.pic img.gc{filter:grayscale(1) sepia(1) hue-rotate(150deg) saturate(6) brightness(1.4);animation:rgbL 2.9s steps(1,end) infinite}
.pic img.gm{filter:grayscale(1) sepia(1) hue-rotate(270deg) saturate(6) brightness(1.3);animation:rgbR 2.9s steps(1,end) infinite}
@keyframes rgbL{0%{transform:translateX(-3px)}25%{transform:translateX(-5px)}50%{transform:translateX(-2px)}75%{transform:translateX(-6px)}100%{transform:translateX(-3px)}}
@keyframes rgbR{0%{transform:translateX(3px)}25%{transform:translateX(5px)}50%{transform:translateX(2px)}75%{transform:translateX(6px)}100%{transform:translateX(3px)}}
.pic img.gs{opacity:0;mix-blend-mode:screen;filter:hue-rotate(40deg) brightness(1.4);animation:joiSlice 5s steps(1,end) infinite}
@keyframes joiSlice{0%,86%{opacity:0}87%{opacity:.9;clip-path:inset(10% 0 80% 0);transform:translateX(-12px)}89%{clip-path:inset(46% 0 40% 0);transform:translateX(14px)}91%{clip-path:inset(68% 0 14% 0);transform:translateX(-10px)}93%{clip-path:inset(24% 0 62% 0);transform:translateX(9px)}95%{clip-path:inset(56% 0 26% 0);transform:translateX(-7px)}97%,100%{opacity:0;clip-path:inset(0);transform:none}}
.scan{position:absolute;inset:0;background:repeating-linear-gradient(0deg,rgba(0,0,0,.45) 0 1px,transparent 1px 3px);z-index:3}
.beam{position:absolute;left:-4%;right:-4%;height:15%;top:-15%;background:linear-gradient(180deg,transparent,rgba(255,120,230,.32),transparent);mix-blend-mode:screen;animation:beamMove 3.6s linear infinite;z-index:3;-webkit-mask-image:linear-gradient(90deg,transparent,#000 18%,#000 82%,transparent);mask-image:linear-gradient(90deg,transparent,#000 18%,#000 82%,transparent)}
@keyframes beamMove{to{top:100%}}
.glow{position:absolute;left:0;right:0;bottom:0;height:50%;background:radial-gradient(ellipse at 50% 100%,rgba(255,40,190,.4),rgba(90,60,255,.12) 45%,transparent 68%);animation:glowBreath 4s ease-in-out infinite}
@keyframes glowBreath{0%,100%{opacity:.7}50%{opacity:1}}
.disc{position:absolute;left:50%;bottom:20%;width:190px;height:40px;margin-left:-95px}
.disc u{position:absolute;inset:0;border-radius:50%;border:2px solid rgba(255,63,210,.85);box-shadow:0 0 12px rgba(255,63,210,.7);animation:ring 2.6s ease-out infinite}
.disc u:nth-child(2){animation-delay:-.87s}.disc u:nth-child(3){animation-delay:-1.73s}
@keyframes ring{0%{transform:scale(.45);opacity:1}100%{transform:scale(1.25);opacity:0}}
.drop{position:absolute;top:-110px;width:1.5px;background:linear-gradient(180deg,rgba(143,176,255,0),rgba(143,176,255,.8));animation:dropFall linear infinite}
@keyframes dropFall{to{transform:translateY(560px)}}
"""),
}


def card_html(cid, src, num):
    C, SC = CHARACTERS[cid], CARD_SCENES[cid]
    pic = SC["pic"].replace("__SRC__", src or "")
    return (CARD_TMPL.replace("/*__CSS__*/", SC["css"]).replace("__SCENE__", SC["scene"]).replace("__PIC__", pic)
            .replace("__BG__", C["theme"]["bg"]).replace("__NUM__", f"{num}")
            .replace("__NAME__", htmllib.escape(C["name"])).replace("__TAG__", htmllib.escape(C["tagline"]))
            .replace("__DESC__", htmllib.escape(C["desc"])).replace("__ID__", cid))


def render_html_frame(page, height):
    if hasattr(st, "iframe"):          # Streamlit terbaru (components.html sudah deprecated)
        st.iframe(page, height=height)
    else:
        components.html(page, height=height)


def render_selector():
    ss = st.session_state
    st.markdown("""<style>
    .stApp { background: linear-gradient(180deg, #0b1020 0%, #151c33 55%, #1b2340 100%) !important; }
    .sel-title { font-size: 2.3rem; font-weight: 800; color: #ffffff; margin-bottom: 2px; }
    .sel-sub { color: #aab6d3; font-size: 1.05rem; margin-bottom: 20px; }
    </style>""", unsafe_allow_html=True)
    st.markdown('<div class="sel-title">🎭 Pilih Karakter Avatar AI</div>', unsafe_allow_html=True)
    st.markdown('<div class="sel-sub">Semua karakter punya kemampuan yang sama — beda tampilan, suara, dan nama panggilan. '
                'Nama AI mengikuti karakter yang kamu pilih, dan itu juga kata panggilnya (wake word).</div>', unsafe_allow_html=True)
    if ss.get("picked"):
        if st.button(f"↩️ Kembali ke {CHARACTERS[ss.char]['name']}"):
            ss.page = "agent"
            st.rerun()
    cols = st.columns(4, gap="medium")
    for i, cid in enumerate(CHAR_ORDER):
        C, b = CHARACTERS[cid], get_bundle(cid)
        with cols[i]:
            render_html_frame(card_html(cid, b["thumb"], i + 1), 450)
            if not b["has"]:
                st.caption(f"⚠️ `{C['files'][0]}` tidak ditemukan — taruh di folder yang sama dengan file ini.")
            is_cur = bool(ss.get("picked")) and ss.char == cid
            if _btn(("✅ Aktif — " if is_cur else "Pilih ") + C["name"], key=f"pick_{cid}",
                    type="primary" if is_cur else "secondary"):
                ss.char, ss.page, ss.picked = cid, "agent", True
                ss.chat = []
                ss.speak = {"id": (ss.get("speak") or {"id": 0})["id"] + 1,
                            "text": C["lines"]["intro_speech"].format(s=C["spoken"]),
                            "display": C["lines"]["intro_cap"], "mood": "happy"}
                ss.speak_new = True
                st.rerun()


def _btn(label, **kw):
    """st.button selebar kolom, kompatibel Streamlit lama & baru."""
    try:
        return st.button(label, width="stretch", **kw)
    except TypeError:
        return st.button(label, use_container_width=True, **kw)


# =========================================================
# PILIH HALAMAN & KARAKTER
# =========================================================
ss = st.session_state
ss.setdefault("page", "pilih")
ss.setdefault("char", "suhu")
ss.setdefault("picked", False)
if ss.char not in CHARACTERS:
    ss.char = "suhu"
if ss.page == "pilih":
    render_selector()
    st.stop()

PERSONA = CHARACTERS[ss.char]
PN, PS = PERSONA["name"], PERSONA["spoken"]          # nama tampilan & ejaan untuk suara
BUNDLE = get_bundle(ss.char)
suhu_component, HAS_AVATAR, COMP_ERRORS = BUNDLE["component"], BUNDLE["has"], BUNDLE["errors"]
st.markdown(f"<style>.stApp {{ background: {PERSONA['page_bg']} !important; }}</style>", unsafe_allow_html=True)

BT_MODES = {
    "trend": "Trend-following (win rate rendah, payoff besar)",
    "target": "Pullback + target cepat (win rate tinggi, payoff kecil)",
}

# =========================================================
# SIDEBAR
# =========================================================
DEFAULT_IDX = ("BBCA,BBRI,BMRI,BBNI,TLKM,ASII,UNVR,ICBP,INDF,KLBF,ADRO,PTBA,ANTM,INCO,MDKA,ITMG,AMRT,CPIN,"
               "GOTO,BRIS,ARTO,SMGR,UNTR,PGAS,EXCL,ISAT,MAPI,ACES,TOWR,AMMN")
DEFAULT_US = "AAPL,MSFT,NVDA,GOOGL,AMZN,META,TSLA,AVGO,JPM,V"

with st.sidebar:
    sidebar_account(ACCESS)
    st.markdown("---")
    st.markdown(f"### {PERSONA['emoji']} Karakter: {PN}")
    if _btn("🎭 Ganti Karakter", key="chg_char"):
        ss.page = "pilih"
        st.rerun()
    st.markdown("---")
    st.markdown(f"### ⚙️ Pengaturan {PN}")
    market = st.selectbox("Market", ["IDX (Bursa Efek Indonesia)", "US (NYSE/NASDAQ)"])
    IDX = market.startswith("IDX")
    SUFFIX = ".JK" if IDX else ""
    chart_period = st.select_slider("Periode chart", options=["3mo", "6mo", "1y", "2y"], value="6mo")
    horizon = st.select_slider("Horizon prediksi (hari bursa)", options=[5, 10, 20, 40, 60], value=20)
    n_sims = st.select_slider("Jumlah simulasi Monte Carlo", options=[1000, 2000, 5000, 10000, 20000], value=5000)
    capital = st.number_input("Modal (Rp)" if IDX else "Modal ($)", min_value=1_000.0,
                              value=100_000_000.0 if IDX else 10_000.0, step=1_000_000.0 if IDX else 1_000.0)
    risk_pct = st.slider("Risiko per trade (% modal)", 0.5, 5.0, 1.5, 0.5) / 100
    max_pos = st.slider("Maks. posisi paper trading", 1, 10, 5)
    bt_mode = st.selectbox("Strategi backtest", list(BT_MODES), index=1, format_func=lambda k: BT_MODES[k])
    watch_raw = st.text_area("Watchlist screening (pisahkan koma)", value=DEFAULT_IDX if IDX else DEFAULT_US, height=110)

    st.markdown("---")
    st.markdown(f"### 🔊 Suara {PN}")
    v_pitch = st.slider("Nada (tinggi = suara imut, rendah = berat)", 0.5, 2.0, float(PERSONA["pitch"]), 0.05, key=f"pitch_{ss.char}")
    v_rate = st.slider("Kecepatan bicara", 0.7, 1.5, float(PERSONA["rate"]), 0.05, key=f"rate_{ss.char}")
    v_robot = st.checkbox("Efek beep robot", value=bool(PERSONA["robot"]), key=f"robot_{ss.char}")
    st.caption("Tips: Edge/Windows memberi suara Indonesia lokal (pitch berpengaruh). "
               "Suara 'Google' di Chrome kadang mengabaikan pitch.")

    use_ai, api_key, model_choice = False, "", "claude-sonnet-5-5"
    if IS_ADMIN:   # pelanggan tidak melihat bagian ini (menghindari biaya API Anda & kebocoran key)
        st.markdown("---")
        st.markdown("### 🧠 Narasi AI tambahan (opsional, admin)")
        use_ai = st.checkbox("Aktifkan narasi Claude", value=False)
        try:
            secret_key = st.secrets.get("ANTHROPIC_API_KEY", "")
        except Exception:
            secret_key = ""
        api_key = st.text_input("Anthropic API Key", value="", type="password") or secret_key or os.environ.get("ANTHROPIC_API_KEY", "")
        model_choice = st.selectbox("Model", ["claude-sonnet-5-5", "claude-haiku-4-5-20251001"])

    st.markdown("---")
    broker_csv = st.file_uploader("📊 CSV broker summary (opsional)", type=["csv"])
    if st.button("🗑️ Reset paper trading"):
        st.session_state.pop("paper", None)
        st.rerun()

CTX = dict(
    idx=IDX, suffix=SUFFIX, horizon=int(horizon), n_sims=int(n_sims), capital=float(capital), risk=float(risk_pct),
    max_alloc=0.25, bars={"3mo": 63, "6mo": 126, "1y": 252, "2y": 504}[chart_period], lot=100 if IDX else 1,
    fee_buy=0.0015 if IDX else 0.0005, fee_sell=0.0025 if IDX else 0.0005, max_pos=int(max_pos), bt_mode=bt_mode,
    cur="Rp" if IDX else "$",
)
WATCH = [x.strip().upper().replace(".JK", "") for x in watch_raw.replace("\n", ",").split(",") if x.strip()]

# =========================================================
# DATA (yfinance — gratis)
# =========================================================
OHLCV = ["Open", "High", "Low", "Close", "Volume"]


def _clean(df):
    if df is None or len(df) == 0:
        return pd.DataFrame(columns=OHLCV)
    if isinstance(df.columns, pd.MultiIndex):
        df.columns = df.columns.get_level_values(0)
    if not all(c in df.columns for c in OHLCV):
        return pd.DataFrame(columns=OHLCV)
    df = df[OHLCV].copy()
    idx = pd.DatetimeIndex(df.index)
    if idx.tz is not None:
        idx = idx.tz_localize(None)
    df.index = idx
    df = df[~df.index.duplicated()].sort_index()
    df = df.dropna(subset=["Close"])
    df["Volume"] = df["Volume"].fillna(0)
    return df[(df["Close"] > 0)]


MIN_BARS = 70  # minimal hari bursa agar Monte Carlo & indikator layak dihitung


@st.cache_data(ttl=900, show_spinner=False)
def _fetch_ok(ticker: str, period: str, with_info: bool):
    """Hanya hasil BERHASIL yang di-cache (exception tidak pernah di-cache)."""
    t = yf.Ticker(ticker)
    best = pd.DataFrame(columns=OHLCV)
    for per in dict.fromkeys([period, "max", "5y"]):
        try:
            h = _clean(t.history(period=per, auto_adjust=True))
        except Exception:
            h = pd.DataFrame(columns=OHLCV)
        if len(h) > len(best):
            best = h
        if len(best) >= MIN_BARS:
            break
    if len(best) < MIN_BARS:  # jalur alternatif: yf.download
        try:
            h = _clean(yf.download(ticker, period="max", auto_adjust=True, progress=False))
            if len(h) > len(best):
                best = h
        except Exception:
            pass
    if len(best) == 0:
        raise RuntimeError("Yahoo Finance mengembalikan data kosong")
    info = {}
    if with_info:
        try:
            info = t.info or {}
        except Exception:
            info = {}
    return best, info


def fetch_data(ticker: str, period: str = "3y", with_info: bool = True):
    try:
        return _fetch_ok(ticker, period, with_info)
    except Exception:
        return pd.DataFrame(columns=OHLCV), {}


@st.cache_data(ttl=900, show_spinner=False)
def fetch_batch(tickers: tuple, period: str = "3y"):
    out = {}
    try:
        raw = yf.download(list(tickers), period=period, auto_adjust=True, group_by="ticker",
                          threads=True, progress=False)
        for tk in tickers:
            try:
                df = raw[tk] if isinstance(raw.columns, pd.MultiIndex) else raw
                df = _clean(df.copy())
                if len(df) > 0:
                    out[tk] = df
            except Exception:
                pass
    except Exception:
        pass
    missing = [tk for tk in tickers if tk not in out][:8]
    for tk in missing:
        try:
            h, _ = fetch_data(tk, period, False)
            if len(h) > 0:
                out[tk] = h
        except Exception:
            pass
    return out


# =========================================================
# INDIKATOR & SKOR
# =========================================================
def _wilder(s, n):
    return s.ewm(alpha=1 / n, adjust=False, min_periods=n).mean()


def add_indicators(df):
    d = df.copy()
    c, h, l, v = d["Close"], d["High"], d["Low"], d["Volume"]
    d["ret"] = np.log(c).diff()
    for n in (20, 50, 200):
        d[f"ema{n}"] = c.ewm(span=n, adjust=False).mean()
    delta = c.diff()
    up, dn = delta.clip(lower=0), -delta.clip(upper=0)
    rs = _wilder(up, 14) / _wilder(dn, 14).replace(0, 1e-12)
    d["rsi"] = (100 - 100 / (1 + rs)).fillna(50)
    pc = c.shift(1)
    tr = pd.concat([h - l, (h - pc).abs(), (l - pc).abs()], axis=1).max(axis=1)
    d["atr"] = _wilder(tr, 14).bfill().fillna(c * 0.02)
    macd = c.ewm(span=12, adjust=False).mean() - c.ewm(span=26, adjust=False).mean()
    d["macd"], d["macd_sig"] = macd, macd.ewm(span=9, adjust=False).mean()
    d["macd_hist"] = d["macd"] - d["macd_sig"]
    ma20, sd20 = c.rolling(20).mean(), c.rolling(20).std()
    d["bb_mid"], d["bb_up"], d["bb_lo"] = ma20, ma20 + 2 * sd20, ma20 - 2 * sd20
    d["pctb"] = ((c - d["bb_lo"]) / (d["bb_up"] - d["bb_lo"]).replace(0, np.nan)).fillna(0.5)
    d["vol_ratio"] = (v / v.rolling(20).mean().replace(0, np.nan)).fillna(1.0)
    d["obv"] = (np.sign(delta.fillna(0)) * v).cumsum()
    d["obv_ma20"] = d["obv"].rolling(20).mean()
    tp = (h + l + c) / 3
    mf = tp * v
    pos = mf.where(tp > tp.shift(1), 0).rolling(14).sum()
    neg = mf.where(tp < tp.shift(1), 0).rolling(14).sum().replace(0, np.nan)
    d["mfi"] = (100 - 100 / (1 + pos / neg)).fillna(50)
    d["vol_now"] = np.sqrt((d["ret"].fillna(0) ** 2).ewm(alpha=0.06, adjust=False).mean())
    return d


def system_score(d):
    """Skor sistem 0-100 per hari (hanya memakai data masa lalu -> aman untuk backtest)."""
    c = d["Close"]
    s = pd.Series(0.0, index=d.index)
    s += np.where(c > d["ema20"], 8, 0) + np.where(d["ema20"] > d["ema50"], 10, 0)
    s += np.where(d["ema50"] > d["ema50"].shift(5), 6, 0) + np.where(c > d["ema200"], 6, 0)
    rsi = d["rsi"]
    s += np.select([(rsi >= 50) & (rsi <= 68), (rsi >= 40) & (rsi < 50), (rsi > 68) & (rsi <= 78)], [15, 8, 7], 0)
    s += np.where(d["macd_hist"] > 0, 6, 0) + np.where(d["macd_hist"] > d["macd_hist"].shift(1), 4, 0)
    s += np.where(d["obv"] > d["obv_ma20"], 8, 0) + np.where((d["mfi"] >= 45) & (d["mfi"] <= 80), 6, 0)
    s += np.where((d["vol_ratio"] > 1.2) & (d["ret"] > 0), 6, 0)
    ext = (c - d["ema20"]) / d["atr"].replace(0, np.nan)
    s += np.where(ext < 2.5, 8, 0) + np.where(d["pctb"] < 0.9, 7, 0)
    med = d["vol_now"].rolling(120, min_periods=30).median()
    s += np.where(d["vol_now"] < med, 10, 0)
    return s.clip(0, 100)


# --- QVTA (selaras dengan 2___AI_Screening.py) ---
def quant_score(hist):
    r = hist["Close"].pct_change().dropna()
    if len(r) < 20:
        return 50.0, 0.0, 0.5
    m, sd = r.iloc[-20:].mean(), r.iloc[-20:].std()
    if not sd or np.isnan(sd):
        return 50.0, 0.0, 0.5
    z = m / (sd / np.sqrt(20))
    p = stats.norm.cdf(z)
    return p * 100, z, p


def volume_score(hist):
    if len(hist) < 21:
        return 50.0, 1.0, False
    avg = hist["Volume"].iloc[-20:].mean()
    ratio = hist["Volume"].iloc[-1] / avg if avg else 1.0
    chg = hist["Close"].pct_change().iloc[-1]
    return float(min(100, max(0, (ratio - 0.5) / 2.5 * 100))), float(ratio), bool(ratio > 1.5 and chg > 0)


def technical_score(hist):
    c = hist["Close"]
    score, sig = 0, []
    delta = c.diff()
    gain = delta.where(delta > 0, 0).rolling(14).mean()
    loss = -delta.where(delta < 0, 0).rolling(14).mean()
    rsi = (100 - 100 / (1 + gain / loss.replace(0, 1e-12))).iloc[-1]
    rsi = 50 if pd.isna(rsi) else float(rsi)
    if 30 < rsi < 50:
        score += 25; sig.append(f"RSI {rsi:.1f} — zona pemulihan oversold")
    elif 50 <= rsi < 70:
        score += 20; sig.append(f"RSI {rsi:.1f} — momentum bullish")
    macd = c.ewm(span=12).mean() - c.ewm(span=26).mean()
    sl = macd.ewm(span=9).mean()
    if len(macd) > 1 and macd.iloc[-1] > sl.iloc[-1] and macd.iloc[-2] <= sl.iloc[-2]:
        score += 35; sig.append("MACD golden crossover ✅")
    elif macd.iloc[-1] > sl.iloc[-1]:
        score += 20; sig.append("MACD di atas signal line")
    if len(c) >= 200 and c.rolling(50).mean().iloc[-1] > c.rolling(200).mean().iloc[-1]:
        score += 20; sig.append("Golden Cross (MA50 > MA200) 🌟")
    if len(c) >= 20 and c.iloc[-1] > c.rolling(20).mean().iloc[-1]:
        score += 20; sig.append("Harga di atas MA20")
    return min(100, score), sig, rsi


def fundamental_score(info):
    keys = ["trailingPE", "returnOnEquity", "revenueGrowth", "earningsGrowth"]
    if not info or not any(info.get(k) for k in keys):
        return 50.0, ["Data fundamental tidak tersedia — dinilai netral"]
    score, sig = 0, []
    pe = info.get("trailingPE")
    if pe and pe < 16:
        score += 30; sig.append(f"P/E {pe:.1f} — undervalued")
    elif pe and pe < 20:
        score += 15; sig.append(f"P/E {pe:.1f} — fair value")
    roe = info.get("returnOnEquity")
    if roe and roe > 0.15:
        score += 25; sig.append(f"ROE {roe*100:.1f}% — return kuat")
    rg = info.get("revenueGrowth")
    if rg and rg > 0.10:
        score += 25; sig.append(f"Pertumbuhan revenue {rg*100:.1f}%")
    eg = info.get("earningsGrowth")
    if eg and eg > 0.10:
        score += 20; sig.append(f"Pertumbuhan EPS {eg*100:.1f}%")
    return min(100, score), sig


def qvta_composite(tk, hist, info):
    q, z, pu = quant_score(hist)
    v, vr, acc = volume_score(hist)
    t, ts, rsi = technical_score(hist)
    f, fs = fundamental_score(info)
    comp = q * 0.35 + v * 0.30 + t * 0.20 + f * 0.15
    return dict(ticker=tk, qvta_score=round(comp, 1), q_score=round(q, 1), v_score=round(v, 1), t_score=round(t, 1),
                f_score=round(f, 1), prob_upward=round(pu * 100, 1), volume_ratio=round(vr, 2),
                is_accumulation=acc, rsi=round(rsi, 1), signals=ts + fs)


def qvta_badge(s):
    return ("🔥 Strong Buy" if s >= 80 else "✅ Buy" if s >= 60 else "⚠️ Neutral / Watch" if s >= 40
            else "🔻 Weak / Avoid" if s >= 20 else "❌ Strong Avoid")


# --- Bandarmology (dari 2___AI_Screening.py) ---
def bandarmology_analysis(hist):
    if len(hist) < 25:
        return {"signal": "Data tidak cukup", "net_accumulation": 0, "obv_trend": "N/A", "mfi": 50.0,
                "accumulation_days_20d": 0, "distribution_days_20d": 0}
    c, h, l, v = hist["Close"], hist["High"], hist["Low"], hist["Volume"]
    rng = (h - l).replace(0, np.nan)
    pos = (c - l) / rng
    vr = v / v.rolling(20).mean()
    acc = int(((pos > 0.75) & (vr > 1.5)).iloc[-20:].sum())
    dist = int(((pos < 0.25) & (vr > 1.5)).iloc[-20:].sum())
    net = acc - dist
    obv = (np.sign(c.diff()) * v).cumsum()
    obv_tr = "Bullish (smart money masuk)" if obv.rolling(5).mean().iloc[-1] > obv.rolling(20).mean().iloc[-1] \
        else "Bearish (smart money keluar)"
    tp = (h + l + c) / 3
    mf = tp * v
    pm = mf.where(tp > tp.shift(1), 0).rolling(14).sum()
    nm = mf.where(tp < tp.shift(1), 0).rolling(14).sum().replace(0, np.nan)
    mfi = (100 - 100 / (1 + pm / nm)).iloc[-1]
    mfi = 50.0 if pd.isna(mfi) else float(mfi)
    sig = ("🟢 Indikasi akumulasi (smart money buying)" if net >= 3 else
           "🔴 Indikasi distribusi (smart money selling)" if net <= -3 else "🟡 Netral / sideways")
    return {"signal": sig, "accumulation_days_20d": acc, "distribution_days_20d": dist, "net_accumulation": net,
            "obv_trend": obv_tr, "mfi": round(mfi, 1)}


def broker_flow_from_csv(df):
    cols = {c.lower().strip(): c for c in df.columns}
    bc = next((cols[c] for c in cols if "broker" in c), None)
    nc = next((cols[c] for c in cols if "net" in c), None)
    buy = next((cols[c] for c in cols if "buy" in c), None)
    sell = next((cols[c] for c in cols if "sell" in c), None)
    if nc is None and buy and sell:
        df["net_calc"] = pd.to_numeric(df[buy], errors="coerce") - pd.to_numeric(df[sell], errors="coerce")
        nc = "net_calc"
    if bc is None or nc is None:
        return None
    df = df[[bc, nc]].dropna()
    df[nc] = pd.to_numeric(df[nc], errors="coerce")
    df = df.dropna().sort_values(nc, ascending=False)
    fn = df[df[bc].astype(str).str.contains("asing|foreign", case=False, na=False)][nc].sum()
    return {"top_buy": df.head(5).rename(columns={bc: "Broker", nc: "Net"}),
            "top_sell": df.tail(5).sort_values(nc).rename(columns={bc: "Broker", nc: "Net"}),
            "total_net": df[nc].sum(), "foreign_net": fn}


def bandar_summary(hist, broker):
    close = hist["Close"].dropna()
    vol = hist["Volume"].reindex(close.index).fillna(0)
    if len(close) < 20:
        return {"status": "Data tidak cukup", "reason": "Minimal 20 hari data.", "buy_price": None, "support": None}
    rc, rv = close.iloc[-20:], vol.iloc[-20:]
    dr = rc.pct_change().fillna(0)
    upv, dnv = rv[dr > 0].sum(), rv[dr < 0].sum()
    bias = (upv - dnv) / max(upv + dnv, 1)
    bn = broker["total_net"] if broker else 0
    if broker and bn > 0 and bias >= -0.1:
        st_, rs_ = "Akumulasi", "Net broker positif dan tekanan volume beli dominan."
    elif broker and bn < 0 and bias <= 0.1:
        st_, rs_ = "Distribusi", "Net broker negatif dan tekanan volume jual dominan."
    elif bias > 0.1:
        st_, rs_ = "Akumulasi (proxy price-volume)", "Volume hari naik lebih dominan; data broker belum ada."
    elif bias < -0.1:
        st_, rs_ = "Distribusi (proxy price-volume)", "Volume hari turun lebih dominan; data broker belum ada."
    else:
        st_, rs_ = "Netral", "Belum ada dominasi akumulasi atau distribusi yang kuat."
    cur, ma20, sup = float(close.iloc[-1]), float(rc.mean()), float(rc.min())
    return {"status": st_, "reason": rs_, "support": sup, "current_price": cur,
            "buy_price": max(sup, min(cur, ma20)) if "Akumulasi" in st_ else None}


def bandar_score(b):
    net = b.get("net_accumulation", 0)
    obv = 1 if "Bullish" in str(b.get("obv_trend", "")) else -1
    return float(np.clip(50 + 6 * net + 10 * obv + (b.get("mfi", 50) - 50) * 0.3, 0, 100))


# =========================================================
# MONTE CARLO (Filtered Historical Simulation)
# =========================================================
def monte_carlo(close, horizon=20, n_sims=5000, seed=42, shrink=0.35):
    c = close.dropna().astype(float)
    r = np.log(c).diff().dropna().iloc[-750:]
    if len(r) < 60:
        raise ValueError("Data terlalu pendek untuk Monte Carlo")
    var = r.pow(2).ewm(alpha=0.06, adjust=False).mean()
    sig_hist = np.sqrt(var.shift(1)).reindex(r.index)
    mu = float(r.mean())
    z = ((r - mu) / sig_hist).replace([np.inf, -np.inf], np.nan).dropna()
    z = (z - z.mean()) / (z.std() or 1.0)
    sig_now = float(np.sqrt(var.iloc[-1]))
    lr = float(r.std())
    blended = 0.6 * sig_now + 0.4 * float(r.iloc[-250:].std())
    sig_path = np.array([lr + (blended - lr) * (0.97 ** t) for t in range(1, horizon + 1)])
    rng = np.random.default_rng(seed)
    eps = rng.choice(z.values, size=(n_sims, horizon), replace=True)
    lret = shrink * mu + sig_path * eps
    s0 = float(c.iloc[-1])
    paths = np.hstack([np.full((n_sims, 1), s0), s0 * np.exp(np.cumsum(lret, axis=1))])
    return {"paths": paths, "s0": s0, "sigma_daily": blended, "mu_daily": shrink * mu}


def mc_summary(paths):
    s0, T = paths[:, 0], paths[:, -1]
    rets = T / s0 - 1
    q5 = np.percentile(rets, 5)
    return {"prob_up": float((T > s0).mean()), "exp_ret": float(rets.mean()), "median": float(np.median(T)),
            "pct": {q: float(np.percentile(T, q)) for q in (5, 25, 50, 75, 95)},
            "var95": float(-q5), "cvar95": float(-rets[rets <= q5].mean()),
            "p_gain5": float((rets > 0.05).mean()), "p_loss5": float((rets < -0.05).mean()), "rets": rets}


def first_passage(paths, tp, sl):
    body = paths[:, 1:]
    htp, hsl = body >= tp, body <= sl
    big = 10 ** 9
    t_tp = np.where(htp.any(1), htp.argmax(1), big)
    t_sl = np.where(hsl.any(1), hsl.argmax(1), big)
    p_tp = float((t_tp < t_sl).mean())
    p_sl = float(((t_sl < t_tp) | ((t_sl == t_tp) & (t_sl < big))).mean())
    return {"p_tp": p_tp, "p_sl": p_sl, "p_none": max(0.0, 1 - p_tp - p_sl)}


# =========================================================
# RENCANA TRADING (tick IDX, ATR, support, sizing)
# =========================================================
def tick_size(p, idx):
    if not idx:
        return 0.01
    return 1 if p < 200 else 2 if p < 500 else 5 if p < 2000 else 10 if p < 5000 else 25


def rnd(p, idx, mode="nearest"):
    t = tick_size(p, idx)
    f = {"nearest": round, "down": math.floor, "up": math.ceil}[mode]
    v = f(p / t) * t
    return float(v) if idx else round(float(v), 2)


def size_position(capital, entry, stop, risk, max_alloc, lot):
    rps = max(entry - stop, 1e-9)
    sh = min(capital * risk / rps, capital * max_alloc / entry)
    return int(math.floor(sh / lot) * lot)


def trade_plan(d, paths, composite, ctx):
    idx = ctx["idx"]
    last = d.iloc[-1]
    price = float(last["Close"])
    atr = float(last["atr"]) or price * 0.02
    cands = [last["ema20"], last["ema50"], last["bb_lo"], d["Low"].iloc[-20:].min(), d["Low"].iloc[-10:].min()]
    below = [float(x) for x in cands if pd.notna(x) and x < price * 0.995]
    support = max(below) if below else price - 1.5 * atr
    if composite >= 70:
        lo, hi = price - 0.5 * atr, price
    else:
        lo = max(support, price - 1.5 * atr)
        hi = max(lo, price - 0.4 * atr)
    entry = (lo + hi) / 2
    stop = min(lo - 1.0 * atr, support - 0.5 * atr)
    if (entry - stop) / entry > 0.12:
        stop = entry * 0.88
    R = entry - stop
    tp1, tp2 = entry + 1.5 * R, entry + 2.5 * R
    tp3 = min(max(entry + 4 * R, float(np.percentile(paths[:, -1], 90))), entry + 6 * R)
    lo, hi, entry = rnd(lo, idx), rnd(hi, idx), rnd(entry, idx)
    stop = rnd(stop, idx, "down")
    tp1, tp2, tp3 = rnd(tp1, idx, "up"), rnd(tp2, idx, "up"), rnd(tp3, idx, "up")
    R = max(entry - stop, tick_size(entry, idx))
    fp1, fp2 = first_passage(paths, tp1, stop), first_passage(paths, tp2, stop)
    ev_r = fp1["p_tp"] * ((tp1 - entry) / R) - fp1["p_sl"]
    shares = size_position(ctx["capital"], entry, stop, ctx["risk"], ctx["max_alloc"], ctx["lot"])
    trail = rnd(max(float(last["ema20"]), price - 2 * atr), idx, "down")
    return dict(price=price, atr=atr, support=rnd(support, idx), entry_lo=lo, entry_hi=hi, entry=entry, stop=stop,
                tp1=tp1, tp2=tp2, tp3=tp3, rr=(tp2 - entry) / R, risk_pct=R / entry, fp1=fp1, fp2=fp2, ev_r=ev_r,
                touch={k: float((paths.max(axis=1) >= v).mean()) for k, v in (("tp1", tp1), ("tp2", tp2), ("tp3", tp3))},
                shares=shares, lots=shares // ctx["lot"], cost=shares * entry, risk_amt=shares * R, trail=trail,
                exit_signal=bool(price < last["ema20"] and last["macd_hist"] < 0))


def decide(composite, plan, ms, d):
    trend_ok = d["Close"].iloc[-1] > d["ema50"].iloc[-1]
    ev, pu = plan["ev_r"], ms["prob_up"]
    if composite >= 72 and ev > 0 and pu >= 0.52 and trend_ok:
        return "🔥 STRONG BUY", "bull"
    if composite >= 60 and ev > 0:
        return "✅ BUY (bertahap)", "bull"
    if composite >= 45:
        return "⚠️ HOLD / WATCH", "neutral"
    if composite >= 30:
        return "🔻 REDUCE / HINDARI", "bear"
    return "❌ SELL / AVOID", "bear"


# =========================================================
# VALIDASI: HIT-RATE WALK-FORWARD & BACKTEST
# =========================================================
def signal_quality(d, score, H=10, thr=65):
    fwd = d["Close"].shift(-H) / d["Close"] - 1
    valid = fwd.notna() & score.notna() & (np.arange(len(d)) >= 60)
    buy = (score >= thr) & (d["Close"] > d["ema50"]) & valid
    n = int(buy.sum())
    base = float((fwd[valid] > 0).mean()) if valid.any() else float("nan")
    if n < 5:
        return {"n": n, "hit": float("nan"), "lo": float("nan"), "base": base, "avg": float("nan"),
                "avg_all": float("nan"), "pf": float("nan"), "H": H}
    f = fwd[buy]
    p, z = float((f > 0).mean()), 1.96
    lo = (p + z * z / (2 * n) - z * math.sqrt(p * (1 - p) / n + z * z / (4 * n * n))) / (1 + z * z / n)
    gains, losses = f[f > 0].sum(), -f[f < 0].sum()
    return {"n": n, "hit": p, "lo": lo, "base": base, "avg": float(f.mean()), "avg_all": float(fwd[valid].mean()),
            "pf": float(gains / losses) if losses > 0 else float("inf"), "H": H}


def backtest(d, score, ctx, mode="trend", entry_thr=65, exit_thr=45, atr_stop=2.0, trail=2.5, max_hold=40,
             tp_atr=1.0, stop_atr_t=2.0, hold_t=15, warm=60):
    """mode='trend'  : masuk saat skor kuat, keluar via trailing stop (banyak cut-loss kecil, sedikit profit besar).
       mode='target' : beli saat koreksi sehat dalam uptrend, ambil untung cepat di tp_atr x ATR, stop tetap,
                       batas waktu hold_t hari -> win rate tinggi, tetapi payoff per kemenangan kecil."""
    o, h, l, c = (d[k].values for k in ("Open", "High", "Low", "Close"))
    atr, ema50, ema20, rsi = (d[k].values for k in ("atr", "ema50", "ema20", "rsi"))
    sc = score.values
    n, lot, init = len(d), ctx["lot"], ctx["capital"]
    cash, pos, eq, trades = init, None, [], []
    pend_in = pend_out = False
    for i in range(warm, n):
        if pos is not None:
            px, why = None, None
            if mode == "trend":
                stop_eff = max(pos["stop0"], pos["hh"] - trail * pos["atr"])
                if o[i] <= stop_eff:
                    px, why = o[i], "Stop/Trailing (gap)"
                elif l[i] <= stop_eff:
                    px, why = stop_eff, "Stop/Trailing"
                elif pend_out:
                    px, why = o[i], "Sinyal keluar"
            else:
                if o[i] <= pos["stop0"]:
                    px, why = o[i], "Stop Loss (gap)"
                elif l[i] <= pos["stop0"]:
                    px, why = pos["stop0"], "Stop Loss"          # konservatif: stop dianggap kena lebih dulu
                elif o[i] >= pos["tp"]:
                    px, why = o[i], "Take Profit (gap)"
                elif h[i] >= pos["tp"]:
                    px, why = pos["tp"], "Take Profit"
                elif pend_out:
                    px, why = o[i], "Batas waktu"
            if px is not None:
                cash += pos["sh"] * px * (1 - ctx["fee_sell"])
                trades.append(dict(Masuk=d.index[pos["i"]], Keluar=d.index[i], HargaMasuk=pos["px"], HargaKeluar=px,
                                   Return=px * (1 - ctx["fee_sell"]) / (pos["px"] * (1 + ctx["fee_buy"])) - 1,
                                   Alasan=why, Hari=i - pos["i"]))
                pos = None
            else:
                pos["hh"] = max(pos["hh"], c[i])
        elif pend_in:
            px = o[i]
            sd = (atr_stop if mode == "trend" else stop_atr_t) * atr[i - 1]
            stop0 = px - sd
            sh = min(size_position(cash, px, stop0, ctx["risk"], 1.0, lot),
                     int(cash / (px * (1 + ctx["fee_buy"]) * lot)) * lot)
            if sh > 0 and stop0 > 0:
                cash -= sh * px * (1 + ctx["fee_buy"])
                pos = dict(i=i, px=px, sh=sh, stop0=stop0, hh=c[i], atr=atr[i - 1], tp=px + tp_atr * atr[i - 1])
        eq.append(cash + (pos["sh"] * c[i] if pos else 0))
        if mode == "trend":
            pend_in = pos is None and sc[i] >= entry_thr and c[i] > ema50[i]
            pend_out = pos is not None and (sc[i] < exit_thr or (i - pos["i"]) >= max_hold)
        else:
            dip = c[i] <= ema20[i] * 1.01 and rsi[i] < 55
            pend_in = pos is None and sc[i] >= 50 and c[i] > ema50[i] and ema20[i] > ema50[i] and dip
            pend_out = pos is not None and (i - pos["i"]) >= hold_t
    eqs = pd.Series(eq, index=d.index[warm:])
    tr = pd.DataFrame(trades)
    dr = eqs.pct_change().dropna()
    yrs = max(len(eqs) / 252, 1e-9)
    bh = d["Close"].iloc[warm:] / d["Close"].iloc[warm] * init
    res = dict(mode=mode, equity=eqs, bh=bh, trades=tr, total_ret=float(eqs.iloc[-1] / init - 1),
               bh_ret=float(bh.iloc[-1] / init - 1), cagr=float((eqs.iloc[-1] / init) ** (1 / yrs) - 1),
               sharpe=float(dr.mean() / dr.std() * math.sqrt(252)) if len(dr) > 2 and dr.std() > 0 else 0.0,
               maxdd=float((eqs / eqs.cummax() - 1).min()), n_trades=len(tr))
    if len(tr):
        w, lz = tr[tr["Return"] > 0]["Return"], tr[tr["Return"] <= 0]["Return"]
        payoff = float(w.mean() / -lz.mean()) if len(w) and len(lz) and lz.mean() < 0 else float("nan")
        res.update(win=float(len(w) / len(tr)), avg_trade=float(tr["Return"].mean()), payoff=payoff,
                   breakeven=float(1 / (1 + payoff)) if payoff == payoff and payoff > 0 else float("nan"),
                   pf=float(w.sum() / -lz.sum()) if lz.sum() < 0 else float("inf"))
    else:
        res.update(win=float("nan"), avg_trade=float("nan"), payoff=float("nan"), breakeven=float("nan"), pf=float("nan"))
    return res


# =========================================================
# ANALISA LENGKAP SATU SAHAM
# =========================================================
def analyze_df(tk, hist, info, ctx, broker=None, full=True):
    if hist is None or len(hist) < MIN_BARS:
        return None
    d = add_indicators(hist)
    score = system_score(d)
    sys_now = float(score.iloc[-1])
    h1 = hist.iloc[-252:]
    qv = qvta_composite(tk, h1, info)
    band = bandarmology_analysis(h1)
    mc = monte_carlo(d["Close"], ctx["horizon"], ctx["n_sims"])
    ms = mc_summary(mc["paths"])
    mc_comp = float(np.clip(50 + (ms["prob_up"] - 0.5) * 400, 0, 100))
    composite = 0.30 * qv["qvta_score"] + 0.30 * sys_now + 0.25 * mc_comp + 0.15 * bandar_score(band)
    plan = trade_plan(d, mc["paths"], composite, ctx)
    decision, mood = decide(composite, plan, ms, d)
    A = dict(tk=tk, d=d, score=score, sys_now=sys_now, qv=qv, band=band, mc=mc, ms=ms, plan=plan, composite=composite,
             decision=decision, mood=mood, sq=signal_quality(d, score), info=info,
             bandar=bandar_summary(h1, broker))
    if full:
        if len(d) >= 150:
            A["bt_all"] = {m: backtest(d, score, ctx, mode=m) for m in BT_MODES}
            A["bt"] = A["bt_all"][ctx.get("bt_mode", "trend")]
        else:
            A["bt_all"], A["bt"] = {}, None
    A["n_bars"] = len(d)
    return A


# =========================================================
# PAPER TRADING (simulasi — tidak ada order sungguhan)
# =========================================================
def paper_init(cap):
    return {"cash": cap, "start": cap, "pos": {}, "pending": [], "log": []}


def paper_equity(p, prices):
    return p["cash"] + sum(v["shares"] * prices.get(k, v["entry"]) for k, v in p["pos"].items())


def _sell(p, tk, pos, shares, px, why, date, ctx):
    shares = min(shares, pos["shares"])
    p["cash"] += shares * px * (1 - ctx["fee_sell"])
    pos["shares"] -= shares
    p["log"].append(dict(Tanggal=str(date)[:10], Aksi="JUAL", Saham=tk, Harga=px, Lot=shares / ctx["lot"],
                         PnL=round(shares * (px - pos["entry"]), 0), Catatan=why))
    if pos["shares"] <= 0:
        p["pos"].pop(tk, None)


def _buy(p, tk, shares, px, A, date, ctx):
    cost = shares * px * (1 + ctx["fee_buy"])
    if shares <= 0 or cost > p["cash"]:
        return False
    p["cash"] -= cost
    pl = A["plan"]
    p["pos"][tk] = dict(entry=px, shares=shares, stop=pl["stop"], tp1=pl["tp1"], tp2=pl["tp2"], tp1_done=False,
                        checked=A["d"].index[-1], opened=str(date)[:10])
    p["log"].append(dict(Tanggal=str(date)[:10], Aksi="BELI", Saham=tk, Harga=px, Lot=shares / ctx["lot"],
                         PnL=0, Catatan=f"SL {pl['stop']} | TP1 {pl['tp1']} | TP2 {pl['tp2']}"))
    return True


def paper_step(p, analyses, data, ctx):
    """Kelola posisi & order pending berdasarkan bar terbaru, lalu buka posisi baru dari sinyal BUY."""
    events = []
    for tk, pos in list(p["pos"].items()):
        df = data.get(tk)
        if df is None:
            continue
        for dt_, bar in df[df.index > pos["checked"]].iterrows():
            if tk not in p["pos"]:
                break
            if bar["Low"] <= pos["stop"]:
                _sell(p, tk, pos, pos["shares"], min(bar["Open"], pos["stop"]),
                      "Stop Loss" if pos["stop"] < pos["entry"] else "Stop di titik impas/trailing", dt_, ctx)
                events.append(f"{tk} kena stop"); break
            if not pos["tp1_done"] and bar["High"] >= pos["tp1"]:
                half = int(math.floor(pos["shares"] / 2 / ctx["lot"]) * ctx["lot"])
                if half > 0:
                    _sell(p, tk, pos, half, pos["tp1"], "Take Profit 1 (50%)", dt_, ctx)
                    events.append(f"{tk} TP1")
                pos["stop"], pos["tp1_done"] = max(pos["stop"], pos["entry"]), True
            if tk in p["pos"] and bar["High"] >= pos["tp2"]:
                _sell(p, tk, pos, pos["shares"], pos["tp2"], "Take Profit 2", dt_, ctx)
                events.append(f"{tk} TP2"); break
            pos["checked"] = dt_
    keep = []
    for o in p["pending"]:
        df = data.get(o["tk"])
        if df is None:
            continue
        bars = df[df.index > o["created"]]
        if len(bars) > 5:
            events.append(f"order {o['tk']} kedaluwarsa"); continue
        hit = bars[bars["Low"] <= o["limit"]]
        if len(hit) and o["tk"] not in p["pos"]:
            b = hit.iloc[0]
            if _buy(p, o["tk"], o["shares"], rnd(float(min(o["limit"], b["Open"])), ctx["idx"]), o["A"], hit.index[0], ctx):
                events.append(f"order {o['tk']} terisi"); continue
        keep.append(o)
    p["pending"] = keep
    prices = {k: float(v["Close"].iloc[-1]) for k, v in data.items() if len(v)}
    eq = paper_equity(p, prices)
    for A in sorted(analyses, key=lambda a: -a["composite"]):
        tk = A["tk"]
        if "BUY" not in A["decision"] or tk in p["pos"] or any(o["tk"] == tk for o in p["pending"]):
            continue
        if len(p["pos"]) + len(p["pending"]) >= ctx["max_pos"]:
            break
        pl = A["plan"]
        sh = size_position(eq, pl["entry"], pl["stop"], ctx["risk"], ctx["max_alloc"], ctx["lot"])
        if sh <= 0:
            continue
        if pl["price"] <= pl["entry_hi"]:
            if _buy(p, tk, sh, pl["price"], A, A["d"].index[-1], ctx):
                events.append(f"beli {tk}")
        else:
            p["pending"].append(dict(tk=tk, limit=pl["entry_hi"], shares=sh, created=A["d"].index[-1], A=A))
            events.append(f"pasang limit {tk} @ {pl['entry_hi']}")
    return events, prices


# =========================================================
# BAHASA & PERINTAH (NLU ringan berbasis aturan, Bahasa Indonesia)
# =========================================================
ALIASES = {"BANK BCA": "BBCA", "BCA": "BBCA", "BRI": "BBRI", "MANDIRI": "BMRI", "BNI": "BBNI", "TELKOM": "TLKM",
           "ASTRA": "ASII", "UNILEVER": "UNVR", "INDOFOOD": "INDF", "ADARO": "ADRO", "ANTAM": "ANTM", "GOJEK": "GOTO",
           "TOKOPEDIA": "GOTO", "BUKIT ASAM": "PTBA", "VALE": "INCO", "MERDEKA": "MDKA", "KALBE": "KLBF",
           "AMMAN": "AMMN", "SAMPOERNA": "HMSP", "GUDANG GARAM": "GGRM", "APPLE": "AAPL", "NVIDIA": "NVDA",
           "MICROSOFT": "MSFT", "TESLA": "TSLA", "GOOGLE": "GOOGL", "AMAZON": "AMZN"}
STOP = set("""BELI JUAL HARGA BISA TOLONG CARI SAHAM YANG DAN UNTUK APA INI ITU DONG SUHU MISS MINUTES IRON MAN IRONMAN JOI JOY MAU DARI KAMU AKU BAIK HALO HAI
COBA TOP BANTU LIHAT TAMPIL MONTE CARLO ATAU SIAPA NAMA NAIK TURUN BESOK MINGGU BULAN HARI AUTO AJA SAJA MANA SIAP
ANALISA ANALISIS CEK TARGET STOP LOSS TAKE PROFIT ENTRY SINYAL BERAPA KAPAN GIMANA BAGAIMANA PREDIKSI SIMULASI
BACKTEST SCREENING TERBAIK BAGUS PASAR PAPER TRADING OTOMATIS ROBOT JALANKAN HASIL DATA DENGAN PADA ADA TIDAK""".split())


def extract_ticker(text):
    t = text.upper()
    for k, v in sorted(ALIASES.items(), key=lambda kv: -len(kv[0])):
        if re.search(r"\b" + re.escape(k) + r"\b", t):
            return v
    toks = re.findall(r"\b[A-Z0-9]{3,5}\b", t)
    for tok in toks:
        if tok in WATCH:
            return tok
    m = re.search(r"\b(?:[A-Z]\s){3,4}[A-Z]\b", t)
    if m:
        return m.group(0).replace(" ", "")
    for tok in toks:
        if tok not in STOP and tok.isalpha() and len(tok) in ((4,) if CTX["idx"] else (3, 4, 5)):
            return tok
    return None


def detect_intent(text):
    t = text.lower()
    has_tk = extract_ticker(text) is not None
    if re.search(r"(auto ?pilot|otomatis|robot trading|paper|jalankan trading|trading sendiri)", t):
        return "autopilot"
    if re.search(r"(backtest|back test|uji historis|akurasi|riwayat sinyal)", t):
        return "backtest"
    if re.search(r"(monte|carlo|prediksi|ramal|proyeksi|forecast|simulasi)", t):
        return "mc"
    if re.search(r"(harga beli|harga jual|beli di|kapan beli|kapan jual|take profit|stop loss|entry|trade plan|rencana|target|rekomendasi|saran)", t):
        return "plan" if has_tk else "screen"
    if re.search(r"(screening|skrining|screener|cari saham|saham bagus|saham apa|top saham|peluang|scan|saham terbaik)", t):
        return "screen"
    if re.search(r"(siapa kamu|siapa namamu|namamu|kenalan)", t):
        return "who"
    if re.search(r"(terima kasih|makasih|thanks)", t):
        return "thanks"
    if re.search(r"(lucu|lawak|joke|hibur|cerita)", t):
        return "joke"
    if re.search(r"(bantuan|bisa apa|help|fitur|perintah apa)", t):
        return "help"
    if has_tk:
        return "analyze"
    if re.search(r"(halo|hai|hello|selamat|hey|hi\b)", t):
        return "greet"
    return "unknown"


JOKES = ["Dulu teriak: Hei antek antek asing! Kini malah ngemis karna market merah bikin pusing",
         "Aku AI, tapi portofolioku nggak pernah merah... soalnya cuma paper trading! Hehe!",
         "Kata analis: pasar itu seperti kopi. Kalau panas jangan buru-buru ditelan, tunggu pullback!"]
def help_txt():
    return ("Aku bisa: skrining saham, analisa lengkap, prediksi Monte Carlo, rekomendasi harga beli dan jual, backtest, "
            f"dan auto pilot paper trading. Coba bilang: {PS}, analisa B B C A. Atau: cari saham bagus. "
            "Atau: prediksi TLKM. Atau: jalankan auto pilot.")


def sp(tk):
    return " ".join(tk.replace(".JK", ""))


def num(x, ctx):
    return f"{x:.0f}" if ctx["idx"] else f"{x:.2f}".replace(".", " koma ")


def plain(s):
    return re.sub(r"[^\w\s/()-]", "", s).strip()


def fmt(x, ctx):
    return f"{x:,.0f}" if ctx["idx"] else f"{x:,.2f}"


def speech_single(intent, A, ctx):
    pl, ms, tk = A["plan"], A["ms"], A["tk"].replace(".JK", "")
    n = lambda x: num(x, ctx)
    base = f"{sp(tk)} ditutup di {n(pl['price'])}. "
    if intent == "mc":
        return (base + f"Simulasi Monte Carlo {ctx['horizon']} hari: peluang naik {ms['prob_up']*100:.0f} persen. "
                f"Harga median {n(ms['median'])}, rentang sembilan puluh persen {n(ms['pct'][5])} sampai {n(ms['pct'][95])}. "
                f"Risiko turun lebih dari lima persen {ms['p_loss5']*100:.0f} persen. Grafiknya ada di tab Monte Carlo.")
    if intent == "backtest":
        bt = A["bt"]
        return (base + f"Backtest strategi: return {bt['total_ret']*100:.0f} persen, buy and hold {bt['bh_ret']*100:.0f} persen. "
                f"Win rate {0 if math.isnan(bt['win']) else bt['win']*100:.0f} persen dari {bt['n_trades']} transaksi, drawdown maksimum {abs(bt['maxdd'])*100:.0f} persen. Ini data historis, bukan jaminan ya!")
    if intent == "plan":
        return (base + f"Zona beli {n(pl['entry_lo'])} sampai {n(pl['entry_hi'])}. Stop loss {n(pl['stop'])}. "
                f"Target satu {n(pl['tp1'])}, target dua {n(pl['tp2'])}, target tiga {n(pl['tp3'])}. "
                f"Rasio risiko banding hasil {pl['rr']:.1f}. Keputusanku: {plain(A['decision'])}.")
    return (base + f"Skor {PS} {A['composite']:.0f} dari seratus. Keputusanku: {plain(A['decision'])}. "
            f"Peluang naik {ctx['horizon']} hari ke depan {ms['prob_up']*100:.0f} persen. "
            f"Zona beli {n(pl['entry_lo'])} sampai {n(pl['entry_hi'])}, stop loss {n(pl['stop'])}, target dua {n(pl['tp2'])}. "
            "Detail lengkap ada di layar!")


def build_narasi(A, ctx):
    pl, ms, sq, tk = A["plan"], A["ms"], A["sq"], A["tk"]
    d = A["d"]
    last = d.iloc[-1]
    trend = ("uptrend kuat (harga di atas EMA20 & EMA50)" if last["Close"] > last["ema20"] > last["ema50"] else
             "uptrend moderat" if last["Close"] > last["ema50"] else "downtrend / di bawah EMA50")
    txt = (f"**{tk}** ditutup di **{ctx['cur']} {fmt(pl['price'], ctx)}** dengan skor {PN} **{A['composite']:.0f}/100** → "
           f"**{A['decision']}**. Tren: {trend}. Monte Carlo {ctx['horizon']} hari memberi peluang naik "
           f"**{ms['prob_up']*100:.0f}%**, median {ctx['cur']} {fmt(ms['median'], ctx)}, VaR 95% {ms['var95']*100:.1f}%. "
           f"Rencana: beli di zona **{fmt(pl['entry_lo'], ctx)}–{fmt(pl['entry_hi'], ctx)}**, stop loss **{fmt(pl['stop'], ctx)}** "
           f"(risiko {pl['risk_pct']*100:.1f}%), TP1/TP2/TP3 **{fmt(pl['tp1'], ctx)} / {fmt(pl['tp2'], ctx)} / {fmt(pl['tp3'], ctx)}**. "
           f"Peluang TP1 tercapai sebelum stop: {pl['fp1']['p_tp']*100:.0f}% (EV {pl['ev_r']:+.2f}R). ")
    if not math.isnan(sq["hit"]):
        txt += (f"Validasi historis: sinyal beli serupa naik dalam {sq['H']} hari pada **{sq['hit']*100:.0f}%** kasus "
                f"(n={sq['n']}, batas bawah 95%: {sq['lo']*100:.0f}%) vs base rate {sq['base']*100:.0f}%.")
    if pl["exit_signal"]:
        txt += " ⚠️ Peringatan: harga di bawah EMA20 dengan MACD negatif — pemegang saham pertimbangkan mengurangi posisi."
    return txt


def call_ai_llm(prompt):
    try:
        import anthropic
    except ImportError:
        return None, "Library `anthropic` belum terinstall."
    if not api_key:
        return None, "API key Anthropic belum diisi."
    try:
        r = anthropic.Anthropic(api_key=api_key).messages.create(
            model=model_choice, max_tokens=800, messages=[{"role": "user", "content": prompt}])
        return "".join(b.text for b in r.content if getattr(b, "type", "") == "text"), None
    except Exception as e:
        return None, f"Gagal memanggil Claude API: {e}"


def ai_prompt(A):
    pl = {k: v for k, v in A["plan"].items() if k in ("price", "entry_lo", "entry_hi", "stop", "tp1", "tp2", "tp3", "rr", "ev_r")}
    payload = dict(ticker=A["tk"], skor=round(A["composite"], 1), keputusan=A["decision"], qvta=A["qv"],
                   bandar=A["band"], prob_naik_mc=round(A["ms"]["prob_up"], 3), rencana=pl,
                   validasi={k: v for k, v in A["sq"].items()})
    return ("Kamu analis kuantitatif saham Indonesia. Data hasil screening:\n"
            f"{json.dumps(payload, indent=2, default=str)}\n\nTulis analisis singkat Bahasa Indonesia (maks 180 kata): "
            "kesimpulan Buy/Hold/Avoid, makna sinyal bandarmology, satu risiko utama. Tutup dengan 1 kalimat disclaimer edukasi.")


# =========================================================
# VISUALISASI
# =========================================================
def gauge(score, title=None):
    title = title or f"{PN} Score"
    f = go.Figure(go.Indicator(mode="gauge+number", value=score, title={"text": title}, gauge={
        "axis": {"range": [0, 100]}, "bar": {"color": "#0077C8"},
        "steps": [{"range": [0, 20], "color": "#fee2e2"}, {"range": [20, 40], "color": "#fed7aa"},
                  {"range": [40, 60], "color": "#fef08a"}, {"range": [60, 80], "color": "#bbf7d0"},
                  {"range": [80, 100], "color": "#86efac"}]}))
    f.update_layout(height=270, margin=dict(l=20, r=20, t=40, b=10), paper_bgcolor="rgba(0,0,0,0)")
    return f


def price_chart(A, ctx):
    d = A["d"].iloc[-ctx["bars"]:]
    pl = A["plan"]
    fig = make_subplots(rows=3, cols=1, shared_xaxes=True, row_heights=[0.62, 0.18, 0.20], vertical_spacing=0.03)
    fig.add_trace(go.Candlestick(x=d.index, open=d["Open"], high=d["High"], low=d["Low"], close=d["Close"], name="Harga",
                                 increasing_line_color="#16a34a", decreasing_line_color="#dc2626"), 1, 1)
    for col, nm, clr in (("ema20", "EMA20", "#f59e0b"), ("ema50", "EMA50", "#7c3aed"), ("bb_up", "BB atas", "#94a3b8"),
                         ("bb_lo", "BB bawah", "#94a3b8")):
        fig.add_trace(go.Scatter(x=d.index, y=d[col], name=nm, line=dict(width=1.2 if "BB" not in nm else 0.8, color=clr,
                                                                      dash="dot" if "BB" in nm else "solid")), 1, 1)
    fig.add_hrect(y0=pl["entry_lo"], y1=pl["entry_hi"], fillcolor="rgba(34,197,94,.18)", line_width=0, row=1, col=1,
                  annotation_text="Zona Beli", annotation_position="top left")
    for y, nm, clr in ((pl["stop"], "Stop Loss", "#dc2626"), (pl["tp1"], "TP1", "#0ea5e9"), (pl["tp2"], "TP2", "#0284c7"),
                       (pl["tp3"], "TP3", "#1d4ed8")):
        fig.add_hline(y=y, line=dict(color=clr, dash="dash", width=1.2), annotation_text=f"{nm} {fmt(y, ctx)}",
                      annotation_position="right", row=1, col=1)
    fig.add_trace(go.Bar(x=d.index, y=d["Volume"], name="Volume", marker_color="#93c5fd"), 2, 1)
    fig.add_trace(go.Scatter(x=d.index, y=d["rsi"], name="RSI", line=dict(color="#0a2540", width=1.4)), 3, 1)
    fig.add_hline(y=70, line=dict(color="#dc2626", dash="dot", width=.8), row=3, col=1)
    fig.add_hline(y=30, line=dict(color="#16a34a", dash="dot", width=.8), row=3, col=1)
    fig.update_xaxes(rangeslider_visible=False, rangebreaks=[dict(bounds=["sat", "mon"])])
    fig.update_layout(height=680, margin=dict(l=10, r=70, t=20, b=10), legend=dict(orientation="h", y=1.04),
                      paper_bgcolor="rgba(0,0,0,0)", plot_bgcolor="white")
    return fig


def mc_fan(A, n_hist=60):
    d, paths = A["d"], A["mc"]["paths"]
    H = paths.shape[1] - 1
    xs = [d.index[-1]] + list(pd.bdate_range(d.index[-1] + pd.Timedelta(days=1), periods=H))
    q = lambda p: np.percentile(paths, p, axis=0)
    fig = go.Figure()
    for k in range(25):
        fig.add_trace(go.Scatter(x=xs, y=paths[k], mode="lines", line=dict(width=.6, color="rgba(100,116,139,.25)"),
                                 showlegend=False, hoverinfo="skip"))
    for lo, hi, col, nm in ((5, 95, "rgba(0,119,200,.13)", "Rentang 90%"), (25, 75, "rgba(0,119,200,.28)", "Rentang 50%")):
        fig.add_trace(go.Scatter(x=xs + xs[::-1], y=list(q(hi)) + list(q(lo))[::-1], fill="toself", fillcolor=col,
                                 line=dict(width=0), name=nm, hoverinfo="skip"))
    h = d["Close"].iloc[-n_hist:]
    fig.add_trace(go.Scatter(x=h.index, y=h.values, name="Harga", line=dict(color="#0a2540", width=2)))
    fig.add_trace(go.Scatter(x=xs, y=q(50), name="Median", line=dict(color="#f59e0b", width=2.5)))
    fig.update_layout(height=430, margin=dict(l=10, r=10, t=20, b=10), paper_bgcolor="rgba(0,0,0,0)", plot_bgcolor="white",
                      legend=dict(orientation="h", y=1.08))
    return fig


def card(label, value, color="#0a2540"):
    return f'<div class="score-card"><small>{label}</small><h2 style="color:{color}">{value}</h2></div>'


# =========================================================
# RENDER HASIL
# =========================================================
def render_ticker(R, ctx):
    A = R["A"]
    pl, ms, sq, bt, tk = A["plan"], A["ms"], A["sq"], A.get("bt"), A["tk"]
    st.markdown(f"## {tk} — {A['decision']}")
    if A.get("n_bars", 999) < 250:
        st.warning(f"Riwayat data hanya {A['n_bars']} hari bursa — indikator jangka panjang (EMA200, validasi, backtest) "
                   "kurang andal atau tidak dihitung. Perlakukan hasil dengan ekstra hati-hati.")
    g1, g2 = st.columns([1, 2])
    with g1:
        st.plotly_chart(gauge(round(A["composite"], 1)), width="stretch", key="g_main")
    with g2:
        c1, c2, c3, c4 = st.columns(4)
        c1.metric("Q — Quant", A["qv"]["q_score"]); c2.metric("V — Volume", A["qv"]["v_score"])
        c3.metric("T — Technical", A["qv"]["t_score"]); c4.metric("F — Fundamental", A["qv"]["f_score"])
        c5, c6, c7, c8 = st.columns(4)
        c5.metric("Skor Sistem", f"{A['sys_now']:.0f}"); c6.metric(f"P(naik {ctx['horizon']}h)", f"{ms['prob_up']*100:.0f}%")
        c7.metric("RSI", A["qv"]["rsi"]); c8.metric("Volume ratio", f"{A['qv']['volume_ratio']}x")
        st.markdown("".join(f"<span class='signal-chip'>{htmllib.escape(s)}</span>" for s in A["qv"]["signals"]),
                    unsafe_allow_html=True)
    t1, t2, t3, t4, t5 = st.tabs(["📌 Rencana Trading", "📈 Chart", "🎲 Monte Carlo", "🕵️ Bandarmology", "🧪 Backtest Quant"])
    with t1:
        cc = st.columns(4)
        cc[0].markdown(card("ZONA BELI", f"{fmt(pl['entry_lo'], ctx)} – {fmt(pl['entry_hi'], ctx)}", "#16a34a"), unsafe_allow_html=True)
        cc[1].markdown(card("STOP LOSS", fmt(pl["stop"], ctx), "#dc2626"), unsafe_allow_html=True)
        cc[2].markdown(card("TARGET JUAL (TP1/2/3)", f"{fmt(pl['tp1'], ctx)} / {fmt(pl['tp2'], ctx)} / {fmt(pl['tp3'], ctx)}", "#0077C8"), unsafe_allow_html=True)
        cc[3].markdown(card("RISK : REWARD (TP2)", f"1 : {pl['rr']:.1f}"), unsafe_allow_html=True)
        st.write("")
        cc = st.columns(4)
        cc[0].markdown(card("UKURAN POSISI", f"{pl['lots']:,} {'lot' if ctx['idx'] else 'saham'}"), unsafe_allow_html=True)
        cc[1].markdown(card("NILAI BELI", f"{ctx['cur']} {pl['cost']:,.0f}"), unsafe_allow_html=True)
        cc[2].markdown(card("RISIKO UANG", f"{ctx['cur']} {pl['risk_amt']:,.0f}"), unsafe_allow_html=True)
        cc[3].markdown(card("TRAILING STOP", fmt(pl["trail"], ctx)), unsafe_allow_html=True)
        st.write("")
        p1, p2 = st.columns(2)
        p1.markdown(f"**Peluang (Monte Carlo, penutupan harian):** TP1 sebelum SL **{pl['fp1']['p_tp']*100:.0f}%** · "
                    f"TP2 sebelum SL **{pl['fp2']['p_tp']*100:.0f}%** · kena SL dulu **{pl['fp1']['p_sl']*100:.0f}%** · "
                    f"EV **{pl['ev_r']:+.2f}R**")
        p2.markdown(f"**Peluang menyentuh:** TP1 {pl['touch']['tp1']*100:.0f}% · TP2 {pl['touch']['tp2']*100:.0f}% · TP3 {pl['touch']['tp3']*100:.0f}%")
        st.markdown(f'<div class="verdict-box">{build_narasi(A, ctx)}</div>', unsafe_allow_html=True)
        st.markdown("#### ✅ Validasi akurasi sinyal (walk-forward, tanpa look-ahead)")
        if math.isnan(sq["hit"]):
            st.info("Sinyal beli historis terlalu sedikit untuk dievaluasi pada saham ini.")
        else:
            v1, v2, v3, v4 = st.columns(4)
            v1.metric(f"Hit-rate naik {sq['H']}h", f"{sq['hit']*100:.0f}%", f"{(sq['hit']-sq['base'])*100:+.0f} pt vs base")
            v2.metric("Batas bawah 95%", f"{sq['lo']*100:.0f}%"); v3.metric("Jumlah sinyal", sq["n"])
            v4.metric("Profit factor", "∞" if sq["pf"] == float("inf") else f"{sq['pf']:.2f}")
            st.caption("Sinyal berurutan saling berkorelasi, jadi n efektif lebih kecil dari jumlah di atas. "
                       "Tidak ada model yang menjamin akurasi tinggi — gunakan angka ini sebagai gambaran jujur, bukan janji.")
        if use_ai:
            with st.spinner("Claude menyusun narasi..."):
                txt, err = call_ai_llm(ai_prompt(A))
            st.markdown("#### 🤖 AI Verdict (Claude)")
            st.warning(err) if err else st.markdown(f'<div class="verdict-box">{txt}</div>', unsafe_allow_html=True)
    with t2:
        st.plotly_chart(price_chart(A, ctx), width="stretch", key="chart_price")
    with t3:
        st.plotly_chart(mc_fan(A), width="stretch", key="chart_mc")
        m1, m2, m3, m4, m5 = st.columns(5)
        m1.metric("P(naik)", f"{ms['prob_up']*100:.0f}%"); m2.metric("Ekspektasi return", f"{ms['exp_ret']*100:+.1f}%")
        m3.metric("VaR 95%", f"{ms['var95']*100:.1f}%"); m4.metric("CVaR 95%", f"{ms['cvar95']*100:.1f}%")
        m5.metric("P(untung >5%)", f"{ms['p_gain5']*100:.0f}%")
        pc = pd.DataFrame({"Persentil": ["5%", "25%", "50%", "75%", "95%"],
                           "Harga": [fmt(ms["pct"][q], ctx) for q in (5, 25, 50, 75, 95)],
                           "Return": [f"{(ms['pct'][q]/pl['price']-1)*100:+.1f}%" for q in (5, 25, 50, 75, 95)]})
        h = go.Figure(go.Histogram(x=ms["rets"] * 100, nbinsx=60, marker_color="#0077C8"))
        h.add_vline(x=0, line=dict(color="#dc2626", dash="dash"))
        h.update_layout(height=260, margin=dict(l=10, r=10, t=10, b=10), xaxis_title="Return akhir (%)",
                        paper_bgcolor="rgba(0,0,0,0)", plot_bgcolor="white")
        a, b = st.columns([1, 2])
        a.dataframe(pc, hide_index=True, width="stretch"); b.plotly_chart(h, width="stretch", key="chart_hist")
        st.caption(f"Metode: Filtered Historical Simulation ({ctx['n_sims']:,} jalur) — residual historis distandarisasi "
                   "dengan volatilitas EWMA, volatilitas kembali ke rata-rata jangka panjang, drift disusutkan (shrinkage) "
                   "agar tidak overfit.")
    with t4:
        band, bandar = A["band"], A["bandar"]
        b1, b2, b3, b4 = st.columns(4)
        b1.metric("Sinyal", band["signal"].split(" ", 1)[-1]); b2.metric("Net Akumulasi (20d)", band["net_accumulation"])
        b3.metric("OBV Trend", "Bullish" if "Bullish" in band["obv_trend"] else "Bearish"); b4.metric("MFI", band["mfi"])
        broker = R.get("broker")
        if broker:
            bc1, bc2 = st.columns(2)
            bc1.markdown("**Top 5 Net Buy**"); bc1.dataframe(broker["top_buy"], hide_index=True, width="stretch")
            bc2.markdown("**Top 5 Net Sell**"); bc2.dataframe(broker["top_sell"], hide_index=True, width="stretch")
            st.metric("Foreign Net Flow", f"{broker['foreign_net']:,.0f}")
        else:
            st.info("Upload CSV broker summary di sidebar untuk top buyer/seller & foreign flow riil. "
                    "Saat ini memakai proxy price-volume.")
        s1, s2, s3 = st.columns(3)
        s1.metric("Status", bandar["status"]); s2.metric("Harga terakhir", fmt(bandar["current_price"], ctx) if bandar.get("current_price") else "-")
        s3.metric("Estimasi harga beli", fmt(bandar["buy_price"], ctx) if bandar.get("buy_price") else "Tunggu / hindari")
        st.caption(bandar["reason"] + (f" Support 20 hari: {fmt(bandar['support'], ctx)}" if bandar.get("support") else ""))
    with t5:
        if bt is None:
            st.info("Backtest memerlukan minimal 150 hari data.")
        else:
            st.caption(f"Strategi aktif: **{BT_MODES[bt['mode']]}** (ganti di sidebar).")
            k = st.columns(6)
            k[0].metric("Return strategi", f"{bt['total_ret']*100:+.1f}%"); k[1].metric("Buy & Hold", f"{bt['bh_ret']*100:+.1f}%")
            k[2].metric("CAGR", f"{bt['cagr']*100:+.1f}%"); k[3].metric("Sharpe", f"{bt['sharpe']:.2f}")
            k[4].metric("Max Drawdown", f"{bt['maxdd']*100:.1f}%"); k[5].metric("Transaksi", bt["n_trades"])
            if bt["n_trades"]:
                k = st.columns(5)
                k[0].metric("Win rate", f"{bt['win']*100:.0f}%")
                k[1].metric("Win rate impas", "-" if math.isnan(bt["breakeven"]) else f"{bt['breakeven']*100:.0f}%",
                            help="Win rate minimum agar strategi tidak rugi, dihitung dari payoff ratio.")
                k[2].metric("Payoff (rata² untung / rugi)", "-" if math.isnan(bt["payoff"]) else f"{bt['payoff']:.2f}")
                k[3].metric("Ekspektasi/trade", f"{bt['avg_trade']*100:+.2f}%")
                k[4].metric("Profit factor", "∞" if bt["pf"] == float("inf") else f"{bt['pf']:.2f}")
                if not math.isnan(bt["breakeven"]) and bt["win"] < bt["breakeven"]:
                    st.warning("Win rate masih di bawah titik impas pada strategi ini — secara matematis rugi setelah fee.")
            if A.get("bt_all"):
                cmp_rows = []
                for m, r in A["bt_all"].items():
                    cmp_rows.append({"Strategi": BT_MODES[m], "Win rate %": None if math.isnan(r["win"]) else round(r["win"] * 100),
                                     "Impas %": None if math.isnan(r["breakeven"]) else round(r["breakeven"] * 100),
                                     "Payoff": None if math.isnan(r["payoff"]) else round(r["payoff"], 2),
                                     "Return %": round(r["total_ret"] * 100, 1), "Max DD %": round(r["maxdd"] * 100, 1),
                                     "Trade": r["n_trades"]})
                st.dataframe(pd.DataFrame(cmp_rows), hide_index=True, width="stretch")
            f = go.Figure()
            f.add_trace(go.Scatter(x=bt["equity"].index, y=bt["equity"].values, name=f"Strategi {PN}", line=dict(color="#0077C8", width=2.5)))
            f.add_trace(go.Scatter(x=bt["bh"].index, y=bt["bh"].values, name="Buy & Hold", line=dict(color="#94a3b8", width=1.5)))
            f.update_layout(height=340, margin=dict(l=10, r=10, t=10, b=10), paper_bgcolor="rgba(0,0,0,0)", plot_bgcolor="white")
            st.plotly_chart(f, width="stretch", key="chart_bt")
            if bt["n_trades"]:
                tr = bt["trades"].copy(); tr["Return"] = (tr["Return"] * 100).round(2)
                st.dataframe(tr, hide_index=True, width="stretch")
            if bt["mode"] == "trend":
                st.caption("Aturan: beli saat skor sistem ≥ 65 & harga > EMA50 (eksekusi open besok), keluar bila skor < 45, "
                           "stop 2×ATR + trailing 2.5×ATR, maks. 40 hari.")
            else:
                st.caption("Aturan: beli koreksi sehat (uptrend EMA20>EMA50, harga ≤ EMA20, RSI<55, skor ≥ 50), "
                           "take profit 1×ATR, stop 2×ATR, keluar paksa setelah 15 hari. Jika stop & TP tersentuh di hari yang sama, "
                           "dihitung stop (konservatif). Sudah termasuk fee.")
            st.caption("Win rate tinggi BUKAN berarti untung: bandingkan dengan 'win rate impas'. Hasil historis tidak menjamin masa depan.")
    st.warning("⚠️ Analisis ini bersifat edukatif dan bukan rekomendasi investasi resmi. Selalu lakukan riset mandiri (DYOR).")


def render_screen(R, ctx):
    df = R["df"]
    st.markdown(f"## 🔎 Hasil Screening — {len(df)} saham")
    st.dataframe(df, hide_index=True, width="stretch")
    st.download_button("⬇️ Download hasil (CSV)", df.to_csv(index=False).encode("utf-8"), file_name=f"{st.session_state.get('char', 'suhu')}_screening.csv", mime="text/csv")
    if R.get("events") is not None:
        render_paper(R["paper"], R["events"], R["prices"], ctx)
    st.warning("⚠️ Analisis ini bersifat edukatif dan bukan rekomendasi investasi resmi. Selalu lakukan riset mandiri (DYOR).")


def render_paper(p, events, prices, ctx):
    st.markdown("### 🤖 Auto-Pilot Paper Trading (simulasi)")
    eq = paper_equity(p, prices)
    m = st.columns(4)
    m[0].metric("Ekuitas", f"{ctx['cur']} {eq:,.0f}", f"{(eq/p['start']-1)*100:+.2f}%")
    m[1].metric("Kas", f"{ctx['cur']} {p['cash']:,.0f}"); m[2].metric("Posisi terbuka", len(p["pos"]))
    m[3].metric("Order pending", len(p["pending"]))
    if events:
        st.info(" • ".join(events))
    if p["pos"]:
        rows = [dict(Saham=k, Lot=v["shares"] / ctx["lot"], Entry=v["entry"], Harga=round(prices.get(k, v["entry"]), 2),
                     PnL_pct=round((prices.get(k, v["entry"]) / v["entry"] - 1) * 100, 2), Stop=v["stop"], TP1=v["tp1"], TP2=v["tp2"])
                for k, v in p["pos"].items()]
        st.dataframe(pd.DataFrame(rows), hide_index=True, width="stretch")
    if p["log"]:
        st.markdown("**Log transaksi**")
        lg = pd.DataFrame(p["log"])
        st.dataframe(lg, hide_index=True, width="stretch")
        st.download_button("⬇️ Download log (CSV)", lg.to_csv(index=False).encode("utf-8"), file_name=f"{st.session_state.get('char', 'suhu')}_paper_log.csv", mime="text/csv")
    st.caption(f"Ini SIMULASI. {PN} tidak terhubung ke broker mana pun dan tidak mengirim order sungguhan. "
               "Status tersimpan selama sesi browser berjalan — unduh log untuk arsip.")


# =========================================================
# PEMROSES PERINTAH
# =========================================================
def full_tk(tk):
    return tk if (not CTX["suffix"] or tk.endswith(CTX["suffix"])) else tk + CTX["suffix"]


def run_screen(ctx, with_paper=False):
    tks = tuple(full_tk(t) for t in WATCH)
    held = tuple(st.session_state.paper["pos"].keys()) if with_paper else ()
    data = fetch_batch(tuple(dict.fromkeys(tks + held)), "3y")
    analyses = []
    for tk in tks:
        df = data.get(tk)
        if df is None:
            continue
        try:
            A = analyze_df(tk, df, {}, ctx, full=False)
            if A:
                analyses.append(A)
        except Exception:
            continue
    rows = []
    for A in sorted(analyses, key=lambda a: -a["composite"]):
        pl = A["plan"]
        rows.append({"Rank": len(rows) + 1, "Saham": A["tk"].replace(ctx["suffix"], ""), "Harga": pl["price"],
                     f"Skor {PN}": round(A["composite"], 1), "Keputusan": A["decision"], "QVTA": A["qv"]["qvta_score"],
                     "Sistem": round(A["sys_now"]), f"P(naik {ctx['horizon']}h) %": round(A["ms"]["prob_up"] * 100),
                     "Zona Beli": f"{fmt(pl['entry_lo'], ctx)}-{fmt(pl['entry_hi'], ctx)}", "Stop Loss": pl["stop"],
                     "TP2": pl["tp2"], "R:R": round(pl["rr"], 1), "EV (R)": round(pl["ev_r"], 2),
                     "Bandar": A["band"]["signal"].split(" ", 1)[-1][:28]})
    return analyses, pd.DataFrame(rows), data


def handle_command(text, ctx):
    intent = detect_intent(text)
    tk = extract_ticker(text)
    res = dict(speech="", display=None, mood="neutral", result=None)
    if intent == "greet":
        res.update(speech=PERSONA["lines"]["greet"].format(s=PS), mood="happy")
    elif intent == "who":
        res.update(speech=PERSONA["lines"]["who"].format(s=PS), mood="happy")
    elif intent == "thanks":
        res.update(speech=PERSONA["lines"]["thanks"].format(s=PS), mood="happy")
    elif intent == "joke":
        res.update(speech=JOKES[len(text) % len(JOKES)], mood="happy")
    elif intent == "help":
        res.update(speech=help_txt(), mood="happy")
    elif intent in ("screen", "autopilot"):
        with st.spinner(f"{PN} memindai watchlist..."):
            paper_on = intent == "autopilot"
            if paper_on and "paper" not in st.session_state:
                st.session_state.paper = paper_init(ctx["capital"])
            analyses, df, data = run_screen(ctx, paper_on)
        if df.empty:
            res.update(speech="Waduh, data pasar tidak berhasil diambil. Cek koneksi internet atau kode saham di watchlist.", mood="bear")
        else:
            top = analyses and sorted(analyses, key=lambda a: -a["composite"])[:3]
            r = dict(kind="screen", df=df)
            names = ". ".join(f"{sp(a['tk'].replace(ctx['suffix'], ''))} skor {a['composite']:.0f}, {plain(a['decision'])}" for a in top)
            if paper_on:
                events, prices = paper_step(st.session_state.paper, analyses, data, ctx)
                r.update(events=events, paper=st.session_state.paper, prices=prices)
                res["speech"] = (f"Auto pilot selesai. {len(events)} kejadian. Posisi terbuka {len(st.session_state.paper['pos'])}. "
                                 f"Ini simulasi paper trading ya. Kandidat teratas: {names}.")
            else:
                res["speech"] = f"Aku sudah memindai {len(df)} saham. Tiga teratas: {names}. Tabel lengkap ada di layar."
            res["mood"] = top[0]["mood"] if top else "neutral"
            res["result"] = r
    elif intent in ("analyze", "mc", "plan", "backtest"):
        if not tk:
            res.update(speech="Saham apa yang mau dianalisa? Sebutkan kodenya, misalnya B B C A.", mood="think")
        else:
            ftk = full_tk(tk)
            with st.spinner(f"{PN} menganalisa {ftk}..."):
                hist, info = fetch_data(ftk, "3y", True)
                A, broker = None, None
                if len(hist) >= MIN_BARS:
                    broker = broker_flow_from_csv(pd.read_csv(broker_csv)) if broker_csv is not None else None
                    A = analyze_df(ftk, hist, info, ctx, broker=broker, full=True)
            if A is None:
                n_got = len(hist)
                why = (f"Yahoo Finance hanya memberi {n_got} hari data, minimal {MIN_BARS}." if n_got
                       else "Yahoo Finance tidak mengembalikan data (kode salah, saham tidak tercakup, atau sedang dibatasi).")
                res.update(speech=f"Maaf, aku tidak bisa menganalisa {sp(tk)}. {why} Coba lagi beberapa menit lagi.",
                           display=f"Maaf, {ftk} gagal dianalisa. {why}", mood="bear")
            else:
                res.update(speech=speech_single(intent, A, ctx), mood=A["mood"],
                           result=dict(kind="ticker", A=A, broker=broker))
    else:
        res.update(speech="Hmm, aku belum paham. Coba bilang: analisa B B C A, atau cari saham bagus, atau bilang bantuan.", mood="think")
    res["display"] = res["speech"].replace(PS, PN)   # teks layar pakai nama karakter; suara pakai ejaan lisan
    return res


# =========================================================
# HALAMAN UTAMA
# =========================================================
st.markdown(f'<div class="page-title">{PERSONA["emoji"]} {PN} — AI Agent Saham</div>', unsafe_allow_html=True)
st.markdown('<p class="page-sub">Asisten Pintar Saham kuantitatif: screening, analisa, prediksi, rekomendasi beli/jual, '
            'backtest, dan auto-pilot paper trading.</p>', unsafe_allow_html=True)

ss.setdefault("chat", [])
ss.setdefault("last_cmd", None)
ss.setdefault("result", None)
ss.setdefault("speak", {"id": 1, "text": PERSONA["lines"]["intro_speech"].format(s=PS),
                        "display": PERSONA["lines"]["intro_cap"], "mood": "happy"})

left, right = st.columns([1, 2.3], gap="large")
with left:
    ret = None
    if suhu_component is not None:
        ret = suhu_component(speak=ss.speak, cfg=dict(pitch=v_pitch, rate=v_rate, robot=v_robot, hasAvatar=HAS_AVATAR),
                             key=f"avatar_{ss.char}", default=None)
    else:
        # MODE CADANGAN: avatar tanpa folder komponen; perintah suara dikirim lewat kotak chat di bawah.
        init = {"cfg": dict(pitch=v_pitch, rate=v_rate, robot=v_robot, hasAvatar=HAS_AVATAR),
                "speak": ss.speak if ss.get("speak_new", True) else None}
        pre = ("<script>window.AG_FALLBACK=true;window.AG_ASSETS=" + json.dumps(BUNDLE["data_urls"]) +
               ";window.AG_INIT=" + json.dumps(init) + ";</script>")
        page = build_component_html(ss.char).replace("<script>", pre + "<script>", 1)
        if hasattr(st, "iframe"):          # Streamlit terbaru (components.html sudah deprecated)
            st.iframe(page, height=590)
        else:
            components.html(page, height=590)
        ss.speak_new = False
        st.caption("⚠️ Mode cadangan aktif (komponen dua arah tidak bisa dibuat). Suara tetap jalan, "
                   "tetapi wake word berhenti setiap halaman dimuat ulang — klik 🎤 lagi untuk tiap perintah.")
        if IS_ADMIN:
            with st.expander("Detail error komponen (admin)"):
                st.code("\n".join(COMP_ERRORS) or "tidak ada detail")
    if not HAS_AVATAR:
        st.warning(f"File `{PERSONA['files'][0]}` tidak ditemukan — taruh di folder yang sama dengan file ini.")
    chat_html = "".join(
        f'<div class="msg-{"u" if r == "u" else "s"}"><span>{htmllib.escape(m)}</span></div>' for r, m in ss.chat[-8:])
    st.markdown(f'<div class="chatbox">{chat_html or "<i>Belum ada percakapan.</i>"}</div>', unsafe_allow_html=True)
    st.caption(f"Contoh: “{PS}, analisa BBCA” · “cari saham bagus” · “prediksi TLKM” · “rekomendasi harga beli BBRI” · "
               "“backtest ASII” · “jalankan auto pilot”")

typed = st.chat_input(f"Ketik perintah untuk {PN}… mis. analisa BBCA")
user_text = None
if isinstance(ret, dict) and ret.get("id") != ss.last_cmd and ret.get("text"):
    ss.last_cmd = ret["id"]
    user_text = ret["text"]
if typed:
    user_text = typed

if user_text:
    with right:
        try:
            out = handle_command(user_text, CTX)
        except Exception as e:
            msg = f"Waduh, ada kendala teknis: {str(e)[:80]}" if IS_ADMIN else "Waduh, ada kendala teknis. Coba ulangi perintahnya sebentar lagi."
            out = dict(speech=msg, display=msg, mood="bear", result=None)
    ss.chat.append(("u", user_text))
    ss.chat.append(("s", out["display"]))
    if out["result"] is not None:
        ss.result = out["result"]
    ss.speak = {"id": ss.speak["id"] + 1, "text": out["speech"], "display": out["display"], "mood": out["mood"]}
    ss.speak_new = True
    st.rerun()

with right:
    R = ss.result
    if R is None:
        st.info(f"👈 Bicara atau ketik perintah ke {PN}. Hasil analisa lengkap akan tampil di sini.")
    elif R["kind"] == "ticker":
        render_ticker(R, CTX)
    elif R["kind"] == "screen":
        render_screen(R, CTX)
