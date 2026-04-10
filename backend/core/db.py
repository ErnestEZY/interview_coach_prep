from motor.motor_asyncio import AsyncIOMotorClient, AsyncIOMotorGridFSBucket
from .config import MONGO_URI, DB_NAME

client = AsyncIOMotorClient(MONGO_URI)
db = client[DB_NAME]

users = db["users"]
pending_users = db["pending_users"]
reset_tokens = db["reset_tokens"]
resumes = db["resumes"]
interviews = db["interviews"]
usage = db["usage"]
audit_logs = db["audit_logs"]
fs = AsyncIOMotorGridFSBucket(db, bucket_name="resume_files")
