import { DatePipe, DecimalPipe } from '@angular/common';
import { Component, DestroyRef, OnInit, inject, signal } from '@angular/core';
import { takeUntilDestroyed } from '@angular/core/rxjs-interop';
import { MatButtonModule } from '@angular/material/button';
import { MatCardModule } from '@angular/material/card';
import { MatIconModule } from '@angular/material/icon';
import { MatSnackBar } from '@angular/material/snack-bar';
import { RouterLink } from '@angular/router';
import { forkJoin } from 'rxjs';

import { ApiError } from '../../core/services/api-error';
import { PipelineService } from '../../core/services/pipeline.service';
import { ProfileService } from '../../core/services/profile.service';
import { SkeletonComponent } from '../../shared/components/skeleton/skeleton.component';
import { BusinessProfile, PipelineRun, PlatformStats } from '../../shared/models/profile.model';

const RECENT_RUNS_LIMIT = 10;

@Component({
  selector: 'app-dashboard',
  imports: [
    DatePipe,
    DecimalPipe,
    RouterLink,
    MatButtonModule,
    MatCardModule,
    MatIconModule,
    SkeletonComponent,
  ],
  templateUrl: './dashboard.component.html',
  styleUrl: './dashboard.component.scss',
})
export class DashboardComponent implements OnInit {
  private readonly profileService = inject(ProfileService);
  private readonly pipelineService = inject(PipelineService);
  private readonly snackBar = inject(MatSnackBar);
  private readonly destroyRef = inject(DestroyRef);

  protected readonly loading = signal(true);
  protected readonly error = signal<string | null>(null);
  protected readonly stats = signal<PlatformStats | null>(null);
  protected readonly runs = signal<PipelineRun[]>([]);
  protected readonly profiles = signal<BusinessProfile[]>([]);

  ngOnInit(): void {
    this.load();
  }

  protected load(): void {
    this.loading.set(true);
    this.error.set(null);
    forkJoin({
      stats: this.profileService.getStats(),
      runs: this.pipelineService.getRuns({ limit: RECENT_RUNS_LIMIT }),
      profiles: this.profileService.getProfiles(),
    })
      .pipe(takeUntilDestroyed(this.destroyRef))
      .subscribe({
        next: ({ stats, runs, profiles }) => {
          this.stats.set(stats);
          this.runs.set(runs);
          this.profiles.set(profiles);
          this.loading.set(false);
        },
        error: (error: ApiError) => {
          this.error.set(error.message);
          this.loading.set(false);
          this.snackBar.open(error.message, 'Dismiss');
        },
      });
  }
}
