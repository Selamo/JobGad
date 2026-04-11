from fastapi import APIRouter

router = APIRouter()

@router.post("/sessions")
async def create_coaching_session():
    return {"message": "Create new coaching session"}

@router.get("/sessions")
async def get_sessions():
    return {"message": "List active/past coaching sessions"}

@router.get("/sessions/{session_id}")
async def get_session(session_id: str):
    return {"message": f"Details for session {session_id}"}

@router.post("/sessions/{session_id}/end")
async def end_session(session_id: str):
    return {"message": f"End session {session_id} and compute scores"}

@router.get("/iri")
async def get_iri_score():
    return {"message": "Get current Interview Readiness Index"}

@router.get("/learning-plan")
async def get_learning_plan():
    return {"message": "Get personalised learning plan"}

@router.get("/progress")
async def get_progress():
    return {"message": "Get progress tracking data/charts"}
