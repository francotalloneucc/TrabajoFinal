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

  // Datos para recruiters
  recruiters: any[] = [];
  recruitingCompanies: any[] = [];
  showRecruiters = false;
  showRecruitingFor = false;
  loadingRecruiters = false;
  newRecruiterEmail = '';

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
        
        // Cargar datos adicionales según el rol
        if (userData.role === 'empresa' && userData.verified) {
          this.loadRecruiters();
        } else if (userData.role === 'candidato') {
          this.loadRecruitingCompanies();
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
    if (!this.user || !this.user.cv_filename) return;
    
    const downloadUrl = `http://localhost:8000/uploaded_cvs/${this.user.cv_filename}`;
    const link = document.createElement('a');
    link.href = downloadUrl;
    link.download = this.getDisplayCvName();
    link.target = '_blank';
    
    document.body.appendChild(link);
    link.click();
    document.body.removeChild(link);
  }

  triggerFileInput() {
    this.photoInput.nativeElement.click();
  }

  onPhotoSelected(event: Event): void {
    const input = event.target as HTMLInputElement;
    const file = input.files?.[0];
    if (file && file.type.startsWith('image/')) {
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

      this.authService.updateCurrentCandidato(updateData, this.tempCvFile || undefined).subscribe({
        next: (updatedUser) => {
          this.user = updatedUser;
          this.isEditing = false;
          this.saving = false;
          this.tempCvFile = null;
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

      this.authService.updateCurrentEmpresa(updateData).subscribe({
        next: (updatedUser) => {
          this.user = updatedUser;
          this.isEditing = false;
          this.saving = false;
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
    this.errorMessage = '';
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
        this.loadRecruiters(); // Recargar lista
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
          this.loadRecruiters(); // Recargar lista
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
}