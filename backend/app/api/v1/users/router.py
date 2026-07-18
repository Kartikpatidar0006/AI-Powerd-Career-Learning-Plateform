from fastapi import APIRouter

router = APIRouter()


@router.get("/")
async def get_users():
    return {"message": "Users list endpoint"}


@router.get("/{id}")
async def get_users_by_id(id: str):
    return {"message": "Users detail endpoint", "id": id}
