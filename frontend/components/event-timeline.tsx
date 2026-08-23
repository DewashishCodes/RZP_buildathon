import type { AuditEvent } from "@/lib/api";
import {
  AlertTriangleIcon,
  BoltIcon,
  ChatIcon,
  CheckCircleIcon,
  CircleIcon,
  ShieldIcon,
  XCircleIcon,
} from "./icons";

const EVENT_CONFIG: Record<string, { label: string; icon: React.ComponentType<{ className?: string }>; color: string; ring: string }> = {
  detected: { label: "Detected", icon: CircleIcon, color: "text-text-secondary", ring: "ring-border" },
  diagnosed: { label: "Diagnosed", icon: CircleIcon, color: "text-text-secondary", ring: "ring-border" },
  action_proposed: { label: "Action proposed", icon: ChatIcon, color: "text-accent", ring: "ring-accent/30" },
  compliance_check: { label: "Compliance check", icon: ShieldIcon, color: "text-status-warning", ring: "ring-status-warning/30" },
  action_executed: { label: "Action executed", icon: BoltIcon, color: "text-text-secondary", ring: "ring-border" },
  outcome_recorded: { label: "Outcome recorded", icon: CheckCircleIcon, color: "text-status-good", ring: "ring-status-good/30" },
  stopped: { label: "Stopped", icon: XCircleIcon, color: "text-status-critical", ring: "ring-status-critical/30" },
  escalated: { label: "Escalated", icon: AlertTriangleIcon, color: "text-status-warning", ring: "ring-status-warning/30" },
};

function titleCase(key: string): string {
  return key.replace(/_/g, " ").replace(/^\w/, (c) => c.toUpperCase());
}

function formatValue(value: unknown): string {
  if (value === null || value === undefined) return "—";
  if (typeof value === "boolean") return value ? "Yes" : "No";
  if (typeof value === "object") return JSON.stringify(value);
  return String(value);
}

function PayloadFields({ payload }: { payload: Record<string, unknown> }) {
  const entries = Object.entries(payload).filter(([, v]) => v !== null && v !== undefined && v !== "");
  if (entries.length === 0) return null;
  return (
    <dl className="mt-2 grid grid-cols-[max-content_1fr] gap-x-4 gap-y-1 text-xs">
      {entries.map(([key, value]) => (
        <div key={key} className="contents">
          <dt className="text-text-muted">{titleCase(key)}</dt>
          <dd className="text-text-secondary">{formatValue(value)}</dd>
        </div>
      ))}
    </dl>
  );
}

export function EventTimeline({ events }: { events: AuditEvent[] }) {
  return (
    <ol className="relative flex flex-col">
      {events.map((event, i) => {
        const config = EVENT_CONFIG[event.event_type] ?? {
          label: titleCase(event.event_type),
          icon: CircleIcon,
          color: "text-text-secondary",
          ring: "ring-border",
        };
        const Icon = config.icon;
        const isLast = i === events.length - 1;

        return (
          <li key={event.id} className="relative flex gap-4 pb-6 last:pb-0">
            {!isLast && (
              <span className="absolute left-[15px] top-8 bottom-0 w-px bg-gridline" aria-hidden="true" />
            )}
            <span
              className={`z-10 flex h-8 w-8 shrink-0 items-center justify-center rounded-full bg-surface-1 ring-1 ${config.ring} ${config.color}`}
            >
              <Icon className="h-4 w-4" />
            </span>
            <div className="flex-1 rounded-lg border border-border bg-surface-1 px-4 py-3">
              <div className="flex items-baseline justify-between gap-4">
                <span className={`text-sm font-medium ${config.color}`}>{config.label}</span>
                <span className="text-xs text-text-muted">
                  {event.actor} · {new Date(event.timestamp).toLocaleString()}
                </span>
              </div>
              <PayloadFields payload={event.payload} />
            </div>
          </li>
        );
      })}
    </ol>
  );
}
