import json
import regex
import dirtyjson

ERR_PARSE_JSON = {"error": "no json found!"}

def parse_json(json_str):
    pattern_comments = regex.compile('//.*\n')
    comments = pattern_comments.findall(json_str)
    for comment in comments:
        json_str = json_str.replace(comment, '\n')

    pattern = regex.compile('\{(?:[^{}]|(?R))*\}')
    json_res = pattern.findall(json_str)
    
    if len(json_res) == 0:
        return ERR_PARSE_JSON

    json_objs = []
    for json_str in json_res:
        json_str = json_str.replace('”','"')
        try:
            json_objs.append(dirtyjson.loads(json_str))
        except Exception:
            # t_res = workaround_illegal_json(json_str)
            # if t_res is not None:
            #     json_objs.append(t_res)
            pass
    
    if len(json_objs) == 0:
        return ERR_PARSE_JSON
    
    return json_objs[-1]


def workaround_illegal_json(json_str:str):
    json_str = json_str.replace(',\n}','\n}')
    try:
        return json.loads(json_str)
    except json.JSONDecodeError:
        return None