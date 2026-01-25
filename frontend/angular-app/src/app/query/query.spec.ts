import { ComponentFixture, TestBed } from '@angular/core/testing';
import { QueryComponent } from './query';

describe('QueryComponent', () => {
  let component: QueryComponent;
  let fixture: ComponentFixture<QueryComponent>;

  beforeEach(async () => {
    await TestBed.configureTestingModule({
      imports: [QueryComponent]
    }).compileComponents();

    fixture = TestBed.createComponent(QueryComponent);
    component = fixture.componentInstance;
    await fixture.whenStable();
  });

  it('should create', () => {
    expect(component).toBeTruthy();
  });
});
