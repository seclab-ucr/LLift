"""
This module is used to parse the variable name from the output of static analysis
when the report is a single IR statement.

We herusticly parse the variable name with Levenshtein distance.


Example 1: 
varname: hv_pci_enter_d0_$comp_pkt$4$obj
code: 	if (comp_pkt.completion_status < 0) {
answer: comp_pkt.completion_status

Example 2: 
varname: free_space_test_bit_$found_end$obj
code: 	ASSERT(offset >= found_start && offset < found_end);
answer: found_end


"""

from Levenshtein import distance as levenshtein_distance
import regex as re


def find_variables(code):
    # remove string literals
    code = re.sub(r'"([^"\\]*(\\.[^"\\]*)*)"','', code)

    # The pattern for a variable name is: word characters, possibly followed by . or -> and more word characters
    pattern = r'\b([a-zA-Z_][a-zA-Z0-9_]*(?:\.[a-zA-Z_][a-zA-Z0-9_]*|\->[a-zA-Z_][a-zA-Z0-9_]*)*)\b(?!\()'
    
    
    # list of common control keywords
    control_keywords = ["if", "else", "for", "while", "do", "switch", "case", "default", "break", "continue", 
                        "goto", "return", "try", "catch", "finally", "throw", "assert", "ASSERT", "true", "false"]
    
    matches = re.findall(pattern, code)
    
    # remove duplicates and control keywords
    variables = list(set(matches) - set(control_keywords))  
    return variables
    


def find_closest_match(varname, code):
    varname = "$".join(varname.split('$')[1:])
    varname= varname.replace("obj", ".")

    # Find all the variable names in the code
    variables = find_variables(code)
    
    # Calculate the Levenshtein distance between the given variable name and all the variable names in the code
    distances = [levenshtein_distance(varname, variable) for variable in variables]
    
    # Find the minimum distance
    min_distance = min(distances)

    # If the minimum distance equals the length of the given variable name, raise an exception
    # if min_distance == len(varname):
    #     raise Exception("The given variable name does not closely match any variable in the code")
    

    # Find the indices of the minimum distance
    min_distance_indices = [i for i, distance in enumerate(distances) if distance == min_distance]

    # Check if the minimum distance occurs more than once
    if len(min_distance_indices) > 1:
        raise Exception("Multiple variables found with the same minimum distance")
    
    # if the closest match not in the code, raise an exception
    res = variables[min_distance_indices[0]]

    if len(res) >= 2 and res[:2] not in varname:
        raise Exception("The given variable name is not in the code") 

    
    # Return the variable name with the minimum distance
    return res

if __name__ == "__main__":
    code = "*file_sz = info->file_size;"
    varname = "efi_file_size_$info$obj"
    print(find_closest_match(varname, code))