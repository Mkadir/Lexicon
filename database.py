import sqlcipher3.dbapi2 as sqlite3
import os
from datetime import datetime
from typing import List, Dict, Optional, Tuple

# Constants for database configuration
DB_FILE = "lexicon.db"  # Database filename
ENCRYPTION_KEY = "lexicon-pro-secure-key-2024"  # Encryption key (in real app, should be more securely stored)


def initialize_db() -> None:
    """Initialize database connection and create tables if they don't exist."""
    conn = None
    try:
        conn = get_connection()
        cursor = conn.cursor()
        
        # Create words table if it doesn't exist
        cursor.execute('''
        CREATE TABLE IF NOT EXISTS words (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            word TEXT NOT NULL UNIQUE,
            definition TEXT NOT NULL,
            added_at TEXT NOT NULL
        )
        ''')
        
        conn.commit()
    except sqlite3.Error as e:
        print(f"Database initialization error: {e}")
    finally:
        if conn:
            conn.close()


def get_connection() -> sqlite3.Connection:
    """Create and return a connection to the encrypted SQLite database."""
    conn = sqlite3.connect(DB_FILE)
    # Set encryption key (SQLCipher specific)
    conn.execute(f"PRAGMA key = '{ENCRYPTION_KEY}';")
    return conn


def add_word(word: str, definition: str) -> bool:
    """Add a new word with definition to the database.
    
    Args:
        word: The word to add
        definition: The definition of the word
        
    Returns:
        bool: True if successful, False otherwise
    """
    conn = None
    try:
        conn = get_connection()
        cursor = conn.cursor()
        
        # Get current timestamp in ISO format
        timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        
        # Insert new word
        cursor.execute(
            "INSERT INTO words (word, definition, added_at) VALUES (?, ?, ?)",
            (word, definition, timestamp)
        )
        
        conn.commit()
        return True
    except sqlite3.IntegrityError:
        # Word already exists (UNIQUE constraint failed)
        print(f"Word '{word}' already exists in the database")
        return False
    except sqlite3.Error as e:
        print(f"Error adding word: {e}")
        return False
    finally:
        if conn:
            conn.close()


def get_all_words() -> List[Dict]:
    """Get all words sorted alphabetically.
    
    Returns:
        List of dictionaries containing word data
    """
    conn = None
    try:
        conn = get_connection()
        cursor = conn.cursor()
        
        cursor.execute(
            "SELECT id, word, definition, added_at FROM words ORDER BY word COLLATE NOCASE ASC"
        )
        
        # Convert to list of dictionaries
        words = [
            {
                "id": row[0],
                "word": row[1],
                "definition": row[2],
                "date_added": row[3]
            }
            for row in cursor.fetchall()
        ]
        
        return words
    except sqlite3.Error as e:
        print(f"Error retrieving words: {e}")
        return []
    finally:
        if conn:
            conn.close()


def get_word_by_id(word_id: int) -> Optional[Dict]:
    """Get a single word by its ID.
    
    Args:
        word_id: The ID of the word to retrieve
        
    Returns:
        Dictionary with word data if found, None otherwise
    """
    conn = None
    try:
        conn = get_connection()
        cursor = conn.cursor()
        
        cursor.execute(
            "SELECT id, word, definition, added_at FROM words WHERE id = ?",
            (word_id,)
        )
        
        row = cursor.fetchone()
        if row:
            return {
                "id": row[0],
                "word": row[1],
                "definition": row[2],
                "date_added": row[3]
            }
        return None
    except sqlite3.Error as e:
        print(f"Error retrieving word: {e}")
        return None
    finally:
        if conn:
            conn.close()


def update_word(word_id: int, new_word: str, new_definition: str) -> bool:
    """Update a word and its definition.
    
    Args:
        word_id: The ID of the word to update
        new_word: The new word text
        new_definition: The new definition text
        
    Returns:
        bool: True if successful, False otherwise
    """
    conn = None
    try:
        conn = get_connection()
        cursor = conn.cursor()
        
        cursor.execute(
            "UPDATE words SET word = ?, definition = ? WHERE id = ?",
            (new_word, new_definition, word_id)
        )
        
        conn.commit()
        return cursor.rowcount > 0
    except sqlite3.IntegrityError:
        # Word already exists (UNIQUE constraint failed)
        print(f"Word '{new_word}' already exists in the database")
        return False
    except sqlite3.Error as e:
        print(f"Error updating word: {e}")
        return False
    finally:
        if conn:
            conn.close()


def delete_word(word_id: int) -> bool:
    """Delete a word from the database.
    
    Args:
        word_id: The ID of the word to delete
        
    Returns:
        bool: True if successful, False otherwise
    """
    conn = None
    try:
        conn = get_connection()
        cursor = conn.cursor()
        
        cursor.execute(
            "DELETE FROM words WHERE id = ?",
            (word_id,)
        )
        
        conn.commit()
        return cursor.rowcount > 0
    except sqlite3.Error as e:
        print(f"Error deleting word: {e}")
        return False
    finally:
        if conn:
            conn.close()


def search_words(query: str) -> List[Dict]:
    """Search for words containing the query string.
    
    Args:
        query: The search query
        
    Returns:
        List of dictionaries containing matching word data
    """
    conn = None
    try:
        conn = get_connection()
        cursor = conn.cursor()
        
        # Use LIKE for partial matching with case insensitivity
        search_pattern = f"%{query}%"
        cursor.execute(
            "SELECT id, word, definition, added_at FROM words WHERE word LIKE ? COLLATE NOCASE ORDER BY word COLLATE NOCASE ASC",
            (search_pattern,)
        )
        
        # Convert to list of dictionaries
        words = [
            {
                "id": row[0],
                "word": row[1],
                "definition": row[2],
                "date_added": row[3]
            }
            for row in cursor.fetchall()
        ]
        
        return words
    except sqlite3.Error as e:
        print(f"Error searching words: {e}")
        return []
    finally:
        if conn:
            conn.close()


# Initialize the database when module is imported
initialize_db() 