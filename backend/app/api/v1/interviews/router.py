from fastapi import APIRouter

router = APIRouter()


@router.get("/")
async def get_interviews():
    return {"message": "Interviews list endpoint"}


@router.get("/{id}")
async def get_interviews_by_id(id: str):
    return {"message": "Interviews detail endpoint", "id": id}
