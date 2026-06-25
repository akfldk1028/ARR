from .agent import ReviewAgent


def build_card():
    return ReviewAgent().build_card()


__all__ = ["build_card"]
