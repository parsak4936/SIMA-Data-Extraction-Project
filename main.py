import pandas as pd
import time

from config import *
from helpers import setup_logger, create_session
from parsing import (
    parse_name,
    get_core_uni_words,
    extract_email_domain,
    reconstruct_abstract
)
from scoring import score_author_candidate
from api import search_openalex_author, get_author_works
from export import export_publications, export_audit


logger = setup_logger()
session = create_session()

logger.info("STARTING OPENALEX PIPELINE")


df = pd.read_csv(INPUT_FILE, encoding="utf-8-sig", on_bad_lines="skip").head(10)

all_papers = []
audit_log = []
author_cache = {}


for i, row in df.iterrows():

    raw_name = str(row.get("Cognome e Nome", "")).strip()
    if not raw_name or raw_name == "nan":
        continue

    university = str(row.get("Ateneo", ""))
    email = str(row.get("Email universitaria", ""))

    first_name, last_name = parse_name(raw_name)
    uni_words = get_core_uni_words(university)

    logger.info(f"[{i+1}/{len(df)}] {first_name} {last_name}")

    cache_key = f"{first_name}_{last_name}"

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
            all_papers.extend(works)
            logger.info(f"{len(works)} papers extracted")
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

    time.sleep(0.5)


logger.info("EXPORTING RESULTS")

export_publications(all_papers, OUTPUT_PUBLICATIONS)
export_audit(audit_log, OUTPUT_AUDIT)

logger.info("PIPELINE COMPLETE")