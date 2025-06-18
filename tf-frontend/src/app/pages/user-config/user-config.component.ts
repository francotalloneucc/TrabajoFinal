import { Component } from '@angular/core';
import { CommonModule } from '@angular/common';
import { FormsModule } from '@angular/forms';
import { Router } from '@angular/router';
import { HttpClientModule } from '@angular/common/http';
import { AuthService, CandidatoRequest, EmpresaRequest } from '../../services/auth.service';

@Component({
  selector: 'app-user-config',
  standalone: true,
  imports: [CommonModule, FormsModule, HttpClientModule],
  templateUrl: './user-config.component.html',
  styleUrls: ['./user-config.component.css']
})
export class UserConfigComponent {
  constructor(
    private router: Router,
    private authService: AuthService
  ) {}

  // Selector de tipo de usuario
  userType: 'candidato' | 'empresa' = 'candidato';

  // Datos comunes
  commonData = {
    email: '',
    password: '',
    confirmPassword: '',
    nombre: ''
  };

  // Datos específicos de candidatos
  candidatoData = {
    apellido: '',
    gender: '',
    birthDate: '',
    cv: null as File | null
  };

  // Datos específicos de empresas
  empresaData = {
    descripcion: ''
  };

  // Estados de validación
  birthDateError = false;
  cvError = false;
  loading = false;
  errorMessage = '';

  // NUEVAS propiedades para validación de CV
  cvValid: boolean = false;
  cvAnalyzing: boolean = false;
  cvValidationMessage: string = '';
  structuredCvData: any = null;
  profilePicture: File | null = null;

  // Cambiar tipo de usuario
  onUserTypeChange(type: 'candidato' | 'empresa'): void {
    this.userType = type;
    // Limpiar datos específicos al cambiar
    this.candidatoData = {
      apellido: '',
      gender: '',
      birthDate: '',
      cv: null
    };
    this.empresaData = {
      descripcion: ''
    };
    this.cvError = false;
    this.birthDateError = false;
    // NUEVO: Reset validación CV
    this.resetCvValidation();
  }

  // Validación de email
  isValidEmail(email: string): boolean {
    const emailRegex = /^[^\s@]+@[^\s@]+\.[^\s@]+$/;
    return emailRegex.test(email);
  }

  // Validación de contraseñas coincidentes
  passwordsMatch(): boolean {
    if (!this.commonData.password || !this.commonData.confirmPassword) {
      return true;
    }
    return this.commonData.password === this.commonData.confirmPassword;
  }

  // Validaciones específicas de candidatos
  preventInvalidChars(event: KeyboardEvent): void {
    const allowed = /^[a-zA-ZÁÉÍÓÚÑáéíóúñ\s]$/;
    if (!allowed.test(event.key)) {
      event.preventDefault();
    }
  }

  sanitizeName(field: 'apellido'): void {
    const input = this.candidatoData[field];
    this.candidatoData[field] = input.replace(/[^a-zA-ZÁÉÍÓÚÑáéíóúñ\s]/g, '');
  }

  hasInvalidChars(value: string): boolean {
    return /[^a-zA-ZÁÉÍÓÚÑáéíóúñ\s]/.test(value);
  }

  checkAge(): void {
    if (!this.candidatoData.birthDate) {
      this.birthDateError = false;
      return;
    }

    const birth = new Date(this.candidatoData.birthDate);
    const today = new Date();
    const age = today.getFullYear() - birth.getFullYear();
    const m = today.getMonth() - birth.getMonth();
    this.birthDateError = age < 18 || (age === 18 && m < 0);
  }

  // ACTUALIZADO: Validación de CV con IA
  onFileSelected(event: any): void {
    const file: File = event.target.files[0];
    if (!file) {
      this.cvError = true;
      this.resetCvValidation();
      return;
    }

    if (file.type !== 'application/pdf') {
      alert('Solo se permiten archivos PDF.');
      this.candidatoData.cv = null;
      this.cvError = true;
      event.target.value = '';
      this.resetCvValidation();
      return;
    }

    this.candidatoData.cv = file;
    this.cvError = false;
    this.validateCvWithAI(file);
  }

  // NUEVO: Validar CV con IA
  private validateCvWithAI(file: File): void {
    this.cvAnalyzing = true;
    this.cvValidationMessage = '🤖 Analizando CV con IA...';
    this.cvValid = false;
    
    this.authService.analyzeCv(file).subscribe({
      next: (result) => {
        console.log('✅ CV Analysis Result:', result);
        
        this.cvAnalyzing = false;
        this.cvValid = true;
        this.structuredCvData = result.data;
        this.cvValidationMessage = '✅ CV válido y analizado correctamente';
      },
      error: (error) => {
        console.error('❌ CV Analysis Error:', error);
        
        this.cvAnalyzing = false;
        this.cvValid = false;
        this.structuredCvData = null;
        
        // Mensaje de error más amigable
        if (error.status === 400) {
          this.cvValidationMessage = `❌ ${error.error?.detail || 'El archivo no es un CV válido'}`;
        } else {
          this.cvValidationMessage = '❌ Error al analizar el CV. Intenta nuevamente.';
        }
      }
    });
  }

  // NUEVO: Reset validación de CV
  private resetCvValidation(): void {
    this.cvValid = false;
    this.cvAnalyzing = false;
    this.cvValidationMessage = '';
    this.structuredCvData = null;
  }

  // NUEVO: Método para remover CV seleccionado
  removeCv(): void {
    this.candidatoData.cv = null;
    this.resetCvValidation();
    this.cvError = false;
    
    // Limpiar el input file
    const cvInput = document.getElementById('cv') as HTMLInputElement;
    if (cvInput) cvInput.value = '';
  }

  // NUEVO: Método para foto de perfil (opcional)
  onProfilePictureSelected(event: Event): void {
    const input = event.target as HTMLInputElement;
    const file = input.files?.[0];
    
    if (file && file.type.startsWith('image/')) {
      this.profilePicture = file;
      console.log('📷 Foto de perfil seleccionada:', file.name);
    } else if (file) {
      alert('La foto de perfil debe ser una imagen válida.');
      this.profilePicture = null;
    }
  }

  // ACTUALIZADO: Validar formulario según el tipo
  isFormValid(): boolean {
    const commonValid = this.commonData.email && 
                       this.commonData.password && 
                       this.commonData.confirmPassword &&
                       this.commonData.nombre &&
                       this.isValidEmail(this.commonData.email) &&
                       this.passwordsMatch();

    if (this.userType === 'candidato') {
      return !!(commonValid && 
             this.candidatoData.apellido &&
             this.candidatoData.gender &&
             this.candidatoData.birthDate &&
             this.candidatoData.cv &&
             this.cvValid &&  // NUEVO: CV debe estar validado
             !this.cvAnalyzing &&  // NUEVO: No debe estar analizando
             !this.birthDateError &&
             !this.cvError &&
             !this.hasInvalidChars(this.candidatoData.apellido));
    } else {
      return !!(commonValid && this.empresaData.descripcion);
    }
  }

  onSubmit(): void {
    if (!this.isFormValid()) {
      if (this.userType === 'candidato' && !this.cvValid) {
        alert('Por favor sube un CV válido antes de continuar');
      }
      return;
    }

    this.loading = true;
    this.errorMessage = '';

    if (this.userType === 'candidato') {
      this.registerCandidato();
    } else {
      this.registerEmpresa();
    }
  }

  // ⭐ ACTUALIZADO: Registro de candidato - NAVEGACIÓN CORREGIDA
  private registerCandidato(): void {
    const candidatoData: CandidatoRequest = {
      email: this.commonData.email,
      password: this.commonData.password,
      nombre: this.commonData.nombre,
      apellido: this.candidatoData.apellido,
      genero: this.candidatoData.gender as 'masculino' | 'femenino' | 'otro',
      fecha_nacimiento: this.candidatoData.birthDate
    };

    console.log('🚀 Registrando candidato...');
    console.log('📋 Datos estructurados del CV:', this.structuredCvData);

    this.authService.registerCandidato(candidatoData, this.candidatoData.cv!, this.profilePicture || undefined).subscribe({
      next: (response: any) => {
        console.log('✅ Registro temporal exitoso:', response);
        
        // ⭐ MENSAJE ACTUALIZADO
        alert('¡Registro iniciado exitosamente! Revisa tu email para verificar tu cuenta.');
        
        // ⭐ NAVEGACIÓN ACTUALIZADA - Con queryParams del email
        this.router.navigate(['/verify-account'], {
          queryParams: { email: this.commonData.email }
        });
      },
      error: (error: any) => {
        this.handleError(error);
      },
      complete: () => {
        this.loading = false;
      }
    });
  }

  // Navegar de vuelta al login
  goBackToLogin(): void {
    this.router.navigate(['/login']);
  }

  // ⭐ ACTUALIZADO: Registro de empresa - También navega a verify-account
  private registerEmpresa(): void {
    const empresaData: EmpresaRequest = {
      email: this.commonData.email,
      password: this.commonData.password,
      nombre: this.commonData.nombre,
      descripcion: this.empresaData.descripcion
    };

    this.authService.registerEmpresa(empresaData, this.profilePicture || undefined).subscribe({
      next: (response: any) => {
        console.log('✅ Empresa registrada exitosamente:', response);
        
        // ⭐ MENSAJE ACTUALIZADO para empresas
        alert('¡Empresa registrada exitosamente! Revisa tu email para verificar tu cuenta. También esperarás verificación de Polo52.');
        
        // ⭐ NAVEGACIÓN ACTUALIZADA - También va a verify-account
        this.router.navigate(['/verify-account'], {
          queryParams: { email: this.commonData.email }
        });
      },
      error: (error: any) => {
        this.handleError(error);
      },
      complete: () => {
        this.loading = false;
      }
    });
  }

  private handleError(error: any): void {
    console.error('Error al registrar:', error);
    this.loading = false;
    
    if (error.error && error.error.detail) {
      if (error.error.detail.includes('CV')) {
        this.errorMessage = 'Error: El CV no pudo ser procesado. Intenta con otro archivo.';
        this.resetCvValidation();
      } else {
        this.errorMessage = error.error.detail;
      }
    } else if (error.status === 400) {
      this.errorMessage = 'El email ya está registrado o hay datos inválidos.';
    } else if (error.status === 0) {
      this.errorMessage = 'No se pudo conectar con el servidor. Verifica que la API esté ejecutándose.';
    } else {
      this.errorMessage = 'Error inesperado. Por favor, intenta nuevamente.';
    }
  }
}