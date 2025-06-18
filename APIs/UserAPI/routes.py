from fastapi import APIRouter, Depends, HTTPException, status, UploadFile, File, Form
from fastapi.security import HTTPBearer
from sqlalchemy.orm import Session
from typing import List, Optional
from datetime import timedelta, date

from database import get_db
from schemas import UserResponse, CandidatoCreate, EmpresaCreate, UserUpdate, Token, UserLogin, CompanyVerification
from services import UserService
from auth import create_access_token, get_current_user, ACCESS_TOKEN_EXPIRE_MINUTES
from models import User, GenderEnum, UserRoleEnum

router = APIRouter()
security = HTTPBearer()

# ⭐ ENDPOINT ACTUALIZADO - Registro temporal de candidatos
@router.post("/register-candidato", response_model=dict)
async def register_candidato(
    email: str = Form(...),
    password: str = Form(...),
    nombre: str = Form(...),
    apellido: str = Form(...),
    genero: GenderEnum = Form(...),
    fecha_nacimiento: date = Form(...),
    cv_file: UploadFile = File(...),
    profile_picture: Optional[UploadFile] = File(None),
    db: Session = Depends(get_db)
):
    """Registra candidato temporalmente - requiere verificación de email"""
    candidato_create = CandidatoCreate(
        email=email,
        password=password,
        nombre=nombre,
        apellido=apellido,
        genero=genero,
        fecha_nacimiento=fecha_nacimiento
    )
    
    user_service = UserService(db)
    # Usar el nuevo método que NO guarda en DB hasta verificar
    result = user_service.create_pending_candidato(candidato_create, cv_file, profile_picture)
    return result

# ⭐ ENDPOINT ACTUALIZADO - Registro temporal de empresas
@router.post("/register-empresa", response_model=dict)
async def register_empresa(
    email: str = Form(...),
    password: str = Form(...),
    nombre: str = Form(...),
    descripcion: str = Form(...),
    profile_picture: Optional[UploadFile] = File(None),
    db: Session = Depends(get_db)
):
    """Registra empresa temporalmente - requiere verificación de email"""
    empresa_create = EmpresaCreate(
        email=email,
        password=password,
        nombre=nombre,
        descripcion=descripcion
    )
    
    user_service = UserService(db)
    # Usar el nuevo método temporal para empresas
    result = user_service.create_empresa(empresa_create, profile_picture)
    return result

# ⭐ ENDPOINT UNIFICADO - Completar cualquier tipo de registro
@router.post("/complete-registration", response_model=UserResponse)
async def complete_registration(
    email: str = Form(...),
    verification_code: str = Form(...),
    db: Session = Depends(get_db)
):
    """Completa el registro después de verificar el email (candidato o empresa)"""
    user_service = UserService(db)
    
    # Obtener datos temporales para determinar el tipo
    temp_data = user_service.temp_storage.get_pending_registration(email)
    if not temp_data:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="No se encontraron datos de registro pendientes para este email"
        )
    
    user_type = temp_data["registration_data"].get("user_type")
    
    if user_type == "candidato":
        user = user_service.complete_candidato_registration(email, verification_code)
    elif user_type == "empresa":
        user = user_service.complete_empresa_registration(email, verification_code)
    else:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Tipo de usuario no válido en los datos temporales"
        )
    
    return user

# ⭐ ENDPOINT ESPECÍFICO - Completar registro de candidato
@router.post("/complete-candidato-registration", response_model=UserResponse)
async def complete_candidato_registration(
    email: str = Form(...),
    verification_code: str = Form(...),
    db: Session = Depends(get_db)
):
    """Completa el registro del candidato después de verificar el email"""
    user_service = UserService(db)
    user = user_service.complete_candidato_registration(email, verification_code)
    return user

# ⭐ ENDPOINT ESPECÍFICO - Completar registro de empresa
@router.post("/complete-empresa-registration", response_model=UserResponse)
async def complete_empresa_registration(
    email: str = Form(...),
    verification_code: str = Form(...),
    db: Session = Depends(get_db)
):
    """Completa el registro de empresa después de verificar el email"""
    user_service = UserService(db)
    user = user_service.complete_empresa_registration(email, verification_code)
    return user

# ⭐ ENDPOINT OBSOLETO - DESHABILITADO
@router.post("/register", response_model=dict)
async def register_user(
    email: str = Form(...),
    password: str = Form(...),
    nombre: str = Form(...),
    apellido: str = Form(...),
    genero: GenderEnum = Form(...),
    fecha_nacimiento: date = Form(...),
    cv_file: UploadFile = File(...),
    profile_picture: Optional[UploadFile] = File(None),
    db: Session = Depends(get_db)
):
    """DESHABILITADO: Usar /register-candidato + /complete-registration"""
    raise HTTPException(
        status_code=status.HTTP_410_GONE,
        detail="Este endpoint está deshabilitado. Usar /register-candidato seguido de /complete-registration"
    )

# ⭐ ENDPOINT ACTUALIZADO - Verificar email (funciona con storage temporal)
@router.post("/verify-email")
async def verify_email(
    email: str = Form(...),
    code: str = Form(...),
    db: Session = Depends(get_db)
):
    """Verifica código de email (solo validación, no completa registro)"""
    user_service = UserService(db)
    success = user_service.verify_email_code(email, code)
    
    if success:
        return {"message": "Código verificado correctamente", "success": True}
    else:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Código inválido o expirado"
        )

# Endpoint para reenviar código de verificación
@router.post("/resend-verification")
async def resend_verification(
    email: str = Form(...),
    db: Session = Depends(get_db)
):
    user_service = UserService(db)
    success = user_service.resend_verification_code(email)
    
    if success:
        return {"message": "Código reenviado exitosamente", "success": True}
    else:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="No se pudo reenviar el código. Verifica que tengas un registro pendiente."
        )

# ⭐ ENDPOINT ACTUALIZADO - Login con validación de email verificado
@router.post("/login", response_model=Token)
async def login_user(user_login: UserLogin, db: Session = Depends(get_db)):
    user_service = UserService(db)
    user = user_service.authenticate_user(user_login.email, user_login.password)
    
    if not user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Email o contraseña incorrectos",
            headers={"WWW-Authenticate": "Bearer"},
        )
    
    # ⭐ NUEVO: Verificar que el email esté verificado
    if not user.email_verified:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Debes verificar tu email antes de iniciar sesión. Revisa tu bandeja de entrada.",
        )
    
    access_token_expires = timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES)
    access_token = create_access_token(
        data={"sub": user.email}, expires_delta=access_token_expires
    )
    return {"access_token": access_token, "token_type": "bearer"}

# Endpoint para obtener el usuario actual
@router.get("/me", response_model=UserResponse)
async def get_current_user_info(current_user: User = Depends(get_current_user)):
    return current_user

# Endpoint para obtener todos los usuarios
@router.get("/users", response_model=List[UserResponse])
async def get_all_users(
    skip: int = 0, 
    limit: int = 100, 
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    user_service = UserService(db)
    return user_service.get_all_users(skip=skip, limit=limit)

# Endpoint para obtener usuario por ID
@router.get("/users/{user_id}", response_model=UserResponse)
async def get_user_by_id(
    user_id: int, 
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    user_service = UserService(db)
    user = user_service.get_user_by_id(user_id)
    if not user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Usuario no encontrado"
        )
    return user

# Endpoint para actualizar usuario
@router.put("/users/{user_id}", response_model=UserResponse)
async def update_user(
    user_id: int,
    email: str = Form(None),
    password: str = Form(None),
    nombre: str = Form(None),
    apellido: str = Form(None),
    genero: GenderEnum = Form(None),
    fecha_nacimiento: date = Form(None),
    cv_file: UploadFile = File(None),
    profile_picture: Optional[UploadFile] = File(None),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    user_update = UserUpdate(
        email=email,
        password=password,
        nombre=nombre,
        apellido=apellido,
        genero=genero,
        fecha_nacimiento=fecha_nacimiento
    )
    
    user_service = UserService(db)
    return user_service.update_user(user_id, user_update, cv_file, profile_picture)

# Endpoint para eliminar usuario
@router.delete("/users/{user_id}")
async def delete_user(
    user_id: int, 
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    user_service = UserService(db)
    user_service.delete_user(user_id)
    return {"message": "Usuario eliminado exitosamente"}

# Endpoint para actualizar candidato actual
@router.put("/me/candidato", response_model=UserResponse)
async def update_current_candidato(
    nombre: str = Form(None),
    apellido: str = Form(None),
    genero: GenderEnum = Form(None),
    fecha_nacimiento: date = Form(None),
    cv_file: UploadFile = File(None),
    profile_picture: Optional[UploadFile] = File(None),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    # Verificar que sea un candidato
    if current_user.role != UserRoleEnum.candidato:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Solo candidatos pueden usar este endpoint"
        )
    
    user_update = UserUpdate()
    if nombre is not None:
        user_update.nombre = nombre
    if apellido is not None:
        user_update.apellido = apellido
    if genero is not None:
        user_update.genero = genero
    if fecha_nacimiento is not None:
        user_update.fecha_nacimiento = fecha_nacimiento
    
    user_service = UserService(db)
    return user_service.update_user(current_user.id, user_update, cv_file, profile_picture)

# Endpoint para actualizar empresa actual
@router.put("/me/empresa", response_model=UserResponse)
async def update_current_empresa(
    nombre: str = Form(None),
    descripcion: str = Form(None),
    profile_picture: Optional[UploadFile] = File(None),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    # Verificar que sea una empresa
    if current_user.role != UserRoleEnum.empresa:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Solo empresas pueden usar este endpoint"
        )
    
    user_update = UserUpdate()
    if nombre is not None:
        user_update.nombre = nombre
    if descripcion is not None:
        user_update.descripcion = descripcion
    
    user_service = UserService(db)
    return user_service.update_user(current_user.id, user_update, None, profile_picture)

# Endpoint genérico (mantener para compatibilidad - decide automáticamente)
@router.put("/me", response_model=UserResponse)
async def update_current_user(
    # Campos comunes
    nombre: str = Form(None),
    
    # Campos específicos de candidatos
    apellido: str = Form(None),
    genero: GenderEnum = Form(None),
    fecha_nacimiento: date = Form(None),
    cv_file: UploadFile = File(None),
    
    # Campos específicos de empresas
    descripcion: str = Form(None),
    
    # Campo común para todos
    profile_picture: Optional[UploadFile] = File(None),
    
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    # Crear user_update dinámicamente según el rol del usuario
    user_update = UserUpdate()
    
    # Campo común para todos los roles
    if nombre is not None:
        user_update.nombre = nombre
    
    # Solo procesar campos específicos según el rol del usuario actual
    if current_user.role == UserRoleEnum.candidato:
        # Solo candidatos pueden actualizar estos campos
        if apellido is not None:
            user_update.apellido = apellido
        if genero is not None:
            user_update.genero = genero
        if fecha_nacimiento is not None:
            user_update.fecha_nacimiento = fecha_nacimiento
    
    elif current_user.role == UserRoleEnum.empresa:
        # Solo empresas pueden actualizar descripción
        if descripcion is not None:
            user_update.descripcion = descripcion
    
    user_service = UserService(db)
    return user_service.update_user(current_user.id, user_update, cv_file, profile_picture)

# Función para verificar si es admin
def require_admin(current_user: User = Depends(get_current_user)):
    if current_user.role != UserRoleEnum.admin:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Acceso denegado: Se requieren permisos de administrador"
        )
    return current_user

# Endpoints para administradores
@router.get("/admin/companies/pending", response_model=List[UserResponse])
async def get_pending_companies(
    db: Session = Depends(get_db),
    admin_user: User = Depends(require_admin)
):
    """Ver empresas pendientes de verificación"""
    user_service = UserService(db)
    return user_service.get_unverified_companies()

# Endpoint simple para verificar empresa (solo email)
@router.post("/admin/companies/verify")
async def verify_company_simple(
    company_email: str,
    db: Session = Depends(get_db),
    admin_user: User = Depends(require_admin)
):
    """Verificar empresa por email (endpoint simple)"""
    user_service = UserService(db)
    
    # Buscar empresa por email
    company = user_service.get_user_by_email(company_email)
    
    if not company:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"No se encontró empresa con email: {company_email}"
        )
    
    if company.role != UserRoleEnum.empresa:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"El usuario {company_email} no es una empresa"
        )
    
    if company.verified:
        return {"message": f"La empresa {company_email} ya está verificada"}
    
    # Verificar empresa
    verified_company = user_service.verify_company(company.id, True)
    
    return {
        "message": f"Empresa {company_email} verificada exitosamente",
        "company": {
            "id": verified_company.id,
            "nombre": verified_company.nombre,
            "email": verified_company.email,
            "verified": verified_company.verified
        }
    }

@router.put("/admin/companies/verify-by-email", response_model=UserResponse)
async def verify_company_by_email(
    company_email: str,
    verification: CompanyVerification,
    db: Session = Depends(get_db),
    admin_user: User = Depends(require_admin)
):
    """Verificar empresa por email"""
    user_service = UserService(db)
    
    # Buscar empresa por email
    company = user_service.get_user_by_email(company_email)
    
    if not company:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"No se encontró empresa con email: {company_email}"
        )
    
    if company.role != UserRoleEnum.empresa:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"El usuario {company_email} no es una empresa"
        )
    
    return user_service.verify_company(company.id, verification.verified)

@router.get("/admin/users", response_model=List[UserResponse])
async def get_all_users_admin(
    skip: int = 0,
    limit: int = 100,
    db: Session = Depends(get_db),
    admin_user: User = Depends(require_admin)
):
    """Ver todos los usuarios (solo admins)"""
    user_service = UserService(db)
    return user_service.get_all_users(skip=skip, limit=limit)

# Función para verificar si es empresa verificada
def require_verified_company(current_user: User = Depends(get_current_user)):
    if current_user.role != UserRoleEnum.empresa:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Solo empresas pueden realizar esta acción"
        )
    if not current_user.verified:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Solo empresas verificadas pueden agregar recruiters"
        )
    return current_user

# Endpoints para gestión de recruiters
@router.post("/companies/add-recruiter")
async def add_recruiter_to_company(
    recruiter_email: str,
    db: Session = Depends(get_db),
    company: User = Depends(require_verified_company)
):
    """Agregar recruiter a mi empresa"""
    user_service = UserService(db)
    
    try:
        company_recruiter = user_service.add_recruiter_to_company(
            company.id, 
            recruiter_email
        )
        
        return {
            "message": f"Recruiter {recruiter_email} agregado exitosamente",
            "recruiter_id": company_recruiter.recruiter_id,
            "assigned_at": company_recruiter.assigned_at
        }
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error al agregar recruiter: {str(e)}"
        )

@router.get("/companies/my-recruiters")
async def get_my_recruiters(
    db: Session = Depends(get_db),
    company: User = Depends(require_verified_company)
):
    """Ver todos mis recruiters"""
    user_service = UserService(db)
    recruiters = user_service.get_company_recruiters(company.id)
    
    recruiter_list = []
    for rel in recruiters:
        recruiter_user = user_service.get_user_by_id(rel.recruiter_id)
        if recruiter_user:
            recruiter_list.append({
                "id": recruiter_user.id,
                "email": recruiter_user.email,
                "nombre": recruiter_user.nombre,
                "apellido": recruiter_user.apellido,
                "assigned_at": rel.assigned_at,
                "is_active": rel.is_active
            })
    
    return {
        "company": company.nombre,
        "recruiters": recruiter_list,
        "total": len(recruiter_list)
    }

@router.delete("/companies/remove-recruiter")
async def remove_recruiter_from_company(
    recruiter_email: str,
    db: Session = Depends(get_db),
    company: User = Depends(require_verified_company)
):
    """Remover recruiter de mi empresa"""
    user_service = UserService(db)
    
    success = user_service.remove_recruiter_from_company(
        company.id, 
        recruiter_email
    )
    
    if success:
        return {
            "message": f"Recruiter {recruiter_email} removido exitosamente"
        }
    else:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="No se pudo remover el recruiter"
        )

@router.get("/me/recruiting-for")
async def get_recruiting_companies(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Ver para qué empresas soy recruiter"""
    if current_user.role != UserRoleEnum.candidato:
        return {
            "message": "Solo candidatos pueden ser recruiters",
            "companies": []
        }
    
    user_service = UserService(db)
    companies = user_service.get_recruiter_companies(current_user.id)
    
    company_list = []
    for rel in companies:
        company_user = user_service.get_user_by_id(rel.company_id)
        if company_user:
            company_list.append({
                "id": company_user.id,
                "nombre": company_user.nombre,
                "email": company_user.email,
                "descripcion": company_user.descripcion,
                "assigned_at": rel.assigned_at,
                "verified": company_user.verified
            })
    
    return {
        "recruiter": f"{current_user.nombre} {current_user.apellido}",
        "companies": company_list,
        "total": len(company_list)
    }

@router.get("/admin/candidates", response_model=List[UserResponse])
async def get_all_candidates(
    skip: int = 0,
    limit: int = 100,
    db: Session = Depends(get_db),
    admin_user: User = Depends(require_admin)
):
    """Ver todos los candidatos con sus datos y CV analizados (solo admins)"""
    user_service = UserService(db)
    candidates = user_service.get_all_candidates(skip=skip, limit=limit)
    return candidates