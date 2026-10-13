"""Fixtures for test_directive_order.py: snakemake code, the directive orders and
the text expected from formatting them and from printing/rejecting them.
"""

from snakefmt.types import TAB

ACTION_DIRECTIVES = (
    "run",
    "shell",
    "script",
    "notebook",
    "wrapper",
    "cwl",
    "template_engine",
)
DEFAULT_RULE_ORDER = (
    "name",
    "default_target",
    "input",
    "output",
    "log",
    "benchmark",
    "pathvars",
    "wildcard_constraints",
    "cache",
    "priority",
    "retries",
    "group",
    "localrule",
    "handover",
    "shadow",
    "conda",
    "container",
    "singularity",
    "containerized",
    "envmodules",
    "threads",
    "resources",
    "params",
    "message",
)
DEFAULT_MODULE_ORDER = (
    "name",
    "pathvars",
    "snakefile",
    "config",
    "skip_validation",
    "prefix",
    "replace_prefix",
    "meta_wrapper",
)
CUSTOM_RULE_ORDER = (
    "message",
    "params",
    "threads",
    "input",
    "output",
    "name",
    "default_target",
    "log",
    "benchmark",
    "pathvars",
    "wildcard_constraints",
    "cache",
    "priority",
    "retries",
    "group",
    "localrule",
    "handover",
    "shadow",
    "conda",
    "container",
    "singularity",
    "containerized",
    "envmodules",
    "resources",
)
CUSTOM_MODULE_ORDER = (
    "prefix",
    "config",
    "snakefile",
    "name",
    "pathvars",
    "skip_validation",
    "replace_prefix",
    "meta_wrapper",
)

CUSTOM_RULE_ORDER_ARG = ",".join(CUSTOM_RULE_ORDER)
CUSTOM_MODULE_ORDER_ARG = ",".join(CUSTOM_MODULE_ORDER)

RULE_CODE = (
    "rule a:\n"
    f'{TAB}shell: "echo"\n'
    f"{TAB}threads: 1\n"
    f'{TAB}params: p="x"\n'
    f'{TAB}output: "o"\n'
    f'{TAB}input: "i"\n'
)
RULE_UNSORTED = (
    "rule a:\n"
    f"{TAB}shell:\n"
    f'{TAB * 2}"echo"\n'
    f"{TAB}threads: 1\n"
    f"{TAB}params:\n"
    f'{TAB * 2}p="x",\n'
    f"{TAB}output:\n"
    f'{TAB * 2}"o",\n'
    f"{TAB}input:\n"
    f'{TAB * 2}"i",\n'
)
RULE_DEFAULT_ORDER = (
    "rule a:\n"
    f"{TAB}input:\n"
    f'{TAB * 2}"i",\n'
    f"{TAB}output:\n"
    f'{TAB * 2}"o",\n'
    f"{TAB}threads: 1\n"
    f"{TAB}params:\n"
    f'{TAB * 2}p="x",\n'
    f"{TAB}shell:\n"
    f'{TAB * 2}"echo"\n'
)
RULE_CUSTOM_ORDER = (
    "rule a:\n"
    f"{TAB}params:\n"
    f'{TAB * 2}p="x",\n'
    f"{TAB}threads: 1\n"
    f"{TAB}input:\n"
    f'{TAB * 2}"i",\n'
    f"{TAB}output:\n"
    f'{TAB * 2}"o",\n'
    f"{TAB}shell:\n"
    f'{TAB * 2}"echo"\n'
)
MODULE_CODE = (
    "module m:\n"
    f'{TAB}config: "c"\n'
    f'{TAB}pathvars: x="y"\n'
    f'{TAB}prefix: "p"\n'
    f'{TAB}name: "n"\n'
    f'{TAB}snakefile: "s"\n'
)
MODULE_UNSORTED = (
    "module m:\n"
    f"{TAB}config:\n"
    f'{TAB * 2}"c"\n'
    f"{TAB}pathvars:\n"
    f'{TAB * 2}x="y",\n'
    f"{TAB}prefix:\n"
    f'{TAB * 2}"p"\n'
    f'{TAB}name: "n"\n'
    f"{TAB}snakefile:\n"
    f'{TAB * 2}"s"\n'
)
MODULE_DEFAULT_ORDER = (
    "module m:\n"
    f'{TAB}name: "n"\n'
    f"{TAB}pathvars:\n"
    f'{TAB * 2}x="y",\n'
    f"{TAB}snakefile:\n"
    f'{TAB * 2}"s"\n'
    f"{TAB}config:\n"
    f'{TAB * 2}"c"\n'
    f"{TAB}prefix:\n"
    f'{TAB * 2}"p"\n'
)
MODULE_CUSTOM_ORDER = (
    "module m:\n"
    f"{TAB}prefix:\n"
    f'{TAB * 2}"p"\n'
    f"{TAB}config:\n"
    f'{TAB * 2}"c"\n'
    f"{TAB}snakefile:\n"
    f'{TAB * 2}"s"\n'
    f'{TAB}name: "n"\n'
    f"{TAB}pathvars:\n"
    f'{TAB * 2}x="y",\n'
)
USE_RULE_CODE = (
    "use rule a from m as b with:\n"
    f"{TAB}threads: 2\n"
    f'{TAB}output: "o"\n'
    f'{TAB}input: "i"\n'
    f"{TAB}params: p=1\n"
)
USE_RULE_DEFAULT_ORDER = (
    "use rule a from m as b with:\n"
    f"{TAB}input:\n"
    f'{TAB * 2}"i",\n'
    f"{TAB}output:\n"
    f'{TAB * 2}"o",\n'
    f"{TAB}threads: 2\n"
    f"{TAB}params:\n"
    f"{TAB * 2}p=1,\n"
)
USE_RULE_CUSTOM_ORDER = (
    "use rule a from m as b with:\n"
    f"{TAB}params:\n"
    f"{TAB * 2}p=1,\n"
    f"{TAB}threads: 2\n"
    f"{TAB}input:\n"
    f'{TAB * 2}"i",\n'
    f"{TAB}output:\n"
    f'{TAB * 2}"o",\n'
)

DEFAULT_PRINT = (
    "# pyproject.toml, under [tool.snakefmt]:\n"
    'directive_order = ["name", "default_target", "input", "output", "log", '
    '"benchmark", "pathvars", "wildcard_constraints", "cache", "priority", '
    '"retries", "group", "localrule", "handover", "shadow", "conda", '
    '"container", "singularity", "containerized", "envmodules", "threads", '
    '"resources", "params", "message"]\n'
    'module_directive_order = ["name", "pathvars", "snakefile", "config", '
    '"skip_validation", "prefix", "replace_prefix", "meta_wrapper"]\n'
    "\n"
    "# command line:\n"
    "--directive-order name,default_target,input,output,log,benchmark,pathvars,"
    "wildcard_constraints,cache,priority,retries,group,localrule,handover,shadow,"
    "conda,container,singularity,containerized,envmodules,threads,resources,"
    "params,message --module-directive-order name,pathvars,snakefile,config,"
    "skip_validation,prefix,replace_prefix,meta_wrapper\n"
)
CUSTOM_RULE_PRINT = (
    "# pyproject.toml, under [tool.snakefmt]:\n"
    'directive_order = ["message", "params", "threads", "input", "output", '
    '"name", "default_target", "log", "benchmark", "pathvars", '
    '"wildcard_constraints", "cache", "priority", "retries", "group", '
    '"localrule", "handover", "shadow", "conda", "container", "singularity", '
    '"containerized", "envmodules", "resources"]\n'
    'module_directive_order = ["name", "pathvars", "snakefile", "config", '
    '"skip_validation", "prefix", "replace_prefix", "meta_wrapper"]\n'
    "\n"
    "# command line:\n"
    "--directive-order message,params,threads,input,output,name,default_target,"
    "log,benchmark,pathvars,wildcard_constraints,cache,priority,retries,group,"
    "localrule,handover,shadow,conda,container,singularity,containerized,"
    "envmodules,resources --module-directive-order name,pathvars,snakefile,"
    "config,skip_validation,prefix,replace_prefix,meta_wrapper\n"
)
CUSTOM_MODULE_PRINT = (
    "# pyproject.toml, under [tool.snakefmt]:\n"
    'directive_order = ["name", "default_target", "input", "output", "log", '
    '"benchmark", "pathvars", "wildcard_constraints", "cache", "priority", '
    '"retries", "group", "localrule", "handover", "shadow", "conda", '
    '"container", "singularity", "containerized", "envmodules", "threads", '
    '"resources", "params", "message"]\n'
    'module_directive_order = ["prefix", "config", "snakefile", "name", '
    '"pathvars", "skip_validation", "replace_prefix", "meta_wrapper"]\n'
    "\n"
    "# command line:\n"
    "--directive-order name,default_target,input,output,log,benchmark,pathvars,"
    "wildcard_constraints,cache,priority,retries,group,localrule,handover,shadow,"
    "conda,container,singularity,containerized,envmodules,threads,resources,"
    "params,message --module-directive-order prefix,config,snakefile,name,"
    "pathvars,skip_validation,replace_prefix,meta_wrapper\n"
)
CUSTOM_BOTH_PRINT = (
    "# pyproject.toml, under [tool.snakefmt]:\n"
    'directive_order = ["message", "params", "threads", "input", "output", '
    '"name", "default_target", "log", "benchmark", "pathvars", '
    '"wildcard_constraints", "cache", "priority", "retries", "group", '
    '"localrule", "handover", "shadow", "conda", "container", "singularity", '
    '"containerized", "envmodules", "resources"]\n'
    'module_directive_order = ["prefix", "config", "snakefile", "name", '
    '"pathvars", "skip_validation", "replace_prefix", "meta_wrapper"]\n'
    "\n"
    "# command line:\n"
    "--directive-order message,params,threads,input,output,name,default_target,"
    "log,benchmark,pathvars,wildcard_constraints,cache,priority,retries,group,"
    "localrule,handover,shadow,conda,container,singularity,containerized,"
    "envmodules,resources --module-directive-order prefix,config,snakefile,name,"
    "pathvars,skip_validation,replace_prefix,meta_wrapper\n"
)

INCOMPLETE_RULE_ORDER_MESSAGE = (
    "incomplete directive order, missing rule directives: name, default_target, "
    "output, log, benchmark, pathvars, wildcard_constraints, cache, priority, "
    "retries, group, localrule, handover, shadow, conda, container, singularity, "
    "containerized, envmodules, threads, resources, message\n"
    "\n"
    "Adding them in default order after yours gives:\n"
    "\n"
    "# pyproject.toml, under [tool.snakefmt]:\n"
    'directive_order = ["params", "input", "name", "default_target", "output", '
    '"log", "benchmark", "pathvars", "wildcard_constraints", "cache", '
    '"priority", "retries", "group", "localrule", "handover", "shadow", '
    '"conda", "container", "singularity", "containerized", "envmodules", '
    '"threads", "resources", "message"]\n'
    "\n"
    "# command line:\n"
    "--directive-order params,input,name,default_target,output,log,benchmark,"
    "pathvars,wildcard_constraints,cache,priority,retries,group,localrule,"
    "handover,shadow,conda,container,singularity,containerized,envmodules,"
    "threads,resources,message"
)
INCOMPLETE_MODULE_ORDER_MESSAGE = (
    "incomplete directive order, missing module directives: name, pathvars, "
    "snakefile, skip_validation, replace_prefix, meta_wrapper\n"
    "\n"
    "Adding them in default order after yours gives:\n"
    "\n"
    "# pyproject.toml, under [tool.snakefmt]:\n"
    'module_directive_order = ["prefix", "config", "name", "pathvars", '
    '"snakefile", "skip_validation", "replace_prefix", "meta_wrapper"]\n'
    "\n"
    "# command line:\n"
    "--module-directive-order prefix,config,name,pathvars,snakefile,"
    "skip_validation,replace_prefix,meta_wrapper"
)
