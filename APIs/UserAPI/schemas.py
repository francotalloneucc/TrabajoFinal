from pydantic import BaseModel
from datetime import date, datetime
from typing import Optional, List
from models import GenderEnum, UserRoleEnum

# Schemas para User Base
class UserBase(BaseModel):
    email: str
    nombre: str
    role: UserRoleEnum

# Schemas para Candidatos
class CandidatoCreate(UserBase):
    password: str
    apellido: str
    genero: GenderEnum
    fecha_nacimiento: date
    role: UserRoleEnum = UserRoleEnum.candidato

class CandidatoResponse(UserBase):
    id: int
    apellido: str
    genero: GenderEnum
    fecha_nacimiento: date
    cv_filename: str
    verified: bool

    class Config:
        from_attributes = True

# Schemas para Empresas
class EmpresaCreate(UserBase):
    password: str
    descripcion: str
    role: UserRoleEnum = UserRoleEnum.empresa

class EmpresaResponse(UserBase):
    id: int
    descripcion: str
    verified: bool

    class Config:
        from_attributes = True

# Schemas para Admin
class AdminCreate(UserBase):
    password: str
    role: UserRoleEnum = UserRoleEnum.admin

class AdminResponse(UserBase):
    id: int
    verified: bool
    created_at: datetime

    class Config:
        from_attributes = True

# Schema unificado para respuestas
class UserResponse(BaseModel):
    id: int
    email: str
    nombre: str
    role: UserRoleEnum
    verified: bool
    # Campos opcionales según el rol
    apellido: Optional[str] = None
    genero: Optional[GenderEnum] = None
    fecha_nacimiento: Optional[date] = None
    cv_filename: Optional[str] = None
    descripcion: Optional[str] = None
    created_at: Optional[datetime] = None

    class Config:
        from_attributes = True

# Schemas para recruiters
class CompanyRecruiterCreate(BaseModel):
    recruiter_email: str

class CompanyRecruiterResponse(BaseModel):
    id: int
    company_id: int
    recruiter_id: int
    assigned_at: datetime
    is_active: bool
    recruiter: UserResponse

    class Config:
        from_attributes = True

# Schemas para actualización
class UserUpdate(BaseModel):
    nombre: Optional[str] = None
    apellido: Optional[str] = None
    genero: Optional[GenderEnum] = None
    fecha_nacimiento: Optional[date] = None
    descripcion: Optional[str] = None

class CompanyVerification(BaseModel):
    verified: bool
    admin_notes: Optional[str] = None

# Schemas para autenticación
class Token(BaseModel):
    access_token: str
    token_type: str

class TokenData(BaseModel):
    email: Optional[str] = None

class UserLogin(BaseModel):
    email: str
    password: str