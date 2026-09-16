from pydantic import BaseModel, EmailStr, Field
from typing import Optional, List


class EmployeeCreateIn(BaseModel):
    name: str = Field(..., min_length=2, max_length=120)
    email: EmailStr
    password: str = Field(..., min_length=6, description="Temporary password for Firebase Authentication")
    role: str = Field(default="employee")
    status: str = Field(default="active")
    assigned_modules: List[str] = Field(default_factory=list)
    store: Optional[str] = "Main Street Store"


class EmployeeUpdateIn(BaseModel):
    name: Optional[str] = None
    role: Optional[str] = None
    status: Optional[str] = None
    assigned_modules: Optional[List[str]] = None
    store: Optional[str] = None


class PermissionsUpdateIn(BaseModel):
    assigned_modules: List[str]


class EmployeeProfileOut(BaseModel):
    uid: str
    id: int
    name: str
    email: str
    role: str
    status: str
    assigned_modules: List[str]
    store: Optional[str] = "Main Street Store"
    created_at: Optional[str] = ""
    last_login: Optional[str] = ""


class StaffListSummary(BaseModel):
    total: int
    active: int
    inactive: int
    max_employees: Optional[int] = None
    capacity_text: Optional[str] = "Unlimited"


class StaffListOut(BaseModel):
    summary: StaffListSummary
    items: List[EmployeeProfileOut]
