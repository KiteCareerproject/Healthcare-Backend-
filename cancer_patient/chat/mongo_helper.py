from pymongo import MongoClient
from django.conf import settings
import os
from dotenv import load_dotenv

load_dotenv()


class MongoHelper:
    """Helper class for MongoDB operations"""

    def __init__(self):

        # Get MongoDB Atlas URI
        mongodb_uri = os.getenv("MONGODB_URI")

        # Get database name
        db_name = os.getenv("DB_NAME", "healthcare")

        if not mongodb_uri:
            raise ValueError("MONGODB_URI is not configured in .env")

        if not db_name:
            raise ValueError("DB_NAME is empty")

        print("MongoDB Database:", db_name)

        try:
            # Connect to MongoDB Atlas
            self.client = MongoClient(mongodb_uri)

            # Select database
            self.db = self.client[db_name]

            # Test connection
            self.client.admin.command("ping")

            print("✅ MongoDB Atlas connected successfully!")
            print(f"✅ Database: {db_name}")

        except Exception as e:
            print(f"❌ MongoDB connection error: {e}")
            raise

    def get_collection(self, collection_name):
        """Get MongoDB collection by name"""
        return self.db[collection_name]

    def close(self):
        """Close MongoDB connection"""
        self.client.close()


# Create single instance
mongo = MongoHelper()