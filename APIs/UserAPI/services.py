from sqlalchemy.orm import Session
from fastapi import HTTPException, status, UploadFile
from models import User, UserRoleEnum, CompanyRecruiter
from schemas import CandidatoCreate, EmpresaCreate, UserUpdate, CompanyRecruiterCreate
from auth import get_password_hash, verify_password
import os
import uuid
import requests
from typing import List, Optional
# IMPORTS para email verification
import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
import secrets  # ⭐ CORREGIDO: Usar secrets en lugar de random
from datetime import datetime, timedelta
# IMPORTS para almacenamiento temporal
import json
from pathlib import Path

# CLASE - Almacenamiento temporal
class TemporaryStorage:
    """Maneja almacenamiento temporal de registros pendientes de verificación"""
    
    def __init__(self):
        self.temp_dir = Path("temp_registrations")
        self.temp_dir.mkdir(exist_ok=True)
        print(f"📁 DEBUG: Directorio temporal inicializado: {self.temp_dir.absolute()}")
    
    def save_pending_registration(self, email: str, registration_data: dict, verification_code: str) -> str:
        """Guarda datos de registro temporalmente"""
        temp_data = {
            "registration_data": registration_data,
            "verification_code": verification_code,
            "created_at": datetime.utcnow().isoformat(),
            "expires_at": (datetime.utcnow() + timedelta(minutes=15)).isoformat()
        }
        
        # Usar email como nombre de archivo (sanitizado)
        safe_email = email.replace("@", "_at_").replace(".", "_dot_")
        file_path = self.temp_dir / f"{safe_email}.json"
        
        try:
            with open(file_path, 'w', encoding='utf-8') as f:
                json.dump(temp_data, f, indent=2)
            
            print(f"📝 DEBUG: Registro temporal guardado para {email}")
            print(f"📁 DEBUG: Archivo creado en: {file_path.absolute()}")
            print(f"🔑 DEBUG: Código generado: {verification_code}")
            return str(file_path)
        except Exception as e:
            print(f"❌ DEBUG: Error guardando registro temporal: {e}")
            raise
    
    def get_pending_registration(self, email: str) -> dict | None:
        """Obtiene datos de registro temporal"""
        safe_email = email.replace("@", "_at_").replace(".", "_dot_")
        file_path = self.temp_dir / f"{safe_email}.json"
        
        print(f"🔍 DEBUG: Buscando archivo: {file_path.absolute()}")
        print(f"📁 DEBUG: Archivo existe: {file_path.exists()}")
        
        if not file_path.exists():
            print(f"❌ DEBUG: No se encontró archivo temporal para {email}")
            return None
        
        try:
            with open(file_path, 'r', encoding='utf-8') as f:
                temp_data = json.load(f)
            
            print(f"📖 DEBUG: Archivo leído correctamente")
            print(f"🔑 DEBUG: Código en archivo: {temp_data.get('verification_code')}")
            
            # Verificar si no ha expirado
            expires_at = datetime.fromisoformat(temp_data["expires_at"])
            now = datetime.utcnow()
            print(f"⏰ DEBUG: Expira en: {expires_at}")
            print(f"⏰ DEBUG: Hora actual: {now}")
            print(f"⏰ DEBUG: ¿Expirado?: {now > expires_at}")
            
            if now > expires_at:
                print(f"⚠️ DEBUG: Registro expirado para {email}")
                self.remove_pending_registration(email)  # Limpiar expirado
                return None
            
            print(f"✅ DEBUG: Registro temporal válido para {email}")
            return temp_data
        except Exception as e:
            print(f"❌ DEBUG: Error leyendo registro temporal: {e}")
            return None
    
    def remove_pending_registration(self, email: str) -> bool:
        """Elimina registro temporal"""
        safe_email = email.replace("@", "_at_").replace(".", "_dot_")
        file_path = self.temp_dir / f"{safe_email}.json"
        
        if file_path.exists():
            try:
                file_path.unlink()
                print(f"🗑️ DEBUG: Registro temporal eliminado para {email}")
                return True
            except Exception as e:
                print(f"❌ DEBUG: Error eliminando archivo: {e}")
                return False
        return False
    
    def cleanup_expired_registrations(self):
        """Limpia registros temporales expirados"""
        for file_path in self.temp_dir.glob("*.json"):
            try:
                with open(file_path, 'r', encoding='utf-8') as f:
                    temp_data = json.load(f)
                
                expires_at = datetime.fromisoformat(temp_data["expires_at"])
                if datetime.utcnow() > expires_at:
                    file_path.unlink()
                    print(f"🧹 DEBUG: Registro expirado eliminado: {file_path.name}")
            except Exception as e:
                print(f"❌ DEBUG: Error procesando {file_path}: {e}")

class UserService:
    def __init__(self, db: Session):
        self.db = db
        self.temp_storage = TemporaryStorage()

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

    # ⭐ CORREGIDO: Generador de códigos usando secrets
    def generate_verification_code(self) -> str:
        """Genera código de 6 dígitos usando secrets (criptográficamente seguro)"""
        code = secrets.randbelow(900000) + 100000  # Asegura 6 dígitos (100000-999999)
        print(f"🔑 DEBUG: Código generado: {code}")
        return str(code)

    def send_verification_email(self, email: str, code: str):
        """Envía email con código de verificación"""
        try:
            # Obtener configuración de email del .env
            sender_email = os.getenv("EMAIL_USER")
            sender_password = os.getenv("EMAIL_PASSWORD")
            
            print(f"📧 DEBUG: Intentando enviar email a {email}")
            print(f"📧 DEBUG: Sender configurado: {sender_email is not None}")
            
            if not sender_email or not sender_password:
                print("❌ DEBUG: EMAIL_USER y EMAIL_PASSWORD no configurados en .env")
                return
            
            # Configurar mensaje
            message = MIMEMultipart()
            message["From"] = sender_email
            message["To"] = email
            message["Subject"] = "Verificación de Email - Polo52"
            
            # Cuerpo del email
            body = f"""
¡Hola!

Tu código de verificación para Polo52 es: {code}

Este código expira en 15 minutos.

¡Bienvenido a Polo52!

---
Equipo Polo52
            """
            
            message.attach(MIMEText(body, "plain"))
            
            # Enviar email usando Gmail
            server = smtplib.SMTP("smtp.gmail.com", 587)
            server.starttls()
            server.login(sender_email, sender_password)
            text = message.as_string()
            server.sendmail(sender_email, email, text)
            server.quit()
            
            print(f"✅ DEBUG: Email de verificación enviado a {email}")
            
        except Exception as e:
            print(f"❌ DEBUG: Error enviando email: {e}")
            # No lanzar excepción para que el registro no falle por problemas de email

    def verify_email_code(self, email: str, code: str) -> bool:
        """Verifica el código de email usando almacenamiento temporal"""
        print(f"🔍 DEBUG: === INICIANDO VERIFICACIÓN ===")
        print(f"🔍 DEBUG: Email: {email}")
        print(f"🔍 DEBUG: Código recibido: {code}")
        
        # Obtener registro temporal
        temp_data = self.temp_storage.get_pending_registration(email)
        if not temp_data:
            print(f"❌ DEBUG: No se encontró registro temporal para {email}")
            return False
        
        stored_code = temp_data["verification_code"]
        print(f"🔑 DEBUG: Código almacenado: {stored_code}")
        print(f"🔑 DEBUG: ¿Códigos coinciden?: {stored_code == code}")
        
        # Verificar código
        if stored_code != code:
            print(f"❌ DEBUG: Código inválido para {email}")
            return False
        
        print(f"✅ DEBUG: Código verificado correctamente para {email}")
        return True

    def resend_verification_code(self, email: str) -> bool:
        """Reenvía código de verificación"""
        print(f"🔄 DEBUG: Reenviando código para {email}")
        
        # Verificar que hay un registro temporal
        temp_data = self.temp_storage.get_pending_registration(email)
        if not temp_data:
            print(f"❌ DEBUG: No hay registro temporal para reenviar a {email}")
            return False
        
        # Generar nuevo código
        verification_code = self.generate_verification_code()
        
        # Actualizar el registro temporal con nuevo código y tiempo
        registration_data = temp_data["registration_data"]
        self.temp_storage.save_pending_registration(email, registration_data, verification_code)
        
        # Enviar email
        self.send_verification_email(email, verification_code)
        
        print(f"🔄 DEBUG: Código reenviado a {email}")
        return True

    # NUEVO MÉTODO - Registro temporal de candidato
    def create_pending_candidato(self, candidato: CandidatoCreate, cv_file: UploadFile, profile_picture: Optional[UploadFile] = None) -> dict:
        """Crea registro temporal de candidato (NO lo guarda en DB hasta verificar email)"""
        
        print(f"🚀 DEBUG: === INICIANDO REGISTRO CANDIDATO ===")
        print(f"📧 DEBUG: Email: {candidato.email}")
        
        # 1. Verificar si el usuario ya existe en DB
        existing_user = self.get_user_by_email(email=candidato.email)
        if existing_user:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="El email ya está registrado"
            )
        
        # 2. Verificar si ya hay un registro temporal pendiente
        existing_temp = self.temp_storage.get_pending_registration(candidato.email)
        if existing_temp:
            print(f"⚠️ DEBUG: Ya existe registro temporal para {candidato.email}")
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Ya hay un registro pendiente para este email. Verifica tu email o espera a que expire."
            )
        
        # 3. Analizar CV con CvAnalyzerAPI
        print(f"🤖 DEBUG: Analizando CV...")
        cv_analysis_result = self.analyze_cv_with_api(cv_file)
        if cv_analysis_result is None:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="El archivo no es un CV válido o no se pudo analizar"
            )
        print(f"✅ DEBUG: CV analizado correctamente")
        
        # 4. Guardar archivos temporalmente
        cv_filename = self.save_temp_cv_file(cv_file, candidato.email)
        
        profile_picture_filename = None
        if profile_picture:
            profile_picture_filename = self.save_temp_profile_picture(profile_picture, candidato.email)
        
        # 5. Preparar datos para almacenamiento temporal
        registration_data = {
            "user_type": "candidato",
            "email": candidato.email,
            "password": candidato.password,  # Se hasheará al crear el usuario real
            "nombre": candidato.nombre,
            "apellido": candidato.apellido,
            "genero": candidato.genero.value,
            "fecha_nacimiento": candidato.fecha_nacimiento.isoformat(),
            "cv_filename": cv_filename,
            "cv_analysis_result": cv_analysis_result,
            "profile_picture_filename": profile_picture_filename
        }
        
        # 6. Generar código de verificación
        verification_code = self.generate_verification_code()
        
        # 7. Guardar temporalmente
        print(f"💾 DEBUG: Guardando registro temporal...")
        file_path = self.temp_storage.save_pending_registration(
            candidato.email, 
            registration_data, 
            verification_code
        )
        print(f"📁 DEBUG: Archivo guardado en: {file_path}")
        
        # 8. Enviar email de verificación
        print(f"📧 DEBUG: Enviando email de verificación...")
        self.send_verification_email(candidato.email, verification_code)
        
        print(f"✅ DEBUG: Proceso de registro temporal completado para {candidato.email}")
        
        return {
            "message": "Registro iniciado. Verifica tu email para completar el proceso.",
            "email": candidato.email,
            "expires_in_minutes": 15
        }

    # NUEVO MÉTODO - Completar registro después de verificación
    def complete_candidato_registration(self, email: str, verification_code: str) -> User:
        """Completa el registro del candidato después de verificar email"""
        
        print(f"🏁 DEBUG: === COMPLETANDO REGISTRO CANDIDATO ===")
        print(f"📧 DEBUG: Email: {email}")
        print(f"🔑 DEBUG: Código: {verification_code}")
        
        # 1. Verificar código
        if not self.verify_email_code(email, verification_code):
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Código de verificación inválido o expirado"
            )
        
        # 2. Obtener datos temporales
        temp_data = self.temp_storage.get_pending_registration(email)
        if not temp_data:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="No se encontraron datos de registro pendientes"
            )
        
        registration_data = temp_data["registration_data"]
        
        # Verificar que sea un candidato
        if registration_data.get("user_type") != "candidato":
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Los datos de registro no corresponden a un candidato"
            )
        
        print(f"📋 DEBUG: Datos temporales recuperados")
        
        # 3. Mover archivos temporales a ubicaciones permanentes
        permanent_cv, permanent_pic = self.move_temp_files_to_permanent(
            registration_data.get("cv_filename"),
            registration_data.get("profile_picture_filename")
        )
        print(f"📁 DEBUG: Archivos movidos a permanentes")
        
        # 4. Crear usuario en la base de datos
        from datetime import date
        from models import GenderEnum
        
        hashed_password = get_password_hash(registration_data["password"])
        db_user = User(
            email=registration_data["email"],
            hashed_password=hashed_password,
            role=UserRoleEnum.candidato,
            nombre=registration_data["nombre"],
            apellido=registration_data["apellido"],
            genero=GenderEnum(registration_data["genero"]),
            fecha_nacimiento=date.fromisoformat(registration_data["fecha_nacimiento"]),
            cv_filename=permanent_cv,
            cv_analizado=registration_data["cv_analysis_result"],
            profile_picture=permanent_pic,
            descripcion=None,
            verified=False,
            email_verified=True,  # Ya verificado!
            verification_code=None,
            verification_expires=None
        )
        
        self.db.add(db_user)
        self.db.commit()
        self.db.refresh(db_user)
        print(f"✅ DEBUG: Usuario creado en base de datos con ID: {db_user.id}")
        
        # 5. Limpiar registro temporal
        self.temp_storage.remove_pending_registration(email)
        print(f"🧹 DEBUG: Registro temporal limpiado")
        
        print(f"🎉 DEBUG: Registro completado exitosamente para {email}")
        return db_user

    # ⭐ NUEVO MÉTODO - Registro temporal de empresa
    def create_empresa(self, empresa: EmpresaCreate, profile_picture: Optional[UploadFile] = None) -> dict:
        """Crea registro temporal de empresa (NO lo guarda en DB hasta verificar email)"""
        
        print(f"🏢 DEBUG: === INICIANDO REGISTRO EMPRESA ===")
        print(f"📧 DEBUG: Email: {empresa.email}")
        
        # 1. Verificar si el usuario ya existe en DB
        existing_user = self.get_user_by_email(email=empresa.email)
        if existing_user:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="El email ya está registrado"
            )
        
        # 2. Verificar si ya hay un registro temporal pendiente
        existing_temp = self.temp_storage.get_pending_registration(empresa.email)
        if existing_temp:
            print(f"⚠️ DEBUG: Ya existe registro temporal para {empresa.email}")
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Ya hay un registro pendiente para este email. Verifica tu email o espera a que expire."
            )
        
        # 3. Guardar foto de perfil temporalmente
        profile_picture_filename = None
        if profile_picture:
            profile_picture_filename = self.save_temp_profile_picture(profile_picture, empresa.email)
        
        # 4. Preparar datos para almacenamiento temporal
        registration_data = {
            "user_type": "empresa",
            "email": empresa.email,
            "password": empresa.password,  # Se hasheará al crear el usuario real
            "nombre": empresa.nombre,
            "descripcion": empresa.descripcion,
            "profile_picture_filename": profile_picture_filename
        }
        
        # 5. Generar código de verificación
        verification_code = self.generate_verification_code()
        
        # 6. Guardar temporalmente
        print(f"💾 DEBUG: Guardando registro temporal de empresa...")
        file_path = self.temp_storage.save_pending_registration(
            empresa.email, 
            registration_data, 
            verification_code
        )
        print(f"📁 DEBUG: Archivo guardado en: {file_path}")
        
        # 7. Enviar email de verificación
        print(f"📧 DEBUG: Enviando email de verificación...")
        self.send_verification_email(empresa.email, verification_code)
        
        print(f"✅ DEBUG: Proceso de registro temporal de empresa completado para {empresa.email}")
        
        return {
            "message": "Registro de empresa iniciado. Verifica tu email para completar el proceso.",
            "email": empresa.email,
            "expires_in_minutes": 15
        }

    # ⭐ NUEVO MÉTODO - Completar registro de empresa
    def complete_empresa_registration(self, email: str, verification_code: str) -> User:
        """Completa el registro de empresa después de verificar email"""
        
        print(f"🏁 DEBUG: === COMPLETANDO REGISTRO EMPRESA ===")
        print(f"📧 DEBUG: Email: {email}")
        print(f"🔑 DEBUG: Código: {verification_code}")
        
        # 1. Verificar código
        if not self.verify_email_code(email, verification_code):
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Código de verificación inválido o expirado"
            )
        
        # 2. Obtener datos temporales
        temp_data = self.temp_storage.get_pending_registration(email)
        if not temp_data:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="No se encontraron datos de registro pendientes"
            )
        
        registration_data = temp_data["registration_data"]
        
        # Verificar que sea una empresa
        if registration_data.get("user_type") != "empresa":
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Los datos de registro no corresponden a una empresa"
            )
        
        print(f"📋 DEBUG: Datos temporales de empresa recuperados")
        
        # 3. Mover archivo temporal a ubicación permanente
        permanent_pic = None
        if registration_data.get("profile_picture_filename"):
            _, permanent_pic = self.move_temp_files_to_permanent(
                None,  # No CV para empresas
                registration_data.get("profile_picture_filename")
            )
            print(f"📁 DEBUG: Foto de empresa movida a permanente")
        
        # 4. Crear empresa en la base de datos
        hashed_password = get_password_hash(registration_data["password"])
        db_user = User(
            email=registration_data["email"],
            hashed_password=hashed_password,
            role=UserRoleEnum.empresa,
            nombre=registration_data["nombre"],
            descripcion=registration_data["descripcion"],
            profile_picture=permanent_pic,
            verified=False,  # Las empresas requieren verificación admin
            # Campos NULL para empresas
            apellido=None,
            genero=None,
            fecha_nacimiento=None,
            cv_filename=None,
            cv_analizado=None,
            # Email ya verificado
            email_verified=True,
            verification_code=None,
            verification_expires=None
        )
        
        self.db.add(db_user)
        self.db.commit()
        self.db.refresh(db_user)
        print(f"✅ DEBUG: Empresa creada en base de datos con ID: {db_user.id}")
        
        # 5. Limpiar registro temporal
        self.temp_storage.remove_pending_registration(email)
        print(f"🧹 DEBUG: Registro temporal de empresa limpiado")
        
        print(f"🎉 DEBUG: Registro de empresa completado exitosamente para {email}")
        return db_user

    # MÉTODOS para archivos temporales
    def save_temp_cv_file(self, cv_file: UploadFile, email: str) -> str:
        """Guarda CV temporalmente"""
        os.makedirs("temp_files", exist_ok=True)
        
        file_extension = cv_file.filename.split(".")[-1]
        safe_email = email.replace("@", "_at_").replace(".", "_dot_")
        temp_filename = f"temp_cv_{safe_email}_{uuid.uuid4()}.{file_extension}"
        file_path = os.path.join("temp_files", temp_filename)
        
        cv_file.file.seek(0)  # Reset file pointer
        with open(file_path, "wb") as buffer:
            content = cv_file.file.read()
            buffer.write(content)
        
        print(f"📄 DEBUG: CV temporal guardado: {temp_filename}")
        return temp_filename

    def save_temp_profile_picture(self, picture_file: UploadFile, email: str) -> str:
        """Guarda foto de perfil temporalmente"""
        os.makedirs("temp_files", exist_ok=True)
        
        # Validar extensión
        allowed_extensions = ["jpg", "jpeg", "png", "gif", "webp"]
        file_extension = picture_file.filename.split(".")[-1].lower()
        
        if file_extension not in allowed_extensions:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Formato de archivo no válido. Permitidos: {', '.join(allowed_extensions)}"
            )
        
        safe_email = email.replace("@", "_at_").replace(".", "_dot_")
        temp_filename = f"temp_pic_{safe_email}_{uuid.uuid4()}.{file_extension}"
        file_path = os.path.join("temp_files", temp_filename)
        
        picture_file.file.seek(0)  # Reset file pointer
        with open(file_path, "wb") as buffer:
            content = picture_file.file.read()
            buffer.write(content)
        
        print(f"📷 DEBUG: Foto temporal guardada: {temp_filename}")
        return temp_filename

    def move_temp_files_to_permanent(self, temp_cv: str = None, temp_pic: str = None) -> tuple:
        """Mueve archivos temporales a ubicaciones permanentes"""
        permanent_cv = None
        permanent_pic = None
        
        if temp_cv:
            # Mover CV
            temp_path = os.path.join("temp_files", temp_cv)
            if os.path.exists(temp_path):
                file_extension = temp_cv.split(".")[-1]
                permanent_cv = f"{uuid.uuid4()}.{file_extension}"
                permanent_path = os.path.join("uploaded_cvs", permanent_cv)
                os.makedirs("uploaded_cvs", exist_ok=True)
                os.rename(temp_path, permanent_path)
                print(f"📄 DEBUG: CV movido: {temp_cv} → {permanent_cv}")
        
        if temp_pic:
            # Mover foto
            temp_path = os.path.join("temp_files", temp_pic)
            if os.path.exists(temp_path):
                file_extension = temp_pic.split(".")[-1]
                permanent_pic = f"{uuid.uuid4()}.{file_extension}"
                permanent_path = os.path.join("profile_pictures", permanent_pic)
                os.makedirs("profile_pictures", exist_ok=True)
                os.rename(temp_path, permanent_path)
                print(f"📷 DEBUG: Foto movida: {temp_pic} → {permanent_pic}")
        
        return permanent_cv, permanent_pic

    # MANTENER método original para compatibilidad (DESHABILITADO)
    def create_candidato(self, candidato: CandidatoCreate, cv_file: UploadFile, profile_picture: Optional[UploadFile] = None) -> User:
        """DEPRECATED: Usar create_pending_candidato + complete_candidato_registration"""
        # Este método se mantiene solo para compatibilidad
        # En el nuevo flujo no se debe usar
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Este endpoint está deprecado. Usar el nuevo flujo de verificación de email."
        )

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
            cv_analizado=None,
            descripcion=None,
            # Admins no necesitan verificación de email
            email_verified=True,
            verification_code=None,
            verification_expires=None
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

    def get_unverified_companies(self) -> List[User]:
        """Obtener empresas no verificadas"""
        return self.db.query(User).filter(
            User.role == UserRoleEnum.empresa,
            User.verified == False
        ).all()

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