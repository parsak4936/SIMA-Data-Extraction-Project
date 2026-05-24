import urllib.parse
import time
import logging
import traceback
import requests

logger = logging.getLogger(__name__)

def search_openalex_author(
    session,
    headers,
    first_name,
    last_name,
    uni_words,
    email,
    score_fn,
    extract_email_domain
):
    email_domain = extract_email_domain(email)
    search_variations = []

    if first_name and last_name:
        search_variations.extend([
            f"{first_name} {last_name}",
            f"{last_name} {first_name}",
            f"{first_name[0]} {last_name}"
        ])
    elif last_name:
        search_variations.append(last_name)
    elif first_name:
        search_variations.append(first_name)

    best_candidate = None
    best_score = -1

    for variation in search_variations:
        encoded = urllib.parse.quote(variation.strip())
        url = f"https://api.openalex.org/authors?search={encoded}&per-page=10"

        try:
            # Increased timeout to 30 seconds to account for slow connections
            r = session.get(url, headers=headers, timeout=30)

            if r.status_code != 200:
                logger.warning(f"API Warning: Server returned {r.status_code} for '{variation}'")
                continue

            results = r.json().get("results", [])

            for candidate in results:
                score = score_fn(
                    candidate,
                    first_name,
                    last_name,
                    uni_words,
                    email_domain
                )

                if score > best_score:
                    best_score = score
                    best_candidate = candidate

        except requests.exceptions.Timeout:
            logger.error(f"TIMEOUT searching '{variation}' (>30s) - skipping")
            time.sleep(2)
            continue
        except requests.exceptions.ConnectionError as e:
            logger.error(f"Connection error searching '{variation}': {e}")
            time.sleep(2)
            continue
        except Exception as e:
            logger.error(f"API Error searching '{variation}': {e}")
            logger.debug(traceback.format_exc())
            time.sleep(1)
            continue

    if best_candidate and best_score >= 10:
        return (
            best_candidate.get("id"),
            best_candidate.get("display_name"),
            best_score
        )

    return None, None, None


def get_author_works(
    session,
    headers,
    start_year,
    author_id,
    reconstruct_abstract
):
    all_works = []
    cursor = "*"
    max_retries = 3
    retry_count = 0

    while cursor:
        url = (
            "https://api.openalex.org/works"
            f"?filter=author.id:{author_id},"
            f"from_publication_date:{start_year}-01-01"
            f"&per-page=200&cursor={cursor}"
        )

        try:
            # Increased timeout to 30 seconds
            r = session.get(url, headers=headers, timeout=30)

            if r.status_code != 200:
                logger.warning(f"API Warning: Server returned {r.status_code} when fetching works for {author_id}")
                if r.status_code == 429:  # Rate limited
                    logger.warning("Rate limited! Backing off for 5 seconds...")
                    time.sleep(5)
                    retry_count += 1
                    if retry_count > max_retries:
                        logger.error("Max retries exceeded. Giving up on this author.")
                        break
                    continue
                break

            data = r.json()
            results = data.get("results", [])

            if not results:
                break

            for work in results:
                journal = (
                    work.get("primary_location", {})
                        .get("source", {})
                        .get("display_name", "")
                )

                keywords = [
                    k.get("display_name")
                    for k in work.get("keywords", [])
                    if k.get("display_name")
                ]

                all_works.append({
                    "author_id": author_id,
                    "title": work.get("title", ""),
                    "year": work.get("publication_year", ""),
                    "journal": journal,
                    "abstract": reconstruct_abstract(
                        work.get("abstract_inverted_index")
                    ),
                    "keywords": ", ".join(keywords),
                    "doi": work.get("doi", ""),
                    "url": work.get("id", "")
                })

            cursor = data.get("meta", {}).get("next_cursor")
            logger.info(f"Fetching works page cursor={cursor}")
            logger.info(f"Received {len(results)} works")
            
            # Increased delay between paginated requests
            time.sleep(0.5)
            retry_count = 0  # Reset retry count on success

        except requests.exceptions.Timeout:
            logger.error(f"TIMEOUT fetching works for {author_id} (>30s)")
            retry_count += 1
            if retry_count > max_retries:
                logger.error("Max retries exceeded. Giving up on this author.")
                break
            time.sleep(2)
            continue
        except requests.exceptions.ConnectionError as e:
            logger.error(f"Connection error for {author_id}: {e}")
            retry_count += 1
            if retry_count > max_retries:
                break
            time.sleep(2)
            continue
        except Exception as e:
            logger.error(f"Error extracting works for {author_id}: {e}")
            logger.debug(traceback.format_exc())
            break

    return all_works