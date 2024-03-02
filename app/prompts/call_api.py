# Note: you need to be using OpenAI Python v0.27.0 for the code below to work
import logging
from time import sleep
import openai
import json

from prompts.prompts import *
from dao.preprocess import Preprocess
from dao.logs import PreprocessLog, AnalysisLog
from helper.get_func_def import get_func_def_easy
from helper.parse_json import parse_json
import os

# api_key = "../openai.key"
# openai.api_key_path = api_key
openai.api_key = os.environ.get("OPENAI_API_KEY")
trivial_funcs = json.load(open("prompts/trivial_funcs.json", "r"))
exclusive_funcs = json.load(open("prompts/exclusive_funcs.json", "r"))


def _do_request(model, temperature, max_tokens, formatted_messages, _retry=0, last_emsg=None):
    sleep(0.2) # avoid rate limit
    if "--" in model:
        model = model.split("--")[0]
    try:
        response = openai.ChatCompletion.create(
            model=model,
            messages=formatted_messages,
            temperature=temperature,
            max_tokens=max_tokens,
            top_p=1,
            frequency_penalty=0,
            presence_penalty=0,
        )
    except Exception as e:
        logging.error(e)
        emsg = str(e)
        if "maximum context length" in emsg:
            if model == "gpt-3.5-turbo-0613":
                return _do_request("gpt-3.5-turbo-16k-0613", temperature, max_tokens, formatted_messages, _retry, last_emsg)

        if last_emsg is not None and emsg[:60] == last_emsg[:60]:
            logging.info("Same error")
            return '{"ret": "failed", "response": "' + emsg[:200] + '"}'

        if _retry < 3 and ("context_length_exceeded" not in emsg):
            sleep(1)
            logging.info(f"Retrying {_retry + 1} time(s)...")
            return _do_request(model, temperature, max_tokens, formatted_messages, _retry + 1, emsg)
        else:
            return '{"ret": "failed", "response": "' + emsg[:200] + '"}'

    return response["choices"][0]["message"]["content"]


def call_gpt_preprocess(message, item_id, prompt=PreprocessPrompt, model="gpt-3.5-turbo", temperature=0.7, max_tokens=2048):

    # Format conversation messages
    formatted_messages = [
        {"role": "system", "content": prompt.system},
        # {"role": "user", "content": },
        # {"role": "assistant","content": start_str},
        {"role": "user", "content": message}
    ]

    # Call the OpenAI API
    assistant_message = _do_request(
        model, temperature, max_tokens, formatted_messages)

    # Extract the assistant's response
    # assistant_message = response["choices"][0]["message"]["content"]

    logging.info(assistant_message)

    # Extend the conversation via:
    formatted_messages.extend([{"role": "assistant", "content": assistant_message},
                               {"role": "user", "content": prompt.continue_text}
                               ])
    assistant_message2 = _do_request(
        model, temperature, max_tokens, formatted_messages)

    plog = PreprocessLog()
    plog.commit(item_id, assistant_message, assistant_message2, model)

    logging.info(assistant_message2)

    # Extend the conversation via:
    formatted_messages.extend([{"role": "assistant", "content": assistant_message2},
                               {"role": "user", "content": prompt.json_gen}
                               ])
    assistant_message3 = _do_request(
        model, temperature, max_tokens, formatted_messages)

    plog = PreprocessLog()
    plog.commit(item_id, assistant_message, assistant_message3, model)

    return assistant_message3.strip()


def call_gpt_analysis(prep, case, prompt=AnalyzePrompt, round=0, model="gpt-3.5-turbo", temperature=0.7, max_tokens=2048):
    _provide_func_heading = "Here is the function of {}, you can continue asking for other functions with that json format I mentioned .\n"
    prep_res = json.loads(prep.initializer)

    # cs = prep_res["initializer"] if "initializer" in prep_res else prep_res["initializers"]
    if "initializer" in prep_res:
        cs = prep_res["initializer"]
    elif "initializers" in prep_res:
        cs = prep_res["initializers"]
    else:
        logging.error(f"no call site info!")
        return {"ret": "failed", "response": "no call site info!"}
    
    if type(cs) == list and len(cs) > 0:
        cs = cs[0]
    if cs == None:
        logging.error(f"no call site info!")
        return {"ret": "failed", "response": "no call site info!"}

    # remove the return value
    if '=' in cs:
        eq_id =  len(cs.split("=")[0])
        if eq_id < len(cs.split('(')[0]):
            cs = cs[eq_id+1:].strip()
    if type(cs) != str:
        logging.error(f"callsite info with wrong format!")
        return {"ret": "failed", "response": "no call site info!"}
    func_name = cs.split("(")[0]
    func_def = get_func_def_easy(func_name)

    if func_def is None:
        logging.error(f"Cannot find function definition in {cs}")
        return {"ret": "failed", "response": f"Cannot find function definition in {cs}"}
    
    # adding some context?
    ctx = case.raw_ctx.split("\n")
    call_ctx_lines = min(10, len(ctx))
    calling_ctx = "\n".join(ctx[:-call_ctx_lines])
    prep_res_str = str(prep_res) + "\nCall Context: ...\n" + calling_ctx

    formatted_messages = [
        {"role": "system", "content": prompt.system},
        # {"role": "user", "content": prompt.system},
        {"role": "user", "content": prep_res_str},
    ]
    if func_name not in trivial_funcs:
        formatted_messages.append(
            {"role": "assistant", "content": prompt.heading.format(func_name, func_name)})
        formatted_messages.append(
            {"role": "user", "content": _provide_func_heading.format(func_name) + func_def})

    logging.info(formatted_messages[-1])

    # for round in range(1):
    # Call the OpenAI API
    assistant_message = _do_request(
        model, temperature, max_tokens, formatted_messages)
    # assistant_message = response["choices"][0]["message"]["content"]
    dialog_id = 0

    if assistant_message.startswith('{"ret": "failed", "response": "'):
        # logging.error(assistant_message)
        return json.loads(assistant_message)

    logging.info(assistant_message)
    alog = AnalysisLog()
    alog.commit(prep.id, round, dialog_id,
                prep_res_str[:50], assistant_message, model)
    formatted_messages.extend(
        [{"role": "assistant", "content": assistant_message}])

    # interactive process
    while True:
        json_res = parse_json(assistant_message)
        if json_res is None or "ret" not in json_res:  # finish the analysis
            # self-refinement
            # sometimes it ask more func defs for refinment
            formatted_messages.extend([
                {"role": "user", "content": prompt.continue_text}
            ])
            assistant_message_refine = _do_request(
                model, temperature, max_tokens, formatted_messages)
            logging.info(assistant_message_refine)
            dialog_id += 1
            alog = AnalysisLog()
            alog.commit(prep.id, round, dialog_id, prompt.continue_text[:40],
                assistant_message_refine, model)
            
            formatted_messages.append(
                    {"role": "assistant", "content": assistant_message_refine})
            if "need_more_info" not in assistant_message_refine: # we can finish safely
                break
            else:
                # formatted_messages.pop() # remove the refine prompt
                assistant_message = assistant_message_refine
                continue
        if json_res["ret"] == "need_more_info":
            is_func_def = False
            provided_defs = ""
            for require in json_res["response"]:
                if require["type"] == "function_def":
                    is_func_def = True
                    required_func = require["name"]
                    if 'name' not in require:
                        logging.error(f"function name not found")
                        provided_defs += f"I don't find the `name` for your request {require}, please try again.\n"
                        continue
                    required_func = require["name"]

                    func_def = get_func_def_easy(require["name"])
                    if func_def is not None:
                        provided_defs += func_def + "\n"
                    else:
                        logging.error(f"function {require['name']} not found")
                        provided_defs += f"Sorry, I don't find function {require['name']}, try to analysis with your expertise in Linux kernel\n \
                                           If this function is called under a return code check, you could assume this function must init when it return 0, and must no init when it returns non-zero \n"
                else:
                    provided_defs += f"Sorry, no information of {require} I can provide, try to analysis with your expertise in Linux kernel\n"

            if is_func_def:
                provided_defs = _provide_func_heading.format(required_func) + provided_defs
            else:
                provided_defs = "" + provided_defs

            formatted_messages.extend([
                {"role": "user", "content": provided_defs}
            ])
            assistant_message = _do_request(
                model, temperature, max_tokens, formatted_messages)
            logging.info(assistant_message)
            dialog_id += 1
            alog = AnalysisLog()
            alog.commit(prep.id, round, dialog_id,
                        provided_defs[:100], assistant_message, model)

            formatted_messages.append(
                {"role": "assistant", "content": assistant_message})
        else:
            break





    # let it generate a json output, and save the result
    # ignore interative messages
    # json_gen_msg = formatted_messages[:3] 
    # json_gen_msg += formatted_messages[-2:]
    
    # json_gen_msg += [
    #     {"role": "assistant", "content": assistant_message_final},
    #     {"role": "user", "content": prompt.json_gen}
    # ]
    formatted_messages.extend([
        {"role": "user", "content": prompt.json_gen}
    ])
    assistant_message = _do_request(
        model, temperature, max_tokens, formatted_messages)
    # assistant_message = response["choices"][0]["message"]["content"]
    dialog_id += 1
    alog = AnalysisLog()
    alog.commit(prep.id, round, dialog_id,
                prompt.json_gen[:40], assistant_message, model)
    return parse_json(assistant_message)



# TODO bug: if the return value reuses the parameter name
# TODO: do we really needs it?
def wrap_postcondition(postcondition: str, initializer):
    """
    wrap the postcondition if:
    - the initializer retutrn a value and save it to a variable
    - the postcondition use the variable
    """
    if postcondition is None:
        return None

    if initializer is None or '=' not in initializer:
        return postcondition
    if initializer[-1] == ';':
        initializer = initializer[:-1]



    ret_val_name = initializer.split("=")[0].strip()

    if " " in ret_val_name:  # contains type
        ret_val_name = ret_val_name.split(" ")[-1].strip()
    initializer_call = initializer.split("=")[1].strip()

    # init_call_func_name = initializer_call.split("(")[0]

    # Workaround: if return value reuses a parameter
    # if ret_val_name in initializer_call[len(init_call_func_name):]:
    #     return postcondition

    if type(postcondition) == str:
        return postcondition.replace(ret_val_name, initializer_call)
    else:
        return postcondition



# change the name of return_value to `func_ret_val` and change them in postcondition and suspicious_vars
def wrap_ret_value(suspicious_vars: list, initializer: str, postcondition: str):
    """
    wrap the ret_value if:
    - return value is the suspicious variable
    - @param suspicious_vars: list of suspicious variables
    - @param initializer: the initializer
    - @return: the new suspicious variables and the new initializer
    """
    if suspicious_vars is None or initializer is None:
        return suspicious_vars, initializer, postcondition
    
    if type(suspicious_vars) is str:
        suspicious_vars = [suspicious_vars]

    if '=' not in initializer:
        return suspicious_vars, initializer, postcondition

    if initializer[-1] == ';':
        initializer = initializer[:-1]

    ret_val_name = initializer.split("=")[0].strip()


    initializer = initializer.replace(ret_val_name, "func_ret_val", 1)
    
    if ret_val_name in suspicious_vars:
        suspicious_vars.remove(ret_val_name)
        suspicious_vars.append("func_ret_val")
    
    if type(postcondition) == list:
        for i, post in enumerate(postcondition):
            if ret_val_name in post:
                postcondition[i] = post.replace(ret_val_name, "func_ret_val", 1)
    elif type(postcondition) == str:
        if ret_val_name in postcondition:
            postcondition = postcondition.replace(ret_val_name, "func_ret_val", 1)

    return suspicious_vars, initializer, postcondition


def do_preprocess(prep,  model):
    use_site = prep.raw_ctx.strip().split("\n")[-1].strip()
    message = f"suspicous varaible: {prep.var_name}\nuse: {use_site}\n\nCode:\n{prep.raw_ctx}"
    print(message)
    responce = call_gpt_preprocess(
        message, prep.id, PreprocessPrompt, model, max_tokens=1024, temperature=1.0)
    print(responce)

    responce = parse_json(responce)
    # if "initializer" in responce:
    #     responce = responce["initializer"]
    if "initializers" in responce:
        responce = responce["initializers"]

    if 'postconditions' in responce:
        responce['postcondition'] = responce['postconditions']
    


    # try not do the wrap
    if 'postcondition' not in responce:
        try_found = False
        try:
            if type(responce) == list:
                response_iterator = responce
            else:
                # {"intializers":[{...}, {...}]}
                response_iterator = next(responce.values())
            if type(response_iterator) == list and 'postcondition' in response_iterator[-1]:
                response_iterator.reverse()
                for item in response_iterator:
                    func_call = item['initializer']
                    if '(' not in func_call:
                        continue
                    exclude = False
                    for exclus in exclusive_funcs:
                        if exclus in func_call:
                            exclude = True
                            break
                    if exclude:
                        continue
                    responce = item
                    # responce['postcondition'] = wrap_postcondition(
                    #     responce['postcondition'], responce['initializer'])
                    try_found = True
                    break
            # assert responce['postcondition'] is None or type(responce['postcondition']) == str
            # try_found = True
        except Exception:
            pass

        if not try_found:
            logging.error("ChatGPT not output in our format: ", responce)
            return json.dumps(responce)
    
    
    if 'postcondition' in responce and 'initializer' in responce and 'suspicious' in responce:
        responce['suspicious'], responce['initializer'], responce['postcondition'] = wrap_ret_value(
            responce['suspicious'], responce['initializer'], responce['postcondition'])
        # pass
    else:
        logging.error("ChatGPT not output in our format: ", responce)
    return json.dumps(responce)


def do_analysis(prep, round, case, model):
    response = call_gpt_analysis(
        prep, case, AnalyzePrompt, round, model, max_tokens=1024, temperature=1.0)
    print(response)
    return json.dumps(response)
