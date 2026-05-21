import pandas as pd
import requests
import urllib.parse
import time
import logging
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry

# =========================================================
# CONFIGURATION
# =========================================================

INPUT_FILE = "SOCISIMA.csv"

OUTPUT_PUBLICATIONS = "Publications_Output.xlsx"
OUTPUT_AUDIT = "Audit_Log_Missing_Authors.csv"

START_YEAR = 2023

EMAIL_CONTACT = "wixloop.contact@gmail.com"

HEADERS = {
    "User-Agent": f"mailto:{EMAIL_CONTACT}"
}

# =========================================================
# LOGGING
# =========================================================

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s"
)

# =========================================================
# SESSION + RETRIES
# =========================================================

session = requests.Session()

retries = Retry(
    total=5,
    backoff_factor=1,
    status_forcelist=[429, 500, 502, 503, 504]
)

session.mount("https://", HTTPAdapter(max_retries=retries))

# =========================================================
# HELPERS
# =========================================================

def parse_name(full_name):
    """
    Safer name parser.
    Handles:
    - ROSSI Mario
    - Mario Rossi
    - Rossi, Mario
    """

    if pd.isna(full_name):
        return "", ""

    name = str(full_name).strip().replace(",", " ")

    words = name.split()

    if len(words) == 1:
        return "", words[0]

    # If first word uppercase -> surname first
    if words[0].isupper():
        last = words[0]
        first = " ".join(words[1:])
    else:
        first = " ".join(words[:-1])
        last = words[-1]

    return first.strip(), last.strip()


def get_core_uni_words(uni_string):

    if pd.isna(uni_string):
        return []

    stopwords = {
        'università',
        'universita',
        'degli',
        'studi',
        'della',
        'delle',
        'di',
        'del',
        'campus',
        'alma',
        'mater',
        'studiorum',
        'libera'
    }

    words = (
        str(uni_string)
        .lower()
        .replace("'", " ")
        .replace('"', '')
        .split()
    )

    return [
        w for w in words
        if w not in stopwords and len(w) > 3
    ]


def extract_email_domain(email):

    if pd.isna(email):
        return None

    email = str(email).lower().strip()

    if '@' not in email:
        return None

    return email.split('@')[-1]


def reconstruct_abstract(inverted_index):

    if not inverted_index:
        return ""

    positions = {}

    for word, pos_list in inverted_index.items():
        for pos in pos_list:
            positions[pos] = word

    ordered_words = [
        positions[pos]
        for pos in sorted(positions.keys())
    ]

    return " ".join(ordered_words)

# =========================================================
# AUTHOR VALIDATION
# =========================================================

def score_author_candidate(candidate,
                           first_name,
                           last_name,
                           uni_words,
                           email_domain):

    score = 0

    candidate_name = (
        candidate.get("display_name", "")
        .lower()
    )

    # -----------------------------------------
    # Exact surname match
    # -----------------------------------------

    if last_name.lower() in candidate_name:
        score += 5

    # -----------------------------------------
    # First name match
    # -----------------------------------------

    if first_name.lower() in candidate_name:
        score += 5

    # -----------------------------------------
    # Institution match
    # -----------------------------------------

    affiliations = candidate.get("affiliations") or []

    for aff in affiliations:

        institution = aff.get("institution")

        if not institution:
            continue

        inst_name = institution.get(
            "display_name",
            ""
        ).lower()

        # University keyword matching
        if any(word in inst_name for word in uni_words):
            score += 10

        # Email domain matching
        if email_domain:

            domain_keywords = email_domain.split('.')

            if any(d in inst_name for d in domain_keywords):
                score += 15

    # -----------------------------------------
    # Geographic fallback
    # -----------------------------------------

    last_inst = candidate.get("last_known_institution")

    if last_inst:

        if last_inst.get("country_code") == "IT":
            score += 2

    return score


# =========================================================
# MAIN EXECUTION
# =========================================================

logging.info("====================================")
logging.info("STARTING OPENALEX EXTRACTION")
logging.info("====================================")

# -----------------------------------------
# Load CSV
# -----------------------------------------

try:

    df = pd.read_csv(
        INPUT_FILE,
        encoding="utf-8-sig",
        on_bad_lines="skip"
    ).head(10)

except Exception as e:

    logging.error(f"Could not load file -> {e}")
    raise SystemExit()

# -----------------------------------------
# Containers
# -----------------------------------------

all_papers = []

audit_log = []

# Optional cache
author_cache = {}

# =========================================================
# PROCESS AUTHORS
# =========================================================

for index, row in df.iterrows():

    raw_name = str(
        row.get("Cognome e Nome", "")
    ).strip()

    if not raw_name or raw_name == "nan":
        continue

    university = str(
        row.get("Ateneo", "")
    )

    email = str(
        row.get("Email universitaria", "")
    )

    first_name, last_name = parse_name(raw_name)

    uni_words = get_core_uni_words(
        university
    )

    logging.info(
        f"[{index+1}/{len(df)}] "
        f"Processing: {first_name} {last_name}"
    )

    # -----------------------------------------
    # Cache
    # -----------------------------------------

    cache_key = f"{first_name}_{last_name}"

    if cache_key in author_cache:

        author_id = author_cache[cache_key]

        logging.info(
            "Using cached author ID"
        )

    else:

        author_id, matched_name, score = (
            search_openalex_author(
                first_name,
                last_name,
                uni_words,
                email
            )
        )

        author_cache[cache_key] = author_id

    # -----------------------------------------
    # If author found
    # -----------------------------------------

    if author_id:

        logging.info(
            f"Matched -> {author_id}"
        )

        works = get_author_works(
            author_id,
            first_name,
            last_name
        )

        if works:

            all_papers.extend(works)

            logging.info(
                f"Extracted "
                f"{len(works)} papers"
            )

        else:

            logging.warning(
                "No papers found"
            )

            audit_log.append({

                "Original_Name": raw_name,
                "Issue": "0 papers found",
                "Author_ID": author_id
            })

    else:

        logging.warning(
            "Author not matched"
        )

        audit_log.append({

            "Original_Name": raw_name,
            "Issue": "Author not found",
            "Author_ID": "N/A"
        })

    time.sleep(0.5)

# =========================================================
# EXPORT
# =========================================================

logging.info("====================================")
logging.info("EXPORTING RESULTS")
logging.info("====================================")

# -----------------------------------------
# Publications
# -----------------------------------------

if all_papers:

    results_df = pd.DataFrame(all_papers)

    # Remove duplicates
    results_df.drop_duplicates(
        subset=["doi", "title"],
        inplace=True
    )

    results_df.to_excel(
        OUTPUT_PUBLICATIONS,
        index=False
    )

    logging.info(
        f"Saved publications -> "
        f"{OUTPUT_PUBLICATIONS}"
    )

else:

    logging.warning(
        "No publications extracted"
    )

# -----------------------------------------
# Audit log
# -----------------------------------------

if audit_log:

    audit_df = pd.DataFrame(audit_log)

    audit_df.to_csv(
        OUTPUT_AUDIT,
        index=False,
        encoding="utf-8-sig"
    )

    logging.info(
        f"Saved audit log -> "
        f"{OUTPUT_AUDIT}"
    )

logging.info("PIPELINE COMPLETE")