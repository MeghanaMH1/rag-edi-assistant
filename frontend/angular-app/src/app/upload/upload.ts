import { Component } from '@angular/core';
import { CommonModule } from '@angular/common';
import { HttpClient } from '@angular/common/http';
import { QueryComponent } from '../query/query';

@Component({
  selector: 'app-upload',
  standalone: true,
  imports: [CommonModule, QueryComponent],
  templateUrl: './upload.html',
  styleUrl: './upload.css'
})
export class UploadComponent {
  selectedFile: File | null = null;
  message: string = '';

  constructor(private http: HttpClient) {}

  onFileSelected(event: any) {
    this.selectedFile = event.target.files[0];
  }

  uploadCsv() {
    if (!this.selectedFile) {
      this.message = 'Please select a CSV file';
      return;
    }

    const formData = new FormData();
    formData.append('file', this.selectedFile);

    this.http
      .post<any>('http://127.0.0.1:8000/upload-csv', formData)
      .subscribe({
        next: (res) => {
          this.message = res.message + ' (Rows: ' + res.rows_loaded + ')';
        },
        error: () => {
          this.message = 'Upload failed';
        }
      });
  }
}
