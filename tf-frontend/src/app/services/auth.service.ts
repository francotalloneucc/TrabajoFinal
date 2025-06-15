import { Injectable } from '@angular/core';
import { HttpClient } from '@angular/common/http';
import { Observable, of } from 'rxjs';
import { map, catchError } from 'rxjs/operators';

export interface User {
  id: number;
  email: string;
  nombre: string;
  role: 'candidato' | 'empresa' | 'admin';
  verified: boolean;
  profile_picture?: string;
  // Campos opcionales según el rol
  apellido?: string;
  genero?: 'masculino' | 'femenino' | 'otro';
  fecha_nacimiento?: string;
  cv_filename?: string;
  cv_analizado?: any; // NUEVO: Datos estructurados del CV
  descripcion?: string;
  created_at?: string;
}

export interface CandidatoRequest {
  email: string;
  password: string;
  nombre: string;
  apellido: string;
  genero: 'masculino' | 'femenino' | 'otro';
  fecha_nacimiento: string;
}

export interface EmpresaRequest {
  email: string;
  password: string;
  nombre: string;
  descripcion: string;
}

// Mantener para compatibilidad con código existente
export interface RegisterRequest {
  email: string;
  password: string;
  nombre: string;
  apellido: string;
  genero: 'masculino' | 'femenino' | 'otro';
  fecha_nacimiento: string;
}

export interface LoginRequest {
  email: string;
  password: string;
}

export interface AuthResponse {
  access_token: string;
  token_type: string;
}

// NUEVO: Interface para respuesta de CvAnalyzer
export interface CvAnalysisResponse {
  valid: boolean;
  message: string;
  data?: any;
}

@Injectable({
  providedIn: 'root'
})
export class AuthService {
  private baseUrl = 'http://localhost:8000/api/v1';
  private cvAnalyzerUrl = 'http://localhost:8001'; // NUEVO: URL de CvAnalyzerAPI

  constructor(private http: HttpClient) {}

  // NUEVO: Analizar CV con IA
  analyzeCv(cvFile: File): Observable<CvAnalysisResponse> {
    const formData = new FormData();
    formData.append('file', cvFile);
    
    return this.http.post<CvAnalysisResponse>(`${this.cvAnalyzerUrl}/analyze/`, formData);
  }

  // NUEVO: Validar solo si el CV es válido (sin obtener datos)
  validateCvOnly(cvFile: File): Observable<boolean> {
    return this.analyzeCv(cvFile).pipe(
      map(result => result.valid === true),
      catchError((error) => {
        console.error('Error validando CV:', error);
        return of(false);
      })
    );
  }

  // Registro de candidatos
  registerCandidato(userData: CandidatoRequest, cvFile: File, profilePicture?: File): Observable<User> {
    const formData = new FormData();
    formData.append('email', userData.email);
    formData.append('password', userData.password);
    formData.append('nombre', userData.nombre);
    formData.append('apellido', userData.apellido);
    formData.append('genero', userData.genero);
    formData.append('fecha_nacimiento', userData.fecha_nacimiento);
    formData.append('cv_file', cvFile);
    if (profilePicture) formData.append('profile_picture', profilePicture);

    return this.http.post<User>(`${this.baseUrl}/register-candidato`, formData);
  }

  // Registro de empresas
  registerEmpresa(userData: EmpresaRequest, profilePicture?: File): Observable<User> {
    const formData = new FormData();
    formData.append('email', userData.email);
    formData.append('password', userData.password);
    formData.append('nombre', userData.nombre);
    formData.append('descripcion', userData.descripcion);
    if (profilePicture) formData.append('profile_picture', profilePicture);

    return this.http.post<User>(`${this.baseUrl}/register-empresa`, formData);
  }

  // Mantener método anterior para compatibilidad
  register(userData: RegisterRequest, cvFile: File, profilePicture?: File): Observable<User> {
    return this.registerCandidato(userData, cvFile, profilePicture);
  }

  login(credentials: LoginRequest): Observable<AuthResponse> {
    return this.http.post<AuthResponse>(`${this.baseUrl}/login`, credentials);
  }

  getCurrentUser(): Observable<User> {
    const token = this.getToken();
    const headers = {
      'Authorization': `Bearer ${token}`
    };
    
    return this.http.get<User>(`${this.baseUrl}/me`, { headers });
  }

  // Actualizar candidato
  updateCurrentCandidato(userData: Partial<CandidatoRequest>, cvFile?: File, profilePicture?: File): Observable<User> {
    const token = this.getToken();
    
    const formData = new FormData();
    if (userData.nombre) formData.append('nombre', userData.nombre);
    if (userData.apellido) formData.append('apellido', userData.apellido);
    if (userData.genero) formData.append('genero', userData.genero);
    if (userData.fecha_nacimiento) formData.append('fecha_nacimiento', userData.fecha_nacimiento);
    if (cvFile) formData.append('cv_file', cvFile);
    if (profilePicture) formData.append('profile_picture', profilePicture);

    return this.http.put<User>(`${this.baseUrl}/me/candidato`, formData, {
      headers: {
        'Authorization': `Bearer ${token}`
      }
    });
  }

  // Actualizar empresa
  updateCurrentEmpresa(userData: Partial<EmpresaRequest>, profilePicture?: File): Observable<User> {
    const token = this.getToken();
    
    const formData = new FormData();
    if (userData.nombre) formData.append('nombre', userData.nombre);
    if (userData.descripcion) formData.append('descripcion', userData.descripcion);
    if (profilePicture) formData.append('profile_picture', profilePicture);

    return this.http.put<User>(`${this.baseUrl}/me/empresa`, formData, {
      headers: {
        'Authorization': `Bearer ${token}`
      }
    });
  }

  // Mantener método anterior para compatibilidad
  updateCurrentUser(userData: Partial<RegisterRequest>, cvFile?: File, profilePicture?: File): Observable<User> {
    return this.updateCurrentCandidato(userData, cvFile, profilePicture);
  }

  saveToken(token: string): void {
    if (typeof window !== 'undefined' && window.localStorage) {
      localStorage.setItem('token', token);
    }
  }

  getToken(): string | null {
    if (typeof window !== 'undefined' && window.localStorage) {
      return localStorage.getItem('token');
    }
    return null;
  }

  isAuthenticated(): boolean {
    const token = this.getToken();
    return token !== null;
  }

  logout(): void {
    if (typeof window !== 'undefined' && window.localStorage) {
      localStorage.removeItem('token');
    }
  }

  // Métodos para recruiters
  getMyRecruiters(): Observable<any> {
    const token = this.getToken();
    return this.http.get(`${this.baseUrl}/companies/my-recruiters`, {
      headers: {
        'Authorization': `Bearer ${token}`
      }
    });
  }

  getRecruitingCompanies(): Observable<any> {
    const token = this.getToken();
    return this.http.get(`${this.baseUrl}/me/recruiting-for`, {
      headers: {
        'Authorization': `Bearer ${token}`
      }
    });
  }

  addRecruiter(recruiterEmail: string): Observable<any> {
    const token = this.getToken();
    
    return this.http.post(
      `${this.baseUrl}/companies/add-recruiter?recruiter_email=${encodeURIComponent(recruiterEmail)}`, 
      {},
      {
        headers: {
          'Authorization': `Bearer ${token}`
        }
      }
    );
  }

  removeRecruiter(recruiterEmail: string): Observable<any> {
    const token = this.getToken();
    
    return this.http.delete(
      `${this.baseUrl}/companies/remove-recruiter?recruiter_email=${encodeURIComponent(recruiterEmail)}`, 
      {
        headers: {
          'Authorization': `Bearer ${token}`
        }
      }
    );
  }

  // Métodos para administradores
  
  // Obtener empresas pendientes de verificación
  getPendingCompanies(): Observable<User[]> {
    const token = this.getToken();
    return this.http.get<User[]>(`${this.baseUrl}/admin/companies/pending`, {
      headers: {
        'Authorization': `Bearer ${token}`
      }
    });
  }

  // Verificar empresa (método simple)
  verifyCompany(companyEmail: string): Observable<any> {
    const token = this.getToken();
    
    return this.http.post(
      `${this.baseUrl}/admin/companies/verify?company_email=${encodeURIComponent(companyEmail)}`,
      {},
      {
        headers: {
          'Authorization': `Bearer ${token}`
        }
      }
    );
  }

    // Agregar este método en tu AuthService
getAllCandidates(skip: number = 0, limit: number = 100): Observable<User[]> {
  const token = this.getToken();
  return this.http.get<User[]>(`${this.baseUrl}/admin/candidates?skip=${skip}&limit=${limit}`, {
    headers: {
      'Authorization': `Bearer ${token}`
    }
  });
}

  // Obtener todos los usuarios (solo admins)
  getAllUsers(skip: number = 0, limit: number = 100): Observable<User[]> {
    const token = this.getToken();
    return this.http.get<User[]>(`${this.baseUrl}/admin/users?skip=${skip}&limit=${limit}`, {
      headers: {
        'Authorization': `Bearer ${token}`
      }
    });
  }
}

