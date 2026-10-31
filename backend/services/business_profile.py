"""Business identity for this single-workspace installation."""
import re
from typing import Literal
from pydantic import BaseModel, Field, field_validator
from services.storage import data_dir, write_json


class BusinessProfile(BaseModel):
    legal_name: str = Field(min_length=1, max_length=200)
    trade_name: str = Field(default="", max_length=200)
    gstins: list[str] = Field(default_factory=list, max_length=50)
    address: str = Field(default="", max_length=1000)

    @field_validator("legal_name")
    @classmethod
    def name_required(cls, value):
        if not value.strip():
            raise ValueError("Business name is required")
        return value.strip()

    @field_validator("gstins")
    @classmethod
    def valid_gstins(cls, values):
        from services.validator.gstin_validator import validate_gstin
        result = []
        for value in values:
            value = re.sub(r"\s+", "", value).upper()
            valid, message = validate_gstin(value)
            if not valid:
                raise ValueError(message)
            if value not in result:
                result.append(value)
        return result


def load_profile():
    path = data_dir() / "business_profile.json"
    return BusinessProfile.model_validate_json(path.read_text(encoding="utf-8")).model_dump() if path.exists() else None


def save_profile(profile):
    write_json(data_dir() / "business_profile.json", profile.model_dump())
    return profile.model_dump()


def assess_parties(fields, profile, role: Literal["buyer", "vendor"]):
    """Flag contradictory identity evidence without rewriting model predictions."""
    values = {f["key"]: re.sub(r"\s+", "", str(f.get("value") or "")).upper() for f in fields}
    own = set(profile["gstins"])
    expected = values.get(role + "_gstin", "")
    opposite = "vendor" if role == "buyer" else "buyer"
    other = values.get(opposite + "_gstin", "")
    reasons = []
    if own and other in own:
        reasons.append(f"Your business GSTIN appears as {opposite}, but you selected {role}. Verify vendor and buyer details.")
    if own and expected and expected not in own:
        reasons.append(f"Extracted {role} GSTIN does not match your business profile. Verify party details.")
    if not own or not expected:
        reasons.append("Business identity could not be verified by GSTIN; check vendor and buyer against the source.")
    return {"business_role": role, "matched": bool(own and expected in own and other not in own), "reasons": reasons}
