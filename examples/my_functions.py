"""
Standalone functions (not in a class) for instrumentation examples.
"""
import time


def calculate_sum(a: int, b: int) -> int:
    """Simple function to add two numbers."""
    time.sleep(0.01)  # Simulate some work
    return a + b


def calculate_product(a: int, b: int) -> int:
    """Simple function to multiply two numbers."""
    time.sleep(0.01)
    return a * b


def complex_calculation(x: int) -> int:
    """Function that calls other functions internally."""
    sum_result = calculate_sum(x, x)
    product_result = calculate_product(x, 2)
    return sum_result + product_result


async def async_fetch_data(item_id: int) -> dict:
    """Async function to simulate fetching data."""
    import asyncio
    await asyncio.sleep(0.01)
    return {"id": item_id, "name": f"Item {item_id}", "price": item_id * 10.5}


async def async_process_items(item_ids: list) -> list:
    """Async function that processes multiple items."""
    results = []
    for item_id in item_ids:
        data = await async_fetch_data(item_id)
        results.append(data)
    return results
