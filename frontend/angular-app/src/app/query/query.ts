import { Component } from '@angular/core';
import { HttpClient } from '@angular/common/http';
import { CommonModule } from '@angular/common';
import { FormsModule } from '@angular/forms';

@Component({
  selector: 'app-query',
  standalone: true,
  imports: [CommonModule, FormsModule],
  templateUrl: './query.html',
  styleUrl: './query.css'
})
export class QueryComponent {
  question: string = '';
  answer: string = '';

  constructor(private http: HttpClient) {}

  askQuestion() {
    if (!this.question.trim()) {
      return;
    }

    this.http.post<any>('http://localhost:8000/ask', {
      question: this.question
    }).subscribe({
      next: (res) => {
        this.answer = res.answer;
      },
      error: () => {
        this.answer = 'Error contacting backend';
      }
    });
  }
}
