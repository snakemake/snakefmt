"""
Completeness tests: checks that the grammar used is a bijection of the snakemake grammar
    To use the latest snakemake grammar, run `poetry update snakemake` from this repo
"""
from snakemake import parser

from tests import setup_formatter
from snakefmt.parser import grammar
from snakefmt.parser.syntax import possibly_duplicated_keywords


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
        existing_keywords = set(grammar.SnakeGlobal.spec)
        self.check_completeness(target_keywords, existing_keywords)

    def test_subworkflow_context_completeness(self):
        target_keywords = set(parser.Subworkflow.subautomata)
        existing_keywords = set(grammar.SnakeSubworkflow.spec)
        self.check_completeness(target_keywords, existing_keywords)

    def test_rule_context_completeness(self):
        target_keywords = set(parser.Rule.subautomata)
        existing_keywords = set(grammar.SnakeRule.spec)
        self.check_completeness(target_keywords, existing_keywords)


class TestAllowedDuplicates:
    def test_allowed_duplicates_in_snakefile(self):
        for keyword in possibly_duplicated_keywords:
            snakefile = ""
            for i in range(2):
                snakefile += f"{keyword}: val{i}\n"
            formatter = setup_formatter(snakefile)
            formatter.get_formatted()  # does not raise error
