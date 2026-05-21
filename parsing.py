import pandas as pd


def parse_name(full_name):
    if pd.isna(full_name):
        return "", ""

    name = str(full_name).strip().replace(",", " ")
    words = name.split()

    if len(words) == 1:
        return "", words[0]

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
        "università", "universita", "degli", "studi", "della",
        "delle", "di", "del", "campus", "alma", "mater",
        "studiorum", "libera"
    }

    words = (
        str(uni_string)
        .lower()
        .replace("'", " ")
        .replace('"', "")
        .split()
    )

    return [w for w in words if w not in stopwords and len(w) > 3]


def extract_email_domain(email):
    if pd.isna(email):
        return None

    email = str(email).lower().strip()

    if "@" not in email:
        return None

    return email.split("@")[-1]


def reconstruct_abstract(inverted_index):
    if not inverted_index:
        return ""

    positions = {}

    for word, pos_list in inverted_index.items():
        for pos in pos_list:
            positions[pos] = word

    return " ".join(
        positions[pos] for pos in sorted(positions.keys())
    )