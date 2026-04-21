export default function InsightActions({ onAccept, onDismiss, onDefer }) {
  return (
    <div className="flex items-center gap-3">
      {onAccept && (
        <button
          type="button"
          onClick={onAccept}
          className="px-3 py-1.5 bg-forest text-bone font-ui font-semibold text-body-sm rounded-[3px] hover:opacity-90"
        >
          Accept
        </button>
      )}
      {onDismiss && (
        <button
          type="button"
          onClick={onDismiss}
          className="font-ui text-body-sm text-subtle hover:text-charcoal"
        >
          Dismiss
        </button>
      )}
      {onDefer && (
        <button
          type="button"
          onClick={onDefer}
          className="font-ui text-body-sm text-muted hover:text-subtle"
        >
          Defer 1 day
        </button>
      )}
    </div>
  )
}
