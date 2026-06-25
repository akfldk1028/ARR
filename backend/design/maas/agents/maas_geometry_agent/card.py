from .agent import MaasGeometryAgent


def build_card():
    return MaasGeometryAgent().build_card()


__all__ = ["build_card"]
