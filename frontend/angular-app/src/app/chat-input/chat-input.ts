import { Component, ChangeDetectorRef, NgZone, Output, EventEmitter } from '@angular/core';
import { CommonModule } from '@angular/common';
import { FormsModule } from '@angular/forms';
import { HttpClient } from '@angular/common/http';

interface ChatMessage {
  role: 'user' | 'assistant';
  content: string;
}

@Component({
  selector: 'app-chat-input',
  standalone: true,
  imports: [CommonModule, FormsModule],
  templateUrl: './chat-input.html',
  styleUrls: ['./chat-input.css'],
})
export class ChatInputComponent {
  question = '';
  thinking = false;
  uploading = false;
  selectedFile: File | null = null;
  messages: ChatMessage[] = [];
  csvUploaded = false;
  @Output() csvUploadedEvent = new EventEmitter<void>();
  @Output() uploadingEvent = new EventEmitter<boolean>();

  private API_URL = 'http://127.0.0.1:8000';

  constructor(
    private http: HttpClient,
    private zone: NgZone,
    private cdr: ChangeDetectorRef
  ) {}

  // -------------------------
  // FILE UPLOAD
  // -------------------------
  onFileSelected(event: Event) {
    const input = event.target as HTMLInputElement;
    if (!input.files || input.files.length === 0) return;

    this.selectedFile = input.files[0];

    const formData = new FormData();
    formData.append('file', this.selectedFile);

    this.uploading = true;
    this.uploadingEvent.emit(true);
    this.cdr.detectChanges();


    this.http.post(`${this.API_URL}/upload-csv`, formData).subscribe({
      next: () => {
        this.zone.run(() => {
          this.messages.push({
            role: 'assistant',
            content: 'CSV uploaded successfully. Ask your question.',
          });
          this.uploading = false;
          this.uploadingEvent.emit(false);
          this.csvUploaded = true;
          this.cdr.detectChanges();
          this.csvUploadedEvent.emit();

        });
      },
      error: () => {
        this.zone.run(() => {
          this.messages.push({
            role: 'assistant',
            content: 'CSV upload failed.',
          });
          this.uploading = false;
          this.uploadingEvent.emit(false);
          this.csvUploaded = false;
          this.cdr.detectChanges();

        });
      },
    });
  }

  removeFile() {
    this.selectedFile = null;
    this.cdr.detectChanges();
  }

  // -------------------------
  // SEND MESSAGE
  // -------------------------
  send() {
    if (!this.question.trim() || this.thinking || this.uploading) return;


    const q = this.question.trim();
    this.question = '';

    this.messages.push({ role: 'user', content: q });
    this.thinking = true;
    this.cdr.detectChanges();

    this.http
      .post<{ answer: string }>(`${this.API_URL}/ask`, { question: q })
      .subscribe({
        next: (res) => {
          this.zone.run(() => {
            this.messages.push({
              role: 'assistant',
              content: res.answer,
            });
            this.thinking = false;
            this.cdr.detectChanges();
          });
        },
        error: () => {
          this.zone.run(() => {
            this.messages.push({
              role: 'assistant',
              content: 'Error contacting backend.',
            });
            this.thinking = false;
            this.cdr.detectChanges();
          });
        },
      });
  }
}
