# Panduan SUHU SaaS — gratis, tanpa server berbayar

## Isi paket
| File | Fungsi |
|---|---|
| `streamlit_app.py` | Aplikasi SUHU Anda (sudah diberi gerbang akses) — **jangan dibagikan** |
| `gate.py` | Homepage + pembayaran + validasi Access Key + panel admin |
| `.streamlit/config.toml` | Menyembunyikan detail error & toolbar dari pelanggan |
| `.streamlit/secrets.toml.example` | Contoh isi "Secrets" (rahasia) — **bukan** file yang di-upload |
| `requirements.txt` | Daftar library yang dipasang otomatis |
| `*.png` | Gambar karakter |

Yang diubah di kode asli Anda (hanya ini): gerbang akses di awal file, sidebar menampilkan status akun,
kolom API Key Claude & detail error hanya tampil untuk admin, dan CSS tambahan agar nyaman di HP.

## A. Pasang online (sekali saja, ±30 menit)

1. **Buat akun GitHub** (gratis) di github.com. Aktifkan **2FA** (Settings → Password and authentication).
2. **Buat repository baru**: tombol *New* → nama `suhu-app` → pilih **Private** → Create.
3. **Upload file**: di halaman repo klik *uploading an existing file* → seret SEMUA isi folder paket ini
   (termasuk folder `.streamlit`) → *Commit changes*.
   - Jika folder `.streamlit` tidak ikut terupload: *Add file → Create new file* → ketik nama
     `.streamlit/config.toml` → tempel isinya → Commit.
   - **JANGAN** upload file `secrets.toml` berisi rahasia asli.
4. Buka **share.streamlit.io** → login dengan GitHub → izinkan akses ke repo private → **Create app**:
   - Repository: `suhu-app`, Branch: `main`, Main file path: `streamlit_app.py`
   - **Advanced settings → Secrets**: tempel isi `secrets.toml.example`, lalu GANTI semua nilainya:
     - `LICENSE_SECRET` : teks acak panjang ≥ 32 karakter (buat dengan password generator). **Simpan cadangannya** —
       jika berubah, semua key pelanggan yang sudah terbit tidak berlaku.
     - `ADMIN_KEY` : key admin Anda (rahasia, jangan dibagikan)
     - `APP_URL` : alamat app Anda (isi setelah app jadi, lalu simpan lagi)
   - Klik **Deploy**. Tunggu beberapa menit.
5. **Tes**: buka alamat app → masukkan `ADMIN_KEY` → pilih karakter → sidebar (ikon `>` di kiri atas) →
   **Panel Admin** → *Buat Access Key* → salin key → buka tab *incognito* → masuk dengan key itu →
   pastikan pelanggan **tidak** melihat Panel Admin / kolom API Key.

## B. Alur harian jualan
1. Pelanggan transfer Rp200.000 → kirim bukti ke Telegram Anda.
2. **Cek mutasi rekening Anda sendiri** (jangan percaya screenshot saja).
3. Masuk app sebagai admin → Panel Admin → isi nama → *Buat Access Key* → salin "Pesan siap kirim" → kirim via Telegram.
4. Catat di spreadsheet: tanggal bayar, nama, username Telegram, **ID key** (4 huruf), tanggal kedaluwarsa.
5. Perpanjang = pelanggan transfer lagi → Anda buat key baru.
6. Menonaktifkan key lebih awal: tambahkan ID key ke `REVOKED = ["AB12"]` di Secrets → Save → reboot app.

Tips: minta pelanggan menambahkan **kode unik** ke nominal (mis. Rp200.123) supaya transfer mudah dicocokkan.

## C. Dibuka di HP (tampilan vertikal)
- Kirim link app ke pelanggan. Di HP, tampilan otomatis menumpuk vertikal; menu pengaturan ada di ikon `>` kiri atas.
- **Android (Chrome)**: menu ⋮ → *Tambahkan ke layar utama*.  **iPhone (Safari)**: tombol Bagikan → *Tambah ke Layar Utama*.
  Ini membuat ikon seperti aplikasi, tetapi tetap berjalan di browser (bukan aplikasi Play Store/App Store).
- Perintah suara paling stabil di Chrome/Edge dan butuh izin mikrofon; di iPhone bisa terbatas — mengetik perintah tetap berfungsi.
- Ceklis "Ingat di perangkat ini" menyimpan key di link, jadi pelanggan tidak perlu mengetik ulang.

## D. Batasan versi gratis yang harus Anda tahu
- Hosting gratis Streamlit Community Cloud: memori ±1 GB, app **tidur** bila 12 jam tanpa pengunjung
  (pengunjung pertama menunggu ±1 menit), tanpa jaminan uptime (SLA), tanpa domain sendiri.
- Batas perangkat (2 per key) disimpan di memori server; reset jika app restart.
- Perubahan Secrets berlaku setelah app di-reboot.
