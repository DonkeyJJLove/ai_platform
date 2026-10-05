"""Deterministic hysteresis over measured host data; not intrusion attribution."""
from __future__ import annotations
from dataclasses import dataclass, asdict
import math
from cyber_lion.mission_control.edge_support import EdgeRejected, canonical, digest

@dataclass(frozen=True)
class YokePolicy:
    cpu_limit: float = 95.0
    memory_limit: float = 92.0
    free_bytes_min: int = 1073741824
    sample_max_age: float = 10.0
    snapshot_ttl: float = 6.0
    hot_samples: int = 3
    cool_samples: int = 5
    margin: float = 5.0
    ema_alpha: float = 0.25
    cpu_step: float = 50.0
    stalled_seconds: float = 120.0

    def validate(self):
        values = asdict(self)
        for key, value in values.items():
            if type(value) not in (int, float) or not math.isfinite(value):
                raise EdgeRejected('finite policy values required: ' + key)
        if not 1 <= self.cpu_limit <= 100 or not 1 <= self.memory_limit <= 100:
            raise EdgeRejected('resource percent')
        if type(self.free_bytes_min) is not int or self.free_bytes_min < 0:
            raise EdgeRejected('disk reserve')
        if not 0 < self.snapshot_ttl <= self.sample_max_age <= 300:
            raise EdgeRejected('freshness bounds')
        if not 0 < self.ema_alpha <= 1 or not 0 <= self.margin < min(self.cpu_limit, self.memory_limit):
            raise EdgeRejected('hysteresis bounds')
        if not 0 < self.cpu_step <= 100 or self.stalled_seconds <= 0:
            raise EdgeRejected('pattern bounds')
        if any(type(x) is not int or not 1 <= x <= 100 for x in (self.hot_samples, self.cool_samples)):
            raise EdgeRejected('sample counts')
        return self

    def digest(self):
        return digest(canonical(asdict(self.validate())))

class VetoMachine:
    def __init__(self, policy):
        self.policy = policy.validate()
        self.ema = None
        self.hot = self.cool = 0
        self.held = True
        self.quarantined = False

    def result(self, state, reasons, notices=()):
        return dict(state=state, reasons=list(reasons), notices=list(notices), cpu_ema=self.ema,
                    max_new_tasks=1 if state == 'NO_VETO' else 0, authority_effect='NONE')

    def update(self, sample, now):
        p = self.policy
        if isinstance(sample, dict) and sample.get('integrity') == 'MISMATCH':
            self.quarantined = True
        if self.quarantined:
            return self.result('QUARANTINE', ['PINNED_SOURCE_MISMATCH'])
        keys = ('observed_at', 'cpu_percent', 'memory_percent', 'free_bytes')
        if (type(sample) is not dict or type(now) not in (int, float) or not math.isfinite(now)
                or any(type(sample.get(k)) not in (int, float) or not math.isfinite(sample[k]) for k in keys)):
            self.held = True
            self.cool = self.hot = 0
            return self.result('UNKNOWN', ['INVALID_TELEMETRY'])
        if (not 0 <= now - sample['observed_at'] <= p.sample_max_age
                or not 0 <= sample['cpu_percent'] <= 100 or not 0 <= sample['memory_percent'] <= 100
                or sample['free_bytes'] < 0 or sample.get('integrity') != 'MATCH'):
            self.held = True
            self.cool = self.hot = 0
            return self.result('UNKNOWN', ['STALE_TELEMETRY_OR_UNKNOWN_INTEGRITY'])
        notices = []
        if self.ema is not None and abs(sample['cpu_percent'] - self.ema) >= p.cpu_step:
            notices.append('CPU_PATTERN_CHANGE_REVIEW')
        self.ema = sample['cpu_percent'] if self.ema is None else p.ema_alpha * sample['cpu_percent'] + (1-p.ema_alpha) * self.ema
        high = sample['cpu_percent'] >= p.cpu_limit or sample['memory_percent'] >= p.memory_limit
        self.hot = self.hot + 1 if high else 0
        reasons = []
        if sample['free_bytes'] < p.free_bytes_min:
            reasons.append('DISK_RESERVE_EXHAUSTED')
        if self.hot >= p.hot_samples:
            reasons.append('SUSTAINED_RESOURCE_PRESSURE')
        if sample.get('task_active') is True:
            progress = sample.get('seconds_without_progress')
            if type(progress) not in (int, float) or not math.isfinite(progress) or progress < 0:
                reasons.append('PROGRESS_UNKNOWN')
            elif progress > p.stalled_seconds:
                reasons.append('PROGRESS_STALLED_REVIEW')
        if reasons:
            self.held = True
            self.cool = 0
        elif sample['cpu_percent'] < p.cpu_limit-p.margin and sample['memory_percent'] < p.memory_limit-p.margin:
            self.cool += 1
            if self.cool >= p.cool_samples:
                self.held = False
        else:
            self.cool = 0
        return self.result('HOLD' if self.held else 'NO_VETO', reasons or (['WARMUP_OR_COOLDOWN'] if self.held else []), notices)
