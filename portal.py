from flask import Flask, request, jsonify, render_template_string
import pandas as pd
import json
from rapidfuzz import process, fuzz

app = Flask(__name__)

# Config - CSV and JSON filenames
csv_files = {
    'ayurveda': 'Ayurvedic_SAT_Morbidity_csv.csv',  # Your actual filename for Ayurveda (a)
    'unani': 'Unani_Morbidity_csv.csv',    # Unani (b)
    'siddha': 'Siddha_Morbidity_csv.csv'       # Siddha (c)
}
icd_json_file = 'tm_complete_dataset.json'  # ICD-11 TM2 JSON filename

# Load CSVs into dataframes
lang_dfs = {}
for lang, file in csv_files.items():
    lang_dfs[lang] = pd.read_csv(file)

# Load ICD-11 JSON (assuming line-delimited JSON)
icd_data = []
with open(icd_json_file, encoding='utf-8') as f:
    for line in f:
        line = line.strip().rstrip(',')
        if line.startswith('{') and line.endswith('}'):
            try:
                icd_data.append(json.loads(line))
            except Exception:
                continue

# Helper to create term index for all languages and ICD terms
term_index = {}  # term_lower -> list of dicts with keys lang, term, icd_id etc.

# Index ICD terms by title and synonyms (lowercase)
for icd_rec in icd_data:
    icd_title = icd_rec.get('title', '').strip()
    if icd_title:
        term_index.setdefault(icd_title.lower(), []).append({
            'lang': 'ICD-11',
            'term': icd_title,
            'icd_id': icd_rec.get('id'),
            'icd_code': icd_rec.get('code'),
            'source_record': icd_rec
        })

# Also index synonyms if present
for icd_rec in icd_data:
    synonyms = icd_rec.get('synonym', [])
    if synonyms and isinstance(synonyms, list):
        for syn in synonyms:
            syn_val = syn.get('value') if isinstance(syn, dict) else syn
            if syn_val:
                term_index.setdefault(syn_val.lower(), []).append({
                    'lang': 'ICD-11',
                    'term': syn_val,
                    'icd_id': icd_rec.get('id'),
                    'icd_code': icd_rec.get('code'),
                    'source_record': icd_rec
                })

# Index CSV terms per language — assume columns: 'EnglishTerm', 'LocalTerm' (adjust as needed)
for lang, df in lang_dfs.items():
    for idx, row in df.iterrows():
        # Index by English term
        eng_term = str(row.get('EnglishTerm', '')).strip()
        if eng_term:
            term_index.setdefault(eng_term.lower(), []).append({
                'lang': lang,
                'term': eng_term,
                'csv_row': row.to_dict()
            })
        # Index by local term if exists
        local_term = None
        # Check for local term column - could be language specific e.g. TamilTerm or similar
        for col in df.columns:
            if col.lower().startswith(lang[:3]) and 'term' in col.lower():
                local_term = str(row.get(col, '')).strip()
                break
        if local_term:
            term_index.setdefault(local_term.lower(), []).append({
                'lang': lang,
                'term': local_term,
                'csv_row': row.to_dict()
            })

def find_closest(term, choices, threshold=80):
    res = process.extractOne(term, choices, scorer=fuzz.ratio)
    if res and res[1] >= threshold:
        return res[0], res[1]
    return None, None

@app.route("/")
def index():
    # Simple HTML UI for autocomplete and display
    return render_template_string("""
<html><head>
<script>
async function searchTerm(term) {
    if(term.length < 2) {
        document.getElementById('results').innerHTML = '';
        return;
    }
    let resp = await fetch('/autocomplete?term=' + encodeURIComponent(term));
    let data = await resp.json();
    let html = '';
    for(let item of data) {
        html += '<div><b>Term:</b> ' + item.term + 
            ' (' + item.lang + ')<br>';
        if(item.lang === 'ICD-11') {
            html += '<b>ICD-11 Code:</b> ' + item.icd_code + '<br>';
            html += '<b>ICD-11 Term:</b> ' + item.term + '<br>';
            // Fetch mapped Ayurvedic, Unani, Siddha for this ICD-11
            html += '<small><b>Mapped NAMASTE terms:</b><br />';
            let mapResp = await fetch('/map_icd?icd_id=' + item.icd_id);
            let maps = await mapResp.json();
            if(maps.length === 0) html += 'No mappings found.';
            for(let m of maps) {
                html += '<b>' + m.lang + ':</b> ' + m.term + '<br>';
            }
            html += '</small>';
        }
        html += '</div><hr>';
    }
    document.getElementById('results').innerHTML = html;
}
</script>
</head><body>
<h3>Search AYUSH/ICD Term:</h3>
<input type="text" oninput="searchTerm(this.value)">
<div id="results"></div>
</body></html>
""")

@app.route('/autocomplete')
def autocomplete():
    term = request.args.get('term', '').strip().lower()
    results = []
    if term:
        keys = list(term_index.keys())
        matches = [k for k in keys if term in k]
        if not matches:
            matches = process.extract(term, keys, scorer=fuzz.ratio, limit=10)
            matches = [m[0] for m in matches if m[1] > 60]
        added = set()
        for k in matches:
            for item in term_index.get(k, []):
                if item.get('term') not in added:
                    added.add(item.get('term'))
                    results.append({
                        'term': item.get('term'),
                        'lang': item.get('lang'),
                        'icd_id': item.get('icd_id', ''),
                        'icd_code': item.get('icd_code', '')
                    })
        results = results[:10]
    print(f"Autocomplete search for '{term}' returns {len(results)} results")  # Debug log
    return jsonify(results)


@app.route('/map_icd')
def map_icd():
    icd_id = request.args.get('icd_id', '')
    if not icd_id:
        return jsonify([])
    # Find ICD record
    icd_rec = next((rec for rec in icd_data if rec.get('id') == icd_id), None)
    if not icd_rec:
        return jsonify([])
    icd_title = icd_rec.get('title', '')
    # Map to each NAMASTE language by fuzzy matching EnglishTerm columns
    mapped = []
    for lang, df in lang_dfs.items():
        eng_terms = df['EnglishTerm'].fillna('').tolist()
        match, score = find_closest(icd_title, eng_terms)
        if match:
            row = df[df['EnglishTerm'] == match].iloc[0]
            mapped.append({'lang': lang, 'term': match, 'score': score})
    return jsonify(mapped)

if __name__ == "__main__":
    app.run(debug=True)
