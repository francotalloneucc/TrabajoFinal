import { Injectable } from '@angular/core';
import { HttpClient } from '@angular/common/http';
import { Observable } from 'rxjs';

export interface User {
  id: number;
  email: string;
  nombre: string;
  role: 'candidato' | 'empresa' | 'admin';
  verified: boolean;
  // Campos opcionales según el rol
  apellido?: string;
  genero?: 'masculino' | 'femenino' | 'otro';
  fecha_nacimiento?: string;
  cv_filename?: string;
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

@Injectable({
  providedIn: 'root'
})
export class AuthService {
  private baseUrl = 'http://localhost:8000/api/v1';

  constructor(private http: HttpClient) {}

  // Registro de candidatos
  registerCandidato(userData: CandidatoRequest, cvFile: File): Observable<User> {
    const formData = new FormData();
    formData.append('email', userData.email);
    formData.append('password', userData.password);
    formData.append('nombre', userData.nombre);
    formData.append('apellido', userData.apellido);
    formData.append('genero', userData.genero);
    formData.append('fecha_nacimiento', userData.fecha_nacimiento);
    formData.append('cv_file', cvFile);

    return this.http.post<User>(`${this.baseUrl}/register-candidato`, formData);
  }

  // Registro de empresas
  registerEmpresa(userData: EmpresaRequest): Observable<User> {
    const formData = new FormData();
    formData.append('email', userData.email);
    formData.append('password', userData.password);
    formData.append('nombre', userData.nombre);
    formData.append('descripcion', userData.descripcion);

    return this.http.post<User>(`${this.baseUrl}/register-empresa`, formData);
  }

  // Mantener método anterior para compatibilidad
  register(userData: RegisterRequest, cvFile: File): Observable<User> {
    return this.registerCandidato(userData, cvFile);
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
  updateCurrentCandidato(userData: Partial<CandidatoRequest>, cvFile?: File): Observable<User> {
    const token = this.getToken();
    
    const formData = new FormData();
    if (userData.nombre) formData.append('nombre', userData.nombre);
    if (userData.apellido) formData.append('apellido', userData.apellido);
    if (userData.genero) formData.append('genero', userData.genero);
    if (userData.fecha_nacimiento) formData.append('fecha_nacimiento', userData.fecha_nacimiento);
    if (cvFile) formData.append('cv_file', cvFile);

    return this.http.put<User>(`${this.baseUrl}/me/candidato`, formData, {
      headers: {
        'Authorization': `Bearer ${token}`
      }
    });
  }

  // Actualizar empresa
  updateCurrentEmpresa(userData: Partial<EmpresaRequest>): Observable<User> {
    const token = this.getToken();
    
    const formData = new FormData();
    if (userData.nombre) formData.append('nombre', userData.nombre);
    if (userData.descripcion) formData.append('descripcion', userData.descripcion);

    return this.http.put<User>(`${this.baseUrl}/me/empresa`, formData, {
      headers: {
        'Authorization': `Bearer ${token}`
      }
    });
  }

  // Mantener método anterior para compatibilidad
  updateCurrentUser(userData: Partial<RegisterRequest>, cvFile?: File): Observable<User> {
    return this.updateCurrentCandidato(userData, cvFile);
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
    const formData = new FormData();
    formData.append('recruiter_email', recruiterEmail);
    
    return this.http.post(`${this.baseUrl}/companies/add-recruiter`, formData, {
      headers: {
        'Authorization': `Bearer ${token}`
      }
    });
  }

  removeRecruiter(recruiterEmail: string): Observable<any> {
    const token = this.getToken();
    const formData = new FormData();
    formData.append('recruiter_email', recruiterEmail);
    
    return this.http.delete(`${this.baseUrl}/companies/remove-recruiter`, {
      headers: {
        'Authorization': `Bearer ${token}`
      },
      body: formData
    });
  }
}