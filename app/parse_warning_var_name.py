import linecache
from helper.var_name_parse import find_closest_match
import psycopg2
from common.config import *
from dao.preprocess import Preprocess
import os

conn = psycopg2.connect(**DATABASE_CONFIG)

# importing required package


def fetch_all(cur):
    batch_size = 1000
    offset = 0
    max_number = 1000000
    max_id = 1000000
    min_id = 0
    while offset < max_number:
        # Fetch data from the PostgreSQL database
        cur.execute(
            f"SELECT * FROM preprocess where type = 'var_name' and id < {max_id} and id > {min_id} LIMIT {batch_size} OFFSET {offset}")
        offset += batch_size

        rows = cur.fetchall()
        yield rows


def read_line_of_file(filepath, lineno):
    # with open(filepath, 'r') as f:
    line = linecache.getline(filepath, lineno)
    return " " + line.strip()


def go():
    cur = conn.cursor()
    failed = []
    suc_count = 0
    for rows in fetch_all(cur):
        # Parse the fetched data
        for row in rows:
            preprocess = Preprocess(
                row[0], row[1], row[3], row[4], row[5], row[6], row[7], row[8])
            if preprocess.raw_ctx is None:
                preprocess.update_raw_ctx()
                cur.execute(
                    "UPDATE preprocess SET raw_ctx = %s WHERE id = %s",
                    (preprocess.raw_ctx, preprocess.id)
                )
            if preprocess.raw_ctx is None:
                continue
            if "$" not in preprocess.var_name:
                continue

            use_site = preprocess.raw_ctx.strip().split("\n")[-1].strip()
            lienno = preprocess.line_no
            while use_site.endswith(",") or use_site.endswith("|") or use_site.endswith("(") or use_site.endswith("&"):
                lienno += 1
                file_path = os.path.join(LINUX_PATH, preprocess.file)
                use_site += read_line_of_file(file_path, lienno)

            try:
                infered_name = find_closest_match(
                    preprocess.var_name, use_site)
                suc_count += 1
            except:
                failed.append((preprocess.var_name, use_site))
                infered_name = None
                continue
            print("="*20)
            print(f"Use site: {use_site}")
            print(f"Var name: {preprocess.var_name}")
            print(f"Infered name: {infered_name}")

            cur.execute(
                "UPDATE preprocess SET var_name = %s WHERE id = %s",
                (infered_name, preprocess.id)
            )
        conn.commit()
    cur.close()
    print("infer failed:")
    for f in failed:
        print(f[0], "; ", f[1], "; ")
    print(f"Success count: {suc_count}")
    print(f"Failed count: {len(failed)}")

if __name__ == "__main__":
    go()