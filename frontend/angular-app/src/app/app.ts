import { Component } from '@angular/core';
import { ChatInputComponent } from './chat-input/chat-input';

@Component({
  selector: 'app-root',
  standalone: true,
  imports: [ChatInputComponent],
  templateUrl: './app.html',
  styleUrl: './app.css'
})
export class AppComponent {}
