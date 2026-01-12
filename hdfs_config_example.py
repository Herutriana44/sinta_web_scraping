"""
Contoh Konfigurasi HDFS untuk SINTA Journals ETL
=================================================
File ini berisi contoh penggunaan ETL dengan HDFS
"""

from sinta_journals_etl import SINTAJournalsETL

# Contoh 1: ETL tanpa HDFS (default)
print("=" * 60)
print("Contoh 1: ETL tanpa HDFS")
print("=" * 60)
etl1 = SINTAJournalsETL(
    input_folder="output_journals",
    output_folder="output_data"
)
# etl1.run(output_format='both')

# Contoh 2: ETL dengan HDFS (localhost)
print("\n" + "=" * 60)
print("Contoh 2: ETL dengan HDFS (localhost)")
print("=" * 60)
etl2 = SINTAJournalsETL(
    input_folder="output_journals",
    output_folder="output_data",
    hdfs_enabled=True,
    hdfs_url="http://localhost:9870",
    hdfs_path="/user/sinta/journals",
    hdfs_user="hadoop"  # optional
)
# etl2.run(output_format='both', save_to_hdfs=True)

# Contoh 3: ETL dengan HDFS (remote server)
print("\n" + "=" * 60)
print("Contoh 3: ETL dengan HDFS (remote server)")
print("=" * 60)
etl3 = SINTAJournalsETL(
    input_folder="output_journals",
    output_folder="output_data",
    hdfs_enabled=True,
    hdfs_url="http://namenode.example.com:9870",
    hdfs_path="/data/sinta/journals",
    hdfs_user="sinta_user"
)
# etl3.run(output_format='both', save_to_hdfs=True)

# Contoh 4: Simpan langsung ke HDFS tanpa local filesystem
print("\n" + "=" * 60)
print("Contoh 4: Simpan langsung ke HDFS")
print("=" * 60)
etl4 = SINTAJournalsETL(
    input_folder="output_journals",
    output_folder="output_data",
    hdfs_enabled=True,
    hdfs_url="http://localhost:9870",
    hdfs_path="/user/sinta/journals"
)

# Extract dan Transform
# extracted_data = etl4.extract()
# transformed_data = etl4.transform(extracted_data)

# Simpan langsung ke HDFS tanpa menyimpan ke local
# etl4.save_dataframe_to_hdfs(transformed_data, "journals_data", format='json')
# etl4.save_dataframe_to_hdfs(transformed_data, "journals_data", format='csv')

print("\n✅ Contoh konfigurasi selesai!")
print("\nCara menjalankan dari command line:")
print("  python sinta_journals_etl.py --hdfs --hdfs-url http://localhost:9870 --hdfs-path /user/sinta/journals")

