from sqlalchemy.orm import Session
from fastapi import HTTPException, status, UploadFile
from models import User, UserRoleEnum, CompanyRecruiter
from schemas import CandidatoCreate, EmpresaCreate, UserUpdate, CompanyRecruiterCreate
from auth import get_password_hash, verify_password
import os
import uuid
import requests
from typing import List, Optional

class UserService:
    def __init__(self, db: Session):
        self.db = db

    def get_user_by_email(self, email: str) -> Optional[User]:
        return self.db.query(User).filter(User.email == email).first()

    def get_user_by_id(self, user_id: int) -> Optional[User]:
        return self.db.query(User).filter(User.id == user_id).first()

    def get_all_users(self, skip: int = 0, limit: int = 100) -> List[User]:
        return self.db.query(User).offset(skip).limit(limit).all()

    def analyze_cv_with_api(self, cv_file: UploadFile) -> Optional[dict]:
        """
        Analiza el CV usando la CvAnalyzerAPI
        """
        try:
            # CORREGIDO: Leer el contenido completo primero
            cv_file.file.seek(0)  # Asegurar que esté al inicio
            file_content = cv_file.file.read()  # Leer todo el contenido
            cv_file.file.seek(0)  # Resetear para uso posterior
            
            # Preparar el archivo para la API usando el contenido leído
            files = {
                'file': (cv_file.filename, file_content, cv_file.content_type)
            }
            
            # Llamar a CvAnalyzerAPI
            response = requests.post(
                'http://localhost:8001/analyze/',
                files=files,
                timeout=30  # 30 segundos timeout
            )
            
            if response.status_code == 200:
                result = response.json()
                return result.get('data', None)
            else:
                print(f"Error en CvAnalyzerAPI: {response.status_code} - {response.text}")
                return None
                
        except requests.exceptions.RequestException as e:
            print(f"Error conectando con CvAnalyzerAPI: {e}")
            return None
        except Exception as e:
            print(f"Error inesperado analizando CV: {e}")
            return None

    def create_candidato(self, candidato: CandidatoCreate, cv_file: UploadFile, profile_picture: Optional[UploadFile] = None) -> User:
        # Verificar si el usuario ya existe
        db_user = self.get_user_by_email(email=candidato.email)
        if db_user:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="El email ya está registrado"
            )
        
        # NUEVO: Analizar CV con CvAnalyzerAPI
        cv_analysis_result = self.analyze_cv_with_api(cv_file)
        if cv_analysis_result is None:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="El archivo no es un CV válido o no se pudo analizar"
            )
        
        # Guardar el archivo CV
        cv_filename = self.save_cv_file(cv_file)
        
        # Guardar la foto de perfil si se proporciona
        profile_picture_filename = None
        if profile_picture:
            profile_picture_filename = self.save_profile_picture(profile_picture)
        
        # Crear el candidato
        hashed_password = get_password_hash(candidato.password)
        db_user = User(
            email=candidato.email,
            hashed_password=hashed_password,
            role=UserRoleEnum.candidato,
            nombre=candidato.nombre,
            apellido=candidato.apellido,
            genero=candidato.genero,
            fecha_nacimiento=candidato.fecha_nacimiento,
            cv_filename=cv_filename,
            cv_analizado=cv_analysis_result,  # NUEVO: Guardar análisis del CV
            profile_picture=profile_picture_filename,
            descripcion=None,  # NULL para candidatos
            verified=False  # Los candidatos no necesitan verificación
        )
        self.db.add(db_user)
        self.db.commit()
        self.db.refresh(db_user)
        return db_user

    def create_empresa(self, empresa: EmpresaCreate, profile_picture: Optional[UploadFile] = None) -> User:
        # Verificar si el usuario ya existe
        db_user = self.get_user_by_email(email=empresa.email)
        if db_user:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="El email ya está registrado"
            )
        
        # Guardar la foto de perfil si se proporciona
        profile_picture_filename = None
        if profile_picture:
            profile_picture_filename = self.save_profile_picture(profile_picture)
        
        # Crear la empresa (sin verificar)
        hashed_password = get_password_hash(empresa.password)
        db_user = User(
            email=empresa.email,
            hashed_password=hashed_password,
            role=UserRoleEnum.empresa,
            nombre=empresa.nombre,
            descripcion=empresa.descripcion,
            profile_picture=profile_picture_filename,
            verified=False,  # Las empresas requieren verificación
            # Campos NULL para empresas
            apellido=None,
            genero=None,
            fecha_nacimiento=None,
            cv_filename=None,
            cv_analizado=None  # NULL para empresas
        )
        self.db.add(db_user)
        self.db.commit()
        self.db.refresh(db_user)
        return db_user

    def create_admin(self, admin_email: str, admin_password: str, admin_name: str, profile_picture: Optional[UploadFile] = None) -> User:
        # Solo para uso interno/scripts
        db_user = self.get_user_by_email(email=admin_email)
        if db_user:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="El email ya está registrado"
            )
        
        # Guardar la foto de perfil si se proporciona
        profile_picture_filename = None
        if profile_picture:
            profile_picture_filename = self.save_profile_picture(profile_picture)
        
        hashed_password = get_password_hash(admin_password)
        db_user = User(
            email=admin_email,
            hashed_password=hashed_password,
            role=UserRoleEnum.admin,
            nombre=admin_name,
            profile_picture=profile_picture_filename,
            verified=True,  # Admins siempre verificados
            # Campos NULL para admin
            apellido=None,
            genero=None,
            fecha_nacimiento=None,
            cv_filename=None,
            cv_analizado=None,  # NULL para admins
            descripcion=None
        )
        self.db.add(db_user)
        self.db.commit()
        self.db.refresh(db_user)
        return db_user

    def update_user(self, user_id: int, user_update: UserUpdate, cv_file: Optional[UploadFile] = None, profile_picture: Optional[UploadFile] = None) -> User:
        db_user = self.get_user_by_id(user_id)
        if not db_user:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Usuario no encontrado"
            )
        
        update_data = user_update.dict(exclude_unset=True)
        
        # Si se proporciona un nuevo CV, guardarlo y analizarlo (solo para candidatos)
        if cv_file and db_user.role == UserRoleEnum.candidato:
            # NUEVO: Analizar nuevo CV
            cv_analysis_result = self.analyze_cv_with_api(cv_file)
            if cv_analysis_result is None:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail="El archivo no es un CV válido o no se pudo analizar"
                )
            
            # Eliminar el CV anterior si existe
            if db_user.cv_filename:
                old_cv_path = os.path.join("uploaded_cvs", db_user.cv_filename)
                if os.path.exists(old_cv_path):
                    os.remove(old_cv_path)
            
            # Guardar el nuevo CV y análisis
            update_data["cv_filename"] = self.save_cv_file(cv_file)
            update_data["cv_analizado"] = cv_analysis_result  # NUEVO
        
        # Si se proporciona una nueva foto de perfil, guardarla (para todos los roles)
        if profile_picture:
            # Eliminar la foto anterior si existe
            if db_user.profile_picture:
                old_picture_path = os.path.join("profile_pictures", db_user.profile_picture)
                if os.path.exists(old_picture_path):
                    os.remove(old_picture_path)
            
            # Guardar la nueva foto
            update_data["profile_picture"] = self.save_profile_picture(profile_picture)
        
        # Actualizar solo los campos permitidos según el rol del usuario
        for field, value in update_data.items():
            if hasattr(db_user, field):
                # Validar que el campo sea apropiado para el rol de usuario
                if db_user.role == UserRoleEnum.candidato:
                    # Candidatos no pueden actualizar descripcion
                    if field != "descripcion":
                        setattr(db_user, field, value)
                elif db_user.role == UserRoleEnum.empresa:
                    # Empresas no pueden actualizar campos específicos de candidatos
                    if field in ["nombre", "descripcion", "profile_picture"]:
                        setattr(db_user, field, value)
                elif db_user.role == UserRoleEnum.admin:
                    # Admins pueden actualizar nombre y foto
                    if field in ["nombre", "profile_picture"]:
                        setattr(db_user, field, value)
        
        self.db.commit()
        self.db.refresh(db_user)
        return db_user

    def verify_company(self, company_id: int, verified: bool) -> User:
        """Solo para uso de admins"""
        company = self.get_user_by_id(company_id)
        if not company or company.role != UserRoleEnum.empresa:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Empresa no encontrada"
            )
        
        company.verified = verified
        self.db.commit()
        self.db.refresh(company)
        return company

    def get_unverified_companies(self) -> List[User]:
        """Obtener empresas pendientes de verificación"""
        return self.db.query(User).filter(
            User.role == UserRoleEnum.empresa,
            User.verified == False
        ).all()

    def delete_user(self, user_id: int) -> bool:
        db_user = self.get_user_by_id(user_id)
        if not db_user:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Usuario no encontrado"
            )
        
        # Eliminar el archivo CV si existe
        if db_user.cv_filename:
            cv_path = os.path.join("uploaded_cvs", db_user.cv_filename)
            if os.path.exists(cv_path):
                os.remove(cv_path)
        
        # Eliminar la foto de perfil si existe
        if db_user.profile_picture:
            picture_path = os.path.join("profile_pictures", db_user.profile_picture)
            if os.path.exists(picture_path):
                os.remove(picture_path)
        
        self.db.delete(db_user)
        self.db.commit()
        return True

    def authenticate_user(self, email: str, password: str) -> Optional[User]:
        user = self.get_user_by_email(email)
        if not user:
            return None
        if not verify_password(password, user.hashed_password):
            return None
        return user

    def save_cv_file(self, cv_file: UploadFile) -> str:
        # Crear directorio si no existe
        os.makedirs("uploaded_cvs", exist_ok=True)
        
        # Generar nombre único para el archivo
        file_extension = cv_file.filename.split(".")[-1]
        unique_filename = f"{uuid.uuid4()}.{file_extension}"
        file_path = os.path.join("uploaded_cvs", unique_filename)
        
        # Guardar el archivo
        with open(file_path, "wb") as buffer:
            content = cv_file.file.read()
            buffer.write(content)
        
        return unique_filename

    def save_profile_picture(self, picture_file: UploadFile) -> str:
        # Crear directorio si no existe
        os.makedirs("profile_pictures", exist_ok=True)
        
        # Validar que sea una imagen
        allowed_extensions = ["jpg", "jpeg", "png", "gif", "webp"]
        file_extension = picture_file.filename.split(".")[-1].lower()
        
        if file_extension not in allowed_extensions:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Formato de archivo no válido. Permitidos: {', '.join(allowed_extensions)}"
            )
        
        # Generar nombre único para el archivo
        unique_filename = f"{uuid.uuid4()}.{file_extension}"
        file_path = os.path.join("profile_pictures", unique_filename)
        
        # Guardar el archivo
        with open(file_path, "wb") as buffer:
            content = picture_file.file.read()
            buffer.write(content)
        
        return unique_filename

    # Métodos para gestión de recruiters
    def add_recruiter_to_company(self, company_id: int, recruiter_email: str) -> CompanyRecruiter:
        """Agregar recruiter a una empresa (solo empresas verificadas)"""
        # Verificar que la empresa existe y está verificada
        company = self.get_user_by_id(company_id)
        if not company or company.role != UserRoleEnum.empresa:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Empresa no encontrada"
            )
        
        if not company.verified:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Solo empresas verificadas pueden agregar recruiters"
            )
        
        # Buscar el candidato por email
        recruiter = self.get_user_by_email(recruiter_email)
        if not recruiter:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"No se encontró candidato con email: {recruiter_email}"
            )
        
        if recruiter.role != UserRoleEnum.candidato:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Solo candidatos pueden ser recruiters"
            )
        
        # Verificar que no sea ya recruiter de esta empresa
        existing = self.db.query(CompanyRecruiter).filter(
            CompanyRecruiter.company_id == company_id,
            CompanyRecruiter.recruiter_id == recruiter.id,
            CompanyRecruiter.is_active == True
        ).first()
        
        if existing:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"{recruiter_email} ya es recruiter de esta empresa"
            )
        
        # Crear relación company-recruiter
        company_recruiter = CompanyRecruiter(
            company_id=company_id,
            recruiter_id=recruiter.id,
            is_active=True
        )
        
        self.db.add(company_recruiter)
        self.db.commit()
        self.db.refresh(company_recruiter)
        
        return company_recruiter

    def get_company_recruiters(self, company_id: int) -> List[CompanyRecruiter]:
        """Obtener todos los recruiters activos de una empresa"""
        return self.db.query(CompanyRecruiter).filter(
            CompanyRecruiter.company_id == company_id,
            CompanyRecruiter.is_active == True
        ).all()

    def get_recruiter_companies(self, recruiter_id: int) -> List[CompanyRecruiter]:
        """Obtener todas las empresas para las que trabaja un recruiter"""
        return self.db.query(CompanyRecruiter).filter(
            CompanyRecruiter.recruiter_id == recruiter_id,
            CompanyRecruiter.is_active == True
        ).all()

    def remove_recruiter_from_company(self, company_id: int, recruiter_email: str) -> bool:
        """Remover recruiter de una empresa"""
        # Buscar recruiter
        recruiter = self.get_user_by_email(recruiter_email)
        if not recruiter:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"No se encontró recruiter con email: {recruiter_email}"
            )
        
        # Buscar relación activa
        company_recruiter = self.db.query(CompanyRecruiter).filter(
            CompanyRecruiter.company_id == company_id,
            CompanyRecruiter.recruiter_id == recruiter.id,
            CompanyRecruiter.is_active == True
        ).first()
        
        if not company_recruiter:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"{recruiter_email} no es recruiter de esta empresa"
            )
        
        # Desactivar relación (no eliminar para mantener historial)
        company_recruiter.is_active = False
        self.db.commit()
        
        return True

    def is_recruiter_for_company(self, recruiter_id: int, company_id: int) -> bool:
        """Verificar si un usuario es recruiter activo de una empresa específica"""
        relation = self.db.query(CompanyRecruiter).filter(
            CompanyRecruiter.company_id == company_id,
            CompanyRecruiter.recruiter_id == recruiter_id,
            CompanyRecruiter.is_active == True
        ).first()
        
        return relation is not None

    def get_all_candidates(self, skip: int = 0, limit: int = 100) -> List[User]:
        """Obtener todos los usuarios candidatos con sus datos completos"""
        return self.db.query(User).filter(
            User.role == UserRoleEnum.candidato
        ).offset(skip).limit(limit).all()