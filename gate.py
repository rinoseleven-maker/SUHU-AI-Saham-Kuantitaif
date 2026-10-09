"""
gate.py — Gerbang akses (paywall) + homepage SUHU
=================================================
Semua logika di file ini berjalan di SERVER. Pelanggan hanya menerima tampilan
(HTML) dan hasil analisis — kode Python dan algoritma TIDAK pernah dikirim ke
browser mereka.

Cara kerja Access Key (tanpa database, tanpa biaya):
  * Key pelanggan  : SUHU-<tglKadaluarsa>-<ID>-<tanda tangan HMAC>
    Tanda tangan dibuat dengan LICENSE_SECRET milik Anda, jadi key palsu tidak bisa dibuat.
  * Key admin      : isi ADMIN_KEY di Secrets. Akses gratis, tanpa batas waktu.
  * Masa aktif     : tertanam di dalam key (default 30 hari sejak key dibuat).
"""
import hashlib
import hmac
import io
import base64
import os
import re
import threading
import time
import uuid
from datetime import datetime, timedelta, timezone
from pathlib import Path

import streamlit as st

# ======================= EDIT BAGIAN INI SAJA =======================
APP_NAME = "SUHU"
APP_TAGLINE = "Asisten AI Analisis Saham Kuantitatif"
PRICE_IDR = 200_000          # harga per paket
ACCESS_DAYS = 30             # masa aktif per paket (hari)
BANK_NAME = "Bank Artha Graha"
BANK_ACCOUNT = "1083865039"
BANK_HOLDER = "Rio Reynaldo Tanos"
TELEGRAM_URL = "https://t.me/+wxZhAyTsupE2NGE1"   # grup/kontak Telegram admin
MAX_DEVICES = 2              # 1 key maksimal dipakai di 2 perangkat aktif bersamaan
# ====================================================================

WIB = timezone(timedelta(hours=7))
_HERE = Path(__file__).resolve().parent


# ---------------------------------------------------------------- secrets
def _secret(name, default=""):
    """Fungsi pembacaan rahasia yang fleksibel untuk Streamlit Cloud (st.secrets) & OS (os.getenv)."""
    val = None
    # 1. Coba baca dari Streamlit Secrets (Streamlit Cloud / .streamlit/secrets.toml)
    try:
        if hasattr(st, "secrets") and name in st.secrets:
            val = st.secrets[name]
    except Exception:
        pass

    # 2. Jika tidak ditemukan di st.secrets, coba baca dari Environment Variables (Lokal/VPS/.env)
    if val in (None, ""):
        val = os.environ.get(name, default)

    return str(val) if val is not None else str(default)


def _rupiah(n):
    return "Rp " + f"{int(n):,}".replace(",", ".")


# ---------------------------------------------------------------- key logic
_KEY_RE = re.compile(r"SUHU-(\d{6})-([A-Z0-9]{4})-([0-9A-F]{4})-([0-9A-F]{4})-([0-9A-F]{4})-([0-9A-F]{4})")
_ID_ALPHABET = "ABCDEFGHJKLMNPQRSTUVWXYZ23456789"   # tanpa 0/O/1/I agar tidak membingungkan


def _sig(secret, exp, kid):
    mac = hmac.new(secret.encode(), f"{exp}|{kid}".encode(), hashlib.sha256).hexdigest().upper()
    return mac[:16]


def make_key(days=ACCESS_DAYS):
    """Buat Access Key pelanggan. Kembalikan (key, tanggal_kadaluarsa)."""
    secret = _secret("LICENSE_SECRET")
    if len(secret) < 16:
        raise ValueError("LICENSE_SECRET belum diisi (minimal 16 karakter) di Secrets.")
    exp_date = datetime.now(WIB).date() + timedelta(days=int(days))
    exp = exp_date.strftime("%y%m%d")
    raw = os.urandom(4)
    kid = "".join(_ID_ALPHABET[b % len(_ID_ALPHABET)] for b in raw)
    s = _sig(secret, exp, kid)
    return f"SUHU-{exp}-{kid}-{s[0:4]}-{s[4:8]}-{s[8:12]}-{s[12:16]}", exp_date


def check_key(raw):
    """Periksa key. Kembalikan (status, info).
    status: admin | ok | expired | revoked | invalid | not_configured
    """
    raw = (raw or "").strip()
    if not raw:
        return "invalid", {}
    admin = _secret("ADMIN_KEY")
    if admin and len(admin) >= 8 and hmac.compare_digest(raw.encode(), admin.encode()):
        return "admin", {"kid": "ADMIN", "exp": None}
    secret = _secret("LICENSE_SECRET")
    if len(secret) < 16:
        return "not_configured", {}
    norm = re.sub(r"\s+", "", raw).upper()
    m = _KEY_RE.fullmatch(norm)
    if not m:
        return "invalid", {}
    exp, kid = m.group(1), m.group(2)
    given = "".join(m.group(i) for i in (3, 4, 5, 6))
    if not hmac.compare_digest(given.encode(), _sig(secret, exp, kid).encode()):
        return "invalid", {}
    try:
        exp_date = datetime.strptime(exp, "%y%m%d").date()
    except ValueError:
        return "invalid", {}
    
    revoked_raw = _secret("REVOKED", "")
    revoked = []
    if isinstance(revoked_raw, str) and revoked_raw:
        revoked = [x.strip().upper() for x in revoked_raw.split(",") if x.strip()]
    elif isinstance(revoked_raw, (list, tuple)):
        revoked = [str(x).strip().upper() for x in revoked_raw]
        
    if kid in revoked:
        return "revoked", {"kid": kid, "exp": exp_date}
    if datetime.now(WIB).date() > exp_date:
        return "expired", {"kid": kid, "exp": exp_date}
    return "ok", {"kid": kid, "exp": exp_date}


# ---------------------------------------------------------------- batas perangkat
@st.cache_resource
def _registry():
    return {"lock": threading.Lock(), "seen": {}}


def _register_device(kid, sid, ttl=900):
    reg, now = _registry(), time.time()
    with reg["lock"]:
        d = reg["seen"].setdefault(kid, {})
        for s, t in list(d.items()):
            if now - t > ttl:
                del d[s]
        if sid not in d and len(d) >= MAX_DEVICES:
            return False
        d[sid] = now
        return True


def _release_device(kid, sid):
    reg = _registry()
    with reg["lock"]:
        reg["seen"].get(kid, {}).pop(sid, None)


# ---------------------------------------------------------------- tampilan homepage
def _avatar_data_uri():
    try:
        from PIL import Image
        for p in (_HERE / "SUHU.png", _HERE / "assets" / "SUHU.png"):
            if p.exists():
                im = Image.open(p).convert("RGBA")
                im.thumbnail((260, 260))
                buf = io.BytesIO()
                im.save(buf, "PNG", optimize=True)
                return "data:image/png;base64," + base64.b64encode(buf.getvalue()).decode()
    except Exception:
        pass
    return ""


def _banner_data_uri():
    """banner.jpg: potong ruang putih di sekeliling logo, kecilkan, lalu sematkan sebagai data URI."""
    try:
        from PIL import Image, ImageChops
        for p in (_HERE / "banner.jpg", _HERE / "assets" / "banner.jpg"):
            if p.exists():
                im = Image.open(p).convert("RGB")
                bg = Image.new("RGB", im.size, (255, 255, 255))
                box = ImageChops.difference(im, bg).convert("L").point(lambda v: 255 if v > 18 else 0).getbbox()
                if box:
                    pad = 12
                    box = (max(box[0] - pad, 0), max(box[1] - pad, 0),
                           min(box[2] + pad, im.width), min(box[3] + pad, im.height))
                    im = im.crop(box)
                im.thumbnail((700, 300))
                buf = io.BytesIO()
                im.save(buf, "JPEG", quality=88, optimize=True)
                return "data:image/jpeg;base64," + base64.b64encode(buf.getvalue()).decode()
    except Exception:
        pass
    return ""


_CSS = """
<style>
.stApp { background: linear-gradient(180deg,#0b1020 0%,#16224a 55%,#1d2f63 100%) !important; }
.block-container { max-width: 540px !important; padding: 1.2rem 1rem 4rem !important; }
header[data-testid="stHeader"], footer { visibility: hidden; height: 0; }
.h-hero { text-align:center; color:#fff; padding: 8px 0 4px; }
.h-hero img { width: 150px; height:auto; filter: drop-shadow(0 8px 22px rgba(80,140,255,.45)); }
.h-hero h1 { font-size: 2.1rem; margin: 6px 0 2px; font-weight: 800; letter-spacing:.5px; color:#fff; }
.h-hero p { color:#b9c7ee; font-size: 1rem; margin: 0 0 6px; }
.h-by { color:#9fb2e6; font-size:.95rem; letter-spacing:2px; margin: 0 0 6px; }
.h-banner { display:inline-block; background:#fff; border-radius:14px; padding:8px 16px; max-width:88%;
            box-shadow: 0 6px 20px rgba(0,0,0,.25); }
.h-banner img { width:100%; max-width:340px; height:auto; display:block; filter:none; }
.h-card { background: rgba(255,255,255,.07); border:1px solid rgba(255,255,255,.12); border-radius: 18px;
          padding: 16px 18px; margin: 14px 0; color:#e8eeff; }
.h-card h3 { margin: 0 0 8px; font-size:1.1rem; color:#fff; }
.h-card li { margin: 5px 0; line-height:1.45; }
.h-price { text-align:center; }
.h-price .big { font-size: 2.3rem; font-weight: 800; color:#7fd1ff; line-height:1.1; }
.h-price .per { color:#b9c7ee; }
.h-step { display:flex; gap:12px; align-items:flex-start; margin: 10px 0; }
.h-step b.n { background:#2f6bff; color:#fff; border-radius:50%; min-width:28px; height:28px; display:flex;
              align-items:center; justify-content:center; font-size:.9rem; }
.h-disc { font-size:.78rem; color:#93a3cf; line-height:1.5; }
.h-hero, .h-card, .h-card * { font-family: 'DM Sans', system-ui, sans-serif; }
</style>
"""


def _render_home(message=None, level="error"):
    st.markdown(_CSS, unsafe_allow_html=True)
    av = _avatar_data_uri()
    img = f'<img src="{av}" alt="{APP_NAME}">' if av else '<div style="font-size:4rem">🤖</div>'
    bn = _banner_data_uri()
    by = (f'<div class="h-by">by</div><div class="h-banner"><img src="{bn}" alt="Saham Kuantitatif"></div>'
          if bn else '<div class="h-by">by Saham Kuantitatif</div>')
    st.markdown(f'<div class="h-hero">{img}<h1>{APP_NAME}</h1>{by}<p style="margin-top:10px">{APP_TAGLINE}</p></div>',
                unsafe_allow_html=True)

    # ---- login
    st.markdown('<div class="h-card"><h3>🔑 Masuk dengan Access Key</h3></div>', unsafe_allow_html=True)
    if message:
        (st.error if level == "error" else st.warning)(message)
    with st.form("login_form", clear_on_submit=False):
        key = st.text_input("Access Key", type="password", placeholder="SUHU-xxxxxx-xxxx-xxxx-xxxx-xxxx-xxxx",
                           label_visibility="collapsed")
        remember = st.checkbox("Ingat di perangkat ini", value=True)
        go = st.form_submit_button("Masuk", type="primary", use_container_width=True)
    if go:
        _handle_login(key, remember)

    # ---- fitur
    st.markdown("""
<div class="h-card"><h3>📊 Yang Anda dapatkan</h3><ul>
<li><b>Screening saham</b> IDX &amp; US — peringkat kandidat terbaik dalam sekali perintah</li>
<li><b>Analisa lengkap</b>: skor kuantitatif, teknikal, fundamental &amp; bandarmology</li>
<li><b>Prediksi Monte Carlo</b> + probabilitas kena target / stop loss</li>
<li><b>Rencana trading</b>: zona beli, stop loss, TP 1-3, ukuran posisi</li>
<li><b>Backtest</b> &amp; uji hit-rate sinyal, <b>paper trading</b> otomatis (simulasi)</li>
<li><b>Asisten suara</b> dengan 4 karakter avatar animasi</li>
<li>Nyaman dibuka di HP maupun komputer — tanpa instal apa pun</li>
</ul></div>
""", unsafe_allow_html=True)

    # ---- harga
    st.markdown(f"""
<div class="h-card h-price"><h3>💳 Berlangganan</h3>
<div class="big">{_rupiah(PRICE_IDR)}</div>
<div class="per">untuk akses {ACCESS_DAYS} hari</div></div>
""", unsafe_allow_html=True)

    st.markdown(f"""
<div class="h-card"><h3>Cara berlangganan</h3>
<div class="h-step"><b class="n">1</b><div>Transfer <b>{_rupiah(PRICE_IDR)}</b> ke rekening di bawah. Tulis <b>nama &amp; username Telegram</b> Anda di berita transfer.</div></div>
<div class="h-step"><b class="n">2</b><div>Kirim <b>bukti transfer</b> ke admin lewat Telegram.</div></div>
<div class="h-step"><b class="n">3</b><div>Setelah pembayaran diverifikasi, Anda menerima <b>Access Key</b>. Masukkan di kolom di atas — langsung aktif {ACCESS_DAYS} hari.</div></div>
</div>
""", unsafe_allow_html=True)

    st.markdown(f'<div class="h-card" style="margin-bottom:4px"><h3>🏦 {BANK_NAME}</h3>'
                f'a.n. <b>{BANK_HOLDER}</b><br>Nomor rekening (ketuk ikon salin):</div>', unsafe_allow_html=True)
    st.code(BANK_ACCOUNT, language=None)

    st.link_button("✈️ Kirim bukti transfer via Telegram", TELEGRAM_URL, use_container_width=True)

    st.markdown(f"""
<div class="h-card h-disc"><b>Syarat singkat</b><br>
- Access Key bersifat pribadi, maksimal dipakai di {MAX_DEVICES} perangkat aktif bersamaan, dan tidak boleh dibagikan atau dijual kembali.<br>
- Masa aktif {ACCESS_DAYS} hari dihitung sejak key diterbitkan.<br><br>
<b>Penafian</b><br>
{APP_NAME} adalah alat bantu analisis kuantitatif untuk tujuan informasi dan edukasi — <b>bukan</b> nasihat, ajakan, atau
rekomendasi investasi resmi. Hasil backtest, simulasi Monte Carlo, dan kinerja masa lalu tidak menjamin hasil di masa depan.
Data bersumber dari pihak ketiga (Yahoo Finance) dan dapat tertunda atau tidak akurat. Investasi saham mengandung risiko
kerugian; keputusan dan risikonya sepenuhnya menjadi tanggung jawab Anda.</div>
""", unsafe_allow_html=True)
    st.stop()


# ---------------------------------------------------------------- login & gerbang
def _handle_login(raw, remember):
    ss = st.session_state
    status, info = check_key(raw)
    if status in ("admin", "ok"):
        ss["_auth"] = dict(role="admin" if status == "admin" else "customer",
                           kid=info["kid"], exp=info["exp"], raw=raw.strip())
        if status == "ok" and remember:
            st.query_params["k"] = raw.strip()
        st.rerun()
    time.sleep(1.2)   # memperlambat tebak-tebakan key
    ss["_login_msg"] = {
        "expired": "Masa aktif Access Key ini sudah habis. Silakan perpanjang dengan transfer lagi.",
        "revoked": "Access Key ini sudah dinonaktifkan. Hubungi admin.",
        "not_configured": "Sistem belum dikonfigurasi (LICENSE_SECRET kosong). Hubungi admin.",
    }.get(status, "Access Key tidak valid. Periksa kembali penulisannya.")
    st.rerun()


def require_access():
    """Panggil di baris paling atas aplikasi. Mengembalikan dict auth bila lolos,
    kalau tidak menampilkan homepage lalu st.stop()."""
    ss = st.session_state
    ss.setdefault("_sid", uuid.uuid4().hex)
    msg = ss.pop("_login_msg", None)

    auth = ss.get("_auth")
    if not auth:                       # login otomatis dari link yang tersimpan (?k=...)
        k = st.query_params.get("k")
        if k:
            status, info = check_key(k)
            if status == "ok":
                auth = ss["_auth"] = dict(role="customer", kid=info["kid"], exp=info["exp"], raw=k)
            else:
                st.query_params.clear()
                msg = {"expired": "Masa aktif Access Key sudah habis. Silakan perpanjang.",
                       "revoked": "Access Key ini sudah dinonaktifkan."}.get(status, msg)

    if auth:
        status, info = check_key(auth["raw"])      # validasi ulang di setiap interaksi
        if status not in ("admin", "ok"):
            ss.pop("_auth", None)
            st.query_params.clear()
            _render_home("Masa aktif Access Key sudah habis atau dinonaktifkan." if status in ("expired", "revoked")
                         else "Sesi tidak valid, silakan masuk lagi.")
        if auth["role"] == "customer" and not _register_device(auth["kid"], ss["_sid"]):
            _render_home(f"Key ini sedang dipakai di {MAX_DEVICES} perangkat lain. Tutup salah satu "
                         f"atau tunggu ±15 menit, lalu muat ulang.", "warning")
        return auth

    _render_home(msg)


# ---------------------------------------------------------------- sidebar akun & admin
def sidebar_account(auth):
    """Dipanggil di dalam `with st.sidebar:` pada aplikasi utama."""
    ss = st.session_state
    if auth["role"] == "admin":
        st.success("👑 Admin — akses gratis tanpa batas")
    else:
        st.success(f"✅ Akses aktif sampai {auth['exp'].strftime('%d %b %Y')}")
    if st.button("🚪 Keluar", use_container_width=True, key="logout_btn"):
        _release_device(auth["kid"], ss.get("_sid", ""))
        ss.pop("_auth", None)
        st.query_params.clear()
        st.rerun()

    if auth["role"] == "admin":
        with st.expander("🔑 Panel Admin — buat key pelanggan"):
            nama = st.text_input("Nama pelanggan (hanya untuk pesan di bawah)", key="adm_nama")
            days = st.number_input("Masa aktif (hari)", 1, 365, ACCESS_DAYS, key="adm_days")
            if st.button("➕ Buat Access Key", type="primary", use_container_width=True, key="adm_make"):
                try:
                    key, exp = make_key(int(days))
                    ss["_last_key"] = (nama.strip(), key, exp)
                except ValueError as e:
                    st.error(str(e))
            last = ss.get("_last_key")
            if last:
                nm, key, exp = last
                st.code(key, language=None)
                url = str(_secret("APP_URL"))
                pesan = (f"Halo {nm or 'Kak'}, pembayaran {APP_NAME} sudah kami terima ✅\n\n"
                         f"Access Key: {key}\nBerlaku sampai: {exp.strftime('%d %B %Y')}\n"
                         + (f"Buka aplikasi: {url}\n" if url else "")
                         + "\nJangan dibagikan ke orang lain ya. Terima kasih 🙏")
                st.text_area("Pesan siap kirim via Telegram (salin)", pesan, height=190, key="adm_msg")
                st.caption(f"ID key: {key.split('-')[2]} — catat ID + nama + tanggal bayar di spreadsheet "
                           "Anda. Untuk menonaktifkan key, tambahkan ID ini ke REVOKED di Secrets.")
            st.markdown("---")
            cek = st.text_input("Cek status sebuah key", key="adm_cek")
            if cek:
                s, info = check_key(cek)
                st.write({"status": s, **({"kedaluwarsa": str(info.get("exp"))} if info.get("exp") else {})})

    st.caption(f"⚠️ {APP_NAME} adalah alat bantu analisis, bukan nasihat investasi. "
               "Hasil masa lalu/simulasi tidak menjamin hasil di masa depan.")
