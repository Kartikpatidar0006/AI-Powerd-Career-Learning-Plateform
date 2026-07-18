from fastapi import APIRouter

router = APIRouter()


@router.get("/")
async def get_professions():
    return {"message": "Professions list endpoint"}


@router.get("/{id}")
async def get_professions_by_id(id: str):
    return {"message": "Professions detail endpoint", "id": id}
