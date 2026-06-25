from .agent import LawGraphAgent


def build_card():
    return LawGraphAgent().build_card()


__all__ = ["build_card"]
