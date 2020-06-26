from os.path import exists
from os import mkdir


def foo():
    print("Hello World!")


workdir: "data"


localrules: run_all


onstart:
    if not exists("logs"):
        mkdir("logs")


rule run_all:
    output:
        my_output="output.txt",
    shell:
        "touch {output.my_output}"


onsuccess:
    print("Workflow finished, no error")


onerror:
    print("An error occurred")
