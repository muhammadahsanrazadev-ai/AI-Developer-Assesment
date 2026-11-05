import { DatePipe, DecimalPipe } from '@angular/common';
import { Component, DestroyRef, OnInit, computed, inject, input, signal } from '@angular/core';
import { takeUntilDestroyed } from '@angular/core/rxjs-interop';
import { MatButtonModule } from '@angular/material/button';
import { MatCardModule } from '@angular/material/card';
import { MatChipsModule } from '@angular/material/chips';
import { MatIconModule } from '@angular/material/icon';
import { MatProgressSpinnerModule } from '@angular/material/progress-spinner';
import { MatSnackBar } from '@angular/material/snack-bar';
import { MatTabsModule } from '@angular/material/tabs';
import { Title } from '@angular/platform-browser';
import { RouterLink, RouterLinkActive, RouterOutlet } from '@angular/router';
import { forkJoin } from 'rxjs';

import { routeAnimations, routeAnimationState } from '../../../core/animations/route.animations';
import { ApiError } from '../../../core/services/api-error';
import { PipelineService } from '../../../core/services/pipeline.service';
import { ProfileService } from '../../../core/services/profile.service';
import { SkeletonComponent } from '../../../shared/components/skeleton/skeleton.component';
import { BusinessProfile, PipelineRun } from '../../../shared/models/profile.model';

interface DetailTab {
  path: string;
  label: string;
  icon: string;
}

@Component({
  selector: 'app-profile-detail',
  imports: [
    DatePipe,
    DecimalPipe,
    RouterOutlet,
    RouterLink,
    RouterLinkActive,
    MatButtonModule,
    MatCardModule,
    MatChipsModule,
    MatIconModule,
    MatProgressSpinnerModule,
    MatTabsModule,
    SkeletonComponent,
  ],
  templateUrl: './profile-detail.component.html',
  styleUrl: './profile-detail.component.scss',
  animations: [routeAnimations],
})
export class ProfileDetailComponent implements OnInit {
  readonly profileUuid = input.required<string>();

  private readonly profileService = inject(ProfileService);
  private readonly pipelineService = inject(PipelineService);
  private readonly snackBar = inject(MatSnackBar);
  private readonly destroyRef = inject(DestroyRef);
  private readonly title = inject(Title);

  protected readonly routeAnimationState = routeAnimationState;

  protected readonly tabs: DetailTab[] = [
    { path: 'queries', label: 'Queries', icon: 'table_rows' },
    { path: 'chart', label: 'Chart', icon: 'bar_chart' },
    { path: 'recommendations', label: 'Recommendations', icon: 'lightbulb' },
  ];

  protected readonly loading = signal(true);
  protected readonly error = signal<ApiError | null>(null);
  protected readonly profile = signal<BusinessProfile | null>(null);
  protected readonly latestRun = signal<PipelineRun | null>(null);
  /** Latest run that finished successfully. Tabs and summary counts use this run. */
  protected readonly completedRun = signal<PipelineRun | null>(null);
  /** True between pressing "Run Pipeline" and the POST /run response. */
  protected readonly starting = signal(false);
  /** Set when polling a running run fails, so the user can refresh instead of waiting forever. */
  protected readonly trackingLost = signal(false);

  protected readonly running = computed(
    () => this.starting() || (this.latestRun()?.status === 'running' && !this.trackingLost()),
  );
  /** Counts shown beside the profile. A failed rerun keeps the previous successful counts. */
  protected readonly summaryRun = computed(() => {
    if (this.running() || this.trackingLost()) {
      return null;
    }
    return this.completedRun() ?? (this.latestRun()?.status === 'failed' ? this.latestRun() : null);
  });
  /** A newer failed run, shown as a warning while the summary stays on the last success. */
  protected readonly failedAttempt = computed(() => {
    const latest = this.latestRun();
    const completed = this.completedRun();
    if (latest?.status !== 'failed' || completed === null || latest.run_uuid === completed.run_uuid) {
      return null;
    }
    return latest;
  });
  protected readonly showingPreviousResults = computed(() => {
    const completed = this.completedRun();
    const latest = this.latestRun();
    return completed !== null && latest !== null && completed.run_uuid !== latest.run_uuid;
  });

  ngOnInit(): void {
    // No route title here: the router would reset it on every tab switch.
    this.title.setTitle('Profile · AI Visibility Intelligence');
    this.load();
  }

  protected load(): void {
    this.loading.set(true);
    this.error.set(null);
    this.trackingLost.set(false);
    forkJoin({
      profile: this.profileService.getProfile(this.profileUuid()),
      runs: this.pipelineService.getRuns({ profileUuid: this.profileUuid(), limit: 50 }),
    })
      .pipe(takeUntilDestroyed(this.destroyRef))
      .subscribe({
        next: ({ profile, runs }) => {
          this.profile.set(profile);
          this.title.setTitle(`${profile.name} · AI Visibility Intelligence`);
          this.rememberRuns(runs);
          this.loading.set(false);
          const latest = runs[0] ?? null;
          if (latest?.status === 'running') {
            this.watchRun(latest.run_uuid);
          }
        },
        error: (error: ApiError) => {
          this.error.set(error);
          this.loading.set(false);
          this.snackBar.open(error.message, 'Dismiss');
        },
      });
  }

  protected runPipeline(): void {
    if (this.running()) {
      return;
    }
    this.starting.set(true);
    this.pipelineService
      .startRun(this.profileUuid())
      .pipe(takeUntilDestroyed(this.destroyRef))
      .subscribe({
        next: (run) => {
          this.starting.set(false);
          this.latestRun.set(run);
          this.setProfileStatus('running');
          this.snackBar.open('Pipeline started. Discovering and scoring queries…', 'OK');
          this.watchRun(run.run_uuid);
        },
        error: (error: ApiError) => {
          this.starting.set(false);
          this.snackBar.open(error.message, 'Dismiss');
        },
      });
  }

  private watchRun(runUuid: string): void {
    this.pipelineService
      .pollRun(runUuid)
      .pipe(takeUntilDestroyed(this.destroyRef))
      .subscribe({
        next: (run) => {
          this.latestRun.set(run);
          if (run.status === 'completed') {
            this.completedRun.set(run);
          }
          if (run.status !== 'running') {
            this.setProfileStatus(run.status);
            this.notifyFinished(run);
          }
        },
        error: (error: ApiError) => {
          this.trackingLost.set(true);
          this.snackBar.open(`Could not check the pipeline status: ${error.message}`, 'Dismiss');
        },
      });
  }

  private notifyFinished(run: PipelineRun): void {
    if (run.status === 'failed') {
      this.snackBar.open(`Pipeline failed: ${run.error_message ?? 'unknown error'}`, 'Dismiss', { duration: 8000 });
    } else if (run.error_message) {
      this.snackBar.open(
        `Pipeline complete with warnings: ${run.queries_scored}/${run.queries_discovered} queries scored.`,
        'OK',
        { duration: 6000 },
      );
    } else {
      this.snackBar.open(`Pipeline complete: ${run.queries_scored} queries scored.`, 'OK');
    }
  }

  private rememberRuns(runs: PipelineRun[]): void {
    this.latestRun.set(runs[0] ?? null);
    this.completedRun.set(runs.find((run) => run.status === 'completed') ?? null);
  }

  private setProfileStatus(status: BusinessProfile['status']): void {
    this.profile.update((profile) => (profile ? { ...profile, status } : profile));
  }
}
