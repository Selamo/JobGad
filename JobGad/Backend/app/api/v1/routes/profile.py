from fastapi import APIRouter

router = APIRouter()

@router.get("/me")
async def get_profile():
    return {"message": "Get profile endpoint"}

@router.put("/me")
async def update_profile():
    return {"message": "Update profile endpoint"}

@router.post("/upload-document")
async def upload_document():
    return {"message": "Document upload endpoint"}

@router.post("/analyse")
async def analyse_profile():
    return {"message": "Trigger async profile parsing"}

@router.get("/skills")
async def get_skills():
    return {"message": "Get extracted skills"}

@router.get("/cv/download")
async def download_cv():
    return {"message": "Download generated CV"}

@router.get("/gap-analysis")
async def get_gap_analysis():
    return {"message": "Get gap analysis"}

@router.get("/completeness")
async def get_profile_completeness():
    return {"message": "Profile completeness score"}
