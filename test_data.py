#!/usr/bin/env python3
"""
Script to generate test CSV files for testing the application
"""

import pandas as pd
import os
from datetime import datetime, timedelta
import random

def create_test_csv_files():
    """Create various test CSV files"""
    
    # Ensure uploads directory exists
    os.makedirs("uploads", exist_ok=True)
    
    # 1. Valid CSV with data
    data = {
        'id': range(1, 101),
        'name': [f'User_{i}' for i in range(1, 101)],
        'email': [f'user{i}@example.com' for i in range(1, 101)],
        'age': [random.randint(18, 80) for _ in range(100)],
        'created_at': [(datetime.now() - timedelta(days=random.randint(1, 365))).isoformat() for _ in range(100)]
    }
    df = pd.DataFrame(data)
    df.to_csv('uploads/test_data_100_rows.csv', index=False)
    print("✅ Created test_data_100_rows.csv (100 rows)")
    
    # 2. Small CSV with few rows
    small_data = {
        'product_id': [1, 2, 3],
        'product_name': ['Apple', 'Banana', 'Orange'],
        'price': [1.50, 0.75, 2.00]
    }
    df_small = pd.DataFrame(small_data)
    df_small.to_csv('uploads/test_small_data.csv', index=False)
    print("✅ Created test_small_data.csv (3 rows)")
    
    # 3. Empty CSV (only headers)
    empty_data = pd.DataFrame(columns=['col1', 'col2', 'col3'])
    empty_data.to_csv('uploads/test_empty_data.csv', index=False)
    print("✅ Created test_empty_data.csv (0 rows)")
    
    # 4. Large CSV for performance testing
    large_data = {
        'transaction_id': range(1, 10001),
        'customer_id': [random.randint(1, 1000) for _ in range(10000)],
        'amount': [round(random.uniform(10.00, 1000.00), 2) for _ in range(10000)],
        'currency': [random.choice(['USD', 'EUR', 'GBP']) for _ in range(10000)],
        'timestamp': [(datetime.now() - timedelta(minutes=random.randint(1, 525600))).isoformat() for _ in range(10000)]
    }
    df_large = pd.DataFrame(large_data)
    df_large.to_csv('uploads/test_large_data.csv', index=False)
    print("✅ Created test_large_data.csv (10,000 rows)")
    
    # 5. CSV with various data types
    mixed_data = {
        'integer_col': [1, 2, 3, 4, 5],
        'float_col': [1.1, 2.2, 3.3, 4.4, 5.5],
        'string_col': ['a', 'b', 'c', 'd', 'e'],
        'boolean_col': [True, False, True, False, True],
        'date_col': [datetime.now().date() for _ in range(5)],
        'null_col': [None, 'value', None, 'another', None]
    }
    df_mixed = pd.DataFrame(mixed_data)
    df_mixed.to_csv('uploads/test_mixed_types.csv', index=False)
    print("✅ Created test_mixed_types.csv (5 rows with mixed data types)")
    
    print("\n🎉 All test CSV files created successfully!")
    print("📁 Files are located in the 'uploads/' directory")
    print("\nYou can now test the API with these files:")
    print("- test_data_100_rows.csv: Normal file with 100 rows")
    print("- test_small_data.csv: Small file with 3 rows")
    print("- test_empty_data.csv: Empty file (will trigger 'Error' status)")
    print("- test_large_data.csv: Large file with 10,000 rows")
    print("- test_mixed_types.csv: File with various data types")

if __name__ == "__main__":
    create_test_csv_files() 