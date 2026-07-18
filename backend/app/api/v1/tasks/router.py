from fastapi import APIRouter

router = APIRouter()


@router.get("/")
async def get_tasks():
    return {"message": "Tasks list endpoint"}


@router.get("/{id}")
async def get_tasks_by_id(id: str):
    return {"message": "Tasks detail endpoint", "id": id}
