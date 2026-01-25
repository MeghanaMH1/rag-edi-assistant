import { Component } from '@angular/core';
import { FormsModule } from '@angular/forms';
import { ApiService } from '../api.service';

@Component({
  selector: 'app-ask',
  standalone: true,
  imports: [FormsModule],
  templateUrl: './ask.html',
  styleUrls: ['./ask.css']
})
export class AskComponent {
  question = '';
  answer = '';

  constructor(private apiService: ApiService) {}

  askQuestion() {
    if (!this.question.trim()) {
      this.answer = 'Please enter a question';
      return;
    }

    this.apiService.askQuestion(this.question).subscribe({
      next: (res) => {
        this.answer = res.answer;
      },
      error: () => {
        this.answer = '❌ Failed to get answer';
      }
    });
  }
}
