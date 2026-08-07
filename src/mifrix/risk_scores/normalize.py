import argparse
import os
import re
import sqlite3
import time
import unicodedata
from typing import Any, Dict, List

import pandas as pd
import requests
from tqdm import tqdm


NCBI_EUTILS = "https://eutils.ncbi.nlm.nih.gov/entrez/eutils"


def clean_label(name: str) -> str:
    s = str(name).strip().replace('"', "")
    s = s.replace("[", "").replace("]", "")
    if s.startswith("X."):
        s = s[2:]
    if s.endswith("."):
        s = s[:-1]
    s = re.sub(r"\s+", "_", s)
    return s


def normalize_query_text(s: str) -> str:
    s = unicodedata.normalize("NFKC", s)
    s = s.replace("\u00A0", " ")
    s = re.sub(r"\s+", " ", s).strip()
    return s


def candidate_queries(cleaned: str) -> List[str]:
    base = cleaned.replace("_", " ").strip()
    candidates = []

    if "/" in base:
        left, right = base.split("/", 1)
        left = left.strip()
        right = right.strip()
        tokens = right.split()
        if len(tokens) >= 2:
            genus2 = tokens[0]
            rest = " ".join(tokens[1:])
            genus1 = left.split()[0] if left else ""
            candidates.append(f"{genus2} {rest}".strip())
            if genus1:
                candidates.append(f"{genus1} {rest}".strip())
        candidates.append(base.replace("/", " "))

    candidates.append(base)

    out, seen = [], set()
    for candidate in candidates:
        candidate = normalize_query_text(candidate)
        if candidate and candidate not in seen:
            out.append(candidate)
            seen.add(candidate)
    return out


def lookup_taxid_offline(cur, name_txt: str):
    name_txt = normalize_query_text(name_txt)

    cur.execute("SELECT tax_id, name_class FROM names WHERE name_txt = ? LIMIT 1", (name_txt,))
    row = cur.fetchone()
    if row:
        return row[0], row[1], "OFFLINE_EXACT", name_txt

    cur.execute("SELECT tax_id, name_class FROM names WHERE lower(name_txt)=lower(?) LIMIT 1", (name_txt,))
    row = cur.fetchone()
    if row:
        return row[0], row[1], "OFFLINE_CASE_INSENSITIVE", name_txt

    cur.execute(
        """
        SELECT tax_id, name_class, name_txt
        FROM names
        WHERE lower(name_txt) LIKE lower(?)
        ORDER BY
          CASE name_class
            WHEN 'scientific name' THEN 0
            WHEN 'synonym' THEN 1
            WHEN 'equivalent name' THEN 2
            WHEN 'includes' THEN 3
            WHEN 'misspelling' THEN 4
            ELSE 5
          END
        LIMIT 1
        """,
        (name_txt + "%",),
    )
    row = cur.fetchone()
    if row:
        return row[0], row[1], "OFFLINE_LIKE_PREFIX", row[2]

    return None, None, "NO_HIT", name_txt


def scientific_name_for_taxid_offline(cur, taxid: int):
    cur.execute(
        "SELECT name_txt FROM names WHERE tax_id = ? AND name_class='scientific name' LIMIT 1",
        (taxid,),
    )
    row = cur.fetchone()
    return row[0] if row else None


def esearch_taxid_online(term: str, session: requests.Session, timeout: int = 30):
    entrez_term = f"\"{term}\"[All Names]"
    params = {"db": "taxonomy", "term": entrez_term, "retmode": "json", "retmax": 1}
    response = session.get(f"{NCBI_EUTILS}/esearch.fcgi", params=params, timeout=timeout)
    response.raise_for_status()
    data = response.json()
    ids = data.get("esearchresult", {}).get("idlist", [])
    return ids[0] if ids else None


def efetch_scientific_name_online(taxid: str, session: requests.Session, timeout: int = 30):
    params = {"db": "taxonomy", "id": taxid, "retmode": "xml"}
    response = session.get(f"{NCBI_EUTILS}/efetch.fcgi", params=params, timeout=timeout)
    response.raise_for_status()
    match = re.search(r"<ScientificName>([^<]+)</ScientificName>", response.text)
    return match.group(1).strip() if match else None


def resolve_names(columns: List[str], db_path: str, online_fallback: bool, online_delay: float) -> pd.DataFrame:
    conn = sqlite3.connect(db_path)
    cur = conn.cursor()

    session = requests.Session() if online_fallback else None
    if session:
        session.headers.update({"User-Agent": "MifRix/0.1.0"})

    out_rows: List[Dict[str, Any]] = []
    misses = []

    for col in tqdm(columns, desc="Offline lookups", unit="taxa", dynamic_ncols=True):
        cleaned = clean_label(col)
        if cleaned.lower() in {"genome_id", "genomeid"}:
            continue

        queries = candidate_queries(cleaned)
        hit = None
        for query in queries:
            taxid, name_class, match_type, matched_txt = lookup_taxid_offline(cur, query)
            if taxid is not None:
                sci = scientific_name_for_taxid_offline(cur, taxid) or matched_txt
                hit = (matched_txt, taxid, name_class, match_type, sci, "")
                break

        if hit is None:
            misses.append((col, cleaned, queries))
            continue

        query_used, taxid, matched_class, match_type, sci, note = hit
        normalized = clean_label(str(sci).replace(" ", "_"))
        out_rows.append(
            {
                "original": col,
                "cleaned": cleaned,
                "query_used": query_used,
                "taxid": taxid,
                "matched_class": matched_class,
                "match_type": match_type,
                "normalized": normalized,
                "note": note,
            }
        )

    if online_fallback and session and misses:
        for col, cleaned, queries in tqdm(misses, desc="Online lookups", unit="taxa", dynamic_ncols=True):
            hit = None
            for query in queries:
                try:
                    taxid = esearch_taxid_online(query, session=session)
                    if not taxid:
                        continue
                    time.sleep(online_delay)
                    sci = efetch_scientific_name_online(taxid, session=session)
                    time.sleep(online_delay)
                    if sci:
                        hit = (query, taxid, "online", "ONLINE_OK", sci, "")
                        break
                except Exception:
                    break

            if hit is None:
                out_rows.append(
                    {
                        "original": col,
                        "cleaned": cleaned,
                        "query_used": queries[0] if queries else cleaned.replace("_", " "),
                        "taxid": "",
                        "matched_class": "",
                        "match_type": "NO_HIT",
                        "normalized": cleaned,
                        "note": "",
                    }
                )
                continue

            query_used, taxid, matched_class, match_type, sci, note = hit
            normalized = clean_label(str(sci).replace(" ", "_"))
            out_rows.append(
                {
                    "original": col,
                    "cleaned": cleaned,
                    "query_used": query_used,
                    "taxid": taxid,
                    "matched_class": matched_class,
                    "match_type": match_type,
                    "normalized": normalized,
                    "note": note,
                }
            )
    else:
        for col, cleaned, queries in misses:
            out_rows.append(
                {
                    "original": col,
                    "cleaned": cleaned,
                    "query_used": queries[0] if queries else cleaned.replace("_", " "),
                    "taxid": "",
                    "matched_class": "",
                    "match_type": "NO_HIT",
                    "normalized": cleaned,
                    "note": "",
                }
            )

    conn.close()
    return pd.DataFrame(out_rows)


def sniff_sep(path: str) -> str:
    return "\t" if path.endswith((".tsv", ".txt")) else ","


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("input_file")
    parser.add_argument("--db", required=True)
    parser.add_argument("--online-fallback", action="store_true")
    parser.add_argument("--online-delay", type=float, default=1.2)
    args = parser.parse_args()

    inp = args.input_file
    sep = sniff_sep(inp)
    header_df = pd.read_csv(inp, sep=sep, nrows=0)
    columns = list(header_df.columns)
    species_cols = columns[1:]

    map_df = resolve_names(species_cols, args.db, args.online_fallback, args.online_delay)
    out_dir = os.path.dirname(os.path.abspath(inp))
    stem = os.path.splitext(os.path.basename(inp))[0]
    out_map = os.path.join(out_dir, f"MAP_{stem}.csv")
    map_df.to_csv(out_map, index=False)
    print(f"Mapping saved: {out_map}")


if __name__ == "__main__":
    main()
