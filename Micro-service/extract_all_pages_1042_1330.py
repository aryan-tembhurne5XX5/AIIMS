# extract_all_pages_1042_1330.py - Complete data extraction with incremental saves
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.chrome.options import Options
import pandas as pd
import time
import json
import os
from datetime import datetime

def setup_headless_driver():
    """Setup headless Chrome driver (no browser window)"""
    chrome_options = Options()
    
    # HEADLESS MODE - No browser window
    chrome_options.add_argument('--headless')
    chrome_options.add_argument('--no-sandbox')
    chrome_options.add_argument('--disable-dev-shm-usage')
    chrome_options.add_argument('--disable-gpu')
    chrome_options.add_argument('--window-size=1920,1080')
    chrome_options.add_argument('--user-agent=Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36')
    
    print("🔧 Setting up headless Chrome driver...")
    
    try:
        driver = webdriver.Chrome(options=chrome_options)
        print("✅ Headless driver ready")
        return driver
    except Exception as e:
        print(f"❌ Driver setup failed: {e}")
        return None

def navigate_to_specific_page(driver, page_num):
    """Navigate to specific page number"""
    try:
        # Method 1: Look for direct page link
        page_selectors = [
            f"//a[text()='{page_num}' and contains(@class, 'paginate')]",
            f"//a[@data-dt-idx='{page_num}']",
            f"//a[text()='{page_num}']"
        ]
        
        for selector in page_selectors:
            try:
                page_link = WebDriverWait(driver, 5).until(
                    EC.element_to_be_clickable((By.XPATH, selector))
                )
                driver.execute_script("arguments[0].click();", page_link)
                time.sleep(2)
                return True
            except:
                continue
        
        # Method 2: Use pagination input if available
        try:
            page_input = driver.find_element(By.CSS_SELECTOR, "input[type='number']")
            page_input.clear()
            page_input.send_keys(str(page_num))
            page_input.send_keys("\n")
            time.sleep(2)
            return True
        except:
            pass
        
        # Method 3: Navigate using Next/Previous buttons
        current_page = get_current_page_number(driver)
        if current_page:
            if page_num > current_page:
                # Click Next repeatedly
                clicks_needed = min(page_num - current_page, 20)  # Limit clicks
                for _ in range(clicks_needed):
                    try:
                        next_btn = driver.find_element(By.XPATH, "//a[contains(text(), 'Next') or contains(@aria-label, 'Next')]")
                        driver.execute_script("arguments[0].click();", next_btn)
                        time.sleep(1)
                    except:
                        break
                return True
            elif page_num < current_page:
                # Click Previous repeatedly
                clicks_needed = min(current_page - page_num, 20)
                for _ in range(clicks_needed):
                    try:
                        prev_btn = driver.find_element(By.XPATH, "//a[contains(text(), 'Previous') or contains(@aria-label, 'Previous')]")
                        driver.execute_script("arguments[0].click();", prev_btn)
                        time.sleep(1)
                    except:
                        break
                return True
        
        return False
        
    except Exception as e:
        print(f"Navigation error for page {page_num}: {e}")
        return False

def get_current_page_number(driver):
    """Get current active page number"""
    try:
        active_selectors = [
            ".paginate_button.current",
            ".page-item.active a",
            ".current",
            "[aria-current='page']"
        ]
        
        for selector in active_selectors:
            try:
                active_page = driver.find_element(By.CSS_SELECTOR, selector)
                page_text = active_page.text.strip()
                if page_text.isdigit():
                    return int(page_text)
            except:
                continue
        
        return None
    except:
        return None

def extract_all_page_data(driver, page_num):
    """Extract ALL data from current page (no filtering)"""
    page_data = []
    
    try:
        # Wait for table to load
        WebDriverWait(driver, 10).until(
            EC.presence_of_element_located((By.CSS_SELECTOR, "tbody tr"))
        )
        
        # Get all table rows
        rows = driver.find_elements(By.CSS_SELECTOR, "tbody tr")
        
        for row_index, row in enumerate(rows):
            try:
                cells = row.find_elements(By.TAG_NAME, "td")
                
                # Extract data from all columns
                if len(cells) >= 7:
                    row_data = {
                        'page_number': page_num,
                        'row_index': row_index + 1,
                        'sr_no': cells[0].text.strip(),
                        'term_id': cells[1].text.strip(),
                        'parent_id': cells[2].text.strip(),
                        'code': cells[3].text.strip(),
                        'word': cells[4].text.strip(),
                        'short_definition': cells[5].text.strip(),
                        'long_definition': cells[6].text.strip(),
                        'reference': cells[7].text.strip() if len(cells) > 7 else '',
                        'extraction_timestamp': datetime.now().isoformat()
                    }
                    
                    # Only add if we have essential data
                    if row_data['term_id'] or row_data['code']:
                        page_data.append(row_data)
            
            except Exception as e:
                print(f"Error extracting row {row_index} on page {page_num}: {e}")
                continue
                
    except Exception as e:
        print(f"Error extracting page {page_num}: {e}")
    
    return page_data

def save_incremental_data(all_data, csv_filename):
    """Save data incrementally after each page"""
    try:
        df = pd.DataFrame(all_data)
        df.to_csv(csv_filename, index=False, encoding='utf-8')
        return True
    except Exception as e:
        print(f"Error saving data: {e}")
        return False

def extract_pages_1042_1330():
    """Extract ALL data from pages 1042-1330 with incremental saves"""
    
    driver = setup_headless_driver()
    if not driver:
        return
    
    # Setup output file with timestamp
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    csv_filename = f'namaste_pages_1042_1330_complete_{timestamp}.csv'
    progress_file = f'extraction_progress_{timestamp}.txt'
    
    all_extracted_data = []
    successful_pages = []
    failed_pages = []
    
    try:
        print("🚀 Navigating to NAMASTE SAT-Combined...")
        driver.get("https://namaste.ayush.gov.in/sat_Ayurveda")
        
        # Click SAT-COMBINED tab
        WebDriverWait(driver, 20).until(
            EC.element_to_be_clickable((By.XPATH, "//a[contains(text(), 'SAT-COMBINED')]"))
        )
        
        sat_combined_tab = driver.find_element(By.XPATH, "//a[contains(text(), 'SAT-COMBINED')]")
        driver.execute_script("arguments[0].click();", sat_combined_tab)
        time.sleep(5)
        
        print(f"📊 Starting extraction from pages 1042-1330...")
        print(f"💾 CSV file: {csv_filename}")
        print(f"📝 Progress file: {progress_file}")
        
        # Extract each page from 1042 to 1330
        total_pages = 1330 - 1042 + 1
        
        for current_page in range(1042, 1331):
            page_start_time = time.time()
            
            try:
                print(f"\n📄 Processing page {current_page}...")
                
                # Navigate to specific page
                if navigate_to_specific_page(driver, current_page):
                    time.sleep(3)  # Wait for page load
                    
                    # Extract ALL data from current page
                    page_data = extract_all_page_data(driver, current_page)
                    
                    if page_data:
                        # Add to main dataset
                        all_extracted_data.extend(page_data)
                        successful_pages.append(current_page)
                        
                        # SAVE INCREMENTALLY after each page
                        if save_incremental_data(all_extracted_data, csv_filename):
                            page_time = time.time() - page_start_time
                            print(f"✅ Page {current_page}: {len(page_data)} terms extracted, CSV updated ({page_time:.1f}s)")
                        else:
                            print(f"⚠️ Page {current_page}: Data extracted but CSV save failed")
                        
                        # Save progress
                        progress_info = {
                            'last_completed_page': current_page,
                            'total_terms_extracted': len(all_extracted_data),
                            'successful_pages': len(successful_pages),
                            'failed_pages': len(failed_pages),
                            'timestamp': datetime.now().isoformat()
                        }
                        
                        with open(progress_file, 'w') as f:
                            json.dump(progress_info, f, indent=2)
                        
                    else:
                        failed_pages.append(current_page)
                        print(f"⚠️ Page {current_page}: No data found")
                
                else:
                    failed_pages.append(current_page)
                    print(f"❌ Page {current_page}: Navigation failed")
                
                # Progress update every 10 pages
                if current_page % 10 == 0:
                    progress_percent = ((current_page - 1042) / total_pages) * 100
                    print(f"\n🔄 PROGRESS UPDATE:")
                    print(f"   Completed: {progress_percent:.1f}% ({current_page - 1042}/{total_pages} pages)")
                    print(f"   Total terms extracted: {len(all_extracted_data)}")
                    print(f"   Successful pages: {len(successful_pages)}")
                    print(f"   Failed pages: {len(failed_pages)}")
                
                # Small delay between pages to be respectful
                time.sleep(1)
                
            except Exception as e:
                failed_pages.append(current_page)
                print(f"❌ Error on page {current_page}: {e}")
                continue
        
        # Final save and summary
        print(f"\n🎯 EXTRACTION COMPLETED!")
        print(f"📊 FINAL SUMMARY:")
        print(f"   Total pages processed: {len(successful_pages) + len(failed_pages)}")
        print(f"   Successful pages: {len(successful_pages)}")
        print(f"   Failed pages: {len(failed_pages)}")
        print(f"   Total terms extracted: {len(all_extracted_data)}")
        print(f"   CSV file: {csv_filename}")
        
        if failed_pages:
            print(f"\n❌ FAILED PAGES: {failed_pages[:10]}{'...' if len(failed_pages) > 10 else ''}")
        
        # Save final JSON backup
        json_filename = csv_filename.replace('.csv', '.json')
        with open(json_filename, 'w', encoding='utf-8') as f:
            json.dump(all_extracted_data, f, ensure_ascii=False, indent=2)
        print(f"💾 JSON backup: {json_filename}")
        
    except Exception as e:
        print(f"❌ Critical error: {e}")
    
    finally:
        print("🔒 Closing browser...")
        driver.quit()

def main():
    """Main execution"""
    print("🎯 NAMASTE Complete Data Extraction (Pages 1042-1330)")
    print("📊 Extracting ALL data (no filtering)")
    print("💾 Incremental CSV saves after each page")
    print("🔒 Running in HEADLESS mode")
    print("=" * 60)
    
    extract_pages_1042_1330()

if __name__ == "__main__":
    main()
