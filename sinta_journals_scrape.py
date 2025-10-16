import os
import time
from selenium import webdriver
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.common.exceptions import TimeoutException, NoSuchElementException, WebDriverException
from webdriver_manager.chrome import ChromeDriverManager

# --- Config Chrome ---
chrome_options = Options()
chrome_options.add_argument("--start-maximized")
chrome_options.add_argument("--disable-notifications")
chrome_options.add_argument("--disable-infobars")
chrome_options.add_argument("--disable-extensions")
# chrome_options.add_argument("--headless=new")  # uncomment jika mau headless

driver = webdriver.Chrome(service=Service(ChromeDriverManager().install()), options=chrome_options)

def save_page_html(driver, output_dir, page_number):
    os.makedirs(output_dir, exist_ok=True)
    timestamp = time.strftime("%Y%m%d_%H%M%S")
    filename = os.path.join(output_dir, f"sinta_journals_page{page_number}_{timestamp}.html")
    with open(filename, "w", encoding="utf-8") as f:
        f.write(driver.page_source)
    print(f"💾 HTML halaman {page_number} disimpan -> {filename}")

try:
    url = "https://sinta.kemdiktisaintek.go.id/journals/index/"
    driver.get(url)
    wait = WebDriverWait(driver, 70)

    # --- buka modal filter dan apply filter seperti sebelumnya ---
    filter_button = wait.until(EC.element_to_be_clickable((By.XPATH, "//button[@data-target='#filterJournal']")))
    driver.execute_script("arguments[0].click();", filter_button)
    print("✅ Modal 'Filter' dibuka")

    wait.until(EC.visibility_of_element_located((By.ID, "filterJournal")))
    time.sleep(1)

    checkbox = wait.until(EC.element_to_be_clickable((By.ID, "filter_accreditation1")))
    driver.execute_script("arguments[0].scrollIntoView({block:'center'});", checkbox)
    time.sleep(0.8)
    if not checkbox.is_selected():
        checkbox.click()
        print("✅ Checkbox 'filter_accreditation1' dicentang")
    else:
        print("☑️ Checkbox sudah tercentang")

    submit_button = wait.until(EC.element_to_be_clickable((By.XPATH, "//button[@name='filter_journals' and @value='1']")))
    driver.execute_script("arguments[0].click();", submit_button)
    print("✅ Tombol 'Filter Journal' diklik")

    # tunggu hasil awal (tunggu tabel atau sedikit jeda)
    try:
        wait.until(EC.presence_of_element_located((By.CSS_SELECTOR, "table.table")))
    except TimeoutException:
        # fallback sleep jika table tidak muncul cepat
        time.sleep(10)

    # --- simpan halaman pertama ---
    output_dir = "output_journals"
    page_number = 1
    save_page_html(driver, output_dir, page_number)

    # --- loop klik "Next" sampai tidak bisa lagi ---
    max_pages = 23 # safety cap
    while True:
        if page_number >= max_pages:
            print(f"⚠️ Mencapai batas max_pages ({max_pages}). Hentikan loop.")
            break

        try:
            # cari link Next (teks persis 'Next' — normalize whitespace)
            next_elem = driver.find_element(By.XPATH, "//a[contains(@class,'page-link') and normalize-space(.)='Next']")
        except NoSuchElementException:
            print("ℹ️ Tombol 'Next' tidak ditemukan. Sudah mencapai halaman terakhir.")
            break

        # Periksa atribut yang menandakan tidak bisa diklik
        cls = (next_elem.get_attribute("class") or "").lower()
        aria_disabled = (next_elem.get_attribute("aria-disabled") or "").lower()
        href = next_elem.get_attribute("href")

        # Jika link tidak punya href atau disabled class/aria -> stop
        if "disabled" in cls or aria_disabled == "true" or (not href or href.strip() == "" or href.startswith("javascript:")):
            print("ℹ️ Tombol 'Next' ditemukan tetapi dalam keadaan tidak aktif/disabled. Stop.")
            break

        # Coba klik Next dengan WebDriverWait element_to_be_clickable
        try:
            wait_short = WebDriverWait(driver, 10)
            clickable_next = wait_short.until(EC.element_to_be_clickable((By.XPATH, "//a[contains(@class,'page-link') and normalize-space(.)='Next']")))
        except TimeoutException:
            print("⚠️ Next element tidak menjadi clickable (timeout). Hentikan loop.")
            break

        # scroll + klik
        try:
            driver.execute_script("arguments[0].scrollIntoView({block:'center'});", clickable_next)
            time.sleep(0.3)
            # klik via JS untuk keandalan
            driver.execute_script("arguments[0].click();", clickable_next)
            print(f"➡️ Klik 'Next' untuk pindah ke halaman berikutnya (dari page {page_number})")
        except WebDriverException as e:
            print("⚠️ Gagal klik 'Next':", e)
            break

        # tunggu halaman berikutnya termuat (cek perubahan page_number atau kehadiran tabel)
        time.sleep(10)  # sedikit jeda awal
        try:
            wait.until(EC.presence_of_element_located((By.CSS_SELECTOR, "table.table")))
        except TimeoutException:
            # kalau tabel lama masih ada atau ajax lambat, beri waktu tambahan
            time.sleep(10)

        # increment page counter dan simpan HTML
        page_number += 1
        save_page_html(driver, output_dir, page_number)

        # loop akan ulang dan cari tombol Next lagi

    print("✅ Selesai iterasi pagination.")

except Exception as e:
    print("❌ Terjadi error:", e)
    # (opsional) simpan diagnostics
    try:
        os.makedirs("logs", exist_ok=True)
        ts = time.strftime("%Y%m%d_%H%M%S")
        driver.save_screenshot(os.path.join("logs", f"exception_{ts}.png"))
        with open(os.path.join("logs", f"exception_page_{ts}.html"), "w", encoding="utf-8") as f:
            f.write(driver.page_source)
        print("🧾 Debug artifacts tersimpan di folder logs/")
    except Exception:
        pass

finally:
    input("Tekan Enter untuk keluar dan menutup browser...")
    driver.quit()
