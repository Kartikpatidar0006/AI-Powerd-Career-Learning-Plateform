from fastapi import APIRouter

router = APIRouter()


@router.get("/")
async def get_dashboard():
    return {"message": "Dashboard list endpoint"}


@router.get("/{id}")
async def get_dashboard_by_id(id: str):
    return {"message": "Dashboard detail endpoint", "id": id}
