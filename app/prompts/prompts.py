
class Prompt:
    def __init__(self, system, json_gen, heading=None, continue_text=None):
        self.system = system
        self.json_gen = json_gen
        self.heading = heading
        self.continue_text = continue_text


# version v4.0 (Jul 23, 2023)
# upd: change to "relevant_constraints"
__preprocess_system_text = """
As a Linux kernel expert, your task is to identify functions (called initializers) that might initialize a particular suspect variable before using it based on the provided context and variable usage.

The “initializer” must be a function, and must be the "actual" function that intilizes the variable.

Another important aspect you must highlight is the “check before use”, initializer usually outputs something, for example, a return value to determine whether it executes successfully. The golden rule to find the check is always “in what case to make the use happen”

There are following typical types of checks, so you can refer:


Type A. Prior to Variable Use:
Consider a scenario where a variable is used after a function check, such as:
```
if (sscanf(str, '%u.%u.%u.%u%n', &a, &b, &c, &d, &n) >= 4) { // use of a, b, c, d }
```
Here, the check would be "ret_val>=4". This means when the program uses a,b,c,d; it must satisfy “ret_val >= 4”.


Another variant (Type A') is when this happens to switch(...) and the variable uses under a specific case:
```
switch(ret_val = func(..., &a)){
   case some_condi:
   …
   break;
   case critical_condi:
      use(a) // use of a
}
```
In this instance, since we focus on the use of 'a', the check here is "critical_condi".


Type B. Return Code Failures:
In some cases, the function check happens before a return code failure, such as:
```
ret_val = func(..., &a); 
if (ret_val < 0) { return/break/goto label/...; }
…
use(a) // use of a

label:
…
```
In this scenario, the check is "ret_val>=0". For “goto,” you should also see the 


Type B’. Retry:
In some cases, it will retry an initializer until it a success:


```
while(func(&a) ==0){
…
}
use(a)
```


In this case, you should consider the “last” initializer to make it break the endless loop and then, therefore, reach the “use.” Hence, the check is “func(&a) != 0).

If the suspicious variable is used in the iteration with the index, include the boundary of the index as a check

If there's NO explicit control change (like return, break, or goto) that prevents reaching the variable's use point, you should disregard it as it provides no guarantees. All functions can always return to their caller.

Again, if you feel uncertain about finding the check, you should always consider our “golden rule”: if it affects the reachability of use?


For multiple checks,  connect them with their relationships, i.e., && or ||.

Please remember that the context provided is complete and sufficient. You should not assume any hidden breaks or returns. 

Think step by step, analyze each code block thoroughly and establish the postcondition (i.e., checks before use) according to these rules.
"""

__preprocess_continue_text = """
looking at the above analysis, thinking critique for the check with its context, consider the following:
- We only consider the case where the initializer is a function, and ignore it if it is not.
- if the initializer has a return value, you must include it assigning to its return value
- if our "use" is exactly a check, please directly ignore the check in your postcondition extraction
- if there's no check (or, no check can be expressed in terms of return value/params), say "postcondition": null
- for `goto`, you should consider carefully to see if the use is under its label, then conclude the postcondition by include its condition or its `!condition`
- if one initializer has multiple checks, using boolean operators (&&, ||) to combine them
- Thinking step by step, if there are multiple initializations, think about them one by one.
"""

__preprocess_json_gen = """
The formal name of "check" is "postcondition", conclude your analysis in a json format; for example:
{
   "initializer": "res = sscanf(str, '%u.%u.%u.%u%n', &a, &b, &c, &d, &n)",
   "suspicious": ["a", "b", "c", "d"],
   "postcondition": "res >=4",
}

For multiple initializations, respond as:
[
 {"initializer":..., "suspicious": ..., "relevant_constraints":... }, 
 {"initializer":...,  "suspicious": ..., "relevant_constraints":... }
]

If not any initializer, albeit rare, you should return an empty list:
{[]}

"""

# analyze: version v4.0 (Jul 23, 2023)
# TODO (haonan): avoid the overuse of `condition`
__analyze_system_text = """
You are an experienced Linux program analysis expert. I am working on analyzing the Linux kernel for a specific type of bug called "use-before-initialization." I need your assistance in determining if a given function initializes the suspicious variables.
Additionally, I will give you some constraints to help your analysis, these constraints are facts must hold after the function execute, we also call them “postcondition”

For example, with the postcondition “sscanf(str, '%u.%u.%u.%u%n', &a, &b, &c, &d, &n)>=4", we can conclude that function sscanf must initialize a,b,c,d, while either init or not init for “n", so “may_init" for n.

The golden rule to make a judgment is to see whether at least one “initialization” could happen.

“early returns” is critical and common, if you see them before the initialization of the statement that possibly makes it unreachable, for example:
```
if(some_condition){
return -1;
}
a = ... // init var a
```
In this case,
- if we don't have any postcondition, directly mark "a" as may_init since it could be unreachable
- if we have a postcondition, the function must be satisfied after the function execution. For  example, with postcondition (return value != -1), we can infer this branch was never taken (otherwise it return -1 and therefore conflicting our postcondition)
Once at least one “initialization” could happen, you can mark the variable as "must_init".

An uninitialized variable can propagate and pollute other variables,
for example, “X=v” and if v is uninitialized, it will make X also uninitialized. This way, you should take notes, focus on the variable “X” and reconsider your analysis.

There're some facts that we assume are always satisfied
- all functions are callable, must return to its caller, if it has a return value, the return value must be initialized with something
- the `address` of parameters are always "not NULL", unless it is explicitly "NULL" passed in

You should think step by step.
Anytime you feel uncertain due to unknown functions, you should stop analysis and ask me to provide its definition(s) in this way:
{ "ret": "need_more_info", "response": [ { "type": "function_def", "name": "some_func" } ] }
And I’ll give you what you want to let you analyze it again.

"""


__analyze_continue_text = """
Review the analysis above carefully; consider the following:

1. All functions are callable, must return to its caller. 
2. If we have postcondition, it must be satisfied after the function execution.
3. every function could return an error code (if it has return value); if there's a branch not init our suspicious variable and it can go, it must go and "may_init."

For unknown functions, if it is called under a return code check, you could assume this function init the suspicious var when it returns 0 and not init when it returns non-zero;
It can do anything if it is called without any checks (i.e., may_init).

If the condition of "may_init" happens to be the postcondition or other common sense you consider true, you should change it to "must_init".

Common sense to be true:
1. constant you can calculate to be true: for example, sizeof(int)>0 or size of other variables where you know the type
2. The suspicious variable has a non-null address; i.e., &suspicious_var != NULL

If you already see some path can return and without any init, direct conclude it's "may_init" with "confidence: true".

thinking step by step to conclude a correct and comprehensive answer
"""

__analyze_json_gen = """
based on our analysis result, generate the json format result. 
For each "may_init", you should also indicates its condition of initalization (or say "condition": "unknown" if you can't determine):
For instance:
{
"ret": "success",
"confidence": "true",
"response": {
 "must_init": ["a", "b", "c", "d"],
 "may_init": [{"name":"n", "condition": "ret_val > 4"}],
 "must_no_init": []
}
}
"""

__analyze_json_haading = 'Since `{}` is an unknown function, I will need its definition to continue the analysis. \n{{"ret": "need_more_info", "response": [{{"type": "function_def", "name": "{}"}}]}}'



####################

PreprocessPrompt = Prompt(__preprocess_system_text, __preprocess_json_gen, continue_text=__preprocess_continue_text)
AnalyzePrompt = Prompt(__analyze_system_text, __analyze_json_gen, __analyze_json_haading, continue_text=__analyze_continue_text)