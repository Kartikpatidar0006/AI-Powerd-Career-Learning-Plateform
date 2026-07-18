from fastapi import APIRouter

router = APIRouter()


@router.get("/")
async def get_resume():
    return {"message": "Resume list endpoint"}


@router.get("/{id}")
async def get_resume_by_id(id: str):
    return {"message": "Resume detail endpoint", "id": id}
