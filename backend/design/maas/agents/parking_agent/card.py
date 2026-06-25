from .agent import ParkingAgent


def build_card():
    return ParkingAgent().build_card()


__all__ = ["build_card"]
