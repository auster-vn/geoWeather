from fastapi import APIRouter
from fastapi.responses import RedirectResponse

router = APIRouter()

@router.get("/{z}/{x}/{y}.mvt")
async def get_tile(z: int, x: int, y: int):
    """
    Proxy or redirect vector tile requests to the Martin tile server.
    """
    # Redirecting to localhost port 3000 where Martin is exposed.
    return RedirectResponse(url=f"http://localhost:3000/cities/{z}/{x}/{y}.mvt")
