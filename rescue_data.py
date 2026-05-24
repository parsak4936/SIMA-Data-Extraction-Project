import pandas as pd
import requests
import time
import csv

# --- CONFIGURATION ---
INPUT_FILE = "./output/papers_partial.csv" 
OUTPUT_FILE = "./output/Cristina_Publications_PERFECT.xlsx"
EMAIL_CONTACT = "wixloop.contact@gmail.com"

def fix_mixed_data():
    print("==================================================")
    print("🚀 INITIATING ADVANCED DATA RESCUE")
    print("==================================================")

    good_rows = []
    bad_rows = []

    print("📊 Scanning uneven CSV file row-by-row...")
    
    # 1. Read the file using the flexible CSV module instead of strict Pandas
    try:
        with open(INPUT_FILE, 'r', encoding='utf-8-sig') as f:
            reader = csv.reader(f)
            for row in reader:
                if not row: continue # Skip empty lines
                
                # Skip header rows
                if str(row[0]).lower() in ['first name', 'author_id']:
                    continue
                
                # 8 Columns = Old format (Missing names)
                if len(row) == 8:
                    bad_rows.append({
                        'author_id': row[0],
                        'title': row[1],
                        'year': row[2],
                        'journal': row[3],
                        'abstract': row[4],
                        'keywords': row[5],
                        'doi': row[6],
                        'url': row[7]
                    })
                # 10 Columns = New format (Has names)
                elif len(row) >= 10:
                    good_rows.append({
                        'First name': row[0],
                        'last name': row[1],
                        'author_id': row[2],
                        'title': row[3],
                        'year': row[4],
                        'journal': row[5],
                        'abstract': row[6],
                        'keywords': row[7],
                        'doi': row[8],
                        'url': row[9]
                    })
    except Exception as e:
        print(f"❌ Cannot load file: {e}")
        return

    print(f"✅ Found {len(good_rows)} perfectly formatted rows.")
    print(f"⚠️ Found {len(bad_rows)} rows requiring name rescue.")

    # 2. Fetch missing names ONLY for the bad rows
    if bad_rows:
        unique_bad_ids = list(set([r['author_id'] for r in bad_rows if str(r['author_id']).startswith('http')]))
        print(f"\n🔗 Fetching missing names from OpenAlex for {len(unique_bad_ids)} unique authors...")
        
        session = requests.Session()
        headers = {'User-Agent': f'mailto:{EMAIL_CONTACT}'}
        id_to_name = {}

        for i, author_id in enumerate(unique_bad_ids):
            clean_id = str(author_id).split('/')[-1]
            api_url = f"https://api.openalex.org/authors/{clean_id}"
            
            try:
                r = session.get(api_url, headers=headers, timeout=10)
                if r.status_code == 200:
                    full_name = r.json().get('display_name', '')
                    words = full_name.split()
                    if len(words) > 1:
                        first = " ".join(words[:-1])
                        last = words[-1].upper()
                    else:
                        first = full_name
                        last = ""
                    id_to_name[author_id] = {'First name': first, 'last name': last}
                else:
                    id_to_name[author_id] = {'First name': 'N/A', 'last name': 'N/A'}
            except Exception:
                id_to_name[author_id] = {'First name': 'Error', 'last name': 'Error'}
                
            time.sleep(0.1) # Polite API sleep

        # Inject the rescued names back into the bad rows
        print("💉 Injecting names...")
        for row in bad_rows:
            names = id_to_name.get(row['author_id'], {'First name': '', 'last name': ''})
            row['First name'] = names['First name']
            row['last name'] = names['last name']

    # 3. Combine both lists
    all_combined = good_rows + bad_rows
    
    # 4. Enforce Cristina's exact column order
    target_columns = [
        'First name', 'last name', 'author_id', 'title', 
        'year', 'journal', 'abstract', 'keywords', 'doi', 'url'
    ]
    
    df_final = pd.DataFrame(all_combined)[target_columns]
    
    # 5. Clean up and Export
    print("\n💾 Exporting perfectly aligned dataset...")
    df_final.drop_duplicates(subset=["doi", "title"], inplace=True)
    df_final.to_excel(OUTPUT_FILE, index=False)
    
    print("==================================================")
    print(f"🎉 DATASET FIXED. File saved as: {OUTPUT_FILE}")
    print("==================================================")

if __name__ == "__main__":
    fix_mixed_data()