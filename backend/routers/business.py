from fastapi import APIRouter
from services.business_profile import BusinessProfile, load_profile, save_profile

router = APIRouter()


@router.get("/business-profile")
def get_profile():
    return load_profile()


@router.put("/business-profile")
def put_profile(profile: BusinessProfile):
    return save_profile(profile)
