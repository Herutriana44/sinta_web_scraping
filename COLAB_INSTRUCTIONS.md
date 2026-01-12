# Instruksi Penggunaan Google Colab untuk SINTA ETL dengan Hadoop

## Cara Menggunakan Notebook

1. **Buka Google Colab**
   - Buka [Google Colab](https://colab.research.google.com/)
   - Buat notebook baru atau upload file `sinta_etl_colab.ipynb`

2. **Upload Notebook**
   - File → Upload notebook
   - Pilih `sinta_etl_colab.ipynb`

3. **Jalankan Sel Secara Berurutan**
   - Jalankan setiap cell secara berurutan dari atas ke bawah
   - Tunggu setiap cell selesai sebelum menjalankan cell berikutnya

## Struktur Notebook

Notebook ini terdiri dari 10 langkah utama:

1. **Clone Repository** - Mengunduh kode dari GitHub
2. **Install Dependencies** - Menginstall library Python yang diperlukan
3. **Install Java** - Menginstall JDK 8 untuk Hadoop
4. **Install Hadoop** - Mengunduh dan mengekstrak Hadoop 3.3.6
5. **Konfigurasi Hadoop** - Setup konfigurasi untuk pseudo-distributed mode
6. **Setup SSH** - Konfigurasi SSH untuk Hadoop
7. **Start Hadoop Services** - Format HDFS dan start NameNode/DataNode
8. **Verifikasi HDFS** - Membuat direktori dan verifikasi HDFS
9. **Jalankan ETL** - Menjalankan proses ekstraksi, transformasi, dan load
10. **Verifikasi Hasil** - Mengecek output lokal dan HDFS

## Catatan Penting

### ⚠️ Batasan Google Colab

1. **Session Timeout**: Colab memiliki batasan waktu session. Jika session timeout, Anda perlu menjalankan ulang dari awal.

2. **Resource Limits**: 
   - Colab memiliki batasan RAM dan disk space
   - Hadoop memerlukan cukup memori untuk berjalan

3. **Port Forwarding**: 
   - NameNode Web UI di `http://localhost:9870` tidak dapat diakses langsung dari browser
   - Gunakan `ngrok` atau `localtunnel` jika ingin mengakses Web UI

### 🔧 Troubleshooting

#### Jika Hadoop tidak start:
```python
# Cek log untuk error
!cat $HADOOP_HOME/logs/hadoop-*-namenode-*.log | tail -50
!cat $HADOOP_HOME/logs/hadoop-*-datanode-*.log | tail -50
```

#### Jika HDFS connection error:
```python
# Cek apakah services berjalan
!jps

# Restart services jika perlu
import subprocess
import os
subprocess.run(['hdfs', '--daemon', 'stop', 'datanode'], env=os.environ)
subprocess.run(['hdfs', '--daemon', 'stop', 'namenode'], env=os.environ)
time.sleep(2)
subprocess.run(['hdfs', '--daemon', 'start', 'namenode'], env=os.environ)
time.sleep(3)
subprocess.run(['hdfs', '--daemon', 'start', 'datanode'], env=os.environ)
```

#### Jika hdfs3 library error:
Notebook ini sudah dilengkapi dengan alternatif otomatis menggunakan subprocess wrapper. Jika hdfs3 gagal diinstall:
1. Notebook akan otomatis membuat wrapper HDFS menggunakan subprocess
2. File `hdfs_helper.py` akan dibuat otomatis
3. File `sinta_journals_etl.py` akan dimodifikasi untuk menggunakan wrapper

Tidak perlu melakukan tindakan manual, notebook akan menangani ini secara otomatis.

### 📊 Akses NameNode Web UI

Untuk mengakses NameNode Web UI di Colab, gunakan ngrok:

```python
# Install ngrok
!pip install pyngrok

# Setup ngrok tunnel
from pyngrok import ngrok
public_url = ngrok.connect(9870)
print(f"NameNode Web UI: {public_url}")
```

## Alternatif: Tanpa Hadoop

Jika mengalami masalah dengan Hadoop di Colab, Anda dapat menjalankan ETL tanpa HDFS:

```python
from sinta_journals_etl import SINTAJournalsETL

# ETL tanpa HDFS
etl = SINTAJournalsETL(
    input_folder="output_journals",
    output_folder="output_data"
)

etl.run(output_format='both', save_to_hdfs=False)
```

## Output yang Dihasilkan

Setelah ETL selesai, Anda akan mendapatkan:

1. **File Lokal** (di folder `output_data/`):
   - `journals_data_[timestamp].csv` - Data dalam format CSV
   - `journals_data_[timestamp].json` - Data dalam format JSON
   - `extraction_stats_[timestamp].json` - Statistik ekstraksi

2. **File HDFS** (di `/user/sinta/journals/`):
   - File yang sama seperti di lokal, tersimpan di HDFS
   - **Struktur folder**: `/user/sinta/journals/{YYYY}/{MM}/{DD}/{filename}`
   - **Contoh**: `/user/sinta/journals/2026/01/12/journals_data_20260112_060509.csv`

## Download Hasil

Untuk mendownload hasil dari Colab:

```python
from google.colab import files

# Download CSV
files.download('output_data/journals_data_[timestamp].csv')

# Download JSON
files.download('output_data/journals_data_[timestamp].json')

# Download stats
files.download('output_data/extraction_stats_[timestamp].json')
```

Atau download dari HDFS:

```python
# Cek struktur folder berdasarkan tanggal
from datetime import datetime
today = datetime.now().strftime("%Y/%m/%d")
hdfs_path = f"/user/sinta/journals/{today}"

# List file di HDFS
!hdfs dfs -ls -R /user/sinta/journals/

# Download dari HDFS ke lokal
!hdfs dfs -get {hdfs_path}/journals_data_*.csv .
!hdfs dfs -get {hdfs_path}/journals_data_*.json .
!hdfs dfs -get {hdfs_path}/extraction_stats_*.json .
```

## Lokasi File di HDFS

File-file yang dihasilkan dari proses ETL disimpan di HDFS dengan struktur berikut:

### Struktur Direktori:
```
/user/sinta/journals/
└── {YYYY}/
    └── {MM}/
        └── {DD}/
            ├── journals_data_{timestamp}.csv
            ├── journals_data_{timestamp}.json
            └── extraction_stats_{timestamp}.json
```

### Contoh Path Lengkap:
Jika ETL dijalankan pada tanggal **12 Januari 2026 pukul 06:05:09**, file akan tersimpan di:
- `/user/sinta/journals/2026/01/12/journals_data_20260112_060509.csv`
- `/user/sinta/journals/2026/01/12/journals_data_20260112_060509.json`
- `/user/sinta/journals/2026/01/12/extraction_stats_20260112_060509.json`

### Cara Mengakses File di HDFS:

1. **List semua file di HDFS:**
   ```bash
   !hdfs dfs -ls -R /user/sinta/journals/
   ```

2. **Lihat isi file CSV:**
   ```bash
   !hdfs dfs -cat /user/sinta/journals/2026/01/12/journals_data_*.csv | head -20
   ```

3. **Download file ke lokal:**
   ```bash
   !hdfs dfs -get /user/sinta/journals/2026/01/12/journals_data_*.csv .
   ```

4. **Copy file ke lokal:**
   ```bash
   !hdfs dfs -copyToLocal /user/sinta/journals/2026/01/12/journals_data_*.csv .
   ```

5. **Cek ukuran file:**
   ```bash
   !hdfs dfs -du -h /user/sinta/journals/2026/01/12/
   ```

## Referensi

- Repository: https://github.com/Herutriana44/sinta_web_scraping
- Hadoop Documentation: https://hadoop.apache.org/docs/
- HDFS3 Python Library: https://github.com/dask/hdfs3

