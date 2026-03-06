# utils/mongodb.py - Create this file
import pymongo

class MongoDB:
    client = None
    db = None
    
    @classmethod
    def connect(cls):
        if cls.client is None:
            cls.client = pymongo.MongoClient('localhost', 27017)
            cls.db = cls.client['cancer']
        return cls.db
    
    @classmethod
    def get_collection(cls, name):
        db = cls.connect()
        return db[name]

# Usage:
# from utils.mongodb import MongoDB
# patients = MongoDB.get_collection('patients')
# patients.insert_one({'name': 'Test'})