"""
Sample application using my_functions.py and my_class.py.
This app will be instrumented via monocle.yaml config.
"""
import sys
import os

# Add examples dir to path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from my_functions import calculate_sum, calculate_product, complex_calculation
from my_class import Calculator


def main():
    print("=" * 60)
    print("Running my_app.py with Monocle instrumentation")
    print("=" * 60)

    # Test standalone functions
    print("\n--- Standalone Functions ---")

    result = calculate_sum(10, 20)
    print(f"calculate_sum(10, 20) = {result}")

    result = calculate_product(5, 6)
    print(f"calculate_product(5, 6) = {result}")

    result = complex_calculation(7)
    print(f"complex_calculation(7) = {result}")

    # Test class methods
    print("\n--- Calculator Class Methods ---")

    calc = Calculator("MyCalculator")

    result = calc.add(100, 200)
    print(f"calc.add(100, 200) = {result}")

    result = calc.multiply(8, 9)
    print(f"calc.multiply(8, 9) = {result}")

    result = calc.complex_operation(10)
    print(f"calc.complex_operation(10) = {result}")

    print("\n" + "=" * 60)
    print("Done! Check Okahu dashboard for traces.")
    print("=" * 60)


if __name__ == "__main__":
    main()
