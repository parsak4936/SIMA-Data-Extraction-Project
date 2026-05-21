def score_author_candidate(
    candidate,
    first_name,
    last_name,
    uni_words,
    email_domain
):
    score = 0

    candidate_name = candidate.get("display_name", "").lower()

    # surname
    if last_name.lower() in candidate_name:
        score += 5

    # first name
    if first_name.lower() in candidate_name:
        score += 5

    # affiliations
    affiliations = candidate.get("affiliations") or []

    for aff in affiliations:
        institution = aff.get("institution")
        if not institution:
            continue

        inst_name = institution.get("display_name", "").lower()

        if any(word in inst_name for word in uni_words):
            score += 10

        if email_domain:
            domain_keywords = email_domain.split(".")
            if any(d in inst_name for d in domain_keywords):
                score += 15

    # fallback geo signal
    last_inst = candidate.get("last_known_institution")
    if last_inst and last_inst.get("country_code") == "IT":
        score += 2

    return score