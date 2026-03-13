"""
Class-based functions for instrumentation examples.
"""
import time


class Calculator:
    """A simple calculator class for demonstration."""

    def __init__(self, name: str = "Calculator"):
        self.name = name
        self.history = []

    def add(self, a: int, b: int) -> int:
        """Add two numbers."""
        time.sleep(0.01)
        result = a + b
        self.history.append(f"add({a}, {b}) = {result}")
        return result

    def multiply(self, a: int, b: int) -> int:
        """Multiply two numbers."""
        time.sleep(0.01)
        result = a * b
        self.history.append(f"multiply({a}, {b}) = {result}")
        return result

    def complex_operation(self, x: int) -> int:
        """Perform a complex operation using other methods."""
        sum_result = self.add(x, x)
        product_result = self.multiply(x, 2)
        return sum_result + product_result


class AsyncDataService:
    """An async service class for demonstration."""

    def __init__(self, service_name: str = "DataService"):
        self.service_name = service_name

    async def fetch_item(self, item_id: int) -> dict:
        """Fetch a single item asynchronously."""
        import asyncio
        await asyncio.sleep(0.01)
        return {"id": item_id, "name": f"Item {item_id}", "source": self.service_name}

    async def fetch_multiple(self, item_ids: list) -> list:
        """Fetch multiple items asynchronously."""
        results = []
        for item_id in item_ids:
            data = await self.fetch_item(item_id)
            results.append(data)
        return results
