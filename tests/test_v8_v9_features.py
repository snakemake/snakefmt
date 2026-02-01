from snakefmt.formatter import TAB
from tests import setup_formatter


class TestSnakemakeV8V9Features:
    def test_global_conda_directive(self):
        """Test for issue #209: Global conda directive"""
        setup_formatter('conda: "envs/global.yaml"')
        setup_formatter('conda:\n    "envs/global.yaml"')

    def test_module_directive(self):
        snake = (
            "module other:\n"
            f'{TAB}snakefile: "other.smk"\n'
            f"{TAB}config: config\n"
            f'{TAB}meta_wrapper: "meta"\n'
        )
        setup_formatter(snake)

    def test_use_rule_with_block(self):
        snake = (
            "use rule * from other as other_* with:\n"
            f'{TAB}conda: "envs/other.yaml"\n'
            f"{TAB}threads: 4\n"
            f"{TAB}resources:\n"
            f"{TAB}{TAB}mem_mb=1000\n"
        )
        setup_formatter(snake)

    def test_storage_directive(self):
        snake = "storage:\n" f'{TAB}provider="s3",\n' f"{TAB}retries=3\n"
        setup_formatter(snake)

    def test_resource_scopes_directive(self):
        snake = "resource_scopes:\n" f'{TAB}mem_mb="global"\n'
        setup_formatter(snake)

    def test_new_rule_properties(self):
        snake = (
            "rule a:\n"
            f'{TAB}output: "a"\n'
            f"{TAB}retries: 3\n"
            f"{TAB}handover: True\n"
            f"{TAB}default_target: True\n"
            f"{TAB}localrule: True\n"
            f"{TAB}cache: True\n"
        )
        setup_formatter(snake)

    def test_input_output_flags(self):
        # inputflags and outputflags take no key parameters (NoKeyParamList)
        snake = "inputflags:\n" f'{TAB}"flag1", "flag2"\n'
        setup_formatter(snake)

    def test_pathvars_directive(self):
        # pathvars is in SnakeGlobal
        snake = "pathvars:\n" f'{TAB}var1="path/to/1"\n'
        setup_formatter(snake)
