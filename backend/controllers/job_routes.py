import httpx
from fastapi import APIRouter, Request, Query, HTTPException
from typing import Optional, Dict, Any
from ..core.config import CAREERJET_API_KEY

router = APIRouter(prefix="/api/jobs", tags=["jobs"])

CAREERJET_HOST = "search.api.careerjet.net"
CAREERJET_PATH = "/v4/query"

@router.get("")
async def search_jobs(
    request: Request,
    keywords: str = Query(..., description="Search keywords for job titles or descriptions"),
    location: Optional[str] = Query(None, description="Location for job search"),
    page: int = Query(1, ge=1),
    contracttype: Optional[str] = None,
    salary: Optional[int] = None
):
    """
    Proxy request to Careerjet API to avoid CORS and hide API keys.
    """
    # Careerjet requires User-IP and User-Agent for tracking
    user_ip = request.client.host
    user_agent = request.headers.get("user-agent", "Mozilla/5.0")
    
    # Construct referer as required by Careerjet
    # Format: https://your-domain.com/find-jobs/?s=keywords&l=location
    base_url = str(request.base_url).rstrip('/')
    referer = f"{base_url}/static/pages/find-jobs.html?s={keywords}"
    if location:
        referer += f"&l={location}"

    params = {
        'locale_code': 'en_MY', # Default to Malaysia since it's an FYP project, but Careerjet handles global
        'keywords': keywords,
        'location': location or "",
        'page': page,
        'user_ip': user_ip,
        'user_agent': user_agent,
    }

    if contracttype:
        params['contracttype'] = contracttype
    if salary:
        params['salary'] = salary

    try:
        async with httpx.AsyncClient() as client:
            response = await client.get(
                url=f"https://{CAREERJET_HOST}{CAREERJET_PATH}",
                params=params,
                auth=(CAREERJET_API_KEY, ""),
                headers={
                    'Content-Type': 'application/json',
                    'Referer': referer,
                },
                timeout=10.0
            )
            
            if response.status_code != 200:
                print(f"Careerjet Error: {response.status_code} - {response.text}")
                return {"jobs": [], "pages": 0, "total": 0, "error": "Failed to fetch jobs from provider"}

            return response.json()
            
    except Exception as e:
        print(f"Job Search Exception: {str(e)}")
        raise HTTPException(status_code=500, detail="Internal server error during job search")

@router.get("/{job_id}")
async def get_job_details(job_id: str):
    # Careerjet V4 API usually provides URLs directly in the search results.
    # If a specific detail endpoint is needed, it would be implemented here.
    # For now, we'll focus on the search results which contain descriptions and links.
    return {"message": "Job detail endpoint not implemented. Use the link from search results."}
