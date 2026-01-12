"""
ETL Framework untuk Ekstraksi Data Jurnal SINTA dari File HTML
===============================================================
Framework ini melakukan:
- Extract: Membaca semua file HTML dari folder output_journals
- Transform: Mengekstrak data jurnal dari HTML
- Load: Menyimpan data ke CSV, JSON, dan HDFS

Cara Penggunaan:
----------------
1. Pastikan semua file HTML ada di folder 'output_journals'
2. Install dependencies: pip install -r requirements.txt
3. Jalankan script: python sinta_journals_etl.py

Atau gunakan sebagai module:
    from sinta_journals_etl import SINTAJournalsETL
    
    # Tanpa HDFS
    etl = SINTAJournalsETL(
        input_folder="output_journals",
        output_folder="output_data"
    )
    etl.run(output_format='both')  # 'csv', 'json', atau 'both'
    
    # Dengan HDFS
    etl = SINTAJournalsETL(
        input_folder="output_journals",
        output_folder="output_data",
        hdfs_enabled=True,
        hdfs_url="http://namenode:9870",
        hdfs_path="/user/sinta/journals"
    )
    etl.run(output_format='both', save_to_hdfs=True)

Output:
-------
- journals_data_[timestamp].csv: Data dalam format CSV
- journals_data_[timestamp].json: Data dalam format JSON
- extraction_stats_[timestamp].json: Statistik ekstraksi
- HDFS: Data juga disimpan ke HDFS jika dikonfigurasi
- etl_journals.log: Log file proses ETL
"""

import os
import re
import json
import csv
import io
from pathlib import Path
from typing import List, Dict, Optional
from datetime import datetime
from bs4 import BeautifulSoup
import logging

# Setup logging terlebih dahulu
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('etl_journals.log', encoding='utf-8'),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)

# HDFS support (optional)
try:
    from hdfs3 import HDFileSystem
    HDFS_AVAILABLE = True
except ImportError:
    HDFS_AVAILABLE = False
    logger.warning("⚠️ Library hdfs3 tidak tersedia. Fitur HDFS akan dinonaktifkan.")
    logger.warning("⚠️ Install dengan: pip install hdfs3")


class SINTAJournalsETL:
    """Framework ETL untuk ekstraksi data jurnal SINTA"""
    
    def __init__(self, input_folder: str = "output_journals", 
                 output_folder: str = "output_data",
                 hdfs_enabled: bool = False,
                 hdfs_url: str = "http://localhost:9870",
                 hdfs_path: str = "/user/sinta/journals",
                 hdfs_user: Optional[str] = None):
        """
        Inisialisasi ETL Framework
        
        Args:
            input_folder: Folder yang berisi file HTML
            output_folder: Folder untuk menyimpan hasil ekstraksi
            hdfs_enabled: Aktifkan penyimpanan ke HDFS
            hdfs_url: URL HDFS NameNode (default: http://localhost:9870)
            hdfs_path: Path di HDFS untuk menyimpan data
            hdfs_user: Username untuk koneksi HDFS (optional)
        """
        self.input_folder = Path(input_folder)
        self.output_folder = Path(output_folder)
        self.output_folder.mkdir(exist_ok=True)
        
        # HDFS Configuration
        self.hdfs_enabled = hdfs_enabled and HDFS_AVAILABLE
        self.hdfs_url = hdfs_url
        self.hdfs_path = hdfs_path.rstrip('/')
        self.hdfs_user = hdfs_user
        self.hdfs_client = None
        
        if self.hdfs_enabled:
            try:
                # Parse URL untuk mendapatkan host dan port
                from urllib.parse import urlparse
                parsed = urlparse(hdfs_url)
                host = parsed.hostname or 'localhost'
                port = parsed.port or 9870
                
                self.hdfs_client = HDFileSystem(host=host, port=port, user=hdfs_user)
                logger.info(f"✅ Koneksi HDFS berhasil: {host}:{port}")
                
                # Buat direktori di HDFS jika belum ada
                if not self.hdfs_client.exists(self.hdfs_path):
                    self.hdfs_client.makedirs(self.hdfs_path)
                    logger.info(f"📁 Direktori HDFS dibuat: {self.hdfs_path}")
            except Exception as e:
                logger.error(f"❌ Gagal koneksi ke HDFS: {str(e)}")
                logger.warning("⚠️ HDFS dinonaktifkan. Data hanya akan disimpan secara lokal.")
                self.hdfs_enabled = False
                self.hdfs_client = None
        elif hdfs_enabled and not HDFS_AVAILABLE:
            logger.warning("⚠️ HDFS diminta tetapi library hdfs3 tidak tersedia.")
            logger.warning("⚠️ Install dengan: pip install hdfs3")
        
        self.journals_data = []
        self.stats = {
            'total_files': 0,
            'total_journals': 0,
            'successful_extractions': 0,
            'failed_extractions': 0,
            'hdfs_saves': 0,
            'hdfs_errors': 0,
            'errors': []
        }
    
    def extract(self) -> List[Dict]:
        """
        Extract: Membaca semua file HTML dari folder input
        
        Returns:
            List of dictionaries berisi data mentah HTML
        """
        logger.info(f"🔍 Memulai proses Extract dari folder: {self.input_folder}")
        
        html_files = sorted(self.input_folder.glob("*.html"))
        self.stats['total_files'] = len(html_files)
        
        if not html_files:
            logger.warning(f"⚠️ Tidak ada file HTML ditemukan di {self.input_folder}")
            return []
        
        logger.info(f"📁 Ditemukan {len(html_files)} file HTML")
        
        extracted_data = []
        for html_file in html_files:
            try:
                logger.info(f"📄 Memproses: {html_file.name}")
                with open(html_file, 'r', encoding='utf-8') as f:
                    content = f.read()
                    extracted_data.append({
                        'file': html_file.name,
                        'content': content
                    })
            except Exception as e:
                error_msg = f"Error membaca {html_file.name}: {str(e)}"
                logger.error(f"❌ {error_msg}")
                self.stats['errors'].append(error_msg)
        
        return extracted_data
    
    def transform(self, extracted_data: List[Dict]) -> List[Dict]:
        """
        Transform: Mengekstrak data jurnal dari HTML
        
        Args:
            extracted_data: List data HTML yang sudah diekstrak
            
        Returns:
            List of dictionaries berisi data jurnal yang sudah ditransformasi
        """
        logger.info("🔄 Memulai proses Transform")
        
        all_journals = []
        
        for data in extracted_data:
            html_content = data['content']
            file_name = data['file']
            
            try:
                soup = BeautifulSoup(html_content, 'html.parser')
                
                # Cari semua journal entries (setiap journal ada di div dengan class "list-item row mt-3")
                journal_items = soup.find_all('div', class_='list-item row mt-3')
                
                logger.info(f"📊 Ditemukan {len(journal_items)} jurnal di {file_name}")
                
                for idx, item in enumerate(journal_items):
                    try:
                        journal_data = self._extract_journal_data(item, file_name, idx + 1)
                        if journal_data:
                            all_journals.append(journal_data)
                            self.stats['successful_extractions'] += 1
                    except Exception as e:
                        error_msg = f"Error ekstraksi jurnal #{idx+1} dari {file_name}: {str(e)}"
                        logger.error(f"❌ {error_msg}")
                        self.stats['errors'].append(error_msg)
                        self.stats['failed_extractions'] += 1
                
            except Exception as e:
                error_msg = f"Error parsing HTML {file_name}: {str(e)}"
                logger.error(f"❌ {error_msg}")
                self.stats['errors'].append(error_msg)
        
        self.journals_data = all_journals
        self.stats['total_journals'] = len(all_journals)
        
        logger.info(f"✅ Transform selesai. Total jurnal diekstrak: {len(all_journals)}")
        return all_journals
    
    def _extract_journal_data(self, journal_item, source_file: str, index: int) -> Optional[Dict]:
        """
        Ekstrak data dari satu item jurnal
        
        Args:
            journal_item: BeautifulSoup element untuk satu jurnal
            source_file: Nama file sumber
            index: Index jurnal dalam file
            
        Returns:
            Dictionary berisi data jurnal
        """
        try:
            # Nama Jurnal
            name_elem = journal_item.find('div', class_='affil-name')
            journal_name = ""
            profile_url = ""
            if name_elem:
                name_link = name_elem.find('a')
                if name_link:
                    journal_name = name_link.get_text(strip=True)
                    profile_url = name_link.get('href', '')
            
            # Links (Google Scholar, Website, Editor URL)
            abbrev_div = journal_item.find('div', class_='affil-abbrev')
            google_scholar_url = ""
            website_url = ""
            editor_url = ""
            
            if abbrev_div:
                links = abbrev_div.find_all('a')
                for link in links:
                    href = link.get('href', '')
                    text = link.get_text(strip=True)
                    if 'scholar.google' in href:
                        google_scholar_url = href
                    elif 'Website' in text or 'el-globe' in str(link):
                        website_url = href
                    elif 'Editor URL' in text or 'el-globe-alt' in str(link):
                        editor_url = href
            
            # Affiliation/Publisher
            loc_div = journal_item.find('div', class_='affil-loc')
            affiliation = ""
            affiliation_url = ""
            if loc_div:
                loc_link = loc_div.find('a')
                if loc_link:
                    affiliation = loc_link.get_text(strip=True)
                    affiliation_url = loc_link.get('href', '')
            
            # ISSN dan Subject Area
            profile_id_div = journal_item.find('div', class_='profile-id')
            p_issn = ""
            e_issn = ""
            subject_area = ""
            
            if profile_id_div:
                text = profile_id_div.get_text()
                # Extract P-ISSN
                p_issn_match = re.search(r'P-ISSN\s*:\s*(\d+)', text)
                if p_issn_match:
                    p_issn = p_issn_match.group(1)
                
                # Extract E-ISSN
                e_issn_match = re.search(r'E-ISSN\s*:\s*(\d+)', text)
                if e_issn_match:
                    e_issn = e_issn_match.group(1)
                
                # Extract Subject Area
                subject_match = re.search(r'Subject Area\s*:\s*([^|]+)', text)
                if subject_match:
                    subject_area = subject_match.group(1).strip()
            
            # Accreditation Status
            stat_prev_div = journal_item.find('div', class_='stat-prev')
            accreditation = ""
            is_scopus_indexed = False
            is_garuda_indexed = False
            garuda_url = ""
            
            if stat_prev_div:
                # Accreditation
                accredited_elem = stat_prev_div.find('span', class_='num-stat accredited')
                if accredited_elem:
                    acc_text = accredited_elem.get_text(strip=True)
                    acc_match = re.search(r'(S\d+)', acc_text)
                    if acc_match:
                        accreditation = acc_match.group(1)
                
                # Scopus Indexed
                scopus_elem = stat_prev_div.find('span', class_='num-stat scopus-indexed')
                if scopus_elem:
                    is_scopus_indexed = True
                
                # Garuda Indexed
                garuda_elem = stat_prev_div.find('a', href=re.compile(r'garuda'))
                if garuda_elem:
                    is_garuda_indexed = True
                    garuda_url = garuda_elem.get('href', '')
            
            # Statistics (Impact, H5-index, Citations)
            stats_div = journal_item.find('div', class_='stat-profile journal-list-stat')
            impact_score = ""
            h5_index = ""
            citations_5yr = ""
            citations_total = ""
            
            if stats_div:
                stat_rows = stats_div.find_all('div', class_='row no-gutters')
                if stat_rows:
                    stat_items = stats_div.find_all('div', class_='pr-num')
                    stat_labels = stats_div.find_all('div', class_='pr-txt')
                    
                    for label, value in zip(stat_labels, stat_items):
                        label_text = label.get_text(strip=True)
                        value_text = value.get_text(strip=True)
                        
                        if 'Impact' in label_text:
                            impact_score = value_text
                        elif 'H5-index' in label_text:
                            h5_index = value_text
                        elif 'Citations 5yr' in label_text:
                            citations_5yr = value_text
                        elif 'Citations' in label_text and '5yr' not in label_text:
                            citations_total = value_text
            
            # Journal Cover Image
            cover_img = journal_item.find('img', class_='journal-cover')
            cover_image_url = ""
            if cover_img:
                cover_image_url = cover_img.get('src', '')
            
            # Extract journal ID from profile URL
            journal_id = ""
            if profile_url:
                id_match = re.search(r'/profile/(\d+)', profile_url)
                if id_match:
                    journal_id = id_match.group(1)
            
            journal_data = {
                'journal_id': journal_id,
                'journal_name': journal_name,
                'profile_url': profile_url,
                'google_scholar_url': google_scholar_url,
                'website_url': website_url,
                'editor_url': editor_url,
                'affiliation': affiliation,
                'affiliation_url': affiliation_url,
                'p_issn': p_issn,
                'e_issn': e_issn,
                'subject_area': subject_area,
                'accreditation': accreditation,
                'is_scopus_indexed': is_scopus_indexed,
                'is_garuda_indexed': is_garuda_indexed,
                'garuda_url': garuda_url,
                'impact_score': impact_score,
                'h5_index': h5_index,
                'citations_5yr': citations_5yr,
                'citations_total': citations_total,
                'cover_image_url': cover_image_url,
                'source_file': source_file,
                'extraction_index': index,
                'extracted_at': datetime.now().isoformat()
            }
            
            return journal_data
            
        except Exception as e:
            logger.error(f"Error dalam _extract_journal_data: {str(e)}")
            return None
    
    def load(self, data: List[Dict], format: str = 'both', save_to_hdfs: bool = False) -> None:
        """
        Load: Menyimpan data ke file (CSV dan/atau JSON) dan HDFS
        
        Args:
            data: List data jurnal yang sudah ditransformasi
            format: Format output ('csv', 'json', atau 'both')
            save_to_hdfs: Simpan ke HDFS jika dikonfigurasi
        """
        logger.info(f"💾 Memulai proses Load (format: {format}, HDFS: {save_to_hdfs})")
        
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        
        # Simpan ke local filesystem
        if format in ['csv', 'both']:
            csv_file = self.output_folder / f"journals_data_{timestamp}.csv"
            self._save_to_csv(data, csv_file)
            logger.info(f"✅ Data disimpan ke CSV: {csv_file}")
            
            # Upload ke HDFS jika diminta
            if save_to_hdfs and self.hdfs_enabled:
                self._save_to_hdfs(csv_file, f"journals_data_{timestamp}.csv", 'csv')
        
        if format in ['json', 'both']:
            json_file = self.output_folder / f"journals_data_{timestamp}.json"
            self._save_to_json(data, json_file)
            logger.info(f"✅ Data disimpan ke JSON: {json_file}")
            
            # Upload ke HDFS jika diminta
            if save_to_hdfs and self.hdfs_enabled:
                self._save_to_hdfs(json_file, f"journals_data_{timestamp}.json", 'json')
        
        # Simpan statistik
        stats_file = self.output_folder / f"extraction_stats_{timestamp}.json"
        self._save_stats(stats_file)
        logger.info(f"✅ Statistik disimpan ke: {stats_file}")
        
        # Upload statistik ke HDFS jika diminta
        if save_to_hdfs and self.hdfs_enabled:
            self._save_to_hdfs(stats_file, f"extraction_stats_{timestamp}.json", 'json')
    
    def _save_to_csv(self, data: List[Dict], filepath: Path) -> None:
        """Menyimpan data ke CSV"""
        if not data:
            logger.warning("⚠️ Tidak ada data untuk disimpan ke CSV")
            return
        
        fieldnames = [
            'journal_id', 'journal_name', 'profile_url', 'google_scholar_url',
            'website_url', 'editor_url', 'affiliation', 'affiliation_url',
            'p_issn', 'e_issn', 'subject_area', 'accreditation',
            'is_scopus_indexed', 'is_garuda_indexed', 'garuda_url',
            'impact_score', 'h5_index', 'citations_5yr', 'citations_total',
            'cover_image_url', 'source_file', 'extraction_index', 'extracted_at'
        ]
        
        with open(filepath, 'w', newline='', encoding='utf-8') as f:
            writer = csv.DictWriter(f, fieldnames=fieldnames)
            writer.writeheader()
            writer.writerows(data)
    
    def _save_to_json(self, data: List[Dict], filepath: Path) -> None:
        """Menyimpan data ke JSON"""
        output = {
            'metadata': {
                'total_journals': len(data),
                'extraction_date': datetime.now().isoformat(),
                'source_folder': str(self.input_folder)
            },
            'journals': data
        }
        
        with open(filepath, 'w', encoding='utf-8') as f:
            json.dump(output, f, ensure_ascii=False, indent=2)
    
    def _save_stats(self, filepath: Path) -> None:
        """Menyimpan statistik ekstraksi"""
        stats_output = {
            'extraction_date': datetime.now().isoformat(),
            'statistics': self.stats
        }
        
        with open(filepath, 'w', encoding='utf-8') as f:
            json.dump(stats_output, f, ensure_ascii=False, indent=2)
    
    def _save_to_hdfs(self, local_file: Path, hdfs_filename: str, file_type: str = 'csv') -> None:
        """
        Menyimpan file ke HDFS
        
        Args:
            local_file: Path file lokal yang akan diupload
            hdfs_filename: Nama file di HDFS
            file_type: Tipe file ('csv' atau 'json')
        """
        if not self.hdfs_enabled or not self.hdfs_client:
            logger.warning("⚠️ HDFS tidak tersedia atau tidak dikonfigurasi")
            return
        
        try:
            # Buat path lengkap di HDFS dengan struktur folder berdasarkan tanggal
            date_folder = datetime.now().strftime("%Y/%m/%d")
            hdfs_full_path = f"{self.hdfs_path}/{date_folder}/{hdfs_filename}"
            
            # Pastikan direktori tanggal ada
            date_dir = f"{self.hdfs_path}/{date_folder}"
            if not self.hdfs_client.exists(date_dir):
                self.hdfs_client.makedirs(date_dir)
            
            # Baca file lokal dan upload ke HDFS
            with open(local_file, 'rb') as local_f:
                with self.hdfs_client.open(hdfs_full_path, 'wb') as hdfs_f:
                    hdfs_f.write(local_f.read())
            
            logger.info(f"✅ File berhasil diupload ke HDFS: {hdfs_full_path}")
            self.stats['hdfs_saves'] += 1
            
        except Exception as e:
            error_msg = f"Error upload ke HDFS {hdfs_filename}: {str(e)}"
            logger.error(f"❌ {error_msg}")
            self.stats['hdfs_errors'] += 1
            self.stats['errors'].append(error_msg)
    
    def save_dataframe_to_hdfs(self, data: List[Dict], hdfs_filename: str, 
                                format: str = 'json') -> None:
        """
        Menyimpan data langsung ke HDFS tanpa menyimpan ke local filesystem terlebih dahulu
        
        Args:
            data: List data jurnal yang sudah ditransformasi
            hdfs_filename: Nama file di HDFS (tanpa extension)
            format: Format file ('csv' atau 'json')
        """
        if not self.hdfs_enabled or not self.hdfs_client:
            logger.warning("⚠️ HDFS tidak tersedia atau tidak dikonfigurasi")
            return
        
        try:
            # Buat path lengkap di HDFS dengan struktur folder berdasarkan tanggal
            date_folder = datetime.now().strftime("%Y/%m/%d")
            date_dir = f"{self.hdfs_path}/{date_folder}"
            
            # Pastikan direktori tanggal ada
            if not self.hdfs_client.exists(date_dir):
                self.hdfs_client.makedirs(date_dir)
            
            if format == 'json':
                hdfs_full_path = f"{date_dir}/{hdfs_filename}.json"
                output = {
                    'metadata': {
                        'total_journals': len(data),
                        'extraction_date': datetime.now().isoformat(),
                        'source_folder': str(self.input_folder)
                    },
                    'journals': data
                }
                content = json.dumps(output, ensure_ascii=False, indent=2).encode('utf-8')
                
            elif format == 'csv':
                hdfs_full_path = f"{date_dir}/{hdfs_filename}.csv"
                # Buat CSV dalam memory
                output_buffer = io.StringIO()
                fieldnames = [
                    'journal_id', 'journal_name', 'profile_url', 'google_scholar_url',
                    'website_url', 'editor_url', 'affiliation', 'affiliation_url',
                    'p_issn', 'e_issn', 'subject_area', 'accreditation',
                    'is_scopus_indexed', 'is_garuda_indexed', 'garuda_url',
                    'impact_score', 'h5_index', 'citations_5yr', 'citations_total',
                    'cover_image_url', 'source_file', 'extraction_index', 'extracted_at'
                ]
                writer = csv.DictWriter(output_buffer, fieldnames=fieldnames)
                writer.writeheader()
                writer.writerows(data)
                content = output_buffer.getvalue().encode('utf-8')
            else:
                logger.error(f"❌ Format tidak didukung: {format}")
                return
            
            # Tulis ke HDFS
            with self.hdfs_client.open(hdfs_full_path, 'wb') as hdfs_f:
                hdfs_f.write(content)
            
            logger.info(f"✅ Data langsung disimpan ke HDFS: {hdfs_full_path}")
            self.stats['hdfs_saves'] += 1
            
        except Exception as e:
            error_msg = f"Error menyimpan langsung ke HDFS {hdfs_filename}: {str(e)}"
            logger.error(f"❌ {error_msg}")
            self.stats['hdfs_errors'] += 1
            self.stats['errors'].append(error_msg)
    
    def run(self, output_format: str = 'both', save_to_hdfs: bool = False) -> None:
        """
        Menjalankan seluruh proses ETL
        
        Args:
            output_format: Format output ('csv', 'json', atau 'both')
            save_to_hdfs: Simpan ke HDFS jika dikonfigurasi
        """
        logger.info("=" * 60)
        logger.info("🚀 Memulai ETL Framework untuk Data Jurnal SINTA")
        logger.info("=" * 60)
        
        start_time = datetime.now()
        
        try:
            # Extract
            extracted_data = self.extract()
            
            if not extracted_data:
                logger.error("❌ Tidak ada data yang berhasil diekstrak")
                return
            
            # Transform
            transformed_data = self.transform(extracted_data)
            
            if not transformed_data:
                logger.error("❌ Tidak ada data yang berhasil ditransformasi")
                return
            
            # Load
            self.load(transformed_data, format=output_format, save_to_hdfs=save_to_hdfs)
            
            # Summary
            end_time = datetime.now()
            duration = (end_time - start_time).total_seconds()
            
            logger.info("=" * 60)
            logger.info("✅ ETL Process Selesai!")
            logger.info(f"⏱️  Durasi: {duration:.2f} detik")
            logger.info(f"📁 Total file diproses: {self.stats['total_files']}")
            logger.info(f"📊 Total jurnal diekstrak: {self.stats['total_journals']}")
            logger.info(f"✅ Ekstraksi berhasil: {self.stats['successful_extractions']}")
            logger.info(f"❌ Ekstraksi gagal: {self.stats['failed_extractions']}")
            if self.hdfs_enabled:
                logger.info(f"📦 HDFS upload berhasil: {self.stats['hdfs_saves']}")
                if self.stats['hdfs_errors'] > 0:
                    logger.warning(f"⚠️ HDFS upload error: {self.stats['hdfs_errors']}")
            logger.info("=" * 60)
            
        except Exception as e:
            logger.error(f"❌ Error dalam proses ETL: {str(e)}", exc_info=True)


def main():
    """Main function untuk menjalankan ETL"""
    import argparse
    
    parser = argparse.ArgumentParser(description='ETL Framework untuk Data Jurnal SINTA')
    parser.add_argument('--hdfs', action='store_true', help='Aktifkan penyimpanan ke HDFS')
    parser.add_argument('--hdfs-url', default='http://localhost:9870', 
                       help='URL HDFS NameNode (default: http://localhost:9870)')
    parser.add_argument('--hdfs-path', default='/user/sinta/journals',
                       help='Path HDFS untuk menyimpan data (default: /user/sinta/journals)')
    parser.add_argument('--hdfs-user', default=None,
                       help='Username untuk koneksi HDFS (optional)')
    parser.add_argument('--format', choices=['csv', 'json', 'both'], default='both',
                       help='Format output (default: both)')
    parser.add_argument('--input-folder', default='output_journals',
                       help='Folder input HTML files (default: output_journals)')
    parser.add_argument('--output-folder', default='output_data',
                       help='Folder output lokal (default: output_data)')
    
    args = parser.parse_args()
    
    # Inisialisasi ETL
    etl = SINTAJournalsETL(
        input_folder=args.input_folder,
        output_folder=args.output_folder,
        hdfs_enabled=args.hdfs,
        hdfs_url=args.hdfs_url,
        hdfs_path=args.hdfs_path,
        hdfs_user=args.hdfs_user
    )
    
    # Jalankan ETL
    etl.run(output_format=args.format, save_to_hdfs=args.hdfs)


if __name__ == "__main__":
    main()

