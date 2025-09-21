# extract_working.py - Simple working parser for ALL records
import requests
import json
import pandas as pd
from datetime import datetime

def extract_all_records():
    """Extract all 14,968 records from the JavaScript file"""
    print("🚀 NAMASTE Complete Extraction - All 14,968 Records")
    print("📥 Downloading JavaScript file...")
    
    js_url = "https://namaste.ayush.gov.in/admin/js/codes/ayu_sat_table_combined.js"
    
    try:
        response = requests.get(js_url, timeout=60)  # Longer timeout
        content = response.text
        print(f"✅ Downloaded {len(content):,} characters")
    except Exception as e:
        print(f"❌ Download error: {e}")
        return
    
    print("🔍 Extracting JSON data...")
    
    try:
        # We know exactly where the JSON starts and ends from debug
        json_start = content.find('[{"rec_id":1')  # Start of JSON array
        json_end = content.rfind('}]') + 2  # End of JSON array
        
        if json_start >= 0 and json_end > json_start:
            json_str = content[json_start:json_end]
            print(f"✅ Found JSON data: {len(json_str):,} characters")
            
            print("🔄 Parsing JSON (this may take a moment)...")
            data = json.loads(json_str)
            
            print(f"✅ Successfully parsed {len(data):,} records!")
            
        else:
            print("❌ Could not locate JSON boundaries")
            return
            
    except json.JSONDecodeError as e:
        print(f"❌ JSON parsing error: {e}")
        return
    except Exception as e:
        print(f"❌ Extraction error: {e}")
        return
    
    print("📊 Converting to DataFrame...")
    
    try:
        # Convert to DataFrame
        df = pd.DataFrame(data)
        df['extraction_timestamp'] = datetime.now().isoformat()
        
        print(f"✅ DataFrame created:")
        print(f"   Records: {len(df):,}")
        print(f"   Columns: {len(df.columns)}")
        
        # Show columns
        print(f"   Available columns: {list(df.columns)}")
        
    except Exception as e:
        print(f"❌ DataFrame error: {e}")
        return
    
    print("💾 Saving to CSV...")
    
    try:
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        filename = f'namaste_complete_all_{timestamp}.csv'
        
        df.to_csv(filename, index=False, encoding='utf-8')
        
        print(f"✅ EXTRACTION SUCCESSFUL!")
        print(f"📁 File: {filename}")
        print(f"📊 Total records: {len(df):,}")
        print(f"💾 File size: ~{len(df) * len(df.columns) * 30 / 1024 / 1024:.1f} MB")
        
        # Show data overview
        print(f"\n📋 DATA OVERVIEW:")
        
        # Show record ID range
        if 'rec_id' in df.columns:
            min_rec = df['rec_id'].min()
            max_rec = df['rec_id'].max()
            print(f"   Record ID range: {min_rec} to {max_rec}")
        
        # Show term_id patterns
        if 'term_id' in df.columns:
            unique_prefixes = df['term_id'].str.split('.').str[0].value_counts().head(10)
            print(f"   Top term_id prefixes:")
            for prefix, count in unique_prefixes.items():
                print(f"      {prefix}: {count} terms")
        
        # Show first 5 records
        print(f"\n📝 FIRST 5 RECORDS:")
        for i in range(min(5, len(df))):
            rec_id = df.iloc[i].get('rec_id', 'N/A')
            term_id = df.iloc[i].get('term_id', 'N/A')
            wordtree = df.iloc[i].get('wordtree', 'N/A')
            w_trans = df.iloc[i].get('w_trans', 'N/A')[:30]
            print(f"   {i+1}. ID:{rec_id:5} | {term_id:12} | {wordtree:15} | {w_trans}")
        
        # Show last 5 records  
        print(f"\n📝 LAST 5 RECORDS:")
        for i in range(max(0, len(df)-5), len(df)):
            rec_id = df.iloc[i].get('rec_id', 'N/A')
            term_id = df.iloc[i].get('term_id', 'N/A')
            wordtree = df.iloc[i].get('wordtree', 'N/A')
            w_trans = df.iloc[i].get('w_trans', 'N/A')[:30]
            print(f"   {i+1}. ID:{rec_id:5} | {term_id:12} | {wordtree:15} | {w_trans}")
        
        print(f"\n🎯 SUCCESS! Now you have ALL the data.")
        print(f"💡 You can filter this CSV however you want to get pages 1042-1330!")
        
        return filename
        
    except Exception as e:
        print(f"❌ Save error: {e}")
        return None

if __name__ == "__main__":
    extract_all_records()
