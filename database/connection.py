# database/connection.py - Database Connection Manager
import psycopg2
import psycopg2.extras
from contextlib import contextmanager
import sys
import os
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from config import Config
from utils.logger import get_logger

logger = get_logger(__name__)

class DatabaseConnection:
    """Database connection manager with connection pooling"""
    
    @staticmethod
    def get_connection():
        """Get a database connection"""
        try:
            conn = psycopg2.connect(
                host=Config.DB_HOST,
                database=Config.DB_NAME,
                user=Config.DB_USER,
                password=Config.DB_PASS,
                port=Config.DB_PORT
            )
            return conn
        except psycopg2.Error as e:
            logger.error(f"Database connection error: {e}")
            return None
    
    @staticmethod
    @contextmanager
    def get_db_cursor(commit=False, cursor_factory=None):
        """
        Context manager for database operations
        
        Args:
            commit: Whether to commit the transaction
            cursor_factory: Cursor factory (e.g., RealDictCursor)
        """
        conn = None
        cursor = None
        try:
            conn = DatabaseConnection.get_connection()
            if not conn:
                raise Exception("Database connection failed")
            
            cursor_args = {}
            if cursor_factory:
                cursor_args['cursor_factory'] = cursor_factory
            
            cursor = conn.cursor(**cursor_args)
            yield cursor
            
            if commit:
                conn.commit()
        except Exception as e:
            if conn:
                conn.rollback()
            logger.error(f"Database operation error: {e}")
            raise
        finally:
            if cursor:
                cursor.close()
            if conn:
                conn.close()
    
    @staticmethod
    def execute_query(query, params=None, fetch=True, commit=False):
        """
        Execute a database query
        
        Args:
            query: SQL query string
            params: Query parameters
            fetch: Whether to fetch results
            commit: Whether to commit the transaction
        
        Returns:
            Query results or None
        """
        with DatabaseConnection.get_db_cursor(commit=commit) as cursor:
            cursor.execute(query, params or ())
            
            if fetch:
                return cursor.fetchall()
            return cursor.rowcount
    
    @staticmethod
    def execute_query_dict(query, params=None, fetch_one=False):
        """Execute query and return results as dictionaries"""
        with DatabaseConnection.get_db_cursor(
            cursor_factory=psycopg2.extras.RealDictCursor
        ) as cursor:
            cursor.execute(query, params or ())
            
            if fetch_one:
                return cursor.fetchone()
            return cursor.fetchall()

# Create a global instance
db = DatabaseConnection()