import { AlertTriangleIcon, CheckCircleIcon, CircleIcon, SwapIcon, XCircleIcon } from "./icons";

const STATUS_CONFIG: Record<string, { label: string; color: string; bg: string; icon: React.ComponentType<{ className?: string }> }> = {
  recovered: { label: "Recovered", color: "text-status-good", bg: "bg-status-good-bg", icon: CheckCircleIcon },
  escalated_human: { label: "Escalated", color: "text-status-warning", bg: "bg-status-warning-bg", icon: AlertTriangleIcon },
  written_off: { label: "Written off", color: "text-status-critical", bg: "bg-status-critical-bg", icon: XCircleIcon },
  recovering: { label: "Recovering", color: "text-accent", bg: "bg-accent/10", icon: SwapIcon },
  open: { label: "Open", color: "text-status-neutral", bg: "bg-status-neutral-bg", icon: CircleIcon },
};

export function StatusBadge({ status, className = "" }: { status: string; className?: string }) {
  const config = STATUS_CONFIG[status] ?? {
    label: status,
    color: "text-status-neutral",
    bg: "bg-status-neutral-bg",
    icon: CircleIcon,
  };
  const Icon = config.icon;
  return (
    <span
      className={`inline-flex items-center gap-1.5 rounded-full px-2.5 py-1 text-xs font-medium ${config.color} ${config.bg} ${className}`}
    >
      <Icon className="h-3 w-3" aria-hidden="true" />
      {config.label}
    </span>
  );
}

export function statusLabel(status: string): string {
  return STATUS_CONFIG[status]?.label ?? status;
}

const TICKET_STATUS_CONFIG: Record<string, { label: string; color: string; bg: string; icon: React.ComponentType<{ className?: string }> }> = {
  open: { label: "Open", color: "text-status-warning", bg: "bg-status-warning-bg", icon: AlertTriangleIcon },
  in_progress: { label: "In progress", color: "text-accent", bg: "bg-accent/10", icon: SwapIcon },
  resolved: { label: "Resolved", color: "text-status-good", bg: "bg-status-good-bg", icon: CheckCircleIcon },
};

export function TicketStatusBadge({ status, className = "" }: { status: string; className?: string }) {
  const config = TICKET_STATUS_CONFIG[status] ?? {
    label: status,
    color: "text-status-neutral",
    bg: "bg-status-neutral-bg",
    icon: CircleIcon,
  };
  const Icon = config.icon;
  return (
    <span
      className={`inline-flex items-center gap-1.5 rounded-full px-2.5 py-1 text-xs font-medium ${config.color} ${config.bg} ${className}`}
    >
      <Icon className="h-3 w-3" aria-hidden="true" />
      {config.label}
    </span>
  );
}

const PRIORITY_CONFIG: Record<string, { color: string; bg: string }> = {
  low: { color: "text-status-neutral", bg: "bg-status-neutral-bg" },
  normal: { color: "text-status-neutral", bg: "bg-status-neutral-bg" },
  high: { color: "text-status-warning", bg: "bg-status-warning-bg" },
  urgent: { color: "text-status-critical", bg: "bg-status-critical-bg" },
};

export function PriorityBadge({ priority, className = "" }: { priority: string; className?: string }) {
  const config = PRIORITY_CONFIG[priority] ?? PRIORITY_CONFIG.normal;
  return (
    <span className={`inline-flex items-center rounded-full px-2.5 py-1 text-xs font-medium capitalize ${config.color} ${config.bg} ${className}`}>
      {priority}
    </span>
  );
}
