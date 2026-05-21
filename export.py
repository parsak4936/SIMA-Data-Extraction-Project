import pandas as pd


def export_publications(data, output_file):
    if not data:
        return False

    df = pd.DataFrame(data)

    df.drop_duplicates(subset=["doi", "title"], inplace=True)

    df.to_excel(output_file, index=False)

    return True


def export_audit(audit_log, output_file):
    if not audit_log:
        return False

    df = pd.DataFrame(audit_log)
    df.to_csv(output_file, index=False, encoding="utf-8-sig")

    return True