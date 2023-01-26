if config["strain-calling"]["use-gisaid"]:
    envvars:
        "GISAID_API_TOKEN",


include: "rules/common.smk"
include: "rules/benchmarking_common.smk"