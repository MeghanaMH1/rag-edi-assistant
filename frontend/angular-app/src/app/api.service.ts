import { Injectable } from '@angular/core';
import { HttpClient } from '@angular/common/http';
import { Observable, of, switchMap, tap } from 'rxjs';

@Injectable({
  providedIn: 'root',
})
export class ApiService {

  private BASE_URL = 'http://127.0.0.1:8000';
  private csvUploaded = false;

  constructor(private http: HttpClient) {}

  uploadCsv(file: File): Observable<any> {
    const formData = new FormData();
    formData.append('file', file);
    return this.http.post(`${this.BASE_URL}/upload-csv`, formData);
  }

  askQuestion(question: string): Observable<any> {
    return this.http.post(`${this.BASE_URL}/ask`, { question });
  }

  uploadOnceAndAsk(file: File | null, question: string): Observable<any> {
    if (file && !this.csvUploaded) {
      this.csvUploaded = true;
      return this.uploadCsv(file).pipe(
        switchMap(() => this.askQuestion(question))
      );
    }

    return this.askQuestion(question);
  }
}
