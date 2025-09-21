import requests
import json
import os
import time
from datetime import datetime
from concurrent.futures import ThreadPoolExecutor, as_completed
from threading import Lock
import threading
from typing import Dict, List, Optional, Set
import unicodedata

class FastTMExtractor:
    """
    Fast, optimized TM data extractor with progressive saving and detailed preservation
    """
    
    def __init__(self, client_id: str, client_secret: str, base_dir: str = "tm_complete_dataset"):
        self.client_id = ""
        self.client_secret = ""
        self.token_endpoint = 'https://icdaccessmanagement.who.int/connect/token'
        self.base_uri = 'https://id.who.int/icd'
        self.access_token = None
        self.base_dir = base_dir
        
        # Thread safety
        self.lock = Lock()
        self.progress_lock = Lock()
        
        # Create directories
        os.makedirs(base_dir, exist_ok=True)
        os.makedirs(os.path.join(base_dir, 'entities'), exist_ok=True)
        os.makedirs(os.path.join(base_dir, 'chunks'), exist_ok=True)
        
        # Progress tracking
        self.progress_file = os.path.join(base_dir, 'extraction_progress.json')
        self.progress = self.load_progress()
        
        # Complete dataset storage
        self.complete_dataset = {
            'metadata': {
                'extraction_timestamp': datetime.now().isoformat(),
                'source': 'ICD-11 2025-01 Release - TM Module',
                'extractor_version': '2.0',
                'total_entities': 0,
                'extraction_completed': False
            },
            'tm_hierarchy': {},
            'flat_entities': {},
            'code_index': {},
            'sanskrit_terms': {},
            'language_mapping': {},
            'statistics': {
                'total_disorders': 0,
                'total_patterns': 0,
                'total_index_terms': 0,
                'languages_detected': {}
            }
        }
        
        # Processed entity tracking
        self.processed_entities: Set[str] = set()
        
    def load_progress(self) -> Dict:
        """Load existing progress"""
        if os.path.exists(self.progress_file):
            try:
                with open(self.progress_file, 'r', encoding='utf-8') as f:
                    return json.load(f)
            except Exception:
                pass
        return {
            'tm_chapter_fetched': False,
            'entities_processed': [],
            'last_update': None,
            'total_found': 0,
            'extraction_stage': 'not_started'
        }
    
    def save_progress(self):
        """Thread-safe progress saving"""
        with self.progress_lock:
            self.progress['last_update'] = datetime.now().isoformat()
            self.progress['total_found'] = len(self.processed_entities)
            try:
                with open(self.progress_file, 'w', encoding='utf-8') as f:
                    json.dump(self.progress, f, indent=2, ensure_ascii=False)
            except Exception as e:
                print(f"⚠️ Progress save failed: {e}")
    
    def authenticate(self) -> bool:
        """Authenticate with ICD-11 API"""
        payload = {
            'client_id': self.client_id,
            'client_secret': self.client_secret,
            'scope': 'icdapi_access',
            'grant_type': 'client_credentials'
        }
        
        try:
            response = requests.post(self.token_endpoint, data=payload, verify=True, timeout=30)
            response.raise_for_status()
            token_data = response.json()
            self.access_token = token_data['access_token']
            print("✅ Authentication successful!")
            return True
        except Exception as e:
            print(f"❌ Authentication failed: {e}")
            return False
    
    def get_headers(self) -> Dict[str, str]:
        """Get API headers"""
        return {
            'Authorization': f'Bearer {self.access_token}',
            'Accept': 'application/json',
            'Accept-Language': 'en',
            'API-Version': 'v2'
        }
    
    def detect_language(self, text: str) -> str:
        """Detect language of traditional medicine terms"""
        if not text:
            return 'unknown'
        
        text_lower = text.lower()
        
        # Sanskrit patterns (most comprehensive)
        sanskrit_indicators = [
            r'[ḥṃṅñṭḍṇśṣṛ]',  # Sanskrit diacritics
            r'(aṃ|aḥ|tam|ṁ|yaṃ|dhiḥ)$',  # Sanskrit endings
            r'^(pra|vi|sam|upa|ni|ā)',  # Sanskrit prefixes
            r'(vaṃ|gaṃ|dhātu|vāta|pitta|kapha|agni)',  # Sanskrit medical terms
        ]
        
        # Arabic/Persian patterns (Unani)
        arabic_indicators = [
            r'(al-|el-|dubayla)',  # Arabic articles/terms
            r'(kabid|jigar)',  # Unani terms
        ]
        
        # Tamil patterns (Siddha)
        tamil_indicators = [
            r'(katti|vali|roga)',  # Tamil medical terms
        ]
        
        import re
        if any(re.search(pattern, text, re.IGNORECASE | re.UNICODE) for pattern in sanskrit_indicators):
            return 'sanskrit'
        elif any(re.search(pattern, text, re.IGNORECASE) for pattern in arabic_indicators):
            return 'arabic_persian'
        elif any(re.search(pattern, text, re.IGNORECASE) for pattern in tamil_indicators):
            return 'tamil'
        else:
            return 'english_or_unknown'
    
    def extract_text_value(self, obj) -> str:
        """Extract text from multilingual object, preserving Unicode"""
        if isinstance(obj, dict):
            return obj.get('@value', '') or obj.get('en', '') or str(obj)
        return str(obj) if obj else ''
    
    def extract_text_list(self, obj_list: List) -> List[str]:
        """Extract text list preserving Unicode"""
        result = []
        for item in obj_list:
            text = self.extract_text_value(item)
            if text and text.strip():
                result.append(text.strip())
        return result
    
    def extract_index_terms_detailed(self, index_terms: List) -> List[Dict]:
        """Extract index terms with language detection and detailed analysis"""
        terms = []
        for term in index_terms:
            if isinstance(term, dict):
                text = self.extract_text_value(term.get('label', {}))
                if text and text.strip():
                    language = self.detect_language(text)
                    
                    term_data = {
                        'text': text.strip(),
                        'language': language,
                        'foundationReference': term.get('foundationReference', ''),
                        'termId': term.get('@id', ''),
                        'raw': term
                    }
                    terms.append(term_data)
                    
                    # Update language statistics
                    with self.lock:
                        if language not in self.complete_dataset['statistics']['languages_detected']:
                            self.complete_dataset['statistics']['languages_detected'][language] = 0
                        self.complete_dataset['statistics']['languages_detected'][language] += 1
        return terms
    
    def process_single_entity(self, entity_uri: str, depth: int = 0, parent_path: List[str] = None) -> Optional[Dict]:
        """Process a single entity with full detail extraction"""
        if parent_path is None:
            parent_path = []
            
        entity_id = entity_uri.split('/')[-1]
        if entity_id in self.processed_entities:
            return None
        
        try:
            response = requests.get(entity_uri, headers=self.get_headers(), verify=True, timeout=30)
            response.raise_for_status()
            entity_data = response.json()
            
            # Extract complete details
            entity_details = {
                'uri': entity_uri,
                'id': entity_id,
                'title': self.extract_text_value(entity_data.get('title', {})),
                'code': self.extract_text_value(entity_data.get('code', {})),
                'definition': self.extract_text_value(entity_data.get('definition', {})),
                'longDefinition': self.extract_text_value(entity_data.get('longDefinition', {})),
                'fullySpecifiedName': self.extract_text_value(entity_data.get('fullySpecifiedName', {})),
                'synonym': self.extract_text_list(entity_data.get('synonym', [])),
                'narrowerTerm': self.extract_text_list(entity_data.get('narrowerTerm', [])),
                'indexTerm': self.extract_index_terms_detailed(entity_data.get('indexTerm', [])),
                'inclusion': self.extract_text_list(entity_data.get('inclusion', [])),
                'exclusion': self.extract_text_list(entity_data.get('exclusion', [])),
                'note': self.extract_text_list(entity_data.get('note', [])),
                'codingNote': self.extract_text_list(entity_data.get('codingNote', [])),
                'children': entity_data.get('child', []),
                'parent': entity_data.get('parent', []),
                'browserUrl': entity_data.get('browserUrl', ''),
                'foundationChildElsewhere': entity_data.get('foundationChildElsewhere', []),
                'isLeaf': len(entity_data.get('child', [])) == 0,
                'childCount': len(entity_data.get('child', [])),
                'depth': depth,
                'parentPath': parent_path.copy(),
                'extractionTimestamp': datetime.now().isoformat(),
                'raw_data': entity_data
            }
            
            # Mark as processed
            with self.lock:
                self.processed_entities.add(entity_id)
                self.complete_dataset['flat_entities'][entity_id] = entity_details
                
                # Update code index
                if entity_details['code']:
                    self.complete_dataset['code_index'][entity_details['code']] = entity_id
                    
                    # Count disorders vs patterns
                    if 'disorder' in entity_details['title'].lower():
                        self.complete_dataset['statistics']['total_disorders'] += 1
                    elif 'pattern' in entity_details['title'].lower():
                        self.complete_dataset['statistics']['total_patterns'] += 1
                
                # Index Sanskrit terms separately
                for index_term in entity_details['indexTerm']:
                    if index_term['language'] == 'sanskrit':
                        if entity_details['code'] not in self.complete_dataset['sanskrit_terms']:
                            self.complete_dataset['sanskrit_terms'][entity_details['code']] = []
                        self.complete_dataset['sanskrit_terms'][entity_details['code']].append({
                            'term': index_term['text'],
                            'entity_id': entity_id
                        })
                
                self.complete_dataset['statistics']['total_index_terms'] += len(entity_details['indexTerm'])
                self.complete_dataset['metadata']['total_entities'] = len(self.processed_entities)
            
            # Save individual entity
            entity_file = os.path.join(self.base_dir, 'entities', f'{entity_id}.json')
            try:
                with open(entity_file, 'w', encoding='utf-8') as f:
                    json.dump(entity_details, f, indent=2, ensure_ascii=False)
            except Exception as e:
                print(f"⚠️ Failed to save entity {entity_id}: {e}")
            
            # Progress logging
            code = entity_details['code']
            title = entity_details['title'][:60] + "..." if len(entity_details['title']) > 60 else entity_details['title']
            indent = "  " * depth
            print(f"{indent}✅ {code} {title} ({len(entity_details['children'])} children, {len(entity_details['indexTerm'])} terms)")
            
            return entity_details
            
        except Exception as e:
            print(f"❌ Failed to process {entity_uri}: {e}")
            return None
    
    def extract_all_tm_entities_recursive(self, start_uri: str, max_depth: int = 15) -> bool:
        """Recursively extract all TM entities starting from TM chapter"""
        print(f"🔄 Starting recursive extraction from: {start_uri}")
        
        def recursive_worker(uri: str, depth: int = 0, parent_path: List[str] = None):
            if depth > max_depth:
                return
            
            entity = self.process_single_entity(uri, depth, parent_path)
            if not entity:
                return
            
            entity_id = entity['id']
            current_path = (parent_path or []) + [entity_id]
            
            # Process children
            for child_uri in entity['children']:
                recursive_worker(child_uri, depth + 1, current_path)
                time.sleep(0.05)  # Rate limiting
        
        # Start recursive extraction
        recursive_worker(start_uri)
        return True
    
    def save_complete_dataset(self, filename: str = None):
        """Save the complete dataset with all extracted data"""
        if filename is None:
            filename = os.path.join(self.base_dir, 'tm_complete_dataset.json')
        
        # Update final metadata
        self.complete_dataset['metadata']['extraction_completed'] = True
        self.complete_dataset['metadata']['completion_timestamp'] = datetime.now().isoformat()
        
        try:
            with open(filename, 'w', encoding='utf-8') as f:
                json.dump(self.complete_dataset, f, indent=2, ensure_ascii=False)
            print(f"💾 Complete dataset saved: {filename}")
            
            # Also save flattened version
            flat_filename = filename.replace('.json', '_flat.json')
            flat_data = {
                'metadata': self.complete_dataset['metadata'],
                'entities': self.complete_dataset['flat_entities'],
                'code_index': self.complete_dataset['code_index'],
                'sanskrit_terms': self.complete_dataset['sanskrit_terms'],
                'statistics': self.complete_dataset['statistics']
            }
            
            with open(flat_filename, 'w', encoding='utf-8') as f:
                json.dump(flat_data, f, indent=2, ensure_ascii=False)
            print(f"💾 Flattened dataset saved: {flat_filename}")
            
            # Save progress every 50 entities
            if len(self.processed_entities) % 50 == 0:
                self.save_progress()
            
            return True
            
        except Exception as e:
            print(f"❌ Failed to save complete dataset: {e}")
            return False
    
    def run_complete_extraction(self) -> bool:
        """Main method to run complete TM extraction"""
        print("🚀 FAST TM COMPLETE EXTRACTOR v2.0")
        print("=" * 60)
        
        if not self.authenticate():
            return False
        
        # TM Chapter URI (from your screenshots: Chapter 718687701)
        tm_chapter_uri = f"{self.base_uri}/release/11/2025-01/mms/718687701"
        
        print(f"📋 Starting extraction from TM Chapter: {tm_chapter_uri}")
        self.progress['extraction_stage'] = 'extracting_entities'
        
        # Extract all entities recursively
        success = self.extract_all_tm_entities_recursive(tm_chapter_uri)
        
        if success:
            self.progress['extraction_stage'] = 'saving_dataset'
            self.save_complete_dataset()
            
            # Final statistics
            stats = self.complete_dataset['statistics']
            print(f"\n🎉 EXTRACTION COMPLETED!")
            print(f"📊 Total Entities: {self.complete_dataset['metadata']['total_entities']}")
            print(f"🏥 Disorders: {stats['total_disorders']}")
            print(f"🔄 Patterns: {stats['total_patterns']}")
            print(f"🔤 Index Terms: {stats['total_index_terms']}")
            print(f"🌐 Languages: {list(stats['languages_detected'].keys())}")
            print(f"📂 Data saved in: {os.path.abspath(self.base_dir)}")
            
            # Show Sanskrit terms sample
            if self.complete_dataset['sanskrit_terms']:
                print(f"\n📜 Sanskrit Terms Sample:")
                for code, terms in list(self.complete_dataset['sanskrit_terms'].items())[:5]:
                    print(f"   {code}: {', '.join([t['term'] for t in terms])}")
            
            self.progress['extraction_stage'] = 'completed'
            self.save_progress()
            return True
        
        return False

def main():
    """Main function for fast TM extraction"""
    
    # Replace with your credentials
    CLIENT_ID = "36ef45cc-f83f-44c1-8798-86d9ba9799df_9b1ffcef-c78b-48cd-9991-362ea3ee8a0e"
    CLIENT_SECRET = "njnCf1CT63WxRAcUiRl8Nxjdb0h7dDZJuwGG8jJdmnE="
    
    print("🧹 Starting fresh extraction...")
    
    # Initialize extractor
    extractor = FastTMExtractor(
        client_id=CLIENT_ID,
        client_secret=CLIENT_SECRET,
        base_dir="tm_complete_dataset"
    )
    
    # Run complete extraction
    success = extractor.run_complete_extraction()
    
    if success:
        print("\n✅ TM EXTRACTION SUCCESSFUL!")
        print(f"\n📁 Generated Files:")
        print(f"   • tm_complete_dataset.json - Complete hierarchical dataset")
        print(f"   • tm_complete_dataset_flat.json - Flattened entities")
        print(f"   • entities/ - Individual entity files")
        print(f"   • extraction_progress.json - Progress tracking")
        print(f"\n🔍 Ready for NAMASTE code mapping!")
    else:
        print("❌ EXTRACTION FAILED!")

if __name__ == "__main__":
    main()
