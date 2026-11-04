import { DecimalPipe } from '@angular/common';
import { Component, DestroyRef, OnInit, inject, input, signal } from '@angular/core';
import { takeUntilDestroyed, toObservable } from '@angular/core/rxjs-interop';
import { FormControl, FormGroup, ReactiveFormsModule } from '@angular/forms';
import { MatButtonModule } from '@angular/material/button';
import { MatCardModule } from '@angular/material/card';
import { MatFormFieldModule } from '@angular/material/form-field';
import { MatIconModule } from '@angular/material/icon';
import { MatPaginatorModule, PageEvent } from '@angular/material/paginator';
import { MatProgressBarModule } from '@angular/material/progress-bar';
import { MatProgressSpinnerModule } from '@angular/material/progress-spinner';
import { MatSelectModule } from '@angular/material/select';
import { MatSliderModule } from '@angular/material/slider';
import { MatSnackBar } from '@angular/material/snack-bar';
import { MatTableModule } from '@angular/material/table';
import { MatTooltipModule } from '@angular/material/tooltip';
import { Subject, catchError, debounceTime, filter, of, skip, switchMap, tap } from 'rxjs';

import { ApiError } from '../../../core/services/api-error';
import { CSV_EXPORT_PAGE_SIZE, CsvExportService } from '../../../core/services/csv-export.service';
import { PipelineService } from '../../../core/services/pipeline.service';
import { QueryService } from '../../../core/services/query.service';
import { ScoreChipComponent } from '../../../shared/components/score-chip/score-chip.component';
import { SkeletonComponent } from '../../../shared/components/skeleton/skeleton.component';
import { DiscoveredQuery, QueryPage, VisibilityStatus, visibilityStatus } from '../../../shared/models/query.model';

const DEFAULT_PAGE_SIZE = 10;

@Component({
  selector: 'app-queries-table',
  imports: [
    DecimalPipe,
    ReactiveFormsModule,
    MatButtonModule,
    MatCardModule,
    MatFormFieldModule,
    MatIconModule,
    MatPaginatorModule,
    MatProgressBarModule,
    MatProgressSpinnerModule,
    MatSelectModule,
    MatSliderModule,
    MatTableModule,
    MatTooltipModule,
    ScoreChipComponent,
    SkeletonComponent,
  ],
  templateUrl: './queries-table.component.html',
  styleUrl: './queries-table.component.scss',
})
export class QueriesTableComponent implements OnInit {
  readonly profileUuid = input.required<string>();

  private readonly queryService = inject(QueryService);
  private readonly csvExport = inject(CsvExportService);
  private readonly pipelineService = inject(PipelineService);
  private readonly snackBar = inject(MatSnackBar);
  private readonly destroyRef = inject(DestroyRef);
  private readonly reload$ = new Subject<void>();

  protected readonly displayedColumns = ['query_text', 'volume', 'difficulty', 'score', 'visibility', 'action'];
  protected readonly pageSizeOptions = [10, 20, 50];
  protected readonly visibilityStatus = visibilityStatus;

  protected readonly filters = new FormGroup({
    minScore: new FormControl(0, { nonNullable: true }),
    status: new FormControl<VisibilityStatus | null>(null),
  });

  protected readonly loading = signal(true);
  protected readonly error = signal<string | null>(null);
  protected readonly page = signal<QueryPage | null>(null);
  protected readonly pageIndex = signal(0);
  protected readonly pageSize = signal(DEFAULT_PAGE_SIZE);
  protected readonly recheckingUuids = signal<ReadonlySet<string>>(new Set());
  protected readonly exporting = signal(false);

  constructor() {
    this.reload$
      .pipe(
        tap(() => {
          this.loading.set(true);
          this.error.set(null);
        }),
        switchMap(() =>
          this.queryService
            .getQueries(this.profileUuid(), {
              min_score: this.filters.controls.minScore.value,
              status: this.filters.controls.status.value,
              page: this.pageIndex() + 1,
              per_page: this.pageSize(),
            })
            .pipe(
              catchError((error: ApiError) => {
                this.error.set(error.message);
                this.snackBar.open(error.message, 'Dismiss');
                return of(null);
              }),
            ),
        ),
        takeUntilDestroyed(),
      )
      .subscribe((page) => {
        if (page) {
          this.page.set(page);
        }
        this.loading.set(false);
      });

    this.filters.valueChanges.pipe(debounceTime(250), takeUntilDestroyed()).subscribe(() => {
      this.pageIndex.set(0);
      this.reload$.next();
    });

    toObservable(this.pipelineService.lastFinishedRun)
      .pipe(
        skip(1),
        filter((run) => run?.profile_uuid === this.profileUuid()),
        takeUntilDestroyed(),
      )
      .subscribe(() => {
        this.pageIndex.set(0);
        this.reload$.next();
      });
  }

  ngOnInit(): void {
    this.reload$.next();
  }

  protected reload(): void {
    this.reload$.next();
  }

  protected onPage(event: PageEvent): void {
    this.pageIndex.set(event.pageIndex);
    this.pageSize.set(event.pageSize);
    this.reload$.next();
  }

  protected resetFilters(): void {
    this.filters.setValue({ minScore: 0, status: null });
  }

  protected hasActiveFilters(): boolean {
    const { minScore, status } = this.filters.getRawValue();
    return minScore > 0 || status !== null;
  }

  protected formatScore(value: number): string {
    return value.toFixed(2);
  }

  protected isRechecking(query: DiscoveredQuery): boolean {
    return this.recheckingUuids().has(query.query_uuid);
  }

  protected exportCsv(): void {
    if (this.exporting()) {
      return;
    }
    this.exporting.set(true);
    this.queryService
      .getQueries(this.profileUuid(), {
        min_score: this.filters.controls.minScore.value,
        status: this.filters.controls.status.value,
        page: 1,
        per_page: CSV_EXPORT_PAGE_SIZE,
      })
      .pipe(takeUntilDestroyed(this.destroyRef))
      .subscribe({
        next: (page) => {
          this.exporting.set(false);
          if (page.items.length === 0) {
            this.snackBar.open('Nothing to export for the current filters.', 'OK');
            return;
          }
          this.csvExport.downloadQueries(page.items);
          const noun = page.items.length === 1 ? 'query' : 'queries';
          this.snackBar.open(`Exported ${page.items.length} ${noun}.`, 'OK');
        },
        error: (error: ApiError) => {
          this.exporting.set(false);
          this.snackBar.open(`Export failed: ${error.message}`, 'Dismiss');
        },
      });
  }

  protected recheck(query: DiscoveredQuery): void {
    if (this.isRechecking(query)) {
      return;
    }
    this.setRechecking(query.query_uuid, true);
    this.queryService
      .recheckQuery(query.query_uuid)
      .pipe(takeUntilDestroyed(this.destroyRef))
      .subscribe({
        next: (updated) => {
          this.setRechecking(query.query_uuid, false);
          this.page.update((page) =>
            page
              ? { ...page, items: page.items.map((item) => (item.query_uuid === updated.query_uuid ? updated : item)) }
              : page,
          );
          const score = updated.opportunity_score === null ? 'n/a' : updated.opportunity_score.toFixed(2);
          this.snackBar.open(`Recheck done. New opportunity score: ${score}.`, 'OK');
        },
        error: (error: ApiError) => {
          this.setRechecking(query.query_uuid, false);
          this.snackBar.open(`Recheck failed: ${error.message}`, 'Dismiss');
        },
      });
  }

  private setRechecking(queryUuid: string, active: boolean): void {
    this.recheckingUuids.update((current) => {
      const next = new Set(current);
      if (active) {
        next.add(queryUuid);
      } else {
        next.delete(queryUuid);
      }
      return next;
    });
  }
}
