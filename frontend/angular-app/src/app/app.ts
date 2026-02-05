import { Component, OnInit } from '@angular/core';
import { ChatInputComponent } from './chat-input/chat-input';
import { HttpClient } from '@angular/common/http';
import { LifecycleModalComponent } from './lifecycle-modal/lifecycle-modal';
import { HttpClientModule } from '@angular/common/http';

@Component({
  selector: 'app-root',
  standalone: true,
  imports: [ChatInputComponent, LifecycleModalComponent, HttpClientModule],
  templateUrl: './app.html',
  styleUrl: './app.css'
})
export class AppComponent implements OnInit {
  lifecycleOpen = false;
  lifecycleEnabled = false;
  isUploading = false;
  private API_URL = 'http://127.0.0.1:8000';

  constructor(private http: HttpClient) {}

  ngOnInit() {
    this.refreshLifecycleEnabled();
  }

  refreshLifecycleEnabled() {
    this.http.get<{ csv_loaded: boolean; pos: any[] }>(`${this.API_URL}/lifecycle/po-list`).subscribe({
      next: (res) => {
        this.lifecycleEnabled = !!res.csv_loaded;
      },
      error: () => {
        this.lifecycleEnabled = false;
      }
    });
  }

  openLifecycle() {
    if (!this.lifecycleEnabled) return;
    this.lifecycleOpen = true;
  }

  closeLifecycle() {
    this.lifecycleOpen = false;
    this.refreshLifecycleEnabled();
  }

  onCsvUploaded() {
    this.refreshLifecycleEnabled();
  }

  onUploading(uploading: boolean) {
    this.isUploading = uploading;
  }
}
