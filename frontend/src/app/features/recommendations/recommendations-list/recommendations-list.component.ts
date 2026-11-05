import { Component, DestroyRef, OnInit, computed, inject, input, signal } from '@angular/core';
import { takeUntilDestroyed, toObservable, toSignal } from '@angular/core/rxjs-interop';
import { FormControl, ReactiveFormsModule } from '@angular/forms';
import { MatButtonModule } from '@angular/material/button';
import { MatButtonToggleModule } from '@angular/material/button-toggle';
import { MatCardModule } from '@angular/material/card';
import { MatChipsModule } from '@angular/material/chips';
import { MatIconModule } from '@angular/material/icon';
import { MatSnackBar } from '@angular/material/snack-bar';
import { filter, skip } from 'rxjs';

import { ApiError } from '../../../core/services/api-error';
import { PipelineService } from '../../../core/services/pipeline.service';
import { ProfileService } from '../../../core/services/profile.service';
import { SkeletonComponent } from '../../../shared/components/skeleton/skeleton.component';
import {
  CONTENT_TYPE_LABELS,
  ContentRecommendation,
  Priority,
  RecommendationEmptyReason,
} from '../../../shared/models/recommendation.model';

type PriorityFilter = 'all' | Priority;

const CONTENT_TYPE_ICONS: Record<ContentRecommendation['content_type'], string> = {
  blog_post: 'article',
  landing_page: 'web',
  faq: 'quiz',
};

@Component({
  selector: 'app-recommendations-list',
  imports: [
    ReactiveFormsModule,
    MatButtonModule,
    MatButtonToggleModule,
    MatCardModule,
    MatChipsModule,
    MatIconModule,
    SkeletonComponent,
  ],
  templateUrl: './recommendations-list.component.html',
  styleUrl: './recommendations-list.component.scss',
})
export class RecommendationsListComponent implements OnInit {
  readonly profileUuid = input.required<string>();

  private readonly profileService = inject(ProfileService);
  private readonly pipelineService = inject(PipelineService);
  private readonly snackBar = inject(MatSnackBar);
  private readonly destroyRef = inject(DestroyRef);

  protected readonly contentTypeLabels = CONTENT_TYPE_LABELS;
  protected readonly contentTypeIcons = CONTENT_TYPE_ICONS;
  protected readonly priorityFilter = new FormControl<PriorityFilter>('all', { nonNullable: true });
  private readonly selectedPriority = toSignal(this.priorityFilter.valueChanges, { initialValue: 'all' });

  protected readonly loading = signal(true);
  protected readonly error = signal<string | null>(null);
  protected readonly recommendations = signal<ContentRecommendation[]>([]);
  protected readonly emptyReason = signal<RecommendationEmptyReason | null>(null);
  protected readonly filtered = computed(() => {
    const priority = this.selectedPriority();
    const items = this.recommendations();
    return priority === 'all' ? items : items.filter((item) => item.priority === priority);
  });

  constructor() {
    toObservable(this.pipelineService.lastFinishedRun)
      .pipe(
        skip(1),
        filter((run) => run?.profile_uuid === this.profileUuid()),
        takeUntilDestroyed(),
      )
      .subscribe(() => this.load());
  }

  ngOnInit(): void {
    this.load();
  }

  protected load(): void {
    this.loading.set(true);
    this.error.set(null);
    this.profileService
      .getRecommendations(this.profileUuid())
      .pipe(takeUntilDestroyed(this.destroyRef))
      .subscribe({
        next: (response) => {
          this.recommendations.set(response.items);
          this.emptyReason.set(response.empty_reason);
          this.loading.set(false);
        },
        error: (error: ApiError) => {
          this.error.set(error.message);
          this.loading.set(false);
          this.snackBar.open(error.message, 'Dismiss');
        },
      });
  }

  protected countFor(priority: Priority): number {
    return this.recommendations().filter((item) => item.priority === priority).length;
  }

  protected emptyTitle(): string {
    switch (this.emptyReason()) {
      case 'all_visible':
        return 'No visibility gap';
      case 'generation_failed':
        return 'Recommendations were not generated';
      default:
        return 'No recommendations yet';
    }
  }

  protected emptyMessage(): string {
    switch (this.emptyReason()) {
      case 'all_visible':
        return 'Every scored query already mentions this business, so there is no missing answer to write content for.';
      case 'generation_failed':
        return 'The content step failed. The pipeline summary above shows the error. Run the pipeline again to try once more.';
      default:
        return 'Run the pipeline and the Content Recommendation Agent will suggest blog posts, landing pages and FAQs for the queries where this business is not visible.';
    }
  }
}
