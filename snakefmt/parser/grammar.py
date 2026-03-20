from collections import OrderedDict

from snakefmt.parser.syntax import (
    Context,
    InlineSingleParam,
    KeywordSyntax,
    NoKeyParamList,
    ParamList,
    SingleParam,
    Vocabulary,
)


class PythonCode(Vocabulary):
    pass


# In common between 'use rule' and 'rule'
rule_properties = OrderedDict(
    # Primary metadata
    name=Context(None, SingleParam),
    default_target=Context(None, InlineSingleParam),
    # I/O
    input=Context(None, ParamList),
    output=Context(None, ParamList),
    log=Context(None, ParamList),
    benchmark=Context(None, SingleParam),
    # Rule logic
    pathvars=Context(None, ParamList),
    wildcard_constraints=Context(None, ParamList),
    # Scheduling & control
    cache=Context(None, InlineSingleParam),
    priority=Context(None, InlineSingleParam),
    retries=Context(None, InlineSingleParam),
    group=Context(None, SingleParam),
    localrule=Context(None, InlineSingleParam),
    handover=Context(None, InlineSingleParam),
    # Execution environment
    shadow=Context(None, SingleParam),
    conda=Context(None, SingleParam),
    container=Context(None, SingleParam),
    singularity=Context(None, SingleParam),
    containerized=Context(None, SingleParam),
    envmodules=Context(None, NoKeyParamList),
    # Execution resources and parameters
    threads=Context(None, InlineSingleParam),
    resources=Context(None, ParamList),
    params=Context(None, ParamList),
    # Rule definition
    message=Context(None, SingleParam),
)


class SnakeUseRule(Vocabulary):
    spec = rule_properties


class SnakeRule(Vocabulary):
    spec = OrderedDict(
        **rule_properties,
        # Action
        run=Context(PythonCode, KeywordSyntax),
        shell=Context(None, SingleParam),
        script=Context(None, SingleParam),
        notebook=Context(None, SingleParam),
        wrapper=Context(None, SingleParam),
        cwl=Context(None, SingleParam),
        template_engine=Context(None, SingleParam),
    )


class SnakeModule(Vocabulary):
    spec = OrderedDict(
        name=Context(None, InlineSingleParam),
        pathvars=Context(None, ParamList),
        snakefile=Context(None, SingleParam),
        config=Context(None, SingleParam),
        skip_validation=Context(None, SingleParam),
        prefix=Context(None, SingleParam),
        replace_prefix=Context(None, SingleParam),
        meta_wrapper=Context(None, SingleParam),
    )


class SnakeGlobal(Vocabulary):
    spec = dict(
        envvars=Context(None, NoKeyParamList),
        include=Context(None, InlineSingleParam),
        workdir=Context(None, InlineSingleParam),
        configfile=Context(None, InlineSingleParam),
        pepfile=Context(None, InlineSingleParam),
        pepschema=Context(None, InlineSingleParam),
        report=Context(None, InlineSingleParam),
        ruleorder=Context(None, InlineSingleParam),
        rule=Context(SnakeRule, KeywordSyntax),
        checkpoint=Context(SnakeRule, KeywordSyntax),
        localrules=Context(None, NoKeyParamList),
        onstart=Context(PythonCode, KeywordSyntax),
        onsuccess=Context(PythonCode, KeywordSyntax),
        onerror=Context(PythonCode, KeywordSyntax),
        wildcard_constraints=Context(None, ParamList),
        singularity=Context(None, InlineSingleParam),
        container=Context(None, InlineSingleParam),
        containerized=Context(None, InlineSingleParam),
        scattergather=Context(None, ParamList),
        inputflags=Context(None, NoKeyParamList),
        outputflags=Context(None, NoKeyParamList),
        module=Context(SnakeModule, KeywordSyntax),
        use=Context(SnakeUseRule, KeywordSyntax),
        resource_scopes=Context(None, ParamList),
        conda=Context(None, InlineSingleParam),
        storage=Context(None, ParamList),
        pathvars=Context(None, ParamList),
    )
