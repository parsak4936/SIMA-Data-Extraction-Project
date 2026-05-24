# OpenAlex Author Paper Extraction - Updated Guide

## 📋 What's Been Improved

### ✅ Fixed Issues
1. **Graceful Interruption (Ctrl+C)** - Script now saves progress safely when interrupted
2. **Timeout Protection** - If no response for 1 minute, script saves and exits automatically
3. **Progress Reset Mechanism** - New `--reset-progress` flag to start fresh
4. **Improved Rate Limiting** - 2 second delays between authors (reduced IP ban risk)
5. **Data Consolidation** - Partial data from previous runs automatically loaded and merged
6. **Better Error Handling** - Specific timeout/connection error handling with backoff

---

## 🚀 Running the Pipeline

### **Option 1: Resume from last checkpoint (DEFAULT)**
```bash
python main.py
```
- Resumes from last_index in progress.json
- Loads papers from previous extraction into memory
- Continues where it left off
- Safe interrupt with Ctrl+C

### **Option 2: Start completely fresh**
```bash
python main.py --reset-progress
```
- Deletes progress.json
- Deletes papers_partial.csv
- Starts extraction from index 0
- **Use this when starting a new dataset**

### **Option 3: Resume but don't reload partial data**
```bash
python main.py --no-consolidate
```
- Resumes from checkpoint
- Ignores papers_partial.csv (new memory-only session)
- Useful if partial file is corrupted

---

## 🛡️ Safety Features Explained

### 1. **Signal Handling (Ctrl+C)**
```
When you press Ctrl+C:
├─ Script catches the interrupt
├─ Saves current progress to progress.json
├─ Exports all collected papers to output/
├─ Exits gracefully
└─ Logs message: "To resume: python main.py"
```

### 2. **Timeout Detection (60 seconds)**
```
If no response from API for 60 seconds:
├─ Script detects stalled request
├─ Saves progress.json with current index
├─ Exports papers collected so far
├─ Exits with message: "Saving and exiting gracefully"
└─ Run "python main.py" to resume
```

### 3. **Rate Limiting**
```
Current delays:
- 2.0 seconds between each author search (prevents IP ban)
- 1.0 second between progress checkpoint saves
- 0.5 seconds between paginated API calls

Adjust in main.py if needed:
  Line ~150: time.sleep(2.0)  # Author delay
  Line ~200: time.sleep(1.0)  # Checkpoint delay
  Line ~150: time.sleep(0.5)  # Pagination delay (in api.py)
```

---

## 📊 Data Flow & Persistence

### File Structure
```
progress.json              ← Tracks: last_index, name, author_id, papers_count
├─ Auto-saved after each author
├─ Atomic write (tmp file → rename)
└─ Safe for interruption

output/
├─ papers_partial.csv      ← Incremental paper collection
│  ├─ Auto-appended after each successful author
│  ├─ Loaded at startup to resume in-memory cache
│  └─ Contains all papers extracted so far
│
└─ Papers_Output.xlsx      ← Final consolidated output
   └─ Generated at end (all unique papers deduplicated)

output/
└─ Audit_Log_Missing_Authors.csv
   └─ Authors not found or with 0 papers
```

### Resume Process
1. Script loads progress.json → gets `last_index`
2. Script loads papers_partial.csv → populates `all_papers`
3. Main loop skips rows 0 to `last_index-1`
4. Continues extraction from author at `last_index`
5. All subsequent papers merged with previous run

---

## 🔍 Progress Tracking Format

### progress.json
```json
{
    "last_index": 204,
    "last_processed_name": "VOLLERO Agostino",
    "found_id": "https://openalex.org/A5035300094",
    "papers_extracted": 12
}
```

- **last_index**: Row number (0-based) of last processed author
- **last_processed_name**: Name for easy debugging
- **found_id**: OpenAlex author ID (or "None" if not found)
- **papers_extracted**: Papers extracted for this author

---

## ⚠️ IP Ban Prevention Tips

**Your setup (1745 authors):**
- Estimated runtime: ~3.5 hours (at 2s per author)
- Total API calls: ~5,200+ (depends on papers per author)
- Current rate: ~0.5 authors/second (safe)

**If you get rate-limited (HTTP 429):**
1. Script will automatically back off 5 seconds and retry (up to 3 times)
2. If still failing, increase delays in main.py:
   ```python
   time.sleep(2.0)  → Change to time.sleep(5.0)  # Between authors
   ```
3. Or split extraction across multiple days

---

## 🐛 Troubleshooting

### "Script just stops without output"
**Likely:** Timeout triggered (60s no response)
- Check internet connection
- Verify OpenAlex API is up (https://openalex.org/)
- Resume with: `python main.py`

### "KeyError: 'Cognome e Nome'"
- Check your CSV column names match config.py
- CSV must have: "Cognome e Nome", "Ateneo", "Email universitaria"

### "papers_partial.csv is corrupted"
```bash
python main.py --no-consolidate  # Skip loading partial file
# or
python main.py --reset-progress  # Start completely fresh
```

### "I want to restart but keep some papers"
1. Manual backup: `cp output/papers_partial.csv output/papers_partial.backup.csv`
2. Manual reset: `del progress.json & del output/papers_partial.csv`
3. Restart: `python main.py`

---

## 📈 Output Columns

Final output (Papers_Output.xlsx):
```
First name | last name | author_id | title | year | journal | abstract | keywords | doi | url
-----------|-----------|-----------|-------|------|---------|----------|----------|-----|----
Giovanni   | Rossi     | A123...   | Title | 2024 | Journal | ...      | keyword1 | ... | ...
```

---

## 🚨 Important Notes

1. **Always use `python main.py`** to continue from checkpoint
2. **Use `--reset-progress` only** when starting a new dataset
3. **Never manually edit progress.json** (automatic atomic writes)
4. **Internet connection required** throughout execution
5. **Data is auto-saved** - you won't lose extraction progress
6. **Press Ctrl+C safely** - script will save before exiting

---

## 📝 Example Session

```bash
$ python main.py
2025-05-24 10:00:00 [INFO] STARTING OPENALEX PIPELINE
2025-05-24 10:00:01 [INFO] Loaded 50 papers from previous extraction
2025-05-24 10:00:01 [INFO] Resuming from index 204
2025-05-24 10:00:03 [INFO] [205/1745] Giovanni Rossi
2025-05-24 10:00:05 [INFO] Matched -> https://openalex.org/A123456
2025-05-24 10:00:07 [INFO] 5 papers extracted + saved
... (continues)

# User presses Ctrl+C at index 350
^C
*** INTERRUPT SIGNAL RECEIVED ***
Saving progress and exiting gracefully...
[INFO] EXPORTING FINAL RESULTS
[INFO] ✓ Exported 250 papers to output/Papers_Output.xlsx
[INFO] Pipeline interrupted - progress saved for resume
[INFO] To resume: python main.py

$ python main.py
2025-05-24 11:00:00 [INFO] STARTING OPENALEX PIPELINE
2025-05-24 11:00:01 [INFO] Loaded 250 papers from previous extraction
2025-05-24 11:00:01 [INFO] Resuming from index 350
2025-05-24 11:00:03 [INFO] [351/1745] Maria Bianchi
... (continues from 351)
```

---

## 🎯 Next Steps

1. Test with a small subset first:
   ```bash
   # Edit config.py INPUT_FILE to use first 50 rows only
   python main.py
   ```

2. Once confident, run the full 1745 author extraction
3. Monitor logs for any errors
4. Use Ctrl+C to pause/resume as needed

Happy extracting! 🎉
