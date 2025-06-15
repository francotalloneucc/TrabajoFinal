import { Component, ViewChild, OnInit } from '@angular/core';
import { CommonModule } from '@angular/common';
import { FormsModule } from '@angular/forms';
import { Router } from '@angular/router';
import { HttpClientModule } from '@angular/common/http';
import { AuthService, User, CandidatoRequest, EmpresaRequest } from '../../services/auth.service';

@Component({
  selector: 'app-my-user',
  standalone: true,
  imports: [CommonModule, FormsModule, HttpClientModule],
  templateUrl: './my-user.component.html',
  styleUrls: ['./my-user.component.css']
})
export class MyUserComponent implements OnInit {
  user: User | null = null;
  loading = true;
  errorMessage = '';

  profileImageUrl: string | null = null;
  isLookingForJob = true;
  isEditing = false;
  saving = false;

  tempUser = {
    nombre: '',
    apellido: '',
    genero: 'masculino' as 'masculino' | 'femenino' | 'otro',
    fecha_nacimiento: '',
    descripcion: ''
  };
  tempCvFile: File | null = null;
  tempProfilePicture: File | null = null;

  // Datos para recruiters
  recruiters: any[] = [];
  recruitingCompanies: any[] = [];
  showRecruiters = false;
  showRecruitingFor = false;
  loadingRecruiters = false;
  newRecruiterEmail = '';

  // Datos para admin
  pendingCompanies: User[] = [];
  showAdminPanel = false;
  loadingPendingCompanies = false;
  verifyingCompany: string | null = null;

  // NUEVAS propiedades para ver candidatos
  candidates: User[] = [];
  showCandidates = false;
  loadingCandidates = false;

  @ViewChild('photoInput') photoInput: any;
  @ViewChild('cvInput') cvInput: any;

  constructor(
    private authService: AuthService,
    private router: Router
  ) {}

  ngOnInit(): void {
    this.loadUserData();
  }

  loadUserData(): void {
    if (!this.authService.isAuthenticated()) {
      this.router.navigate(['/login']);
      return;
    }

    this.loading = true;
    this.authService.getCurrentUser().subscribe({
      next: (userData) => {
        this.user = userData;
        this.loading = false;
        
        // Cargar imagen de perfil si existe
        if (userData.profile_picture) {
          this.profileImageUrl = `http://localhost:8000/profile_pictures/${userData.profile_picture}`;
        }
        
        // Cargar datos adicionales según el rol
        if (userData.role === 'empresa' && userData.verified) {
          this.loadRecruiters();
        } else if (userData.role === 'candidato') {
          this.loadRecruitingCompanies();
        } else if (userData.role === 'admin') {
          this.loadPendingCompanies();
        }
      },
      error: (error) => {
        console.error('Error al cargar datos del usuario:', error);
        this.loading = false;
        
        if (error.status === 401) {
          this.authService.logout();
          this.router.navigate(['/login']);
        } else {
          this.errorMessage = 'Error al cargar los datos del usuario';
        }
      }
    });
  }

  getGenderDisplay(genero: string | undefined): string {
    if (!genero) return '';
    switch(genero) {
      case 'masculino': return 'Masculino';
      case 'femenino': return 'Femenino';
      case 'otro': return 'Otro';
      default: return genero;
    }
  }

  getDisplayCvName(): string {
    if (!this.user || !this.user.apellido) return 'CV.pdf';
    return `${this.user.nombre}_${this.user.apellido}_CV.pdf`;
  }

  downloadCV(): void {
    if (!this.user || !this.user.cv_filename) {
      alert('No hay CV disponible para descargar');
      return;
    }
    
    const downloadUrl = `http://localhost:8000/uploaded_cvs/${this.user.cv_filename}`;
    console.log('🔗 Intentando descargar CV desde:', downloadUrl);
    
    fetch(downloadUrl, { method: 'HEAD' })
      .then(response => {
        if (response.ok) {
          const link = document.createElement('a');
          link.href = downloadUrl;
          link.download = this.getDisplayCvName();
          link.target = '_blank';
          
          document.body.appendChild(link);
          link.click();
          document.body.removeChild(link);
        } else {
          alert('El archivo CV no se encuentra disponible en el servidor');
          console.error('❌ CV no encontrado:', response.status);
        }
      })
      .catch(error => {
        console.error('❌ Error al acceder al CV:', error);
        alert('Error al acceder al archivo CV');
      });
  }

  triggerFileInput() {
    if (!this.isEditing) return;
    this.photoInput.nativeElement.click();
  }

  onPhotoSelected(event: Event): void {
    if (!this.isEditing) return;
    
    const input = event.target as HTMLInputElement;
    const file = input.files?.[0];
    if (file && file.type.startsWith('image/')) {
      this.tempProfilePicture = file;
      
      const reader = new FileReader();
      reader.onload = () => {
        this.profileImageUrl = reader.result as string;
      };
      reader.readAsDataURL(file);
    } else {
      alert('Por favor seleccioná una imagen válida.');
    }
  }

  triggerCvUpload() {
    this.cvInput.nativeElement.click();
  }

  onCvSelected(event: Event): void {
    const input = event.target as HTMLInputElement;
    const file = input.files?.[0];
    if (file && file.type === 'application/pdf') {
      this.tempCvFile = file;
    } else {
      alert('El archivo debe ser un PDF válido.');
    }
  }

  toggleJobStatus() {
    this.isLookingForJob = !this.isLookingForJob;
  }

  enableEdit() {
    if (!this.user) return;
    
    this.tempUser = {
      nombre: this.user.nombre,
      apellido: this.user.apellido || '',
      genero: this.user.genero || 'masculino',
      fecha_nacimiento: this.user.fecha_nacimiento || '',
      descripcion: this.user.descripcion || ''
    };
    this.tempCvFile = null;
    this.tempProfilePicture = null;
    this.isEditing = true;
  }

  saveChanges() {
    if (!this.user) return;

    this.saving = true;
    this.errorMessage = '';

    if (this.user.role === 'candidato') {
      const updateData: Partial<CandidatoRequest> = {
        nombre: this.tempUser.nombre,
        apellido: this.tempUser.apellido,
        genero: this.tempUser.genero,
        fecha_nacimiento: this.tempUser.fecha_nacimiento
      };

      this.authService.updateCurrentCandidato(
        updateData, 
        this.tempCvFile || undefined,
        this.tempProfilePicture || undefined
      ).subscribe({
        next: (updatedUser) => {
          this.user = updatedUser;
          
          if (updatedUser.profile_picture) {
            this.profileImageUrl = `http://localhost:8000/profile_pictures/${updatedUser.profile_picture}`;
          }
          
          this.isEditing = false;
          this.saving = false;
          this.tempCvFile = null;
          this.tempProfilePicture = null;
          alert('Cambios guardados correctamente.');
        },
        error: (error) => {
          this.handleUpdateError(error);
        }
      });
    } else if (this.user.role === 'empresa') {
      const updateData: Partial<EmpresaRequest> = {
        nombre: this.tempUser.nombre,
        descripcion: this.tempUser.descripcion || ''
      };

      this.authService.updateCurrentEmpresa(
        updateData,
        this.tempProfilePicture || undefined
      ).subscribe({
        next: (updatedUser) => {
          this.user = updatedUser;
          
          if (updatedUser.profile_picture) {
            this.profileImageUrl = `http://localhost:8000/profile_pictures/${updatedUser.profile_picture}`;
          }
          
          this.isEditing = false;
          this.saving = false;
          this.tempProfilePicture = null;
          alert('Cambios guardados correctamente.');
        },
        error: (error) => {
          this.handleUpdateError(error);
        }
      });
    }
  }

  private handleUpdateError(error: any): void {
    console.error('Error al guardar cambios:', error);
    this.saving = false;
    
    if (error.error && error.error.detail) {
      this.errorMessage = error.error.detail;
    } else {
      this.errorMessage = 'Error al guardar los cambios';
    }
  }

  discardChanges() {
    this.isEditing = false;
    this.tempCvFile = null;
    this.tempProfilePicture = null;
    this.errorMessage = '';
    
    if (this.user?.profile_picture) {
      this.profileImageUrl = `http://localhost:8000/profile_pictures/${this.user.profile_picture}`;
    } else {
      this.profileImageUrl = null;
    }
  }

  logout() {
    this.authService.logout();
    this.router.navigate(['/login']);
  }

  // Métodos para recruiters
  loadRecruiters(): void {
    this.loadingRecruiters = true;
    this.authService.getMyRecruiters().subscribe({
      next: (response: any) => {
        this.recruiters = response.recruiters || [];
        this.loadingRecruiters = false;
      },
      error: (error) => {
        console.error('Error al cargar recruiters:', error);
        this.loadingRecruiters = false;
      }
    });
  }

  loadRecruitingCompanies(): void {
    this.authService.getRecruitingCompanies().subscribe({
      next: (response: any) => {
        this.recruitingCompanies = response.companies || [];
      },
      error: (error) => {
        console.error('Error al cargar empresas:', error);
      }
    });
  }

  toggleRecruiters(): void {
    this.showRecruiters = !this.showRecruiters;
    if (this.showRecruiters && this.recruiters.length === 0) {
      this.loadRecruiters();
    }
  }

  toggleRecruitingFor(): void {
    this.showRecruitingFor = !this.showRecruitingFor;
  }

  addRecruiter(): void {
    if (!this.newRecruiterEmail.trim()) {
      alert('Por favor ingresa un email válido');
      return;
    }

    this.authService.addRecruiter(this.newRecruiterEmail).subscribe({
      next: (response: any) => {
        alert(response.message);
        this.newRecruiterEmail = '';
        this.loadRecruiters();
      },
      error: (error) => {
        console.error('Error al agregar recruiter:', error);
        alert(error.error?.detail || 'Error al agregar recruiter');
      }
    });
  }

  removeRecruiter(recruiterEmail: string): void {
    if (confirm(`¿Estás seguro de remover a ${recruiterEmail} como recruiter?`)) {
      this.authService.removeRecruiter(recruiterEmail).subscribe({
        next: (response: any) => {
          alert(response.message);
          this.loadRecruiters();
        },
        error: (error) => {
          console.error('Error al remover recruiter:', error);
          alert(error.error?.detail || 'Error al remover recruiter');
        }
      });
    }
  }

  isRecruiter(): boolean {
    return this.recruitingCompanies && this.recruitingCompanies.length > 0;
  }

  // Métodos para admin
  loadPendingCompanies(): void {
    this.loadingPendingCompanies = true;
    this.authService.getPendingCompanies().subscribe({
      next: (companies) => {
        this.pendingCompanies = companies;
        this.loadingPendingCompanies = false;
      },
      error: (error) => {
        console.error('Error al cargar empresas pendientes:', error);
        this.loadingPendingCompanies = false;
        this.errorMessage = 'Error al cargar empresas pendientes';
      }
    });
  }

  toggleAdminPanel(): void {
    this.showAdminPanel = !this.showAdminPanel;
    if (this.showAdminPanel && this.pendingCompanies.length === 0) {
      this.loadPendingCompanies();
    }
  }

  verifyCompany(companyEmail: string): void {
    if (!confirm(`¿Estás seguro de verificar la empresa ${companyEmail}?`)) {
      return;
    }

    this.verifyingCompany = companyEmail;
    this.authService.verifyCompany(companyEmail).subscribe({
      next: (response: any) => {
        alert(response.message);
        this.verifyingCompany = null;
        this.pendingCompanies = this.pendingCompanies.filter(c => c.email !== companyEmail);
      },
      error: (error) => {
        console.error('Error al verificar empresa:', error);
        this.verifyingCompany = null;
        alert(error.error?.detail || 'Error al verificar la empresa');
      }
    });
  }

  // NUEVOS métodos para candidatos
  loadCandidates(): void {
    this.loadingCandidates = true;
    this.authService.getAllCandidates().subscribe({
      next: (candidates) => {
        this.candidates = candidates;
        this.loadingCandidates = false;
        console.log('📋 Candidatos cargados:', candidates);
      },
      error: (error) => {
        console.error('Error al cargar candidatos:', error);
        this.loadingCandidates = false;
        this.errorMessage = 'Error al cargar candidatos';
      }
    });
  }

  toggleCandidates(): void {
    this.showCandidates = !this.showCandidates;
    if (this.showCandidates && this.candidates.length === 0) {
      this.loadCandidates();
    }
  }

  viewCvAnalysis(candidate: User): void {
    if (candidate.cv_analizado) {
      console.log('🧠 CV Analizado de', candidate.nombre, candidate.apellido, ':', candidate.cv_analizado);
      
      const analysisData = JSON.stringify(candidate.cv_analizado, null, 2);
      alert(`CV Analizado de ${candidate.nombre} ${candidate.apellido}:\n\n${analysisData}`);
    } else {
      alert('Este candidato no tiene CV analizado disponible.');
    }
  }

  downloadCandidateCV(candidate: User): void {
    if (!candidate.cv_filename) {
      alert('Este candidato no tiene CV disponible');
      return;
    }
    
    const downloadUrl = `http://localhost:8000/uploaded_cvs/${candidate.cv_filename}`;
    const link = document.createElement('a');
    link.href = downloadUrl;
    link.download = `${candidate.nombre}_${candidate.apellido}_CV.pdf`;
    link.target = '_blank';
    
    document.body.appendChild(link);
    link.click();
    document.body.removeChild(link);
  }
}