# Smart Weighbridge AI & OpenPLC Integration 🚛⚖️

Sistem Jembatan Timbang Otomatis yang memadukan **Computer Vision (AI)** untuk pengenalan plat nomor kendaraan (ANPR) dan **OpenPLC** untuk kalkulasi beban secara *real-time*. Proyek ini dirancang untuk menghilangkan intervensi manual yang rentan terhadap *human error*, mempercepat antrean operasional, dan memastikan pencatatan log tersentralisasi ke dalam *database*.

---

## 🌟 Fitur Utama

- **AI-Powered ANPR** — Mendeteksi kendaraan dan membaca plat nomor secara presisi menggunakan **YOLOv10** dan **PaddleOCR**.
- **Auto-Correction & Anti-Spam** — Algoritma pembersih teks khusus format plat nomor Indonesia dan fitur *cooldown* untuk mencegah *double-entry*.
- **Industrial Automation Logic** — Pemrosesan nilai sensor (*Gross Weight*, *Tare*, *Volume*) dan perhitungan persentase/kepadatan (*Density*) langsung di memori PLC menggunakan bahasa *Ladder Diagram*.
- **Seamless Modbus TCP Integration** — Komunikasi dua arah secara *real-time* antara sistem AI (Python Client) dan PLC (Server).
- **Automated Database Logging** — Pencatatan riwayat timbangan secara otomatis ke dalam MySQL.


---

## 🛠️ Persyaratan Sistem (Prerequisites)

Sebelum memulai, pastikan sistem komputermu sudah terinstal perangkat lunak berikut:

1. **Python 3.10+** (Sangat disarankan menggunakan Miniconda/Anaconda)
2. **OpenPLC Runtime** (Untuk menjalankan server PLC)
3. **OpenPLC Editor** (Opsional, jika ingin melihat/mengedit skema *Ladder Diagram*)
4. **MySQL Server** (Bisa menggunakan XAMPP, MAMP, atau instalasi *native*)
5. **Git** (Untuk *cloning* repositori)

---

## 🚀 Panduan Setup & Instalasi

Ikuti langkah-langkah di bawah ini secara berurutan untuk menjalankan sistem di komputermu.

### Langkah 1 — Clone Repositori

```bash
git clone https://github.com/USERNAME_GITHUB_KAMU/smart-weighbridge-ai.git
cd smart-weighbridge-ai
```

### Langkah 2 — Setup Database (MySQL)

1. Buka terminal MySQL atau phpMyAdmin.
2. Buat database baru bernama `smart_weighbridge`:

   ```sql
   CREATE DATABASE smart_weighbridge;
   USE smart_weighbridge;
   ```

3. Buat tabel master dan log beserta data sampel untuk pengujian:

   ```sql
   -- Tabel Master Truk
   CREATE TABLE data_truk (
       plat_nomor VARCHAR(15) PRIMARY KEY,
       tare_weight INT,
       jenis_muatan VARCHAR(50)
   );

   -- Tabel Log Hasil Penimbangan
   CREATE TABLE log_penimbangan (
       id INT AUTO_INCREMENT PRIMARY KEY,
       plat_nomor VARCHAR(15),
       gross_weight INT,
       netto_weight INT,
       volume FLOAT,
       density FLOAT,
       waktu TIMESTAMP DEFAULT CURRENT_TIMESTAMP
   );

   -- Insert Dummy Data untuk Testing
   INSERT INTO data_truk (plat_nomor, tare_weight, jenis_muatan)
   VALUES ('BA8281HA', 7000, 'Kelapa Sawit');
   ```

### Langkah 3 — Setup OpenPLC Runtime

Karena sistem operasi (terutama Linux) sering memblokir port rendah (Port 502), kita akan menggunakan port **5020**.

1. Jalankan **OpenPLC Runtime** dan buka *dashboard* melalui browser di `http://localhost:8080`.
2. Login (Default kredensial: username `openplc`, password `openplc`).
3. Masuk ke menu **Settings**:
   - Cari bagian **Modbus Server**.
   - Ubah nilai **Modbus Port** menjadi `5020`.
   - Klik **Save Changes**.
4. Masuk ke menu **Programs**:
   - Klik **Choose File** dan pilih file `.st` atau `.xml` dari dalam folder `plc_program/` (dibuat oleh Rifki).
   - Klik **Upload Program**.
5. Definisikan variabel berikut pada OpenPLC Editor (bagian deklarasi variabel):

   ```pascal
   VAR
       PC_ANPR_Truk_Detected : BOOL AT %QX0.0 := FALSE;
       S1_LiDAR_Posisi       : BOOL AT %QX0.1 := FALSE;
       S2_LoadCell_Stable    : BOOL AT %QX0.2 := FALSE;
       Reset_Button          : BOOL AT %QX0.3 := FALSE;
       LiDAR_Volume_Raw      : UINT AT %QW1  := 0;
       LoadCell_Weight_Raw   : UINT AT %QW2  := 0;
       Database_Tare_Weight  : UINT AT %QW3  := 0;
       Palang_masuk          : BOOL AT %QX0.4 := FALSE;
       Sistem_Ready          : BOOL AT %QX0.5 := FALSE;
       Alarm_Posisi          : BOOL AT %QX0.6 := FALSE;
       Netto_Weight          : UINT AT %QW4  := 0;
       Density_Result        : UINT AT %QW5  := 0;
       Lock_Data             : BOOL AT %QX0.7 := FALSE;
       Volume_Locked         : UINT := 0;
       Weight_Locked         : UINT := 0;
   END_VAR
   ```

6. Setelah berhasil diunggah, kembali ke *Dashboard* utama dan klik tombol **Start PLC**.
   *(Pastikan statusnya berubah menjadi "Running").*

### Langkah 4 — Setup Environment Computer Vision (Python)

Sangat disarankan menggunakan *virtual environment* agar *dependencies* tidak bentrok.

1. Buat dan aktifkan *environment* (contoh menggunakan Conda):

   ```bash
   conda create -n weighbridge_env python=3.10
   conda activate weighbridge_env
   ```

2. Instal *library* utama untuk AI, Database, dan Modbus:

   ```bash
   pip install opencv-python torch torchvision ultralytics paddlepaddle paddleocr pymodbus mysql-connector-python
   ```

   > **Catatan:** Saat pertama kali kode dijalankan, sistem akan otomatis mengunduh model ringan `yolov10n.pt` dan model bahasa Inggris dari `PaddleOCR`.

---

## 🎮 Cara Menjalankan Sistem (Eksekusi)

Setelah semua *setup* selesai (MySQL menyala, OpenPLC berstatus *Running*), sistem siap diuji coba.

1. Buka terminal di dalam folder proyek.
2. Pastikan *environment* Python sudah aktif.
3. Jalankan *script* utama:

   ```bash
   python YoloOCRfinal_Integrasi.py
   ```

4. **Cara Kerja Simulasi:**
   - Jendela kamera akan terbuka.
   - Arahkan gambar plat nomor (contoh: plat `BA 8281 HA`) ke arah kamera.
   - AI akan mendeteksi kotak *bumper* dan mengekstrak teks.
   - Jika teks dikenali dan ada di database, Python akan menembak data *Tare Weight* dan *Dummy Gross Weight* ke OpenPLC via Modbus.
   - OpenPLC menghitung beban *Netto*, Python menarik kembali hasilnya, dan menyimpannya ke MySQL.
5. Tekan tombol **`q`** pada *keyboard* (saat berada di jendela kamera) untuk mematikan program.

---

## 📁 Struktur Repositori

```text
📦 smart-weighbridge-ai
 ┣ 📂 assets/                    # Dokumentasi visual (skema PLC, screenshot, dll)
 ┣ 📂 plc_program/               # Source code & logic Ladder Diagram OpenPLC (Rifki)
 ┣ 📜 YoloOCRfinal_Integrasi.py  # Main script integrasi (Computer Vision + Modbus TCP + MySQL)
 ┣ 📜 .gitignore                 # File ignore untuk menyembunyikan kredensial & environment
 ┗ 📜 README.md                  # Dokumentasi utama
```

---

## 📌 Catatan

Proyek ini merupakan purwarupa (*prototype*) yang disimulasikan untuk Pembelajaran dan pengetahuan serta keperluan Kerja Praktek
