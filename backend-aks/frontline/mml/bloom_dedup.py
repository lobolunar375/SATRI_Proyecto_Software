from pybloom_live import ScalableBloomFilter
import logging

logger = logging.getLogger("bloom_dedup")

# Usar pybloom-live in-memory (reemplazo gratuito de Redis para esta función puntual)
# ScalableBloomFilter crece automáticamente si superamos la capacidad inicial
bloom_filter = ScalableBloomFilter(initial_capacity=100000, error_rate=0.001)

class InMemoryBloomDedup:
    def add(self, item: str) -> bool:
        # bloom_filter.add() devuelve True si el elemento YA ESTABA en el filtro.
        is_duplicate = bloom_filter.add(item)
        return not is_duplicate

    def is_duplicate(self, item: str) -> bool:
        return item in bloom_filter

# Instancia global para ser usada por main.py
bloom = InMemoryBloomDedup()
