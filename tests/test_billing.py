import pytest
import os
import sys
import sqlite3
import uuid

# Add backend to path
sys.path.append(os.path.join(os.getcwd(), 'backend'))
from main import _deduct, get_conn, DB_PATH

@pytest.fixture
def temp_db(tmp_path):
    db_file = tmp_path / "test_usage.db"
    # Use real schema from main.py or just enough for tests
    conn = sqlite3.connect(str(db_file))
    conn.execute("""
        CREATE TABLE users (
            id INTEGER PRIMARY KEY,
            username TEXT,
            credits REAL
        )
    """)
    conn.execute("""
        CREATE TABLE credit_ledger (
            id INTEGER PRIMARY KEY,
            user_id INTEGER,
            amount REAL,
            type TEXT,
            description TEXT,
            timestamp DATETIME DEFAULT CURRENT_TIMESTAMP
        )
    """)
    conn.execute("INSERT INTO users (username, credits) VALUES (?,?)", ("testuser", 100.0))
    conn.commit()
    conn.close()
    
    # Patch DB_PATH in main.py globally for the duration of this test
    import backend.main as main_module
    old_path = main_module.DB_PATH
    main_module.DB_PATH = str(db_file)
    
    yield str(db_file)
    
    main_module.DB_PATH = old_path

def test_credit_deduction_success(temp_db):
    # testuser has 100 credits
    ok = _deduct(1, 10.0, "test deduction")
    assert ok is True
    
    conn = sqlite3.connect(temp_db)
    row = conn.execute("SELECT credits FROM users WHERE id=1").fetchone()
    assert row[0] == 90.0
    
    ledger = conn.execute("SELECT amount FROM credit_ledger WHERE user_id=1").fetchone()
    assert ledger[0] == -10.0
    conn.close()

def test_credit_deduction_insufficient(temp_db):
    # testuser has 100 credits, try to deduct 150
    ok = _deduct(1, 150.0, "expensive task")
    assert ok is False
    
    conn = sqlite3.connect(temp_db)
    row = conn.execute("SELECT credits FROM users WHERE id=1").fetchone()
    assert row[0] == 100.0
    conn.close()
