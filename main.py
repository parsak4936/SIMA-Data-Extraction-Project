import pandas as pd
import time
import json
import os
import signal
import sys
import argparse
from datetime import datetime

from config import *
from helpers import setup_logger, create_session, reset_progress
from parsing import (
    parse_name,
    get_core_uni_words,
    extract_email_domain,
    reconstruct_abstract
)
from scoring import score_author_candidate
from api import search_openalex_author, get_author_works
from export import export_publications, export_audit


# =========================================================
# CLI ARGS
# =========================================================
parser = argparse.ArgumentParser(description="OpenAlex author paper extraction pipeline")
parser.add_argument("--reset-progress", action="store_true", help="Reset progress.json and start fresh")
parser.add_argument("--no-consolidate", action="store_true", help="Skip consolidating partial results")
args = parser.parse_args()

# =========================================================
# INIT
# =========================================================

logger = setup_logger()
session = create_session()

logger.info("STARTING OPENALEX PIPELINE")

PROGRESS_FILE = "progress.json"
PAPERS_PARTIAL_FILE = "./output/papers_partial.csv"

os.makedirs("output", exist_ok=True)

# Handle --reset-progress flag
if args.reset_progress:
    if reset_progress(PROGRESS_FILE, PAPERS_PARTIAL_FILE):
        logger.info("✓ Progress reset. Starting fresh.")
    else:
        logger.warning("No progress to reset.")

df = pd.read_csv(
    INPUT_FILE,
    encoding="utf-8-sig",
    on_bad_lines="skip"
)

all_papers = []
audit_log = []
author_cache = {}
should_exit = False

# =========================================================
# SIGNAL HANDLERS (Graceful Interrupt)
# =========================================================

def save_and_exit(signum, frame):
    """Handle Ctrl+C gracefully by saving progress before exit"""
    global should_exit
    should_exit = True
    logger.warning("\n\n*** INTERRUPT SIGNAL RECEIVED ***")
    logger.warning("Saving progress and exiting gracefully...")
    
signal.signal(signal.SIGINT, save_and_exit)
signal.signal(signal.SIGTERM, save_and_exit)


# =========================================================
# LOAD PROGRESS & CONSOLIDATE PARTIAL DATA
# =========================================================

start_index = 0

if os.path.exists(PROGRESS_FILE):
    with open(PROGRESS_FILE, "r") as f:
        progress = json.load(f)
        start_index = progress.get("last_index", 0)
    logger.info(f"Resuming from index {start_index}")

# If not resetting, try to load partial results from previous run
if not args.no_consolidate and os.path.exists(PAPERS_PARTIAL_FILE):
    try:
        df_partial = pd.read_csv(PAPERS_PARTIAL_FILE, encoding="utf-8-sig")
        all_papers = df_partial.to_dict('records')
        logger.info(f"Loaded {len(all_papers)} papers from previous extraction")
    except Exception as e:
        logger.warning(f"Could not load partial results: {e}")


# =========================================================
# MAIN LOOP
# =========================================================

TIMEOUT_DELAY = 60  # seconds - if no response for 1 min, save and exit
last_activity_time = time.time()

for i, row in df.iterrows():
    
    # Check for interrupt signal
    if should_exit:
        logger.warning("Stopping extraction due to interrupt signal.")
        break
    
    # Check for timeout (stalled request)
    if time.time() - last_activity_time > TIMEOUT_DELAY:
        logger.error(f"TIMEOUT: No activity for {TIMEOUT_DELAY}s. Saving and exiting.")
        break

    # Heartbeat - update activity time
    last_activity_time = time.time()

    # -----------------------------------------------------
    # SKIP ALREADY PROCESSED
    # -----------------------------------------------------
    if i < start_index:
        continue

    raw_name = str(row.get("Cognome e Nome", "")).strip()

    if not raw_name or raw_name == "nan":
        continue

    university = str(row.get("Ateneo", ""))
    email = str(row.get("Email universitaria", ""))

    first_name, last_name = parse_name(raw_name)
    uni_words = get_core_uni_words(university)

    logger.info(f"[{i+1}/{len(df)}] {first_name} {last_name}")

    cache_key = f"{first_name}_{last_name}"
    
    # Add adaptive delay to avoid IP ban
    # Increase this if you get rate-limited
    time.sleep(2.0)  # 2 second delay between authors
    
    # Ensure fresh variables for this specific loop
    author_id = None
    works = []


    # -----------------------------------------------------
    # AUTHOR CACHE
    # -----------------------------------------------------
    if cache_key in author_cache:
        author_id = author_cache[cache_key]
    else:
        author_id, matched_name, score = search_openalex_author(
            session,
            HEADERS,
            first_name,
            last_name,
            uni_words,
            email,
            score_author_candidate,
            extract_email_domain
        )

        author_cache[cache_key] = author_id


    # -----------------------------------------------------
    # WORK EXTRACTION & FORMATTING
    # -----------------------------------------------------
    if author_id:
        logger.info(f"Matched -> {author_id}")

        works = get_author_works(
            session,
            HEADERS,
            START_YEAR,
            author_id,
            reconstruct_abstract
        )

        if works:
            # === THE COLUMN FORMATTING FIX ===
            # We intercept the papers right here before they are saved.
            # We inject the first/last name and force the exact order you need.
            formatted_works = []
            for paper in works:
                formatted_paper = {
                    "First name": first_name,
                    "last name": last_name,
                    "author_id": paper.get("author_id", ""),
                    "title": paper.get("title", ""),
                    "year": paper.get("year", ""),
                    "journal": paper.get("journal", ""),
                    "abstract": paper.get("abstract", ""),
                    "keywords": paper.get("keywords", ""),
                    "doi": paper.get("doi", ""),
                    "url": paper.get("url", "")
                }
                formatted_works.append(formatted_paper)
            
            # Replace the old works with the perfectly formatted ones
            works = formatted_works
            # ===============================================

            all_papers.extend(works)

            # =================================================
            # INCREMENTAL SAVE
            # =================================================
            df_new = pd.DataFrame(works)

            file_exists = os.path.exists(PAPERS_PARTIAL_FILE)

            df_new.to_csv(
                PAPERS_PARTIAL_FILE,
                mode="a",
                header=not file_exists,
                index=False,
                encoding="utf-8-sig"
            )

            logger.info(f"{len(works)} papers extracted + saved")

        else:
            audit_log.append({
                "Original_Name": raw_name,
                "Issue": "0 papers found",
                "Author_ID": author_id
            })

    else:
        audit_log.append({
            "Original_Name": raw_name,
            "Issue": "Author not found",
            "Author_ID": "N/A"
        })


    # -----------------------------------------------------
    # SAFE CHECKPOINT (UPGRADED AUDIT TRAIL)
    # -----------------------------------------------------
    tmp_file = PROGRESS_FILE + ".tmp"

    with open(tmp_file, "w") as f:
        json.dump(
            {
                "last_index": i,
                "last_processed_name": raw_name,
                "found_id": author_id if author_id else "None",
                "papers_extracted": len(works) if works else 0
            },
            f,
            indent=4
        )

    os.replace(tmp_file, PROGRESS_FILE)

    time.sleep(1.0)  # Increased delay for better rate limiting


# =========================================================
# FINAL EXPORT & CLEANUP
# =========================================================

logger.info("EXPORTING FINAL RESULTS")

if all_papers:
    export_publications(all_papers, OUTPUT_PUBLICATIONS)
    logger.info(f"✓ Exported {len(all_papers)} papers to {OUTPUT_PUBLICATIONS}")

if audit_log:
    export_audit(audit_log, OUTPUT_AUDIT)
    logger.info(f"✓ Exported {len(audit_log)} audit entries to {OUTPUT_AUDIT}")

# If extraction was interrupted, keep progress.json for resume
if not should_exit:
    logger.info("PIPELINE COMPLETE")
    logger.info("Cleaning up temporary files...")
    # Optional: delete progress.json on full completion
    # if os.path.exists(PROGRESS_FILE):
    #     os.remove(PROGRESS_FILE)
else:
    logger.warning("Pipeline interrupted - progress saved for resume")
    logger.warning(f"To resume: python main.py")
    logger.warning(f"To start fresh: python main.py --reset-progress")