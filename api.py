import urllib.parse
import time


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
        encoded = urllib.parse.quote(variation)

        url = (
            "https://api.openalex.org/authors"
            f"?search={encoded}&per-page=10"
        )

        try:
            r = session.get(url, headers=headers, timeout=15)

            if r.status_code != 200:
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

        except Exception:
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

    while cursor:
        url = (
            "https://api.openalex.org/works"
            f"?filter=author.id:{author_id},"
            f"from_publication_date:{start_year}-01-01"
            f"&per-page=200&cursor={cursor}"
        )

        try:
            r = session.get(url, headers=headers, timeout=20)

            if r.status_code != 200:
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
            time.sleep(0.3)

        except Exception:
            break

    return all_works