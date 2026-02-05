import { Component, EventEmitter, Input, OnChanges, Output, SimpleChanges, ChangeDetectorRef } from '@angular/core';
import { CommonModule } from '@angular/common';
import { FormsModule } from '@angular/forms';
import { HttpClient } from '@angular/common/http';
import { HttpClientModule } from '@angular/common/http';
import { finalize } from 'rxjs';

interface POListItem {
  document_id: string;
  partner?: string | null;
  status?: string | null;
  po_date?: string | null;
}

type EventType = 'PO' | 'ACK' | 'ASN' | 'INV' | 'FA';

interface LifecycleEvent {
  event_type: EventType;
  document_id?: string | null;
  related_document_id?: string | null;
  status?: string | null;
  event_date?: string | null;
  partner?: string | null;
}

interface CompletenessFlags {
  has_po: boolean;
  has_ack: boolean;
  has_asn: boolean;
  has_inv: boolean;
  has_fa: boolean;
}

interface LifecycleResponse {
  po_id: string;
  events: LifecycleEvent[];
  completeness: CompletenessFlags;
}

@Component({
  selector: 'app-lifecycle-modal',
  standalone: true,
  imports: [CommonModule, FormsModule, HttpClientModule],
  templateUrl: './lifecycle-modal.html',
  styleUrls: ['./lifecycle-modal.css'],
})
export class LifecycleModalComponent implements OnChanges {
  @Input() open = false;
  @Output() close = new EventEmitter<void>();

  private API_URL = 'http://127.0.0.1:8000';

  loadingPos = false;
  loadingLifecycle = false;
  errorMsg: string | null = null;

  csvLoaded = false;
  pos: POListItem[] = [];
  selectedPoId: string | null = null;
  lifecycle: LifecycleResponse | null = null;

  constructor(private http: HttpClient, private cdr: ChangeDetectorRef) {}

  ngOnChanges(changes: SimpleChanges) {
    if (changes['open'] && this.open) {
      this.lifecycle = null;
      this.selectedPoId = null;
      this.fetchPoList();
    }
  }

  fetchPoList() {
    this.loadingPos = true;
    this.errorMsg = null;
    this.http
      .get<{ csv_loaded: boolean; pos: POListItem[] }>(`${this.API_URL}/lifecycle/po-list`)
      .pipe(finalize(() => { this.loadingPos = false; this.cdr.detectChanges(); }))
      .subscribe({
        next: (res) => {
          this.csvLoaded = !!res.csv_loaded;
          this.pos = res.pos || [];
          this.cdr.detectChanges();
        },
        error: () => {
          this.csvLoaded = false;
          this.pos = [];
          this.errorMsg = 'Failed to load PO list.';
          this.cdr.detectChanges();
        }
      });
  }

  viewLifecycle() {
    if (!this.selectedPoId) return;
    this.loadingLifecycle = true;
    this.errorMsg = null;
    this.lifecycle = null;
    this.http
      .get<LifecycleResponse>(`${this.API_URL}/lifecycle/po/${this.selectedPoId}`)
      .pipe(finalize(() => { this.loadingLifecycle = false; this.cdr.detectChanges(); }))
      .subscribe({
        next: (res) => {
          this.lifecycle = res;
          this.cdr.detectChanges();
        },
        error: (err) => {
          this.errorMsg = (err?.error?.detail as string) || 'Failed to load lifecycle.';
          this.cdr.detectChanges();
        }
      });
  }

  getEvent(type: EventType): LifecycleEvent | null {
    if (!this.lifecycle) return null;
    const e = this.lifecycle.events.find(ev => ev.event_type === type);
    return e || null;
  }

  onPoChange() {
    this.lifecycle = null;
    this.errorMsg = null;
    this.cdr.detectChanges();
  }

  closeModal() {
    this.close.emit();
  }
}
