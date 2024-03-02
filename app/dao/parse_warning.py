import psycopg2
import json
import os
import re

from common.config import *

# Function to read the configuration from a JSON file
def read_config(file_path):
    with open(file_path, 'r') as file:
        return json.load(file)

# Read the configuration from the config.json file
# config = read_config('config.json')

# Connect to PostgreSQL database using the configuration
conn = psycopg2.connect(**DATABASE_CONFIG)

cur = conn.cursor()

# Function to parse arg_id into the required format
def parse_arg_id(arg_id, argno, line_no):
    file_name, rest = arg_id.split(".bc_")
    file_name += ".c"

    if argno >= 0:
        file_path = os.path.join('/Volumes/Data/linux-4.14', file_name)
        var_name = get_variable_from_file(file_path, int(line_no), argno)

        return {
            "type": "arg_no",
            "file": file_name,
            "name": var_name
        }
    
    if '%' not in rest:
        return {
            "type": "unknown",
            "file": file_name,
            "name": f"{rest}"
        }


    func_name, var_name = rest.split("%", 1)
    return {
        "type": "var_name",
        "file": file_name,
        "name": f"{func_name}${var_name}"
    }

# Function to get the variable from the file using the given path, line number, and argno index
def get_variable_from_file(file_path, line_number, argno):
    with open(file_path, 'r', errors='ignore') as file:
        lines = file.readlines()
        if 0 <= line_number - 1 < len(lines):
            line = lines[line_number - 1]
            pattern = re.compile(r"(\w+)\s*\(((?:.|\n)+)\)")
            match = pattern.search(line)
            if not match:
                line += lines[line_number]
                match = pattern.search(line)

            if match:
                args_str = match.group(2).replace('\n', '')
                args = [arg.strip() for arg in args_str.split(',')]
                if 0 <= argno < len(args):
                    return args[argno]
    return None


# Function to insert the parsed data into the preprocess table
def insert_into_preprocess(parsed_data):
    cur = conn.cursor()

    for data in parsed_data:
        raw_data = data['raw_data']
        function = raw_data['function_name']
        type = raw_data['arg_id']['type']
        var_name = raw_data['arg_id']['name']
        file_p  = raw_data['arg_id']['file']
        line_no = raw_data['lineno']
        id = raw_data['id']
        selected = raw_data['selected']
        priority = raw_data['priority'] if 'priority' in raw_data else None

        if type == 'arg_no':
            if var_name is None or '(' in var_name:
                continue

        cur.execute(
            "INSERT into preprocess (id, function, type, var_name, line_no, file, selected, priority) VALUES (%s, %s, %s, %s, %s, %s, %s, %s) on conflict (id) do update set file = EXCLUDED.file ",
            (id, function, type, var_name, line_no, file_p, selected, priority)
        )
        conn.commit()
    cur.close()


def run(table='timout', selected=False, id_offset = 0):
    batch_size = 1000
    offset = 0
    max_number = 200000
    while offset < max_number:
        # Fetch data from the PostgreSQL database
        if selected:
            query = f"SELECT DISTINCT ON (function) id, function, lineno, arg_id, argno FROM {table} WHERE selected = True LIMIT {batch_size} OFFSET {offset}"
        else:
            query = f"SELECT DISTINCT ON (function) id, function, lineno, arg_id, argno FROM {table} LIMIT {batch_size} OFFSET {offset}"
        cur.execute(query)
        offset += batch_size


        rows = cur.fetchall()
        # Parse the fetched data
        parsed_data = []
        for row in rows:
            raw_data = {
                "id": row[0] + id_offset, 
                "function_name": row[1],  # Replace indices with appropriate column indices
                "lineno": row[2],
                "arg_id": parse_arg_id(row[3], row[4], row[2]),
                "argno": row[4],
                "selected": selected
            }
            parsed_data.append({"raw_data": raw_data})

        # Print parsed data as a JSON string
        print(json.dumps(parsed_data, indent=2))
        insert_into_preprocess(parsed_data)
        # Close the cursor and the connection

    
    # Insert the parsed data into the preprocess table
    
    cur.close()
    conn.close()
