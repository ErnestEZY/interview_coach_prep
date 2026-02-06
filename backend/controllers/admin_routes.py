from fastapi import APIRouter, Depends, HTTPException, Query, Form
from fastapi.responses import Response
import base64
from bson import ObjectId
from ..core.security import get_current_user, DYNAMIC_JWT_SECRET
from ..core.db import resumes, interviews, users, fs
import jwt
from ..core.config import JWT_ALGORITHM

router = APIRouter(prefix="/api/admin", tags=["admin"])

def ensure_admin_role(current):
    if current.get("role") not in ("admin", "super_admin"):
        raise HTTPException(status_code=403, detail="Forbidden")

@router.get("/resumes")
async def list_resumes(
    q: str = Query(None),
    status: str = Query(None),
    tag: str = Query(None),
    current=Depends(get_current_user),
):
    print(f"DEBUG: list_resumes called with q={q}, status={status}, tag={tag}")
    print(f"DEBUG: Current user: {current.get('email')} (Role: {current.get('role')})")
    ensure_admin_role(current)
    filt = {}
    if q:
        filt["filename"] = {"$regex": q, "$options": "i"}
    if status:
        filt["status"] = status
    if tag:
        filt["tags"] = tag
    
    print(f"DEBUG: Database filter: {filt}")
    cur = resumes.find(filt)
    items = []
    async for r in cur:
        print(f"DEBUG: Processing resume {r.get('_id')} - {r.get('filename')}")
        created = r.get("created_at")
        try:
            created_iso = created.isoformat() if created else None
        except Exception:
            created_iso = str(created) if created else None
        
        # Fetch user email via user_id
        user_email = "unknown"
        user_id = r.get("user_id")
        if user_id:
            try:
                # user_id in resume is the _id in users collection
                try:
                    query_id = ObjectId(user_id)
                except:
                    query_id = user_id
                
                user_doc = await users.find_one({"_id": {"$in": [query_id, user_id]}})
                if user_doc:
                    user_email = user_doc.get("email", "unknown")
            except Exception:
                pass

        items.append(
            {
                "id": str(r["_id"]),
                "user_id": str(user_id) if user_id else None,
                "user_email": user_email,
                "filename": r["filename"],
                "status": r.get("status", "pending"),
                "tags": r.get("tags", []),
                "created_at": created_iso,
                "mime_type": r.get("mime_type"),
                "file_available": bool(r.get("file_b64") or r.get("file_id")),
                "notes": r.get("notes", ""),
            }
        )
    print(f"DEBUG: Returning {len(items)} items to frontend")
    return items

@router.get("/resumes/{resume_id}")
async def get_resume(resume_id: str, current=Depends(get_current_user)):
    ensure_admin_role(current)
    r = await resumes.find_one({"_id": ObjectId(resume_id)})
    if not r:
        raise HTTPException(status_code=404, detail="Not found")
    
    # Fetch user email via user_id
    user_email = "unknown"
    user_id = r.get("user_id")
    if user_id:
        try:
            # user_id in resume is the _id in users collection
            try:
                query_id = ObjectId(user_id)
            except:
                query_id = user_id
                
            user_doc = await users.find_one({"_id": {"$in": [query_id, user_id]}})
            if user_doc:
                user_email = user_doc.get("email", "unknown")
        except Exception:
            pass

    return {
        "id": str(r["_id"]),
        "user_id": str(user_id) if user_id else None,
        "user_email": user_email,
        "filename": r["filename"],
        "status": r.get("status", "pending"),
        "text": r.get("text", ""),
        "feedback": r.get("feedback", {}),
        "tags": r.get("tags", []),
        "notes": r.get("notes", ""),
        "mime_type": r.get("mime_type"),
        "file_available": bool(r.get("file_b64") or r.get("file_id")),
        "created_at": (r.get("created_at").isoformat() if r.get("created_at") else None),
    }

@router.patch("/resumes/{resume_id}")
async def update_resume(
    resume_id: str,
    status: str = Form(None),
    notes: str = Form(None),
    tags: str = Form(None),
    current=Depends(get_current_user),
):
    ensure_admin_role(current)
    update = {}
    if status:
        update["status"] = status
    if notes is not None:
        update["notes"] = notes
    if tags is not None:
        try:
            import json
            parsed = json.loads(tags)
            if isinstance(parsed, list):
                update["tags"] = parsed
        except Exception:
            pass
    if not update:
        return {"updated": False}
    await resumes.update_one({"_id": ObjectId(resume_id)}, {"$set": update})
    return {"updated": True}

@router.delete("/resumes/{resume_id}")
async def delete_resume(resume_id: str, current=Depends(get_current_user)):
    ensure_admin_role(current)
    try:
        oid = ObjectId(resume_id)
    except Exception:
        raise HTTPException(status_code=400, detail="Invalid Resume ID format")
    
    r = await resumes.find_one({"_id": oid})
    if not r:
        raise HTTPException(status_code=404, detail="Resume not found in database")
    
    fid = r.get("file_id")
    gridfs_deleted = False
    if fid:
        try:
            # GridFS delete handles both files and chunks
            await fs.delete(ObjectId(fid))
            gridfs_deleted = True
        except Exception as e:
            # Log but don't block resume document deletion
            print(f"Error deleting GridFS file {fid}: {e}")
            
    res = await resumes.delete_one({"_id": oid})
    return {
        "deleted": res.deleted_count > 0,
        "gridfs_deleted": gridfs_deleted,
        "resume_id": resume_id
    }

@router.get("/resumes/{resume_id}/file")
async def get_resume_file(resume_id: str, current=Depends(get_current_user)):
    print(f"DEBUG: get_resume_file called for {resume_id}")
    ensure_admin_role(current)
    try:
        r = await resumes.find_one({"_id": ObjectId(resume_id)})
    except Exception as e:
        print(f"DEBUG: Invalid ObjectId {resume_id}: {e}")
        raise HTTPException(status_code=400, detail="Invalid ID format")
        
    if not r:
        print(f"DEBUG: Resume {resume_id} not found")
        raise HTTPException(status_code=404, detail="Not found")
    
    print(f"DEBUG: Resume found: {r.get('filename')}, file_id: {r.get('file_id')}, mime_type: {r.get('mime_type')}")
    try:
        raw = None
        fid = r.get("file_id")
        if fid:
            try:
                print(f"DEBUG: Attempting to open GridFS stream for {fid}")
                stream = fs.open_download_stream(ObjectId(fid))
                raw = await stream.read()
                print(f"DEBUG: Successfully read {len(raw)} bytes from GridFS")
            except Exception as e:
                print(f"DEBUG: GridFS read error: {e}")
                raise HTTPException(status_code=500, detail=f"File download error: {e}")
        elif r.get("file_b64"):
            try:
                print("DEBUG: Using base64 data")
                raw = base64.b64decode(r.get("file_b64"))
            except Exception as e:
                print(f"DEBUG: Base64 decode error: {e}")
                raise HTTPException(status_code=500, detail="File decode error")
        else:
            print("DEBUG: No file_id or file_b64 found")
            raise HTTPException(status_code=404, detail="No stored file")
    except HTTPException:
        raise
    except Exception as e:
        print(f"DEBUG: Unexpected error: {e}")
        raise HTTPException(status_code=500, detail=str(e))
    
    mtype = r.get("mime_type") or "application/octet-stream"
    headers = {
        "Content-Disposition": f'inline; filename="{r.get("filename", "resume")}"',
        "Content-Length": str(len(raw))
    }
    print(f"DEBUG: Returning Response with mtype={mtype}, headers={headers}")
    return Response(content=raw, media_type=mtype, headers=headers)

@router.get("/resumes/{resume_id}/file_open")
async def get_resume_file_open(resume_id: str, token: str = Query(...)):
    try:
        payload = jwt.decode(token, DYNAMIC_JWT_SECRET, algorithms=[JWT_ALGORITHM])
        user_id = payload.get("sub")
        role = payload.get("role")
        if not user_id or role not in ("admin", "super_admin"):
            raise HTTPException(status_code=403, detail="Forbidden")
        # ensure user exists
        try:
            oid = ObjectId(user_id)
            doc = await users.find_one({"_id": oid})
        except Exception:
            doc = await users.find_one({"_id": user_id})
        if not doc:
            raise HTTPException(status_code=401, detail="Invalid token")
    except jwt.ExpiredSignatureError:
        raise HTTPException(status_code=401, detail="Token expired")
    except Exception:
        raise HTTPException(status_code=401, detail="Invalid token")
    r = await resumes.find_one({"_id": ObjectId(resume_id)})
    if not r:
        print(f"DEBUG: file_open - Resume {resume_id} not found")
        raise HTTPException(status_code=404, detail="Not found")
    try:
        raw = None
        fid = r.get("file_id")
        if fid:
            print(f"DEBUG: file_open - Attempting to open GridFS stream for {fid}")
            stream = fs.open_download_stream(ObjectId(fid))
            raw = await stream.read()
            print(f"DEBUG: file_open - Successfully read {len(raw)} bytes from GridFS")
        elif r.get("file_b64"):
            print("DEBUG: file_open - Using base64 data")
            raw = base64.b64decode(r.get("file_b64"))
        else:
            print("DEBUG: file_open - No file_id or file_b64 found")
            raise HTTPException(status_code=404, detail="No stored file")
    except HTTPException:
        raise
    except Exception as e:
        print(f"DEBUG: file_open - Unexpected error: {e}")
        raise HTTPException(status_code=500, detail=str(e))
    
    mtype = r.get("mime_type") or "application/octet-stream"
    headers = {
        "Content-Disposition": f'inline; filename="{r.get("filename", "resume")}"',
        "Content-Length": str(len(raw))
    }
    print(f"DEBUG: file_open - Returning Response with mtype={mtype}, headers={headers}")
    return Response(content=raw, media_type=mtype, headers=headers)

@router.get("/metrics")
async def metrics(current=Depends(get_current_user)):
    ensure_admin_role(current)
    count = await interviews.count_documents({})
    return {"interview_count": count}
