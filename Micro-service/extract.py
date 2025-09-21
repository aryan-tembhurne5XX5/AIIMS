# extract.py
import sys
import subprocess

# Check and install required packages
required_packages = ['selenium', 'pandas', 'openpyxl']

for package in required_packages:
    try:
        __import__(package)
    except ImportError:
        print(f"Installing {package}...")
        subprocess.check_call([sys.executable, '-m', 'pip', 'install', package])

from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.chrome.options import Options
import pandas as pd
import time
import json
import os

def setup_chrome_driver():
    """Setup Chrome driver with proper options for macOS"""
    chrome_options = Options()
    chrome_options.add_argument('--no-sandbox')
    chrome_options.add_argument('--disable-dev-shm-usage')
    chrome_options.add_argument('--disable-web-security')
    chrome_options.add_argument('--allow-running-insecure-content')
    
    # Uncomment below to run headless (no browser window)
    # chrome_options.add_argument('--headless')
    
    try:
        # Try to create driver
        driver = webdriver.Chrome(options=chrome_options)
        return driver
    except Exception as e:
        print(f"❌ Chrome driver setup failed: {e}")
        print("💡 Please install ChromeDriver:")
        print("   brew install chromedriver")
        return None

def extract_namaste_data():
    """Extract SAT-Combined data from NAMASTE portal"""
    
    driver = setup_chrome_driver()
    if not driver:
        return []
    
    extracted_data = []
    
    try:
        print("🚀 Navigating to NAMASTE portal...")
        driver.get("https://namaste.ayush.gov.in/sat_Ayurveda")
        
        # Wait for page load
        WebDriverWait(driver, 15).until(
            EC.presence_of_element_located((By.TAG_NAME, "body"))
        )
        
        print("📋 Looking for SAT-COMBINED tab...")
        
        # Try multiple selectors for SAT-COMBINED tab
        tab_selectors = [
            "//a[contains(text(), 'SAT-COMBINED')]",
            "//button[contains(text(), 'SAT-COMBINED')]",
            "//div[contains(text(), 'SAT-COMBINED')]",
            "#pills-tab11",
            "[data-bs-target='#pills-t11']"
        ]
        
        sat_combined_tab = None
        for selector in tab_selectors:
            try:
                if selector.startswith('//'):
                    sat_combined_tab = driver.find_element(By.XPATH, selector)
                else:
                    sat_combined_tab = driver.find_element(By.CSS_SELECTOR, selector)
                break
            except:
                continue
        
        if not sat_combined_tab:
            print("❌ Could not find SAT-COMBINED tab")
            return []
        
        print("✅ Found SAT-COMBINED tab, clicking...")
        driver.execute_script("arguments[0].click();", sat_combined_tab)
        time.sleep(5)
        
        print("🔍 Looking for table data...")
        
        # Wait for table to appear
        WebDriverWait(driver, 15).until(
            EC.presence_of_element_located((By.TAG_NAME, "table"))
        )
        
        # Try to show all entries
        try:
            show_all_selector = driver.find_element(By.CSS_SELECTOR, "select[name*='length'] option[value='-1']")
            show_all_selector.click()
            time.sleep(10)
            print("✅ Set to show all entries")
        except:
            print("⚠️ Could not set 'show all', proceeding with current view...")
        
        # Extract table data
        rows = driver.find_elements(By.CSS_SELECTOR, "tbody tr")
        print(f"📊 Found {len(rows)} table rows")
        
        for i, row in enumerate(rows):
            try:
                cells = row.find_elements(By.TAG_NAME, "td")
                
                if len(cells) >= 7:
                    term_data = {
                        'term_id': cells[0].text.strip(),
                        'parent_id': cells[1].text.strip(),
                        'code': cells[2].text.strip(),
                        'word': cells[3].text.strip(),
                        'short_definition': cells[4].text.strip(),
                        'long_definition': cells[5].text.strip(),
                        'reference': cells[6].text.strip() if len(cells) > 6 else ''
                    }
                    
                    if term_data['term_id'] and term_data['code']:
                        extracted_data.append(term_data)
                        
                        # Progress indicator
                        if i % 50 == 0 and i > 0:
                            print(f"🔄 Processed {i} rows, extracted {len(extracted_data)} terms...")
            
            except Exception as e:
                continue
        
        print(f"✅ Extraction completed: {len(extracted_data)} terms found")
        
    except Exception as e:
        print(f"❌ Error during extraction: {e}")
    
    finally:
        driver.quit()
    
    return extracted_data

def save_data(data):
    """Save extracted data to files"""
    if not data:
        print("❌ No data to save")
        return
    
    # Create output directory
    os.makedirs('output', exist_ok=True)
    
    # Save as CSV
    df = pd.DataFrame(data)
    csv_file = 'output/namaste_sat_combined.csv'
    df.to_csv(csv_file, index=False, encoding='utf-8')
    print(f"✅ Saved CSV: {csv_file}")
    
    # Save as JSON
    json_file = 'output/namaste_sat_combined.json'
    with open(json_file, 'w', encoding='utf-8') as f:
        json.dump(data, f, ensure_ascii=False, indent=2)
    print(f"✅ Saved JSON: {json_file}")
    
    # Save as Excel
    try:
        excel_file = 'output/namaste_sat_combined.xlsx'
        df.to_excel(excel_file, index=False)
        print(f"✅ Saved Excel: {excel_file}")
    except:
        print("⚠️ Could not save Excel file")
    
    # Print analysis
    print(f"\n📊 DATA ANALYSIS:")
    print(f"   Total terms: {len(data)}")
    
    # Find morbidity terms
    morbidity_terms = []
    for term in data:
        if any(keyword in term['word'].lower() or keyword in term['short_definition'].lower()
               for keyword in ['vyādhi', 'roga', 'vikāra', 'disorder', 'disease', 'syndrome', 'condition']):
            morbidity_terms.append(term)
    
    print(f"   Morbidity terms: {len(morbidity_terms)}")
    
    if morbidity_terms:
        morbidity_file = 'output/namaste_morbidity_only.csv'
        pd.DataFrame(morbidity_terms).to_csv(morbidity_file, index=False, encoding='utf-8')
        print(f"✅ Saved morbidity terms: {morbidity_file}")
        
        print(f"\n🏥 SAMPLE MORBIDITY TERMS:")
        for term in morbidity_terms[:5]:
            print(f"   {term['code']}: {term['word']} - {term['short_definition']}")

def main():
    """Main function"""
    print("🎯 NAMASTE SAT-Combined Data Extraction")
    print("=" * 50)
    
    # Extract data
    data = extract_namaste_data()
    
    # Save data
    if data:
        save_data(data)
        print("\n✅ Extraction completed successfully!")
    else:
        print("\n❌ No data extracted")

if __name__ == "__main__":
    main()
