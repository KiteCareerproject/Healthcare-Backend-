from pymongo import MongoClient
from django.conf import settings
import os

class MongoHelper:
    """Helper class for MongoDB operations"""
    
    def __init__(self):
        # Get database settings
        db_settings = settings.DATABASES['default']
        
        # Try to get connection details in different formats
        host = None
        port = 27017
        username = None
        password = None
        auth_source = 'admin'
        
        # Check if using CLIENT format
        if 'CLIENT' in db_settings:
            client_config = db_settings['CLIENT']
            host = client_config.get('host', 'localhost')
            port = client_config.get('port', 27017)
            username = client_config.get('username')
            password = client_config.get('password')
            auth_source = client_config.get('authSource', 'admin')
        else:
            # Direct format
            host = db_settings.get('HOST', 'localhost')
            port = db_settings.get('PORT', 27017)
            username = db_settings.get('USER')
            password = db_settings.get('PASSWORD')
            auth_source = db_settings.get('AUTH_SOURCE', 'admin')
        
        # Ensure port is integer
        try:
            port = int(port)
        except (TypeError, ValueError):
            port = 27017
        
        # Build connection string
        if username and password:
            # With authentication
            connection_string = f"mongodb://{username}:{password}@{host}:{port}/?authSource={auth_source}"
        else:
            # Without authentication
            connection_string = f"mongodb://{host}:{port}/"
        
        try:
            # Connect using connection string
            self.client = MongoClient(connection_string)
            self.db = self.client[db_settings['NAME']]
            # Test connection
            self.client.admin.command('ping')
            print(f"Connected to MongoDB at {host}:{port}")
        except Exception as e:
            print(f"MongoDB connection error: {e}")
            # Fallback to localhost
            self.client = MongoClient('localhost', 27017)
            self.db = self.client[db_settings['NAME']]
    
    def get_collection(self, collection_name):
        """Get MongoDB collection by name"""
        return self.db[collection_name]
    
    def close(self):
        """Close MongoDB connection"""
        self.client.close()

# Create single instance
mongo = MongoHelper()