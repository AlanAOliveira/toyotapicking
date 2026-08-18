"""PickingItem data model."""
from dataclasses import dataclass


@dataclass
class PickingItem:
    endereco: str
    back: str
    part_number: str
    qtd: int
    exporter: str
    caixa: str
    status: str