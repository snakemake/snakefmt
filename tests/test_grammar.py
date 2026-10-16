"""
Completeness tests: checks that the parser's recognised keywords are a bijection of the
snakemake grammar.
    To use the latest snakemake grammar, run `uv update snakemake` from this repo
"""

from snakemake import parser

from snakefmt.parser.grammar import Module, Rule, UseRule, global_snakemake_subautomata


class TestCompleteness:
    @classmethod
    def check_completeness(cls, target_keywords: set, existing_keywords: set):
        spurious_keywords = existing_keywords.difference(target_keywords)
        assert (
            len(spurious_keywords) == 0
        ), f"Keywords {spurious_keywords} do not exist in snakemake grammar"

        missing_keywords = target_keywords.difference(existing_keywords)
        assert (
            len(missing_keywords) == 0
        ), f"Keywords {missing_keywords} from snakemake grammar are missing"

    def test_global_context_completeness(self):
        target_keywords = set(parser.Python.subautomata)
        existing_keywords = set(global_snakemake_subautomata)
        self.check_completeness(target_keywords, existing_keywords)

    def test_module_context_completeness(self):
        target_keywords = set(parser.Module.subautomata)
        existing_keywords = set(Module.subautomata)
        self.check_completeness(target_keywords, existing_keywords)

    def test_use_rule_context_completeness(self):
        target_keywords = set(parser.UseRule.subautomata)
        existing_keywords = set(UseRule.subautomata)
        self.check_completeness(target_keywords, existing_keywords)

    def test_rule_context_completeness(self):
        target_keywords = set(parser.Rule.subautomata)
        existing_keywords = set(Rule.subautomata)
        self.check_completeness(target_keywords, existing_keywords)
